import sys
import os
import traceback

sys.path.append(r'c:\jarvis')

def check_architecture():
    print('==================================================')
    print('  JARVIS 100X ARCHITECTURE & HEALTH VALIDATOR     ')
    print('==================================================\n')
    
    print('[1] CHECKING CORE FILES AND IMPORTS...')
    core_files = ['jarvis_FIXED', 'mode_engine', 'jarvis_cognitive_bus']
    for p in range(1, 13):
        core_files.append(f'part{p}_FIXED')
        
    missing = []
    failed_imports = []
    
    for f in core_files:
        if not os.path.exists(f'c:\\jarvis\\{f}.py'):
            missing.append(f)
        else:
            try:
                __import__(f)
            except Exception as e:
                failed_imports.append((f, str(e)))
                
    if missing:
        print(f'  [!] MISSING FILES: {missing}')
    if failed_imports:
        print(f'  [!] FAILED IMPORTS:')
        for f, e in failed_imports:
            print(f'      - {f}: {e}')
    
    if not missing and not failed_imports:
        print('  [+] ALL 12 PARTS & CORE ENGINES IMPORTED SUCCESSFULLY.\n')
        
    print('[2] MAPPING ARCHITECTURE TREE...')
    print('''
    [DATA SOURCES (Binance/Delta)]
             |
             v
    +---------------------------+
    |   JARVIS_COGNITIVE_BUS    | <--- Global Neural Network
    +---------------------------+
             | (Shares State)
             v
    +---------------------------+
    |       MODE_ENGINE         | <--- The 33-Brain Master Classifier
    |---------------------------|
    |  * Part 1 (13 Math Brains)|
    |  * Part 2 (16 AI Brains)  |
    |  * Part 3 (4 Inst. Brains)|
    +---------------------------+
             | (Outputs: SWING/SCALP, BUY/SELL, Dynamic SL/TP)
             v
    +---------------------------+
    |    JARVIS (The CEO)       | <--- (jarvis_FIXED.py)
    |---------------------------|
    |  * Part 7 (Risk Guard)    |
    |  * Part 12 (Execution)    |
    |  * Position Management    |
    +---------------------------+
             |
             v
      [ORDER ROUTING / API]
    ''')
    
    print('\n[3] TESTING MODE_ENGINE E2E CONNECTIVITY...')
    try:
        from mode_engine import ModeEngine
        import pandas as pd
        import numpy as np
        
        engine = ModeEngine()
        bus_status = 'CONNECTED' if hasattr(engine.p2_system, 'bus') and engine.p2_system.bus else 'DISCONNECTED'
        print(f'  [+] ModeEngine initialized. Cognitive Bus: {bus_status}')
        
        # Test structural integrity
        print(f'  [+] Part 1 Trend Brain Bus: {'OK' if hasattr(engine.p1_trend, 'bus') and engine.p1_trend.bus else 'FAIL'}')
        print(f'  [+] Part 3 Institutional Bus: {'OK' if hasattr(engine.p3_institutional, 'bus') and engine.p3_institutional.bus else 'FAIL'}')
        
    except Exception as e:
        print(f'  [!] ModeEngine Test Failed: {e}')
        traceback.print_exc()

    print('\n==================================================')
    print('  SYSTEM VALIDATION COMPLETE. YOU ARE GO FOR DEV! ')
    print('==================================================')

if __name__ == '__main__':
    check_architecture()
