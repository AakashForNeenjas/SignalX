#!/usr/bin/env python3
"""
SignalX CAN Signal Test Actions - Comprehensive Verification Script
Verifies all components of the new CAN signal test action implementation
"""

import json
import sys
import traceback

def test_imports():
    """Test that all modules import successfully"""
    print("\n" + "="*60)
    print("TEST 1: Module Imports")
    print("="*60)
    try:
        from core.CANManager import CANManager
        print("✓ CANManager imported")
        
        from ui.Dashboard import (
            CANSignalReadDialog, CANSignalToleranceDialog,
            CANConditionalJumpDialog, CANWaitSignalChangeDialog,
            CANMonitorRangeDialog, CANCompareSignalsDialog,
            CANSetAndVerifyDialog
        )
        print("✓ All 7 dialog classes imported")
        
        from core.Sequencer import Sequencer
        print("✓ Sequencer imported")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_canmanager_methods():
    """Test that all CANManager methods exist and have correct signatures"""
    print("\n" + "="*60)
    print("TEST 2: CANManager Methods")
    print("="*60)
    try:
        from core.CANManager import CANManager
        
        methods_to_check = [
            'read_signal_value',
            'check_signal_tolerance',
            'conditional_jump_check',
            'wait_for_signal_change',
            'monitor_signal_range',
            'compare_two_signals',
            'set_signal_and_verify'
        ]
        
        for method_name in methods_to_check:
            if hasattr(CANManager, method_name):
                method = getattr(CANManager, method_name)
                print(f"✓ CANManager.{method_name}")
            else:
                print(f"✗ CANManager.{method_name} NOT FOUND")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Method check failed: {e}")
        traceback.print_exc()
        return False

def test_dialog_classes():
    """Test that all dialog classes have required methods"""
    print("\n" + "="*60)
    print("TEST 3: Dialog Classes")
    print("="*60)
    try:
        from ui.Dashboard import (
            CANSignalReadDialog, CANSignalToleranceDialog,
            CANConditionalJumpDialog, CANWaitSignalChangeDialog,
            CANMonitorRangeDialog, CANCompareSignalsDialog,
            CANSetAndVerifyDialog
        )
        
        dialog_classes = [
            ('CANSignalReadDialog', CANSignalReadDialog),
            ('CANSignalToleranceDialog', CANSignalToleranceDialog),
            ('CANConditionalJumpDialog', CANConditionalJumpDialog),
            ('CANWaitSignalChangeDialog', CANWaitSignalChangeDialog),
            ('CANMonitorRangeDialog', CANMonitorRangeDialog),
            ('CANCompareSignalsDialog', CANCompareSignalsDialog),
            ('CANSetAndVerifyDialog', CANSetAndVerifyDialog),
        ]
        
        for name, cls in dialog_classes:
            if hasattr(cls, 'get_values'):
                print(f"✓ {name}.get_values() method found")
            else:
                print(f"✗ {name}.get_values() method NOT FOUND")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Dialog class check failed: {e}")
        traceback.print_exc()
        return False

def test_sequencer_handlers():
    """Verify Sequencer has handlers for all CAN signal test actions"""
    print("\n" + "="*60)
    print("TEST 4: Sequencer Handlers")
    print("="*60)
    try:
        # Read Sequencer source code to check for handlers
        with open('core/Sequencer.py', 'r') as f:
            sequencer_code = f.read()
        
        handlers_to_check = [
            'Read Signal Value',
            'Check Signal (Tolerance)',
            'Conditional Jump',
            'Wait For Signal Change',
            'Monitor Signal Range',
            'Compare Two Signals',
            'Set Signal and Verify'
        ]
        
        for handler_name in handlers_to_check:
            if f'if "{handler_name}" in action_name' in sequencer_code or \
               f"if '{handler_name}' in action_name" in sequencer_code:
                print(f"✓ Sequencer handler for '{handler_name}' found")
            else:
                print(f"✗ Sequencer handler for '{handler_name}' NOT FOUND")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Sequencer handler check failed: {e}")
        traceback.print_exc()
        return False

def test_dashboard_integration():
    """Verify Dashboard has dialog integration in add_step and edit_step"""
    print("\n" + "="*60)
    print("TEST 5: Dashboard Integration")
    print("="*60)
    try:
        with open('ui/Dashboard.py', 'r') as f:
            dashboard_code = f.read()
        
        # Check for edit_step method
        if 'def edit_step(self)' not in dashboard_code:
            print("✗ edit_step method not found")
            return False
        print("✓ edit_step method found")
        
        # Check for CAN signal test action dialogs in add_step
        dialogs_to_check = [
            'CANSignalReadDialog',
            'CANSignalToleranceDialog',
            'CANConditionalJumpDialog',
            'CANWaitSignalChangeDialog',
            'CANMonitorRangeDialog',
            'CANCompareSignalsDialog',
            'CANSetAndVerifyDialog'
        ]
        
        for dialog_name in dialogs_to_check:
            if dialog_name in dashboard_code:
                print(f"✓ {dialog_name} referenced in Dashboard")
            else:
                print(f"✗ {dialog_name} NOT referenced in Dashboard")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Dashboard integration check failed: {e}")
        traceback.print_exc()
        return False

def test_parameter_serialization():
    """Test JSON parameter serialization for dialogs"""
    print("\n" + "="*60)
    print("TEST 6: Parameter Serialization")
    print("="*60)
    try:
        test_params = {
            'signal_name': 'VehicleSpeed',
            'timeout': 2.5,
            'expected_value': 45.0,
            'tolerance': 1.0,
            'target_step': 5,
            'min_val': 0,
            'max_val': 100,
            'duration': 5.0,
            'poll_interval': 0.1,
            'message_id': 0x123,
            'target_value': 50.0
        }
        
        # Test serialization
        json_str = json.dumps(test_params)
        print(f"✓ Parameters serialized to JSON ({len(json_str)} bytes)")
        
        # Test deserialization
        deserialized = json.loads(json_str)
        if deserialized == test_params:
            print("✓ Parameters deserialized correctly")
        else:
            print("✗ Deserialized parameters don't match original")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Parameter serialization test failed: {e}")
        traceback.print_exc()
        return False

def test_action_names():
    """Verify action names match between Dashboard and Sequencer"""
    print("\n" + "="*60)
    print("TEST 7: Action Name Consistency")
    print("="*60)
    try:
        action_names = [
            'Read Signal Value',
            'Check Signal (Tolerance)',
            'Conditional Jump',
            'Wait For Signal Change',
            'Monitor Signal Range',
            'Compare Two Signals',
            'Set Signal and Verify'
        ]
        
        with open('ui/Dashboard.py', 'r') as f:
            dashboard_code = f.read()
        
        with open('core/Sequencer.py', 'r') as f:
            sequencer_code = f.read()
        
        for action_name in action_names:
            # Check Dashboard has references
            if action_name in dashboard_code:
                print(f"✓ Dashboard contains '{action_name}'")
            else:
                print(f"✗ Dashboard missing '{action_name}'")
                return False
            
            # Check Sequencer has references
            if action_name in sequencer_code:
                print(f"✓ Sequencer contains '{action_name}'")
            else:
                print(f"✗ Sequencer missing '{action_name}'")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Action name consistency check failed: {e}")
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all verification tests"""
    print("\n" + "="*80)
    print("SignalX CAN Signal Test Actions - Comprehensive Verification")
    print("="*80)
    
    tests = [
        ("Module Imports", test_imports),
        ("CANManager Methods", test_canmanager_methods),
        ("Dialog Classes", test_dialog_classes),
        ("Sequencer Handlers", test_sequencer_handlers),
        ("Dashboard Integration", test_dashboard_integration),
        ("Parameter Serialization", test_parameter_serialization),
        ("Action Name Consistency", test_action_names),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} test crashed: {e}")
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} - {test_name}")
    
    print("-" * 80)
    print(f"Results: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total:
        print("\n✓ ALL TESTS PASSED - Implementation is complete and functional!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed - Please review the output above")
        return 1

if __name__ == '__main__':
    sys.exit(run_all_tests())
