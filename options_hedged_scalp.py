#!/usr/bin/env python3
"""
Options-Hedged Scalp Execution Engine
Executes dual-leg trades: Futures Scalp (main) + Options (hedge)
"""

import time
import logging
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

class OptionsHedgedScalpEngine:
    def __init__(self, delta_client, ai_hedge_advisor, ai_roundtable):
        self.delta = delta_client
        self.ai_advisor = ai_hedge_advisor
        self.ai_roundtable = ai_roundtable
        
        self.active_positions = {}
        self.closed_positions = []
        self.is_monitoring = False
        self.monitor_thread = None
        
    def start_monitor(self):
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("✅ Hedged Scalp Monitor Started")

    def stop_monitor(self):
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
            logger.info("🛑 Hedged Scalp Monitor Stopped")

    def execute_hedged_scalp(self, signal: dict, current_price: float, atr: float, options_chain: dict, jarvis_result: dict = None) -> dict:
        """
        Main entry point for placing a hedged scalp trade.
        """
        direction = signal.get('direction', 'NO_TRADE')
        
        if direction not in ['BUY', 'SELL', 'CALL', 'PUT']:
            return {"status": "skipped", "reason": f"Invalid direction: {direction}"}
            
        confidence = signal.get('confidence', 0)
        expected_profit = self._estimate_scalp_profit(current_price, atr)
        
        # 1. Ask AI Hedge Advisor
        hedge_decision = self.ai_advisor.evaluate_hedge_setup(
            signal_direction=direction,
            signal_confidence=confidence,
            current_price=current_price,
            atr=atr,
            options_chain=options_chain,
            expected_profit=expected_profit,
            jarvis_result=jarvis_result
        )
        
        # 2. Extract AI Decision
        do_hedge = hedge_decision.get('hedge', 'NO') == 'YES'
        target_strike = hedge_decision.get('strike')
        hedge_ratio = hedge_decision.get('hedge_ratio', 0.5)
        
        # Determine Option Type needed
        # BUY Futures (Long) -> Hedge with PUT (downside protection)
        # SELL Futures (Short) -> Hedge with CALL (upside protection)
        option_type = 'PUT' if direction in ['BUY', 'CALL'] else 'CALL'
        
        logger.info(f"\n┌───────────────────────────────────────────────┐")
        logger.info(f"│ 🛡️ HEDGE ADVISOR: {do_hedge}")
        if do_hedge:
            logger.info(f"│ 🎯 Target Option: {target_strike} {option_type}")
            logger.info(f"│ ⚖️ Ratio: {hedge_ratio}x")
            logger.info(f"│ 🧠 AI Reason: {hedge_decision.get('reason')}")
        logger.info(f"└───────────────────────────────────────────────┘\n")

        # 3. Find specific option contract
        option_contract = None
        if do_hedge and target_strike:
            option_contract = self._find_matching_option(options_chain, target_strike, option_type)
            if not option_contract:
                logger.warning(f"⚠️ Could not find {option_type} at strike {target_strike}. Trading unhedged!")
                do_hedge = False

        # 4. Execute orders (Paper mode for now, easily switchable to Delta API)
        futures_size = 0.01  # Fixed size for example
        position_id = f"pos_{int(time.time())}"
        
        position = {
            "id": position_id,
            "status": "OPEN",
            "entry_time": datetime.now().isoformat(),
            "futures_leg": {
                "direction": direction,
                "entry_price": current_price,
                "size": futures_size,
                "tp1": current_price + (atr * 1.5) if direction in ['BUY', 'CALL'] else current_price - (atr * 1.5),
                "sl": current_price - (atr * 1.0) if direction in ['BUY', 'CALL'] else current_price + (atr * 1.0),
                "current_price": current_price,
                "pnl": 0.0
            },
            "hedge_leg": None,
            "net_pnl": 0.0
        }
        
        if do_hedge and option_contract:
            option_size = futures_size * hedge_ratio
            position["hedge_leg"] = {
                "symbol": option_contract.get("symbol"),
                "type": option_type,
                "strike": target_strike,
                "entry_premium": option_contract.get("price", 0),
                "size": option_size,
                "current_premium": option_contract.get("price", 0),
                "pnl": 0.0
            }
            logger.info(f"🚀 Executed Dual-Leg: {direction} Futures + BUY {option_type} {target_strike}")
        else:
            logger.info(f"🚀 Executed Single-Leg: {direction} Futures (Unhedged)")
            
        self.active_positions[position_id] = position
        
        # Ensure monitor is running
        self.start_monitor()
        
        return {"status": "executed", "position_id": position_id, "hedge_applied": do_hedge}

    def _monitor_loop(self):
        """Background thread monitoring active dual-leg positions"""
        while self.is_monitoring:
            if not self.active_positions:
                time.sleep(5)
                continue
                
            try:
                # In live mode, we'd fetch actual prices from Delta here
                current_price = self.delta.get_live_price("BTCUSDT")
                if current_price <= 0:
                    time.sleep(2)
                    continue
                    
                to_close = []
                
                for pos_id, pos in self.active_positions.items():
                    # Update Futures PnL
                    f_leg = pos["futures_leg"]
                    f_dir = f_leg["direction"]
                    f_entry = f_leg["entry_price"]
                    f_size = f_leg["size"]
                    
                    if f_dir in ['BUY', 'CALL']:
                        f_pnl = (current_price - f_entry) * f_size
                    else:
                        f_pnl = (f_entry - current_price) * f_size
                        
                    f_leg["current_price"] = current_price
                    f_leg["pnl"] = f_pnl
                    
                    # Update Hedge PnL (Mocked for paper mode, use Delta options ticker in live)
                    h_pnl = 0.0
                    h_leg = pos.get("hedge_leg")
                    if h_leg:
                        # Simple intrinsic value mock
                        if h_leg["type"] == 'PUT':
                            intrinsic = max(0, h_leg["strike"] - current_price)
                        else:
                            intrinsic = max(0, current_price - h_leg["strike"])
                            
                        # Assuming delta 0.5 for ATM, rough approximation
                        current_premium = h_leg["entry_premium"] + (intrinsic * 0.5)
                        h_leg["current_premium"] = current_premium
                        h_pnl = (current_premium - h_leg["entry_premium"]) * h_leg["size"]
                        h_leg["pnl"] = h_pnl
                        
                    pos["net_pnl"] = f_pnl + h_pnl
                    
                    # Ask AI Monitor if we have a hedge
                    if h_leg:
                        monitor_decision = self.ai_advisor.monitor_active_hedge(
                            hedge_position=h_leg,
                            current_price=current_price,
                            main_trade_pnl=f_pnl,
                            hedge_pnl=h_pnl
                        )
                        
                        if monitor_decision.get("action") == "CLOSE_HEDGE_EARLY":
                            logger.info(f"🤖 AI advised taking hedge profit: {monitor_decision.get('reason')}")
                            # Close hedge leg only
                            pos["hedge_leg"] = None 
                            pos["net_pnl"] += h_pnl # Lock it in
                            
                    # Check Futures TP / SL
                    close_reason = None
                    if f_dir in ['BUY', 'CALL']:
                        if current_price >= f_leg["tp1"]: close_reason = "TP1 Hit"
                        elif current_price <= f_leg["sl"]: close_reason = "SL Hit"
                    else:
                        if current_price <= f_leg["tp1"]: close_reason = "TP1 Hit"
                        elif current_price >= f_leg["sl"]: close_reason = "SL Hit"
                        
                    if close_reason:
                        pos["close_reason"] = close_reason
                        to_close.append(pos_id)
                        
                # Process closures
                for pos_id in to_close:
                    self._close_position(pos_id)
                    
            except Exception as e:
                logger.error(f"[HEDGE-ENGINE] Monitor loop error: {e}")
                
            time.sleep(10) # 10 sec polling

    def _close_position(self, position_id: str):
        if position_id in self.active_positions:
            pos = self.active_positions.pop(position_id)
            pos["status"] = "CLOSED"
            pos["exit_time"] = datetime.now().isoformat()
            self.closed_positions.append(pos)
            
            logger.info(f"\n{'='*50}")
            logger.info(f"🏁 CLOSED HEDGED POSITION: {pos_id}")
            logger.info(f"Reason: {pos.get('close_reason')}")
            logger.info(f"Futures PnL: ${pos['futures_leg']['pnl']:.2f}")
            if pos.get("hedge_leg"):
                logger.info(f"Hedge PnL: ${pos['hedge_leg']['pnl']:.2f}")
            logger.info(f"💰 NET PnL: ${pos['net_pnl']:.2f}")
            logger.info(f"{'='*50}\n")

    def _find_matching_option(self, options_chain: dict, target_strike: int, option_type: str) -> dict:
        """Find the specific option contract from the chain"""
        key = "puts" if option_type == "PUT" else "calls"
        options = options_chain.get(key, [])
        
        # Find exact strike match
        for opt in options:
            if opt.get("strike") == target_strike:
                return opt
                
        # If not exact, find closest
        if options:
            return min(options, key=lambda x: abs(x.get("strike", 0) - target_strike))
            
        return None

    def _estimate_scalp_profit(self, current_price: float, atr: float) -> float:
        """Rough estimate of $ profit for a 1 ATR move on 0.01 BTC"""
        return (atr * 0.01)
