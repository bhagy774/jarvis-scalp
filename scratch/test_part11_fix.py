import sys
import os

def simulate_fusion(buy_names, neutral_names):
    weights = {
        'part1_breakout': 1.1,      
        'part2_zone': 1.3,          
        'part3_psychology': 1.0,    
        'part4_volume': 1.3,        
        'part5_ml': 1.2,            
        'part6_trend': 1.5,         
        'part7_volatility': 1.1,    
        'part8_structure': 1.4,     
        'part9_orderflow': 1.4,     
        'part10_candlestats': 1.0,  
    }
    
    weighted_buy = 0.0
    weighted_sell = 0.0
    weighted_neutral = 0.0
    active_buy_engines = []
    active_sell_engines = []
    active_neutral_engines = []
    
    for name in buy_names:
        w = weights.get(name, 1.0)
        weighted_buy += w
        active_buy_engines.append(name)
        
    for name in neutral_names:
        w = weights.get(name, 1.0)
        weighted_neutral += w
        active_neutral_engines.append(name)
        
    total_weight = weighted_buy + weighted_sell + weighted_neutral
    total_active_engines = len(active_buy_engines) + len(active_sell_engines) + len(active_neutral_engines)
    
    buy_ratio = weighted_buy / total_weight if total_weight > 0 else 0
    print(f"Old System: total_weight={weighted_buy}, buy_ratio={weighted_buy/weighted_buy*100}% -> TRADE TAKEN")
    print(f"New System: total_weight={total_weight:.2f}, buy_ratio={buy_ratio*100:.1f}%")
    print(f"Trade would be taken? {'YES' if buy_ratio >= 0.65 and weighted_buy >= 3.5 else 'NO (BLOCKED BY CHOP)'}\n")

print("--- Testing LOSS #6 ---")
simulate_fusion(['part3_psychology', 'part4_volume', 'part5_ml', 'part6_trend'], 
                ['part1_breakout', 'part2_zone', 'part7_volatility', 'part8_structure', 'part9_orderflow', 'part10_candlestats'])

print("--- Testing LOSS #16 ---")
simulate_fusion(['part3_psychology', 'part5_ml', 'part8_structure', 'part10_candlestats'], 
                ['part1_breakout', 'part2_zone', 'part4_volume', 'part6_trend', 'part7_volatility', 'part9_orderflow'])
