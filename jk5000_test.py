import serial
import time

PORT = "COM3"

# Common baud rates to try for older instruments using 7E1
BAUDS = [9600, 19200, 4800, 2400, 38400]

# Candidate probe commands (replace/add once you have JK5000 manual)
CMDS = ["ID", "ID?", "*IDN?", "VER", "HELP", "?"]

ENDINGS = ["\r", "\n", "\r\n"]

def open_7E1(baud: int) -> serial.Serial:
    ser = serial.Serial(
        port=PORT,
        baudrate=baud,
        bytesize=serial.SEVENBITS,      # 7 data bits
        parity=serial.PARITY_EVEN,      # Even parity
        stopbits=serial.STOPBITS_ONE,   # 1 stop bit
        timeout=1.5,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False
    )

    # Some devices need these asserted even without flow control
    ser.rts = True
    ser.dtr = True
    return ser

def probe(ser: serial.Serial, cmd: str, ending: str) -> bytes:
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    payload = (cmd + ending).encode("ascii", errors="ignore")
    ser.write(payload)
    ser.flush()

    time.sleep(0.35)  # give the device time to respond
    data = ser.read(ser.in_waiting or 256)
    return data

def listen_only(ser: serial.Serial, seconds: float = 5.0) -> bytes:
    """If the device streams data automatically, you’ll see it here."""
    ser.reset_input_buffer()
    t0 = time.time()
    out = b""
    while time.time() - t0 < seconds:
        chunk = ser.read(256)
        if chunk:
            out += chunk
    return out

def main():
    print(f"Testing {PORT} with 7E1...")

    for baud in BAUDS:
        try:
            with open_7E1(baud) as ser:
                print(f"\n--- Baud {baud} (7E1) ---")

                # First: listen briefly (detect streaming)
                stream = listen_only(ser, seconds=2.0)
                if stream.strip():
                    print("✅ Streaming data detected at", baud)
                    print("RAW:", stream)
                    return

                # Second: probe with commands
                for cmd in CMDS:
                    for ending in ENDINGS:
                        resp = probe(ser, cmd, ending)
                        if resp and resp.strip():
                            print("✅ Response detected!")
                            print("baud:", baud, "cmd:", cmd, "ending:", repr(ending))
                            print("RAW:", resp)
                            return
                        else:
                            print(f"no resp | cmd={cmd} ending={repr(ending)}")

        except serial.SerialException as e:
            print(f"❌ Could not open {PORT} at {baud} (7E1): {e}")
        except Exception as e:
            print(f"❌ Error at {baud}: {e}")

    print("\n❌ No readable response with 7E1 on tested baud rates.")
    print("Next suspects: wrong baud, needs null-modem (TX/RX swap), or device uses 8N1/7O1/7N2/RTS/CTS, or command set is different.")

if __name__ == "__main__":
    main()
