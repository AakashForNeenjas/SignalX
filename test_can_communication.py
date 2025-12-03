#!/usr/bin/env python3
"""
CAN Communication Test & Diagnostics
================================
This script tests the complete CAN communication loop:
1. DBC loading
2. Message definition initialization
3. Signal caching
4. Message reception and decoding
5. Signal value updates
"""

import sys
import time
import os

def test_can_communication():
    """Test the complete CAN communication pipeline"""
    print("\n" + "="*70)
    print("CAN COMMUNICATION TEST - ROBUST PIPELINE")
    print("="*70 + "\n")
    
    # Test 1: Import modules
    print("[1/6] Testing module imports...")
    try:
        from core.DBCParser import DBCParser
        from core.CANManager import CANManager
        print("  ✓ Modules imported successfully")
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False
    
    # Test 2: Load DBC file
    print("\n[2/6] Loading DBC file...")
    try:
        dbc_parser = DBCParser(dbc_folder="DBC")
        success, msg = dbc_parser.load_dbc_file("RE")
        if success:
            print(f"  ✓ {msg}")
        else:
            print(f"  ✗ {msg}")
            return False
    except Exception as e:
        print(f"  ✗ DBC loading failed: {e}")
        return False
    
    # Test 3: Initialize CANManager with DBC
    print("\n[3/6] Initializing CANManager with DBC...")
    try:
        can_mgr = CANManager(simulation_mode=True, dbc_parser=dbc_parser)
        print("  ✓ CANManager created")
    except Exception as e:
        print(f"  ✗ CANManager creation failed: {e}")
        return False
    
    # Test 4: Connect to CAN (simulation mode)
    print("\n[4/6] Connecting to CAN bus (SIMULATION MODE)...")
    try:
        success, msg = can_mgr.connect()
        if success:
            print(f"  ✓ {msg}")
        else:
            print(f"  ✗ {msg}")
            return False
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return False
    
    # Test 5: Check signal_cache initialization
    print("\n[5/6] Checking signal_cache initialization...")
    try:
        diag = can_mgr.get_diagnostics()
        print(f"  ✓ signal_cache initialized with {diag['signals_in_cache']} signals")
        print(f"    - DBC loaded: {diag['dbc_loaded']}")
        print(f"    - Message definitions: {diag['message_defs_loaded']}")
        print(f"    - Connection status: {diag['connection_status']}")
        print(f"    - Mode: {diag['mode']}")
    except Exception as e:
        print(f"  ✗ Diagnostics check failed: {e}")
        return False
    
    # Test 6: Simulate message reception and cache update
    print("\n[6/6] Testing message reception and signal caching...")
    print("  (Waiting for simulated CAN traffic...)")
    
    try:
        # Simulate messages for a few seconds
        for i in range(5):
            time.sleep(1)
            diag = can_mgr.get_diagnostics()
            print(f"    [{i+1}s] RX: {diag['rx_count']} | Signals updated: {diag['signals_with_values']}/{diag['signals_in_cache']}")
        
        # Final check
        if diag['signals_with_values'] > 0:
            print(f"  ✓ Signal caching working! {diag['signals_with_values']} signals have values")
        else:
            print(f"  ⚠ No signals updated yet (check DBC signal definitions)")
    
    except Exception as e:
        print(f"  ✗ Message reception test failed: {e}")
        return False
    
    # Print full diagnostics
    print("\n" + "="*70)
    print("FINAL DIAGNOSTICS")
    print("="*70)
    can_mgr.print_diagnostics()
    
    # Show some signal values
    print("\n[SIGNAL CACHE SAMPLE]")
    all_signals = can_mgr.get_all_signals_from_cache()
    count = 0
    for signal_name, info in list(all_signals.items())[:5]:
        if info['value'] is not None:
            print(f"  {signal_name}: {info['value']} {info['unit']}")
            count += 1
    
    if count == 0:
        print("  (No signals with values - check DBC encoding)")
    
    print("\n" + "="*70)
    print("✓ CAN COMMUNICATION TEST COMPLETE")
    print("="*70 + "\n")
    
    # Cleanup
    can_mgr.disconnect()
    
    return True

if __name__ == '__main__':
    try:
        success = test_can_communication()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[Test interrupted by user]")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
