"""Omni-timeframe decision engine with explicit Parts 1–12 integration.

Part 1's 13 and Part 2's 16 brains retain their existing votes. Parts 4–10
add seven independent engine votes (36 total). Part 3 retains its institutional
super-vote. Part 11 confirms direction; Part 12 gates confidence. The separate
Part 5 institutional override remains subordinate to risk/model gates.

Each provided nonempty frame is analyzed. XGBoost consumes actual named Part
results, with missing features reported rather than fabricated. No orders here.
"""
import time as _real_time
import numpy as np
import pandas as pd

import part1_FIXED as p1
import part2_FIXED as p2
import part3_FIXED as p3


# ------------------------------------------------------------------ simulated clock
class _SimClock:
    now = None

    def time(self):
        return self.now if self.now is not None else _real_time.time()

    def __getattr__(self, name):
        return getattr(_real_time, name)


CLOCK = _SimClock()
p2.time = CLOCK


# ------------------------------------------------------------------ helpers
def _p1_market_data(df):
    if df is None or df.empty:
        return {"price_action": [], "volume_pattern": []}
    return {
        "price_action": df[["open", "high", "low", "close"]].to_dict("records"),
        "volume_pattern": df["volume"].tolist(),
    }


def _breakout_strength(df, n=20):
    if df is None or len(df) < n + 1:
        return 0.2
    c, h, l = df["close"].iloc[-1], df["high"].iloc[-n - 1:-1].max(), df["low"].iloc[-n - 1:-1].min()
    return 0.6 if (c > h or c < l) else 0.2


class _Silent:
    def __enter__(self):
        import io, sys
        self._o, sys.stdout = sys.stdout, io.StringIO()

    def __exit__(self, *a):
        import sys
        sys.stdout = self._o


# ------------------------------------------------------------------ universal 29-brain engine
class ModeEngine:
    SWING_CONSENSUS_THRESHOLD = 5
    SCALP_CONSENSUS_THRESHOLD = 6

    def __init__(self, *, enable_extended_parts=True, require_xgboost=True,
                 min_part12_confidence=65.0, part_bridge=None, xgboost_engine=None):
        self.enable_extended_parts = bool(enable_extended_parts)
        self.require_xgboost = bool(require_xgboost)
        self.min_part12_confidence = float(min_part12_confidence)
        if not np.isfinite(self.min_part12_confidence) or not 0 <= self.min_part12_confidence <= 100:
            raise ValueError('Part 12 confidence threshold must be 0–100')
        self.xgboost_engine = xgboost_engine
        self.last_xgboost_report = {'available': False, 'approved': False, 'reason': 'not_evaluated'}
        if self.enable_extended_parts:
            from mode_part_bridge import PartEngineBridge
            self.part_bridge = part_bridge if part_bridge is not None else PartEngineBridge()
            # Retain the old approximate quorum fraction for 36 independent votes.
            self.SWING_CONSENSUS_THRESHOLD = 7  # ceil(5 * 36 / 29)
            self.SCALP_CONSENSUS_THRESHOLD = 8  # ceil(6 * 36 / 29)
        else:
            self.part_bridge = None
        with _Silent():
            self.p2_system = p2.AdvancedAnalysisSystem()
            self.p2_brains = self.p2_system.brains
            
        # Part 1 All 13 Brains
        self.p1_trend = p1.TrendBrain()
        self.p1_vol = p1.VolatilityBrain()
        self.p1_strength = p1.StrengthBrain()
        self.p1_risk = p1.RiskBrain()
        self.p1_reversal = p1.ReversalBrain()
        self.p1_regime = p1.RegimeBrain()
        self.p1_deepseek = p1.DeepSeekBrain()
        self.p1_evolution = p1.EvolutionBrain()
        self.p1_memory = p1.MemoryBrain()
        self.p1_self_healing = p1.SelfHealingBrain()
        self.p1_meta_fusion = p1.MetaFusionBrain()
        self.p1_r1 = p1.MiniR1Brain()
        self.p1_v3 = p1.MiniV3Brain()
        # Part 3 Institutional Engine
        try:
            self.p3_institutional = p3.InstitutionalTradingEngineGPU()
        except Exception:
            self.p3_institutional = None
            
        # Part 5 Institutional Fusion Veto Engine
        try:
            import part5_FIXED as p5
            self.p5_fusion = p5.InstitutionalFusionEngine()
        except Exception:
            self.p5_fusion = None
            
        # Wire the Global Cognitive Bus to ALL Brains (Part 1, 2, and 3)
        try:
            from jarvis_cognitive_bus import CognitiveBus
            bus = CognitiveBus()
        except ImportError:
            bus = None

        if bus:
            self.p2_system.bus = bus
            for p2_brain in self.p2_brains.values():
                p2_brain.bus = bus
                
            p1_brains = [
                self.p1_trend, self.p1_vol, self.p1_strength, self.p1_risk, 
                self.p1_reversal, self.p1_regime, self.p1_deepseek, self.p1_evolution, 
                self.p1_memory, self.p1_self_healing, self.p1_meta_fusion, self.p1_r1, self.p1_v3
            ]
            for b in p1_brains:
                b.bus = bus
                
            if self.p3_institutional:
                self.p3_institutional.bus = bus

    def evaluate_all_brains(self, tf_dict, context=None):
        """
        Omni-Timeframe Loop:
        EVERY SINGLE ONE of the 29 Brains evaluates ALL available timeframes (1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d).
        """
        if self.part_bridge is not None:
            self.part_bridge.reset()
        available_tfs = {}
        for k, v in tf_dict.items():
            if v is not None and not v.empty:
                available_tfs[k] = v

        primary_df = list(available_tfs.values())[0] if available_tfs else None
        price = primary_df['close'].iloc[-1] if primary_df is not None else 0
        
        brain_tf_signals = {}  # {brain_name: {tf_name: (direction, confidence)}}

        # Iterate through EVERY timeframe provided by API
        for tf_name, df in available_tfs.items():
            md = _p1_market_data(df)
            cndl = df.iloc[-1].to_dict() if not df.empty else {}
            
            # --- Part 1 Brains on this specific TF ---
            t_res = self.p1_trend.analyze_trend(md)
            v_res = self.p1_vol.analyze_volatility(md)
            brk_res = {"strength": _breakout_strength(df)}
            st_res = self.p1_strength.analyze_strength(md, brk_res, {})
            rk_res = self.p1_risk.analyze_risk(md, v_res, t_res)
            rv_res = self.p1_reversal.analyze_reversal(md, t_res, st_res)
            reg_res = self.p1_regime.analyze_regime(md, t_res, v_res)
            ds_res = self.p1_deepseek.analyze_deepseek(md, {"trend": t_res, "strength": st_res, "risk": rk_res, "reversal": rv_res})
            evo_res = self.p1_evolution.analyze_evolution(md, [])
            mem_res = self.p1_memory.analyze_memory(md, None)
            heal_res = self.p1_self_healing.analyze_self_heal(md, {})
            r1_res = self.p1_r1.analyze_mini_r1(md, brk_res, rk_res)
            v3_res = self.p1_v3.analyze_mini_v3(md)
            mf_res = self.p1_meta_fusion.analyze_meta_fusion({
                'trend': t_res,
                'volatility': v_res,
                'strength': st_res,
                'risk': rk_res,
                'reversal': rv_res,
                'regime': reg_res,
                'deepseek': ds_res,
                'evolution': evo_res,
                'memory': mem_res,
                'self_healing': heal_res,
                'mini_r1': r1_res,
                'mini_v3': v3_res
            })

            def add_tf_sig(b_name, dir_val, conf_val):
                if b_name not in brain_tf_signals: brain_tf_signals[b_name] = {}
                brain_tf_signals[b_name][tf_name] = (dir_val, conf_val)

            add_tf_sig("P1_Trend", "BUY" if t_res["support_score"] > 0.05 else "SELL" if t_res["support_score"] < -0.05 else "NEUTRAL", abs(t_res["support_score"]))
            add_tf_sig("P1_Volatility", "BUY" if v_res.get("volatility_regime") == "HIGH" and t_res["trend_direction"] == 1 else "SELL" if v_res.get("volatility_regime") == "HIGH" else "NEUTRAL", 0.7)
            add_tf_sig("P1_Strength", "BUY" if st_res["overall_strength"] > 0.3 and t_res["trend_direction"] == 1 else "SELL" if st_res["overall_strength"] > 0.3 else "NEUTRAL", st_res["overall_strength"])
            add_tf_sig("P1_Risk", "BUY" if rk_res.get("risk_level") == "LOW" and t_res["trend_direction"] == 1 else "SELL" if rk_res.get("risk_level") == "LOW" else "NEUTRAL", 0.6)
            add_tf_sig("P1_Reversal", "SELL" if rv_res["reversal_probability"] > 0.001 and t_res["trend_direction"] == 1 else "BUY" if rv_res["reversal_probability"] > 0.001 else "NEUTRAL", rv_res["reversal_probability"])
            add_tf_sig("P1_Regime", "BUY" if "BULL" in reg_res.get("regime_type", "") else "SELL" if "BEAR" in reg_res.get("regime_type", "") else "NEUTRAL", reg_res.get("regime_confidence", 0.5))
            add_tf_sig("P1_DeepSeek", "BUY" if ds_res.get("fakeout_block", 0) < 0.3 and t_res["trend_direction"] == 1 else "SELL" if ds_res.get("fakeout_block", 0) < 0.3 else "NEUTRAL", 0.7)
            add_tf_sig("P1_Evolution", "BUY" if evo_res.get("support_score", 0) > 0.5 and t_res["trend_direction"] == 1 else "SELL" if evo_res.get("support_score", 0) > 0.5 else "NEUTRAL", evo_res.get("support_score", 0.5))
            add_tf_sig("P1_Memory", "BUY" if mem_res.get("support_score", 0) > 0.1 else "SELL" if mem_res.get("support_score", 0) < -0.1 else "NEUTRAL", abs(mem_res.get("support_score", 0)))
            add_tf_sig("P1_SelfHealing", "BUY" if heal_res.get("health_index", 0) > 0.6 and t_res["trend_direction"] == 1 else "SELL" if heal_res.get("health_index", 0) > 0.6 else "NEUTRAL", heal_res.get("health_index", 0.6))
            add_tf_sig("P1_MiniR1", "BUY" if r1_res.get("trap_probability", 0) < 0.4 and t_res["trend_direction"] == 1 else "SELL" if r1_res.get("trap_probability", 0) < 0.4 else "NEUTRAL", 0.7)
            add_tf_sig("P1_MiniV3", "BUY" if v3_res.get("tick_momentum", 0) > 0.15 else "SELL" if v3_res.get("tick_momentum", 0) < -0.15 else "NEUTRAL", abs(v3_res.get("tick_momentum", 0)))
            add_tf_sig("P1_MetaFusion", "BUY" if mf_res.get("support_score", 0) > 0.1 and t_res["trend_direction"] == 1 else "SELL" if mf_res.get("support_score", 0) > 0.1 else "NEUTRAL", abs(mf_res.get("support_score", 0)))

            # --- Part 2 Brains on this specific TF ---
            b2 = self.p2_brains
            psy = b2["candle_psychology"].analyze_candle_psychology(cndl)

            def eval_p2_tf(fn):
                try:
                    sigs = fn() or []
                    if isinstance(sigs, dict): sigs = list(sigs.items())
                    call_s = sum(s[1] for s in sigs if isinstance(s, (list, tuple)) and len(s) >= 2 and str(s[0]).upper() in ("CALL", "BUY"))
                    put_s = sum(s[1] for s in sigs if isinstance(s, (list, tuple)) and len(s) >= 2 and str(s[0]).upper() in ("PUT", "SELL"))
                    if call_s > put_s and call_s > 4.0: return ("BUY", call_s)
                    elif put_s > call_s and put_s > 4.0: return ("SELL", put_s)
                except Exception: pass
                return ("NEUTRAL", 0)

            add_tf_sig("P2_ZonePointFiveDetector", *eval_p2_tf(lambda: b2["zone_detector"].detect_0_5_zone_signals(cndl, psy, df, df, df)))
            add_tf_sig("P2_CandlePsychologyMaster", "BUY" if psy.get("is_bullish") else "SELL" if psy.get("is_bearish") else "NEUTRAL", 7.0)
            add_tf_sig("P2_VolumeProfile", *eval_p2_tf(lambda: (b2["volume_profile"].analyze_volume_profile(df, tf_name), b2["volume_profile"].detect_volume_signals(cndl, psy, df))[1]))
            add_tf_sig("P2_MarketStructure", *eval_p2_tf(lambda: (b2["market_structure"].analyze_market_structure(df, tf_name), b2["market_structure"].get_structure_signals(price, psy))[1]))
            add_tf_sig("P2_OrderFlow", *eval_p2_tf(lambda: (b2["order_flow"].analyze_order_flow(df), b2["order_flow"].get_orderflow_signals(price, psy, b2["volume_profile"].detect_volume_spike(df)))[1]))
            add_tf_sig("P2_MomentumOscillator", *eval_p2_tf(lambda: (b2["momentum_oscillator"].calculate_all_oscillators(df), b2["momentum_oscillator"].get_momentum_signals(price, psy))[1]))
            add_tf_sig("P2_VolatilityRegime", *eval_p2_tf(lambda: (b2["volatility_regime"].analyze_volatility_regime(df), b2["volatility_regime"].get_volatility_signals(price, psy))[1]))
            add_tf_sig("P2_CycleAnalysis", *eval_p2_tf(lambda: (b2["cycle_analysis"].analyze_market_cycles(df), b2["cycle_analysis"].get_cycle_signals(price, psy))[1]))
            add_tf_sig("P2_CorrelationMatrix", *eval_p2_tf(lambda: (b2["correlation_matrix"].analyze_correlations(df, {"BTCUSDT": df}), b2["correlation_matrix"].get_correlation_signals(price, psy))[1]))
            add_tf_sig("P2_PatternRecognition", *eval_p2_tf(lambda: (b2["pattern_recognition"].recognize_chart_patterns(df), b2["pattern_recognition"].get_pattern_signals(price, psy))[1]))
            add_tf_sig("P2_SupportResistance", *eval_p2_tf(lambda: (b2["support_resistance"].calculate_support_resistance(df), b2["support_resistance"].get_sr_signals(price, psy))[1]))
            add_tf_sig("P2_TrendAnalysis", *eval_p2_tf(lambda: (al := b2["trend_analysis"].analyze_multi_timeframe_trends(tf_dict), b2["trend_analysis"].get_trend_signals(price, psy, al.get("alignment", "NEUTRAL")))[1]))
            add_tf_sig("P2_MarketRegime", *eval_p2_tf(lambda: (b2["market_regime"].detect_market_regime(df), b2["market_regime"].get_regime_signals(price, psy))[1]))
            add_tf_sig("P2_PriceAction", *eval_p2_tf(lambda: (b2["price_action"].analyze_price_action(df), b2["price_action"].get_pa_signals(price, psy))[1]))
            add_tf_sig("P2_InstitutionalFlow", *eval_p2_tf(lambda: (b2["institutional_flow"].analyze_institutional_flow(df), b2["institutional_flow"].get_institutional_signals(price, psy))[1]))
            add_tf_sig("P2_SignalFusion", *eval_p2_tf(lambda: b2["signal_fusion"].fuse_signals([], price, {})))

            # Parts 4–12 use the same native OHLCV frame, not aggregate vote
            # counts disguised as candle input. Parts 11/12 get named results.
            if self.part_bridge is not None:
                from mode_part_bridge import VOTE_NAMES, direction
                meta_score = float(mf_res.get('support_score', 0.0))
                p1_dir = 1 if meta_score > 0.1 and t_res['trend_direction'] == 1 else -1 if meta_score > 0.1 else 0
                zone_dir = brain_tf_signals['P2_ZonePointFiveDetector'][tf_name][0]
                seed = {
                    'part1_breakout': {'signal': p1_dir, 'thought': 'ModeEngine Part 1 MetaFusion summary',
                                       'source': 'P1_MetaFusion', 'raw_result': mf_res},
                    'part2_zone': {'signal': 1 if zone_dir == 'BUY' else -1 if zone_dir == 'SELL' else 0,
                                   'thought': 'ModeEngine Part 2 native zone signal', 'source': 'P2_ZonePointFiveDetector'},
                    'part3_psychology': {'signal': 0, 'thought': 'institutional engine unavailable',
                                        'source': 'Part3_Institutional', 'runtime_status': 'unavailable'},
                }
                frame_context = dict(context or {})
                if self.p3_institutional is not None:
                    try:
                        p3_frame = self.p3_institutional.generate_mtf_signals({tf_name: df})
                        consensus = float(p3_frame.get('mtf_consensus', 0.0))
                        if not np.isfinite(consensus):
                            raise ValueError('non-finite institutional consensus')
                        components = p3_frame.get('components', {})
                        if isinstance(components, dict):
                            external_components = frame_context.get('institutional_components', {})
                            if not isinstance(external_components, dict):
                                external_components = {}
                            frame_context['institutional_components'] = {
                                **external_components, **components,
                                # A supplied neutral regime must not erase a
                                # native PANIC/VOLATILE observation, or vice versa.
                                'regime': f"{components.get('regime', '')} {external_components.get('regime', '')}".strip(),
                            }
                        seed['part3_psychology'] = {
                            'signal': 1 if consensus >= 0.25 else -1 if consensus <= -0.25 else 0,
                            'thought': 'ModeEngine Part 3 institutional frame consensus',
                            'source': 'Part3_Institutional', 'raw_result': p3_frame,
                        }
                    except Exception as error:
                        seed['part3_psychology']['error'] = f'{type(error).__name__}: {error}'
                frame_results = self.part_bridge.evaluate_frame(tf_name, df, seed, context=frame_context)
                for key, vote_name in VOTE_NAMES.items():
                    result = frame_results[key]
                    add_tf_sig(vote_name, direction(result.get('signal')), float(result.get('confidence', 0)))

        # Synthesize final vote per brain across ALL timeframes
        final_brain_votes = {}
        high_tfs = {"1h", "4h", "1d", "60m", "240m"}

        for b_name, tf_map in brain_tf_signals.items():
            buy_count = sum(1 for tf, (d, _) in tf_map.items() if d == "BUY")
            sell_count = sum(1 for tf, (d, _) in tf_map.items() if d == "SELL")
            
            high_tf_buy = sum(1 for tf, (d, _) in tf_map.items() if d == "BUY" and tf in high_tfs)
            high_tf_sell = sum(1 for tf, (d, _) in tf_map.items() if d == "SELL" and tf in high_tfs)
            
            if buy_count > sell_count:
                mode = "SWING" if high_tf_buy > 0 else "SCALP"
                final_brain_votes[b_name] = (mode, "BUY")
            elif sell_count > buy_count:
                mode = "SWING" if high_tf_sell > 0 else "SCALP"
                final_brain_votes[b_name] = (mode, "SELL")
            else:
                final_brain_votes[b_name] = ("NEUTRAL", "NEUTRAL")

        return final_brain_votes

    def calculate_dynamic_sl_tp(self, df, price, direction, trade_type="SCALP"):
        """Calculates dynamic SL/TP using SupportResistanceBrainGPU + ATR Guard."""
        b = self.p2_brains
        try:
            b["support_resistance"].calculate_support_resistance(df)
            levels = b["support_resistance"].get_nearest_levels(price)
        except Exception:
            levels = {'support': price * 0.99, 'resistance': price * 1.01}
            
        md = _p1_market_data(df)
        t = self.p1_trend.analyze_trend(md)
        v = self.p1_vol.analyze_volatility(md)
        rk = self.p1_risk.analyze_risk(md, v, t)
        atr_stop = max(float(rk.get("stop_distance", price * 0.003)), price * 0.0015)
        
        if direction == "BUY":
            sr_sl = levels['support'] * 0.998
            sl = min(sr_sl, price - (atr_stop * (2.5 if trade_type == "SWING" else 1.2)))
            sl_pct = (price - sl) / price
            
            min_rr = 2.0 if trade_type == "SWING" else 1.5
            sr_tp = max(levels['resistance'] * 1.002, price + (price - sl) * min_rr)
            tp = sr_tp
            tp_pct = (tp - price) / price
        else: # SELL
            sr_sl = levels['resistance'] * 1.002
            sl = max(sr_sl, price + (atr_stop * (2.5 if trade_type == "SWING" else 1.2)))
            sl_pct = (sl - price) / price
            
            min_rr = 2.0 if trade_type == "SWING" else 1.5
            sr_tp = min(levels['support'] * 0.998, price - (sl - price) * min_rr)
            tp = sr_tp
            tp_pct = (price - tp) / price
            
        rr = tp_pct / max(sl_pct, 1e-8)
        return round(sl, 2), round(tp, 2), round(rr, 2)

    @staticmethod
    def _prepare_inputs(m5, h1, tf_dict):
        required = ['open', 'high', 'low', 'close', 'volume']
        def validate(frame, name):
            if frame is None:
                return None
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                raise ValueError(f'{name}: empty or non-DataFrame input')
            if not set(required).issubset(frame.columns):
                raise ValueError(f'{name}: missing OHLCV columns')
            normalized = frame.copy(deep=True)
            try:
                normalized[required] = normalized[required].astype(float)
                values = normalized[required].to_numpy()
            except (ValueError, TypeError) as error:
                raise ValueError(f'{name}: nonnumeric OHLCV') from error
            if not np.isfinite(values).all() or (values[:, :4] <= 0).any() or (values[:, 4] < 0).any():
                raise ValueError(f'{name}: nonfinite/nonpositive prices or invalid volume')
            if (normalized['high'] < normalized[['open', 'close', 'low']].max(axis=1)).any() or (normalized['low'] > normalized[['open', 'close', 'high']].min(axis=1)).any():
                raise ValueError(f'{name}: invalid candle geometry')
            return normalized
        m5 = validate(m5, 'm5')
        h1 = validate(h1, 'h1')
        if tf_dict is None:
            tf_dict = {'5min': m5, '1h': h1}
        if not isinstance(tf_dict, dict):
            raise ValueError('timeframes must be a dictionary')
        frames = {str(tf): validate(df, str(tf)) for tf, df in tf_dict.items() if df is not None}
        if not frames:
            raise ValueError('no usable OHLCV timeframes')
        # The provided timeframe map is the decision evidence source of truth.
        # Resolve execution anchors from it before using optional legacy args.
        m5 = next((frames[tf] for tf in ('5m', '5min', '1m', '3m') if tf in frames), m5)
        h1 = next((frames[tf] for tf in ('1h', '60m', '4h', '240m', '1d') if tf in frames), h1)
        return m5, h1, frames

    def master_evaluate(self, m5, h1, tf_dict=None, *, snapshot=None, options_data=None):
        """Evaluate Parts 1–12 and attach auditable frame/model diagnostics.

        Extended mode defaults to fail-closed when real XGBoost inference is
        unavailable. Set require_xgboost=False explicitly for algorithm-only
        operation. This class never submits an order.
        """
        self.last_xgboost_report = {'available': False, 'approved': False, 'reason': 'no_candidate'}
        self._evaluation_snapshot = dict(snapshot or {})
        self._evaluation_options = dict(options_data or {})
        self._candidate_mode = None
        if self.part_bridge is not None:
            self.part_bridge.reset()
        try:
            m5, h1, tf_dict = self._prepare_inputs(m5, h1, tf_dict)
        except ValueError as error:
            result = {'action': 'HOLD', 'trade_type': None, 'direction': None,
                      'entry': None, 'sl': None, 'tp': None, 'rr': None,
                      'total_brains_voted': 0, 'timeframes_evaluated': [],
                      'all_brain_votes': {}, 'vote_tally': {}, 'reason': f'INVALID_MARKET_DATA: {error}'}
            self.last_xgboost_report = {'available': False, 'approved': False, 'reason': 'invalid_market_data'}
        else:
            result = self._master_evaluate(m5, h1, tf_dict)
        result['extended_parts_enabled'] = self.enable_extended_parts
        result['consensus_thresholds'] = {'SWING': self.SWING_CONSENSUS_THRESHOLD,
                                          'SCALP': self.SCALP_CONSENSUS_THRESHOLD}
        result['xgboost_report'] = self.last_xgboost_report
        if self.part_bridge is not None:
            report = self.part_bridge.report(result.get('trade_type') or getattr(self, '_candidate_mode', None))
            result['part_engine_report'] = report
            result['part12_confidence'] = report['selected_part_results'].get('part12_confidence', {}).get('confidence')
        return result

    def _master_evaluate(self, m5, h1, tf_dict=None):
        """
        Universal Master Evaluator:
        Tallies votes from ALL 29 BRAINS evaluated across ALL API TIMEFRAMES (1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d).
        """
        if tf_dict is None:
            tf_dict = {"5min": m5, "1h": h1}
            
        self._candidate_mode = None
        entry_frame = m5 if m5 is not None else h1
        if entry_frame is None:
            entry_frame = next(iter(tf_dict.values()))
        price = float(entry_frame['close'].iloc[-1])
        votes = self.evaluate_all_brains(tf_dict, context=self._evaluation_snapshot)

        tally = {
            ("SWING", "BUY"): 0,
            ("SWING", "SELL"): 0,
            ("SCALP", "BUY"): 0,
            ("SCALP", "SELL"): 0,
        }
        
        for brain_name, (m, d) in votes.items():
            if (m, d) in tally:
                tally[(m, d)] += 1

        # --- PART 3 INSTITUTIONAL SUPER-VOTING ---
        institutional_veto_dir = None
        if getattr(self, 'p3_institutional', None) is not None:
            try:
                p3_res = self.p3_institutional.generate_mtf_signals(tf_dict)
                p3_consensus = p3_res.get('mtf_consensus', 0.0)
                p3_regime = p3_res.get('components', {}).get('regime', 'UNKNOWN')
                
                if abs(p3_consensus) >= 0.25:
                    p3_dir = "BUY" if p3_consensus > 0 else "SELL"
                    p3_mode = "SWING" if "TRENDING" in str(p3_regime) else "SCALP"
                    institutional_veto_dir = p3_dir  # Save institutional direction to prevent counter-scalping
                    
                    if (p3_mode, p3_dir) in tally:
                        tally[(p3_mode, p3_dir)] += 3  # The Institutional Super-Vote
            except Exception:
                pass
        # --- END PART 3 ---

        # --- PART 5 EMERGENCY VETO (BLACK SWAN CATCHER) ---
        part5_veto = False
        if getattr(self, 'p5_fusion', None) is not None:
            try:
                m1 = tf_dict.get('1m')
                m5_data = tf_dict.get('5m', tf_dict.get('5min'))
                m15 = tf_dict.get('15m')
                if m1 is not None and m5_data is not None:
                    p5_res = self.p5_fusion.process_market_data(m1, m5_data, m15)
                    p5_signal = p5_res.get('fused_signal', 'NO TRADE')
                    if p5_signal in ["BUY", "SELL"]:
                        # Market is crashing/spiking - WIPE ALL NORMAL VOTES!
                        tally = {k: 0 for k in tally} 
                        tally[("SWING", p5_signal)] = 100  # God-Mode VETO
                        tally[("SCALP", p5_signal)] = 100
                        part5_veto = True
            except Exception:
                pass
        # --- END PART 5 VETO ---

        swing_buy = tally[("SWING", "BUY")]
        swing_sell = tally[("SWING", "SELL")]
        scalp_buy = tally[("SCALP", "BUY")]
        scalp_sell = tally[("SCALP", "SELL")]

        winning_mode = None
        winning_dir = None

        if swing_buy >= self.SWING_CONSENSUS_THRESHOLD and swing_buy > swing_sell:
            winning_mode, winning_dir = "SWING", "BUY"
        elif swing_sell >= self.SWING_CONSENSUS_THRESHOLD and swing_sell > swing_buy:
            winning_mode, winning_dir = "SWING", "SELL"
        elif scalp_buy >= self.SCALP_CONSENSUS_THRESHOLD and scalp_buy > scalp_sell:
            winning_mode, winning_dir = "SCALP", "BUY"
        elif scalp_sell >= self.SCALP_CONSENSUS_THRESHOLD and scalp_sell > scalp_buy:
            winning_mode, winning_dir = "SCALP", "SELL"

        # --- INSTITUTIONAL ANTI-COUNTER-SCALP RULE ---
        if winning_mode == "SCALP" and institutional_veto_dir:
            if winning_dir != institutional_veto_dir:
                return {
                    "action": "HOLD",
                    "trade_type": None,
                    "direction": None,
                    "entry": price,
                    "sl": None,
                    "tp": None,
                    "rr": None,
                    "total_brains_voted": len(votes),
                    "timeframes_evaluated": list(tf_dict.keys()),
                    "all_brain_votes": votes,
                    "vote_tally": tally,
                    "reason": f"INSTITUTIONAL_VETO: Refusing to SCALP {winning_dir} against Institutional {institutional_veto_dir}"
                }
        # --- END VETO ---

        self._candidate_mode = winning_mode
        # Native Part 11 and 12 are confirmations, not extra copies of the
        # same evidence in the vote denominator. Part 7 risk outranks the
        # legacy Part 5 override as well.
        def extended_hold(reason):
            return {'action': 'HOLD', 'trade_type': None, 'direction': None,
                    'entry': price, 'sl': None, 'tp': None, 'rr': None,
                    'total_brains_voted': len(votes), 'timeframes_evaluated': list(tf_dict),
                    'all_brain_votes': votes, 'vote_tally': tally, 'reason': reason}

        if winning_dir and (m5 if winning_mode == 'SCALP' else h1) is None:
            return extended_hold('MISSING_EXECUTION_TIMEFRAME')

        if winning_dir and self.part_bridge is not None:
            gate_reason = self.part_bridge.gate(winning_mode, winning_dir, self.min_part12_confidence)
            if gate_reason:
                self.last_xgboost_report = {'available': False, 'approved': False,
                                            'reason': 'deterministic_part_gate_blocked'}
                return extended_hold(gate_reason)
            try:
                if self.xgboost_engine is None:
                    from jarvis_xgboost_engine import JarvisXGBoostEngine
                    # Never authorize trades with a synthetic on-the-fly model.
                    self.xgboost_engine = JarvisXGBoostEngine(allow_bootstrap=False)
                report = self.part_bridge.report(winning_mode)
                self.last_xgboost_report = self.xgboost_engine.evaluate_parts(
                    self._evaluation_snapshot, report['selected_part_results'],
                    self._evaluation_options, direction=winning_dir)
                if not isinstance(self.last_xgboost_report, dict):
                    raise ValueError('XGBoost report must be a dictionary')
            except Exception as error:
                self.last_xgboost_report = {'available': False, 'approved': False,
                    'reason': 'inference_error', 'error': f'{type(error).__name__}: {error}'}
            if type(self.last_xgboost_report.get('available')) is not bool or type(self.last_xgboost_report.get('approved')) is not bool:
                self.last_xgboost_report = {'available': False, 'approved': False, 'reason': 'invalid_model_report'}
            if not self.last_xgboost_report.get('available'):
                if self.require_xgboost:
                    return extended_hold('XGBOOST_UNAVAILABLE: ' + str(self.last_xgboost_report.get('reason', 'unknown')))
            elif not self.last_xgboost_report.get('approved'):
                return extended_hold('XGBOOST_PARTS_VETO')

        # Legacy 5-feature model was trained on 29-vote counts. Do NOT feed
        # 36-vote counts to it; keep it only in explicit legacy operation.
        # --- XGBOOST CONTINUOUS META-LEARNING VETO ---
        if winning_dir and self.part_bridge is None:
            try:
                import os
                import pandas as pd
                import xgboost as xgb
                if os.path.exists("live_godmode.xgb"):
                    # Create the feature array [SwingBuy, SwingSell, ScalpBuy, ScalpSell, Part5Veto]
                    p5_val = 1 if part5_veto else 0
                    xgb_features = pd.DataFrame([{
                        'Swing_Buy_Votes': swing_buy,
                        'Swing_Sell_Votes': swing_sell,
                        'Scalp_Buy_Votes': scalp_buy,
                        'Scalp_Sell_Votes': scalp_sell,
                        'Part5_Veto': p5_val
                    }])
                    
                    xgb_model = xgb.Booster()
                    xgb_model.load_model("live_godmode.xgb")
                    dtest = xgb.DMatrix(xgb_features)
                    win_prob = xgb_model.predict(dtest)[0]
                    
                    if win_prob < 0.65:
                        return {
                            "action": "HOLD",
                            "trade_type": None,
                            "direction": None,
                            "entry": price,
                            "sl": None,
                            "tp": None,
                            "rr": None,
                            "total_brains_voted": len(votes),
                            "timeframes_evaluated": list(tf_dict.keys()),
                            "all_brain_votes": votes,
                            "vote_tally": tally,
                            "reason": f"XGBOOST_META_VETO: AI calculated only {win_prob*100:.1f}% win probability for this {winning_mode} {winning_dir}."
                        }
                    else:
                        tally["XGBoost_Win_Prob"] = f"{win_prob*100:.1f}%" # Attach for logging
            except Exception as e:
                pass # If model fails to load or predict, fallback to normal ModeEngine
        # --- END XGBOOST VETO ---

        if not winning_dir:
            return {
                "action": "HOLD",
                "trade_type": None,
                "direction": None,
                "entry": price,
                "sl": None,
                "tp": None,
                "rr": None,
                "total_brains_voted": len(votes),
                "timeframes_evaluated": list(tf_dict.keys()),
                "all_brain_votes": votes,
                "vote_tally": tally,
                "reason": f"NO_{len(votes)}_BRAIN_CONSENSUS"
            }

        sl, tp, rr = self.calculate_dynamic_sl_tp(m5 if winning_mode == "SCALP" else h1, price, winning_dir, winning_mode)

        result = {
            "action": "EXECUTE",
            "trade_type": winning_mode,
            "direction": winning_dir,
            "entry": price,
            "sl": sl,
            "tp": tp,
            "rr": rr,
            "total_brains_voted": len(votes),
            "timeframes_evaluated": list(tf_dict.keys()),
            "all_brain_votes": votes,
            "vote_tally": tally,
            "reason": f"ALL_{len(votes)}_BRAIN_CONSENSUS_{winning_mode}_{winning_dir}"
        }

        # Let the internal brains know the final verdict via the Cognitive Bus
        if hasattr(self, 'p2_system') and hasattr(self.p2_system, 'bus'):
            try:
                self.p2_system.bus.publish('SYSTEM', 'ModeEngine', 
                    f"Consensus Reached: {winning_mode} {winning_dir} (Score: {tally[(winning_mode, winning_dir)]}). Informing all internal brains.")
            except Exception:
                pass
                
        return result
