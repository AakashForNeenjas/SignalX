# 🚀 Quick Reference: CAN Signal Test Actions

## Action Summary (7 Total)

### 1. Read Signal Value
**Purpose:** Read current signal value with timeout
**Parameters:**
- Signal name (text)
- Timeout (seconds, default 2.0)
**Returns:** Signal value or timeout error
**Example:** Read "VehicleSpeed" with 2s timeout

### 2. Check Signal (Tolerance)
**Purpose:** Validate signal within tolerance band
**Parameters:**
- Signal name (text)
- Expected value (number)
- Tolerance band (number)
- Timeout (seconds)
**Returns:** PASS if within band, FAIL otherwise
**Example:** EngineRPM should be 3000±100

### 3. Conditional Jump
**Purpose:** Jump to different step based on signal condition
**Parameters:**
- Signal name (text)
- Expected value (number)
- Tolerance (number)
- Target step (number)
**Action:** If condition met → jump to step, else continue
**Example:** If EngineStatus = 1 → jump to step 10

### 4. Wait For Signal Change
**Purpose:** Wait for signal to change from initial value
**Parameters:**
- Signal name (text)
- Initial value (number)
- Timeout (seconds)
- Poll interval (seconds)
**Returns:** New value when changed, or timeout error
**Example:** Wait for VehicleSpeed to change from 0

### 5. Monitor Signal Range
**Purpose:** Verify signal stays within range for duration
**Parameters:**
- Signal name (text)
- Min value (number)
- Max value (number)
- Duration (seconds)
- Poll interval (seconds)
**Returns:** PASS if always in range, FAIL if violations
**Example:** BatteryVoltage stay in [11.0, 14.0] for 5s

### 6. Compare Two Signals
**Purpose:** Compare two signals for equivalence
**Parameters:**
- Signal 1 name (text)
- Signal 2 name (text)
- Tolerance (number)
- Timeout (seconds)
**Returns:** PASS if signals within tolerance, FAIL otherwise
**Example:** VehicleSpeed ≈ GPS_Speed within ±0.5

### 7. Set Signal and Verify
**Purpose:** Set signal value and verify round-trip
**Parameters:**
- Message ID (hex, e.g., 0x123)
- Signal name (text)
- Target value (number)
- Tolerance (number)
- Verify timeout (seconds)
**Returns:** SUCCESS with round-trip time, or FAIL
**Example:** Set EngineTarget = 2500, verify in 2s

---

## Usage Workflow

### Step 1: Add Action
1. Click "Add Step" in Dashboard
2. Select desired CAN action from dropdown
3. Dialog opens with parameter fields

### Step 2: Enter Parameters
1. Fill in required fields
2. Use default values for optional fields
3. Click OK to confirm

### Step 3: Execute Sequence
1. Click "Run Sequence" or "Step"
2. Watch output_log for diagnostics
3. Check action status (PASS/FAIL/ERROR)

### Step 4: Edit Parameters
1. Right-click action in sequence
2. Click "Edit"
3. Dialog opens with current values
4. Modify and click OK

---

## Parameter Guidelines

### Text Parameters (Signal Names)
- Must match DBC signal definitions exactly
- Case-sensitive
- Examples: "VehicleSpeed", "EngineRPM", "BatteryVoltage"

### Number Parameters
- Decimal format (e.g., 3000.5)
- Can be positive or negative
- Tolerance should be reasonable for value range

### Timeout Parameters
- Seconds (decimal)
- Recommended: 2-5 seconds for most operations
- Longer timeouts = slower execution

### Poll Interval
- Seconds (decimal)
- Controls sampling frequency
- Smaller = more responsive, higher CPU
- Typical: 0.1 - 0.5 seconds

### Message ID
- Hexadecimal format
- Can enter as: 0x123 or 123 (auto-converted)
- Must match DBC message definitions

---

## Expected Output Messages

### Success Messages
```
✓ Signal VehicleSpeed = 45.2 km/h (read in 0.05s)
✓ EngineRPM = 3050 (within 3000±100)
✓ Condition met, jumping to step 10
✓ Signal changed from 0 to 1 (waited 2.3s)
✓ Signal stayed in [11.0, 14.0] for 5.0s (45 samples)
✓ VehicleSpeed(45.2) ≈ GPS_Speed(45.1) within ±0.5
✓ Set EngineTarget=2500 verified in 0.12s
```

### Error Messages
```
✗ CAN Read Signal Value failed: signal not found
✗ Check Signal (Tolerance) failed: value out of range
✗ Wait For Signal Change failed: timeout after 5.0s
✗ Monitor Signal Range failed: signal left range [11.0, 14.0]
✗ Compare Two Signals failed: difference 5.2 exceeds ±0.5
✗ Set Signal and Verify failed: verification timeout
```

---

## Troubleshooting

### "Signal not found" Error
- Check signal name in DBC file
- Verify DBC is loaded in CANManager
- Check signal_mapping.json

### Timeout Errors
- Increase timeout value
- Check CAN bus is connected
- Verify signal update frequency
- Check poll_interval is reasonable

### Always FAIL Result
- Check expected value is reasonable
- Verify tolerance band is wide enough
- Monitor actual signal values first
- Check signal units match expectation

### Parameter Won't Save
- Ensure all required fields filled
- Check parameter format (numbers vs text)
- Verify no special characters in names
- Check JSON serialization works

---

## Performance Tips

### For Faster Execution
- Use shorter timeouts when possible
- Use larger poll_intervals (less sampling)
- Use narrower tolerance bands
- Avoid very long monitoring durations

### For Better Accuracy
- Use shorter poll_intervals
- Use wider tolerance bands for noisy signals
- Longer timeouts for slow-changing signals
- Multiple checks instead of single long monitor

### For Debugging
- Add Read Signal Value actions to inspect values
- Use short timeouts to fail fast
- Check output_log messages for diagnostics
- Enable verbose logging if available

---

## Common Patterns

### Pattern 1: Conditional Flow
```
1. Read Signal Value: "EngineStatus"
2. Conditional Jump: If Status = "RUNNING" → step 10
3. (Alternative path if not running)
...
10. (Continue main sequence)
```

### Pattern 2: Verification Chain
```
1. Set Signal and Verify: EngineTarget = 2500
2. Wait For Signal Change: RPM changes from 1000
3. Monitor Signal Range: RPM stays in [2400, 2600]
4. Check Signal (Tolerance): Final RPM ≈ 2500
```

### Pattern 3: Signal Comparison
```
1. Read Signal Value: "Sensor1"
2. Read Signal Value: "Sensor2"
3. Compare Two Signals: Sensor1 vs Sensor2
```

### Pattern 4: Timeout Handling
```
1. Wait For Signal Change: "DoorOpen" with 5s timeout
   (If succeeds, door opened within 5s)
   (If fails, door didn't open)
```

---

## Quick Tips

✓ Always read signal value first to see current state
✓ Use conditional jumps to create complex flows
✓ Set tolerance bands wide for noisy signals
✓ Use shorter timeouts to fail fast on issues
✓ Monitor output_log for detailed diagnostics
✓ Test with short sequences before long ones
✓ Save sequences frequently
✓ Check signal names match DBC exactly

---

## Getting Help

1. **Check Output Log**
   - Shows detailed diagnostic messages
   - Includes timing and error context

2. **Review Signal Mapping**
   - Verify signal name exists
   - Check signal units
   - Confirm signal update frequency

3. **Read Full Documentation**
   - `CAN_SIGNAL_TEST_IMPLEMENTATION.md` - Details
   - `README_CAN_SIGNAL_TESTS.md` - Complete guide
   - See verify_implementation.py for test examples

4. **Test Individual Actions**
   - Add single action with Read Signal Value
   - Check output first
   - Build complex sequences incrementally

---

**All 7 CAN Signal Test Actions Ready to Use!**
