# CAN Signal Test Actions - Full Implementation

## Overview
Complete implementation of 7 CAN signal test actions with robust feedback loops, following the GS/PS segregation pattern. This includes:
- Backend signal testing methods in CANManager
- UI dialog classes for parameter collection
- Sequencer handlers for execution and feedback
- Dashboard integration for parameter editing

## Implementation Summary

### 1. CANManager Signal Test Methods (core/CANManager.py)
Added 7 new methods before `_simulate_traffic()`:

#### a) read_signal_value(signal_name, timeout=2.0)
- Reads current value of a signal
- Returns: `(bool, value, diagnostic_message)`
- Includes timeout mechanism for non-blocking operation

#### b) check_signal_tolerance(signal_name, expected, tolerance, timeout)
- Validates signal value is within expected tolerance band
- Returns: `(bool, value, diagnostic_message)`
- PASS/FAIL result with detailed diagnostic

#### c) conditional_jump_check(signal_name, expected, tolerance)
- Evaluates condition for conditional jump actions
- Returns: `(bool, diagnostic_message)`
- Returns True if condition met (for jump), False otherwise

#### d) wait_for_signal_change(signal_name, initial_value, timeout, poll_interval)
- Monitors signal for state change with timeout
- Returns: `(bool, new_value, diagnostic_message)`
- Non-blocking with configurable poll interval

#### e) monitor_signal_range(signal_name, min_val, max_val, duration, poll_interval)
- Continuously monitors signal stays within range
- Returns: `(bool, readings_list, diagnostic_message)`
- Reports violations if signal leaves range

#### f) compare_two_signals(signal1, signal2, tolerance, timeout)
- Compares two signals for equivalence within tolerance
- Returns: `(bool, (value1, value2), diagnostic_message)`
- Detailed comparison diagnostics

#### g) set_signal_and_verify(message_id, signal_name, target_value, verify_timeout, tolerance)
- Sets signal value and verifies it was set (round-trip)
- Returns: `(bool, value, round_trip_time, diagnostic_message)`
- Includes round-trip latency timing

**All methods:**
- Use `signal_cache` for real-time signal values
- Support timeout/poll mechanisms for robust operation
- Include detailed diagnostic messages for troubleshooting
- Return tuples compatible with Sequencer callback pattern

### 2. UI Dialog Classes (ui/Dashboard.py)
Added 7 new QDialog classes for parameter input (lines ~150-442):

#### CANSignalReadDialog
- Parameters: signal_name, timeout
- Returns: `{'signal_name': str, 'timeout': float}`

#### CANSignalToleranceDialog
- Parameters: signal_name, expected_value, tolerance, timeout
- Returns: `{'signal_name': str, 'expected_value': float, 'tolerance': float, 'timeout': float}`

#### CANConditionalJumpDialog
- Parameters: signal_name, expected_value, tolerance, target_step
- Returns: `{'signal_name': str, 'expected_value': float, 'tolerance': float, 'target_step': int}`

#### CANWaitSignalChangeDialog
- Parameters: signal_name, initial_value, timeout, poll_interval
- Returns: `{'signal_name': str, 'initial_value': float, 'timeout': float, 'poll_interval': float}`

#### CANMonitorRangeDialog
- Parameters: signal_name, min_val, max_val, duration, poll_interval
- Returns: `{'signal_name': str, 'min_val': float, 'max_val': float, 'duration': float, 'poll_interval': float}`

#### CANCompareSignalsDialog
- Parameters: signal1, signal2, tolerance, timeout
- Returns: `{'signal1': str, 'signal2': str, 'tolerance': float, 'timeout': float}`

#### CANSetAndVerifyDialog
- Parameters: message_id, signal_name, target_value, tolerance, verify_timeout
- Returns: `{'message_id': int, 'signal_name': str, 'target_value': float, 'tolerance': float, 'verify_timeout': float}`

**All dialogs:**
- Follow standard QDialog pattern
- Include `get_values()` method returning dict
- Support pre-population with `initial` parameter
- Use PyQt6 form layouts with labeled inputs

### 3. Sequencer Handlers (core/Sequencer.py)
Added 7 handlers in CAN action section (before PS section, ~lines 510-650):

Each handler:
- Checks for action name match
- Parses JSON parameters
- Calls corresponding CANManager method
- Emits action_info signal with diagnostic message
- Returns `(bool, diagnostic_message)` tuple
- Handles exceptions with detailed error messages

Special handling for Conditional Jump:
- On condition met: Updates `self.current_step` for jump
- On condition not met: Continues normally with True return

### 4. Dashboard Integration (ui/Dashboard.py)
Updated `add_step()` method (~lines 762-840) with dialog handling.
Updated `edit_step()` method (~lines 921-1100) to support parameter editing.

**add_step() changes:**
- Each CAN signal test action opens appropriate dialog
- Parameters collected as JSON
- Display text formatted for readability
- Stored in UserRole for later retrieval

**edit_step() changes:**
- Cleaned up duplicate code
- Added handlers for all 7 CAN signal test actions
- Supports parameter re-editing with pre-population
- Consistent JSON storage and display formatting

## Feature Highlights

### Robust Feedback Loop
- Real-time diagnostics via `action_info` signal
- Detailed error messages for troubleshooting
- Timeout/poll mechanisms prevent blocking

### Parameter Validation
- JSON-based parameter storage
- Type conversion with error handling
- Hex string support for message IDs

### Signal Management
- DBC-based signal decoding
- Real-time signal_cache access
- Timeout mechanisms for all read operations

### User Experience
- Structured parameter dialogs instead of free-form input
- Readable display text in sequence table
- Edit capability for all parameterized actions

## Usage Examples

### 1. Read Signal Value
1. Select "CAN / Read Signal Value" from dropdown
2. Dialog opens: Enter signal name and timeout
3. Executes: Reads signal with timeout protection
4. Result: `PASS - Signal: VehicleSpeed = 45.2 km/h (read in 0.05s)`

### 2. Check Signal Tolerance
1. Select "CAN / Check Signal (Tolerance)" from dropdown
2. Dialog opens: Signal name, expected value, tolerance band
3. Executes: Validates signal within band
4. Result: `PASS - VehicleSpeed = 45.2 km/h (expected 45.0 ±1.0)`

### 3. Conditional Jump
1. Select "CAN / Conditional Jump" from dropdown
2. Dialog opens: Signal, expected value, target step
3. Executes: Evaluates condition
4. Result: Jumps to target step if condition met

### 4. Wait For Signal Change
1. Select "CAN / Wait For Signal Change" from dropdown
2. Dialog opens: Signal name, initial value, timeout
3. Executes: Monitors signal for change
4. Result: `SUCCESS - Signal changed from 0 to 1 (waited 2.3s)`

### 5. Monitor Signal Range
1. Select "CAN / Monitor Signal Range" from dropdown
2. Dialog opens: Signal name, min/max range, duration
3. Executes: Continuous monitoring for duration
4. Result: `PASS - Signal stayed in range [0, 100] for 5.0s (45 samples)`

### 6. Compare Two Signals
1. Select "CAN / Compare Two Signals" from dropdown
2. Dialog opens: Two signal names, tolerance
3. Executes: Compares signals
4. Result: `PASS - VehicleSpeed(45.2) ≈ EngineSpeeds/10(45.0) within ±0.5`

### 7. Set Signal and Verify
1. Select "CAN / Set Signal and Verify" from dropdown
2. Dialog opens: Message ID, signal name, target value
3. Executes: Sets signal and verifies round-trip
4. Result: `SUCCESS - Set VehicleSpeed=50 verified in 0.12s`

## Architecture Pattern

Follows established GS/PS segregation:
```
CAN action name
    ↓
Dashboard.add_step() opens dialog
    ↓
Dialog collects parameters as JSON
    ↓
Sequencer._execute_action() routes to handler
    ↓
Handler parses JSON and calls CANManager method
    ↓
CANManager executes signal operation
    ↓
Returns (bool, data, time, message) tuple
    ↓
Handler emits action_info signal
    ↓
MainWindow receives signal for dashboard output_log
```

## Error Handling

All components include comprehensive error handling:
- CANManager: Timeouts, invalid signals, communication errors
- Dialogs: Type conversion, required field validation
- Sequencer: Exception catching with detailed messages
- Dashboard: Parameter parsing, JSON handling

## Dependencies

- `cantools`: DBC parsing and signal decoding
- `python-can`: CAN message handling
- `PyQt6`: UI dialogs and display
- `json`: Parameter serialization
- `time`: Timeout and latency measurements

## Testing Checklist

- [x] CANManager methods compile without errors
- [x] Dialog classes compile and instantiate
- [x] Sequencer handlers added without syntax errors
- [x] Dashboard edit_step cleaned up and enhanced
- [x] Parameter JSON serialization works
- [x] All 7 actions appear in CAN dropdown
- [ ] Live test: Execute each action in test sequence
- [ ] Live test: Verify diagnostics in output_log
- [ ] Live test: Test conditional jump routing
- [ ] Live test: Edit parameters for existing actions
- [ ] Live test: Monitor signal changes with real CAN traffic

## Files Modified

1. **core/CANManager.py**
   - Added 7 signal test methods
   - Lines: ~1450-1650 (before _simulate_traffic)

2. **ui/Dashboard.py**
   - Added QLineEdit import (line 3-4)
   - Added 7 dialog classes (lines ~150-442)
   - Updated add_step() CAN handling (lines ~762-840)
   - Updated edit_step() method (lines ~921-1100)

3. **core/Sequencer.py**
   - Added 7 CAN signal test action handlers (lines ~510-650)
   - Inserted before PS action section

## Next Steps

1. **Live Testing**: Execute sequences with real CAN data
2. **Edge Cases**: Test with invalid signal names, out-of-range values
3. **Performance**: Validate timeout mechanisms under load
4. **Documentation**: Update user guide with new actions
5. **Advanced Features**: Consider batching multiple signal reads, conditional logic enhancements

## Notes

- All methods support simulation mode via CANManager
- Signal names must match DBC definitions
- JSON parameters preserved in UserRole for edit capability
- Diagnostic messages include timestamps and latency info
- Conditional jump updates step counter for seamless routing
