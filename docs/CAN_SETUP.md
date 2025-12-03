# AtomX - CAN Bus Error Explanation

## Understanding the Bus Error

The error message you're seeing:
```
Bus error: an error counter reached the 'heavy'/'warning' limit
```

This is **normal behavior** when:
- You're sending CAN messages but there's no other device on the bus to acknowledge them
- The CAN bus is not properly terminated (120Ω resistors at both ends)
- You're testing in isolation without a complete CAN network

## How to Fix

### Option 1: Add Another CAN Device
Connect at least one other CAN device (like your OBC) to the bus to acknowledge messages.

### Option 2: Use CAN Loopback Mode (Testing Only)
For testing without hardware, you can enable loopback mode in the CAN interface settings.

### Option 3: Ignore the Warnings
If you're just testing the software functionality, these warnings are harmless. The messages are still being transmitted.

## Configuring Cyclic Messages

Edit `AtomX/config.py` to define which messages to send:

```python
CYCLIC_CAN_MESSAGES = {
    0x100: {
        'data': [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08],
        'cycle_time': 0.1  # Send every 100ms
    },
    0x200: {
        'data': [0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80],
        'cycle_time': 0.05  # Send every 50ms
    },
}
```

**Parameters:**
- **Message ID** (hex): CAN identifier (e.g., `0x100`, `0x200`)
- **data**: List of 8 bytes to send
- **cycle_time**: Period in seconds (e.g., `0.1` = 100ms, `0.05` = 50ms)

## Usage

1. **Connect CAN**: Click "Connect CAN" button first
2. **Start Cyclic**: Click "Start Cyclic CAN" to begin sending all configured messages
3. **Stop Cyclic**: Click "Stop Cyclic CAN" to stop all messages

The application will now send all messages defined in `config.py` automatically.
