"""ModeEngine's explicit Parts 4–12 runtime adapter (no order execution).

Parts 4–10 contribute one directional vote each. Part 11 confirms direction;
Part 12 gates confidence, never inventing a directional vote. All raw frame
results are retained for XGBoost features and diagnostics.
"""
from __future__ import annotations

import copy
import importlib
import math
from typing import Any

PART_CLASSES = {
    'part4_volume': ('part4_FIXED', 'VolumeProfileEngineGPU'),
    'part5_ml': ('part5_FIXED', 'MLEngineGPU'),
    'part6_trend': ('part6_FIXED', 'TrendEngineGPU'),
    'part7_volatility': ('part7_FIXED', 'VolatilityEngineGPU'),
    'part8_structure': ('part8_FIXED', 'MarketStructureEngineGPU'),
    'part9_orderflow': ('part9_FIXED', 'OrderflowEngineGPU'),
    'part10_candlestats': ('part10_FIXED', 'CandleStatsEngineGPU'),
    'part11_fusion': ('part11_FIXED', 'SignalFusionEngineGPU'),
    'part12_confidence': ('part12_FIXED', 'ConfidenceEngineGPU'),
}
VOTE_NAMES = {
    'part4_volume': 'P4_VolumeProfile', 'part5_ml': 'P5_StatisticalML',
    'part6_trend': 'P6_Trend', 'part7_volatility': 'P7_Volatility',
    'part8_structure': 'P8_MarketStructure', 'part9_orderflow': 'P9_Orderflow',
    'part10_candlestats': 'P10_CandleStats',
}


def direction(value: Any) -> str:
    if isinstance(value, str):
        named = {'BUY': 'BUY', 'CALL': 'BUY', 'SELL': 'SELL', 'PUT': 'SELL',
                 'NEUTRAL': 'NEUTRAL', 'NO TRADE': 'NEUTRAL', 'HOLD': 'NEUTRAL'}
        if value.upper() in named:
            return named[value.upper()]
    try:
        number = float(value)
        if not math.isfinite(number):
            return 'NEUTRAL'
        return 'BUY' if number > 0 else 'SELL' if number < 0 else 'NEUTRAL'
    except (ValueError, TypeError):
        return 'NEUTRAL'


class PartEngineBridge:
    def __init__(self, engines=None, *, importer=importlib.import_module):
        self.engines = {}
        self.initialization = {}
        if engines is not None:  # Explicit dependency injection for offline tests.
            self.engines.update(engines)
            for name in PART_CLASSES:
                self.initialization[name] = {'status': 'ready' if name in engines else 'unavailable'}
        else:
            for name, (module, cls) in PART_CLASSES.items():
                try:
                    self.engines[name] = getattr(importer(module), cls)()
                    self.initialization[name] = {'status': 'ready', 'class': cls}
                except Exception as error:
                    self.initialization[name] = {'status': 'unavailable', 'class': cls,
                                                 'error': f'{type(error).__name__}: {error}'}
        self.reset()

    def reset(self):
        self.frames = {}
        self.errors = {}

    def _analyze(self, name, data, context):
        engine = self.engines.get(name)
        error = None
        if engine is not None:
            try:
                # Prevent an analyzer from mutating another Part's evidence.
                payload = data.copy(deep=True) if name in VOTE_NAMES and hasattr(data, 'iloc') else copy.deepcopy(data)
                result = engine.analyze(payload, context=dict(context)) if name in VOTE_NAMES else engine.analyze(payload)
                if not isinstance(result, dict):
                    raise ValueError('analyzer returned non-dictionary')
                field = 'confidence' if name == 'part12_confidence' else 'signal'
                if field not in result:
                    raise ValueError(f'missing {field}')
                value = float(result[field])
                if not math.isfinite(value):
                    raise ValueError(f'non-finite {field}')
                if field == 'confidence' and not 0 <= value <= 100:
                    raise ValueError('confidence outside 0–100 scale')
                if field == 'signal' and value not in (-1, 0, 1):
                    raise ValueError('directional signal must be -1, 0, or 1')
                if 'confidence' in result:
                    confidence = float(result['confidence'])
                    if not math.isfinite(confidence) or not 0 <= confidence <= 100:
                        raise ValueError('invalid confidence')
                if 'telemetry' in result and not isinstance(result['telemetry'], dict):
                    raise ValueError('telemetry must be a dictionary')
                if name == 'part7_volatility' and result.get('telemetry', {}).get('status') in ('insufficient_or_invalid_ohlcv', 'analysis_error'):
                    self.errors.setdefault(context['timeframe'], {})[name] = result.get('thought', 'volatility unavailable')
                    return {**result, 'runtime_status': 'unavailable', 'runtime_source': PART_CLASSES[name][1]}
                return {**result, 'runtime_status': 'native', 'runtime_source': PART_CLASSES[name][1]}
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
        else:
            error = self.initialization[name].get('error', 'engine unavailable')
        self.errors.setdefault(context['timeframe'], {})[name] = error
        if name in VOTE_NAMES:
            # Parts 4–6 and 8–10 delegate to these same mathematical functions.
            # Part 7 uses a different, explicitly labeled CPU risk fallback.
            # Neither path fabricates a successful native/GPU invocation.
            try:
                import quantitative_math as qm
                number = name.split('_', 1)[0][4:]
                return {**qm.part_signal(number, data), 'runtime_status': 'math_fallback',
                        'runtime_source': f'quantitative_math.part_signal({number})',
                        'native_error': error}
            except Exception as exc:
                error += f'; fallback {type(exc).__name__}: {exc}'
        return {'signal': 0, 'confidence': 0, 'runtime_status': 'unavailable',
                'runtime_source': PART_CLASSES[name][1], 'thought': 'engine unavailable', 'error': error}

    def evaluate_frame(self, timeframe, frame, seed_results, context=None):
        context = dict(context or {})
        context['timeframe'] = timeframe
        results = dict(seed_results)
        for name in VOTE_NAMES:
            results[name] = self._analyze(name, frame, context)
        # Named dictionaries preserve Part 11/12 weights and anchors. Part 12
        # evaluates Parts 1–10, not an extra copy of the Part 11 aggregate.
        inputs = dict(results)
        results['part11_fusion'] = self._analyze('part11_fusion', inputs, context)
        results['part12_confidence'] = self._analyze('part12_confidence', inputs, context)
        self.frames[timeframe] = results
        return results

    def select_frame(self, mode):
        preferred = ('1h', '60m', '4h', '240m', '1d') if mode == 'SWING' else ('5m', '5min', '1m', '3m', '15m')
        return next((tf for tf in preferred if tf in self.frames), next(iter(self.frames), None))

    def gate(self, mode, winning_direction, min_confidence=65.0):
        tf = self.select_frame(mode)
        if tf is None:
            return 'PART_ENGINE_NO_DATA'
        # A risk flag on any evaluated frame cannot disappear during voting.
        for frame_results in self.frames.values():
            risk = frame_results.get('part7_volatility', {})
            telemetry = risk.get('telemetry', {})
            if risk.get('entry_blocked') or risk.get('risk_veto') or telemetry.get('entry_blocked') or telemetry.get('risk_veto'):
                return 'PART7_VOLATILITY_VETO'
            if risk.get('runtime_status') == 'unavailable' or telemetry.get('status') == 'insufficient_or_invalid_ohlcv':
                return 'PART7_VOLATILITY_UNAVAILABLE'
        results = self.frames[tf]
        fusion = results['part11_fusion']
        confidence = results['part12_confidence']
        if fusion.get('runtime_status') == 'unavailable':
            return 'PART11_FUSION_UNAVAILABLE'
        if direction(fusion.get('signal')) != winning_direction:
            return 'PART11_FUSION_NO_CONFIRMATION'
        if confidence.get('runtime_status') == 'unavailable':
            return 'PART12_CONFIDENCE_UNAVAILABLE'
        if float(confidence['confidence']) < min_confidence:
            return 'PART12_LOW_CONFIDENCE'
        return None

    def report(self, mode=None):
        tf = self.select_frame(mode)
        return {'initialization': dict(self.initialization), 'errors': dict(self.errors),
                'timeframe_results': dict(self.frames), 'selected_timeframe': tf,
                'selected_part_results': dict(self.frames.get(tf, {})),
                'roles': {'parts4_to10': 'directional_votes', 'part11': 'direction_confirmation',
                          'part12': 'confidence_gate', 'part7': 'directional_vote_and_risk_veto'}}
