#!/usr/bin/env python3
"""
Professional Signal Display - Clean, formatted terminal output
પ્રોફેશનલ સિગ્નલ ડિસ્પ્લે - સાફ, ફોર્મેટેડ ટર્મિનલ આઉટપુટ
"""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ProfessionalSignalDisplay:
    """Display trading signals in professional format"""
    
    def __init__(self):
        self.width = 80
        
    def display_full_signal(self, signal_data, current_price=None):
        """
        Display professional signal with distinct Scalp & Swing setups
        
        Parameters:
        - signal_data: Dictionary containing all signal components
        - current_price: Live market price (float)
        """
        
        # Extract core data
        direction = signal_data.get('direction', 'NEUTRAL')
        confidence = signal_data.get('confidence', 0)
        ai_reason = signal_data.get('ai_reason', 'No reasoning provided')
        
        # Use valid price or fallback
        price = current_price if current_price is not None and current_price > 0 else signal_data.get('entry_price', 0)
        
        # If still 0, try to get from trade_signal if available
        if not price and 'trade_signal' in signal_data:
            price = signal_data['trade_signal'].get('entry_price', 0)
        
        lines = []
        
        # Header
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append("╔" + "═" * (self.width - 2) + "╗")
        lines.append(f"║ 🎯 JARVIS TRADE ELITE v7.0 (PRO) {' ' * (self.width - 34)} ║")
        lines.append(f"║ 🕒 Time: {timestamp} {' ' * (self.width - 29)} ║")
        lines.append("╠" + "═" * (self.width - 2) + "╣")
        
        # Main Signal
        if direction in ['BUY', 'CALL']:
            sig_color = "🟢 BULLISH / CALL"
            side_arrow = "⬆️"
        elif direction in ['SELL', 'PUT']:
            sig_color = "🔴 BEARISH / PUT"
            side_arrow = "⬇️"
        else:
            sig_color = "⚪ NEUTRAL / WAIT"
            side_arrow = "↔️"
            
        lines.append(f"║ 💎 SIGNAL: {sig_color:<20} │ Conf: {confidence:>3}% {side_arrow} {' ' * (self.width - 50)} ║")
        lines.append(f"║ 💰 PRICE:  ${price:,.2f} {' ' * (self.width - 20 - len(f'{price:,.2f}'))} ║")
        lines.append("╠" + "═" * (self.width - 2) + "╣")
        
        # Strategy Section (Scalp vs Swing)
        if direction in ['BUY', 'SELL', 'CALL', 'PUT'] and price > 0:
            # Calculate Levels
            is_buy = direction in ['BUY', 'CALL']
            
            # Scalp (High Leverage, Short Duration)
            scalp_sl_pct = 0.003 # 0.3%
            scalp_tp_pct = 0.006 # 0.6%
            
            # Swing (Low Leverage, Long Duration)
            swing_sl_pct = 0.015 # 1.5%
            swing_tp_pct = 0.035 # 3.5%
            
            if is_buy:
                scalp_entry = price
                scalp_sl = price * (1 - scalp_sl_pct)
                scalp_tp = price * (1 + scalp_tp_pct)
                
                swing_entry = price * 0.998 # Slight pullback entry
                swing_sl = price * (1 - swing_sl_pct)
                swing_tp = price * (1 + swing_tp_pct)
            else:
                scalp_entry = price
                scalp_sl = price * (1 + scalp_sl_pct)
                scalp_tp = price * (1 - scalp_tp_pct)
                
                swing_entry = price * 1.002 # Slight pullback entry
                swing_sl = price * (1 + swing_sl_pct)
                swing_tp = price * (1 - swing_tp_pct)

            lines.append(f"║ ⚡ SCALPING SETUP (1-15m) {' ' * (self.width - 28)} ║")
            lines.append(f"║    Entry: ${scalp_entry:,.2f} (Market) {' ' * (self.width - 34 - len(f'{scalp_entry:,.2f}'))} ║")
            lines.append(f"║    ❌ SL:  ${scalp_sl:,.2f} (0.3%) {' ' * (self.width - 30 - len(f'{scalp_sl:,.2f}'))} ║")
            lines.append(f"║    ✅ TP:  ${scalp_tp:,.2f} (0.6%) {' ' * (self.width - 30 - len(f'{scalp_tp:,.2f}'))} ║")
            lines.append("╟" + "─" * (self.width - 2) + "╢")
            
            lines.append(f"║ 🌊 SWING SETUP (1h-4h) {' ' * (self.width - 26)} ║")
            lines.append(f"║    Entry: ${swing_entry:,.2f} (Limit) {' ' * (self.width - 33 - len(f'{swing_entry:,.2f}'))} ║")
            lines.append(f"║    ❌ SL:  ${swing_sl:,.2f} (1.5%) {' ' * (self.width - 30 - len(f'{swing_sl:,.2f}'))} ║")
            lines.append(f"║    ✅ TP:  ${swing_tp:,.2f} (3.5%) {' ' * (self.width - 30 - len(f'{swing_tp:,.2f}'))} ║")

        else:
            lines.append(f"║ ⚠️  NO TRADE SETUP AVAILABLE {' ' * (self.width - 30)} ║")
            
        lines.append("╠" + "═" * (self.width - 2) + "╣")
        
        # AI Reasoning
        lines.append(f"║ 🧠 AI RATIONALE: {' ' * (self.width - 19)} ║")
        wrapped_reason = self._wrap_text(ai_reason, self.width - 4)
        for line in wrapped_reason:
             lines.append(f"║ {line:<{self.width - 4}} ║")
             
        lines.append("╚" + "═" * (self.width - 2) + "╝")
        
        # Print
        output = "\n".join(lines)
        print(output)
        return output
    
    def _wrap_text(self, text, width):
        """Wrap text to fit within width"""
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1  # +1 for space
            if current_length + word_length <= width:
                current_line.append(word)
                current_length += word_length
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines
    
    def display_compact(self, final_decision):
        """Display compact one-line signal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        direction = final_decision.get('direction', 'HOLD')
        confidence = final_decision.get('confidence', 0)
        entry = final_decision.get('entry', 0)
        
        if direction in ['BUY', 'CALL']:
            emoji = "🟢"
        elif direction in ['SELL', 'PUT']:
            emoji = "🔴"
        else:
            emoji = "⚪"
        
        line = f"[{timestamp}] {emoji} {direction} | Conf: {confidence}% | Entry: ${entry:,.0f}"
        print(line)
        return line


# Test
if __name__ == "__main__":
    display = ProfessionalSignalDisplay()
    
    # Test data
    math = {
        'direction': 'BUY',
        'confidence': 72,
        'breakdown': 'P1:0, P2:1, P3:0, P4:1, P5:1, P6:0'
    }
    
    quantum = {
        'prediction': 'BULLISH',
        'confidence': 65,
        'thought': 'QUANTUM (Physics): 52.3% paths UP | Drift: +12.5bps'
    }
    
    ai = {
        'bias': 'CALL',
        'confidence': 75,
        'reasoning': 'Despite the mixed signals from various parts of our analysis, there is a slight lean towards bullish sentiment due to part2_zone and part5_ml. The pivot point remains steady at close price which often indicates market continuation bias.'
    }
    
    final = {
        'direction': 'BUY',
        'confidence': 70,
        'entry': 50000,
        'tp1': 50750,
        'tp2': 51500,
        'sl': 49500
    }
    
    signal_data = {
        'direction': final['direction'],
        'confidence': final['confidence'],
        'entry_price': final['entry'],
        'ai_reason': ai['reasoning']
    }
    display.display_full_signal(signal_data, current_price=final['entry'])
