"""
Siglent SDS1104X-U - Usage Examples
====================================
Practical examples covering all major oscilloscope operations.
Run each example function individually after connecting the scope.

Setup:  pip install pyvisa pyvisa-py numpy matplotlib Pillow scipy
        For USB on Windows, also install NI-VISA runtime from ni.com/visa
"""

from siglent_sds1104xu import SiglentSDS1104XU, interactive_mode
import argparse
import functools
import inspect
import time


# ─────────────────────────────────────────────────────────────────────
#  1. BASIC CONNECTION & IDENTITY
# ─────────────────────────────────────────────────────────────────────

def example_connect():
    """Connect, identify, and disconnect."""
    scope = SiglentSDS1104XU()  # USB auto-detect (default)
    idn = scope.connect()
    print(f"Instrument: {idn}")
    print(f"System status: {scope.get_system_status()}")
    scope.disconnect()


def example_context_manager():
    """Using the context manager (recommended)."""
    with SiglentSDS1104XU() as scope:
        print(scope.idn())
        print(f"Sample rate: {scope.get_sample_rate()}")
        print(f"Timebase: {scope.get_tdiv()}")


# ─────────────────────────────────────────────────────────────────────
#  2. CHANNEL CONFIGURATION
# ─────────────────────────────────────────────────────────────────────

def example_channel_setup():
    """Configure all 4 channels with different settings."""
    with SiglentSDS1104XU() as scope:
        # Channel 1: 1V/div, DC coupling, 10x probe, enabled
        scope.configure_channel(1, vdiv=1.0, coupling="D1M", probe=10,
                                offset=0, bw="FULL", enable=True)

        # Channel 2: 500mV/div, AC coupling, 1x probe
        scope.configure_channel(2, vdiv=0.5, coupling="A1M", probe=1,
                                offset=-1.5, bw="20M", enable=True)

        # Channel 3: 2V/div, DC 50-Ohm
        scope.configure_channel(3, vdiv=2.0, coupling="D50", probe=1,
                                enable=True)

        # Channel 4: disabled
        scope.configure_channel(4, vdiv=1.0, enable=False)

        # Verify
        for ch in range(1, 5):
            print(f"CH{ch}: {scope.get_vdiv(ch)}, "
                  f"Coupling={scope.get_coupling(ch)}, "
                  f"Offset={scope.get_offset(ch)}")


def example_channel_invert():
    """Invert a channel and set deskew."""
    with SiglentSDS1104XU() as scope:
        scope.set_invert(1, True)    # invert CH1
        scope.set_skew(1, 5e-9)     # 5 ns deskew
        scope.set_unit(1, "A")      # display as Amps (for current probe)

        time.sleep(2)
        scope.set_invert(1, False)   # restore
        scope.set_unit(1, "V")


# ─────────────────────────────────────────────────────────────────────
#  3. TIMEBASE CONTROL
# ─────────────────────────────────────────────────────────────────────

def example_timebase():
    """Adjust timebase and horizontal position."""
    with SiglentSDS1104XU() as scope:
        # Set 1 ms/div
        scope.set_tdiv(1e-3)
        print(f"Time/div: {scope.get_tdiv()}")

        # Offset trigger point 2 ms to the left
        scope.set_time_offset(-2e-3)
        print(f"Time offset: {scope.get_time_offset()}")

        # Check sample rate and memory
        print(f"Sample rate: {scope.get_sample_rate()}")
        print(f"Memory depth: {scope.get_memory_size()}")

        # Change memory depth
        scope.set_memory_size("14M")
        print(f"New memory: {scope.get_memory_size()}")


def example_zoom():
    """Enable horizontal zoom (magnify) window."""
    with SiglentSDS1104XU() as scope:
        scope.set_tdiv(1e-3)                   # main: 1 ms/div
        scope.set_hor_magnify(True)             # enable zoom
        scope.set_hor_magnify_scale(100e-6)     # zoom: 100 µs/div
        scope.set_hor_magnify_position(0)       # centered

        time.sleep(3)
        scope.set_hor_magnify(False)            # disable zoom


# ─────────────────────────────────────────────────────────────────────
#  4. TRIGGER CONFIGURATIONS
# ─────────────────────────────────────────────────────────────────────

def example_edge_trigger():
    """Basic edge trigger on CH1."""
    with SiglentSDS1104XU() as scope:
        scope.setup_edge_trigger(
            source_ch=1,
            level=1.5,         # 1.5 V
            slope="POS",       # rising edge
            coupling="DC",
            mode="AUTO"
        )
        print(f"Trigger type: {scope.get_trigger_type()}")
        print(f"Trigger level: {scope.get_trig_level(1)}")
        print(f"Trigger slope: {scope.get_trig_slope()}")


def example_pulse_trigger():
    """Pulse width trigger: trigger on pulses shorter than 1 µs."""
    with SiglentSDS1104XU() as scope:
        scope.setup_pulse_trigger(
            source_ch=1,
            level=1.0,
            condition="P2",    # positive pulse < width
            width=1e-6         # 1 µs
        )


def example_video_trigger():
    """Video trigger for NTSC signal."""
    with SiglentSDS1104XU() as scope:
        scope.setup_video_trigger(
            source_ch=1,
            standard="NTSC",
            sync="LINE"
        )


def example_pattern_trigger():
    """Trigger when CH1=High AND CH2=Low."""
    with SiglentSDS1104XU() as scope:
        scope.setup_pattern_trigger(
            c1="H",  # CH1 high
            c2="L",  # CH2 low
            c3="X",  # CH3 don't care
            c4="X"   # CH4 don't care
        )


def example_advanced_triggers():
    """Slope, dropout, runt, and window triggers."""
    with SiglentSDS1104XU() as scope:
        # Slope trigger: rising edge slower than 1 µs
        scope.setup_slope_trigger(
            source_ch=1, level_high=2.0, level_low=0.5,
            condition="RIS", time_limit=1e-6
        )
        time.sleep(2)

        # Dropout trigger: no edge for >5 µs
        scope.setup_dropout_trigger(
            source_ch=1, level=1.0, time_val=5e-6, slope="POS"
        )
        time.sleep(2)

        # Runt trigger: pulses that cross low but not high threshold
        scope.setup_runt_trigger(
            source_ch=1, level_high=3.0, level_low=1.0
        )
        time.sleep(2)

        # Window trigger
        scope.setup_window_trigger(
            source_ch=1, level_high=3.0, level_low=1.0
        )


def example_trigger_holdoff():
    """Adjust trigger holdoff for complex repetitive signals."""
    with SiglentSDS1104XU() as scope:
        scope.setup_edge_trigger(1, level=1.0)
        scope.set_trig_holdoff(100e-6)  # 100 µs holdoff
        print(f"Holdoff: {scope.get_trig_holdoff()}")


# ─────────────────────────────────────────────────────────────────────
#  5. ACQUISITION MODES
# ─────────────────────────────────────────────────────────────────────

def example_acquisition():
    """Cycle through acquisition modes."""
    with SiglentSDS1104XU() as scope:
        # Normal sampling
        scope.set_acquire_mode("SAMPLING")
        print(f"Mode: {scope.get_acquire_mode()}")

        # Peak detect (glitch capture)
        scope.set_acquire_mode("PEAK_DETECT")
        time.sleep(2)

        # Averaging (noise reduction)
        scope.set_acquire_mode("AVERAGE")
        scope.set_average_count(64)
        print(f"Avg count: {scope.get_average_count()}")
        time.sleep(3)

        # High resolution
        scope.set_acquire_mode("HIGH_RES")
        time.sleep(2)

        # Back to normal
        scope.set_acquire_mode("SAMPLING")


def example_single_shot():
    """Single-shot capture with wait."""
    with SiglentSDS1104XU() as scope:
        scope.setup_edge_trigger(1, level=1.0, mode="SINGLE")
        scope.single()
        print("Waiting for trigger...")
        if scope.wait_for_trigger(timeout=10):
            print("Triggered! Downloading waveform...")
            scope.save_waveform_csv(1, "single_shot.csv")
        else:
            print("Timeout - no trigger received")


def example_sequence_mode():
    """Segmented memory acquisition."""
    with SiglentSDS1104XU() as scope:
        scope.set_sequence(on=True, count=100)  # 100 segments
        print(f"Sequence: {scope.get_sequence_count()}")
        scope.run()
        time.sleep(5)
        scope.stop()
        scope.set_sequence(on=False)


# ─────────────────────────────────────────────────────────────────────
#  6. MEASUREMENTS
# ─────────────────────────────────────────────────────────────────────

def example_measurements():
    """Take various measurements."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(2)

        # Individual measurements
        freq = scope.measure_value(1, "FREQ")
        pkpk = scope.measure_pkpk(1)
        rms = scope.measure_value(1, "RMS")
        rise = scope.measure_value(1, "RISE")
        fall = scope.measure_value(1, "FALL")
        duty = scope.measure_value(1, "DUTY")

        print(f"Frequency : {freq:.3f} Hz")
        print(f"Pk-Pk     : {pkpk:.4f} V")
        print(f"RMS       : {rms:.4f} V")
        print(f"Rise time : {rise*1e9:.1f} ns")
        print(f"Fall time : {fall*1e9:.1f} ns")
        print(f"Duty cycle: {duty:.1f} %")

        # Full report
        scope.print_report(1)


def example_ripple_noise(interface: str = "usb",
                         ip: str = SiglentSDS1104XU.DEFAULT_IP,
                         port: int = SiglentSDS1104XU.DEFAULT_PORT,
                         lan_mode: str = "socket"):
    """Measure ripple (Vpp) and noise (Vrms) with the helper."""
    with SiglentSDS1104XU(interface=interface, ip=ip, port=port,
                          lan_mode=lan_mode) as scope:
        result = scope.measure_ripple_noise(
            1,
            ac_coupling=True,
            bw_limit="20M",
            acquire_mode="HIGH_RES",
            fallback_waveform=True,
        )
        print(result)


def _example_items():
    items = []
    for name, obj in globals().items():
        if name.startswith("example_") and callable(obj):
            try:
                lineno = inspect.getsourcelines(obj)[1]
            except Exception:
                lineno = 10**9
            items.append((lineno, name, obj))
    items.sort(key=lambda x: x[0])
    return [(name, obj) for _, name, obj in items]


def _bind_scope_defaults(interface: str, ip: str, port: int,
                         lan_mode: str, resource: str | None):
    original = SiglentSDS1104XU

    def _factory(**kwargs):
        params = {
            "interface": interface,
            "ip": ip,
            "port": port,
            "lan_mode": lan_mode,
        }
        if resource:
            params["resource"] = resource
        params.update(kwargs)
        return original(**params)

    return _factory


def example_measurement_display():
    """Add measurements to on-screen display with statistics."""
    with SiglentSDS1104XU() as scope:
        scope.clear_measurements()
        scope.add_measurement(1, "FREQ")
        scope.add_measurement(1, "PKPK")
        scope.add_measurement(1, "RMS")
        scope.add_measurement(1, "DUTY")
        scope.set_statistics(True)

        time.sleep(5)
        scope.reset_statistics()


def example_counter():
    """Use the hardware frequency counter."""
    with SiglentSDS1104XU() as scope:
        scope.set_counter(True, ch=1)
        time.sleep(2)
        print(f"Counter: {scope.get_counter()}")
        scope.set_counter(False)


# ─────────────────────────────────────────────────────────────────────
#  7. CURSORS
# ─────────────────────────────────────────────────────────────────────

def example_cursors():
    """Manual cursor measurements."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        # Time cursors
        scope.set_cursor_type("MANUAL")
        scope.set_cursor_source(1)
        scope.set_cursor_mode("TIME")
        scope.set_cursor_hpos(-1e-3, 1e-3)  # -1 ms to +1 ms
        print(f"Time cursors: {scope.get_cursor_values()}")

        time.sleep(2)

        # Voltage cursors
        scope.set_cursor_mode("AMPL")
        scope.set_cursor_vpos(0.5, 2.5)     # 0.5 V to 2.5 V
        print(f"Voltage cursors: {scope.get_cursor_values()}")

        time.sleep(2)
        scope.set_cursor_type("OFF")


# ─────────────────────────────────────────────────────────────────────
#  8. MATH & FFT
# ─────────────────────────────────────────────────────────────────────

def example_math():
    """Math operations between channels."""
    with SiglentSDS1104XU() as scope:
        # Addition: CH1 + CH2
        scope.set_math("+", src1=1, src2=2)
        scope.math_on()
        print(f"Math: {scope.get_math_define()}")
        time.sleep(3)

        # Subtraction: CH1 - CH2
        scope.set_math("-", src1=1, src2=2)
        time.sleep(3)

        # Multiply: CH1 * CH2
        scope.set_math("*", src1=1, src2=2)
        time.sleep(3)

        # Integration of CH1
        scope.set_math("INTG", src1=1)
        time.sleep(3)

        # Differentiation of CH1
        scope.set_math("DIFF", src1=1)
        time.sleep(3)

        scope.math_off()


def example_fft():
    """FFT analysis."""
    with SiglentSDS1104XU() as scope:
        # On-scope FFT
        scope.set_fft_source(1)
        scope.set_fft_window("HANNING")
        scope.fft_on()
        scope.set_fft_scale(10)          # 10 dB/div
        scope.set_fft_center(1e6)        # center at 1 MHz
        scope.set_fft_span(2e6)          # 2 MHz span
        time.sleep(3)

        # Software FFT from downloaded data
        scope.fft_off()
        scope.plot_fft(1)


# ─────────────────────────────────────────────────────────────────────
#  9. WAVEFORM CAPTURE & EXPORT
# ─────────────────────────────────────────────────────────────────────

def example_waveform_download():
    """Download and plot a waveform."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(2)

        # Download and plot
        scope.plot_waveform(1, title="My Signal")

        # Save to CSV
        scope.save_waveform_csv(1, "waveform_ch1.csv")

        # Save as numpy archive
        scope.save_waveform_numpy(1, "waveform_ch1.npz")


def example_multi_channel_capture():
    """Capture and plot multiple channels simultaneously."""
    with SiglentSDS1104XU() as scope:
        scope.channel_on(1)
        scope.channel_on(2)
        scope.set_tdiv(1e-3)

        # Download all enabled channels
        data = scope.capture_multi_channel([1, 2])
        for ch, wf in data.items():
            print(f"CH{ch}: {len(wf['voltage'])} points, "
                  f"min={wf['voltage'].min():.3f}V, "
                  f"max={wf['voltage'].max():.3f}V")

        # Overlay plot
        scope.plot_multi_channel([1, 2])


def example_continuous_logging():
    """Log measurements to CSV at regular intervals."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        with open("measurement_log.csv", "w") as f:
            f.write("timestamp,freq_hz,pkpk_v,rms_v,mean_v\n")
            print("Logging... (Ctrl+C to stop)")
            try:
                for i in range(100):  # 100 samples
                    freq = scope.measure_value(1, "FREQ")
                    pkpk = scope.measure_value(1, "PKPK")
                    rms = scope.measure_value(1, "RMS")
                    mean = scope.measure_value(1, "MEAN")
                    ts = time.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{ts},{freq:.6g},{pkpk:.6g},"
                            f"{rms:.6g},{mean:.6g}\n")
                    f.flush()
                    print(f"  [{i+1:3d}] {ts}  f={freq:.1f}Hz  "
                          f"Vpp={pkpk:.3f}V  Vrms={rms:.3f}V")
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nLogging stopped.")


# ─────────────────────────────────────────────────────────────────────
#  10. DISPLAY & SCREENSHOT
# ─────────────────────────────────────────────────────────────────────

def example_display():
    """Adjust display settings."""
    with SiglentSDS1104XU() as scope:
        scope.set_grid("FULL")
        scope.set_intensity(grid=30, trace=80)
        scope.set_persistence("INFINITE")
        time.sleep(5)
        scope.set_persistence("OFF")
        scope.clear_sweeps()


def example_screenshot():
    """Capture a screenshot in BMP and PNG."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(2)
        scope.screenshot("scope_capture.bmp")
        scope.screenshot_png("scope_capture.png")


# ─────────────────────────────────────────────────────────────────────
#  11. REFERENCE WAVEFORMS
# ─────────────────────────────────────────────────────────────────────

def example_reference():
    """Store and display reference waveforms."""
    with SiglentSDS1104XU() as scope:
        # Capture CH1 into Reference A
        scope.ref_save(ch=1, ref="REFA")
        scope.ref_on("REFA")
        scope.set_ref_vdiv("REFA", 1.0)
        scope.set_ref_offset("REFA", 0)

        time.sleep(3)
        scope.ref_off("REFA")


# ─────────────────────────────────────────────────────────────────────
#  12. PASS/FAIL TESTING
# ─────────────────────────────────────────────────────────────────────

def example_passfail():
    """Automated pass/fail mask testing."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(2)

        scope.passfail_source(1)
        scope.passfail_create_mask(x_tolerance=0.4, y_tolerance=0.4)
        scope.passfail_set_action(stop_on_fail=True, buzzer_on_fail=True)
        scope.passfail_on()

        time.sleep(10)
        result = scope.passfail_result()
        print(f"Pass/Fail result: {result}")
        scope.passfail_off()


# ─────────────────────────────────────────────────────────────────────
#  13. SERIAL DECODE
# ─────────────────────────────────────────────────────────────────────

def example_uart_decode():
    """Decode UART on CH1."""
    with SiglentSDS1104XU() as scope:
        scope.setup_uart_decode(
            bus=1, rx_ch=1, baud=115200,
            data_bits=8, parity="NONE", stop_bits=1
        )
        scope.setup_uart_trigger(bus=1, condition="START")
        time.sleep(5)
        scope.decode_off(1)


def example_spi_decode():
    """Decode SPI across CH1-CH4."""
    with SiglentSDS1104XU() as scope:
        scope.setup_spi_decode(
            bus=1, clk_ch=1, mosi_ch=2,
            miso_ch=3, cs_ch=4,
            bit_order="MSB", word_size=8,
            cpol=0, cpha=0
        )
        time.sleep(5)
        scope.decode_off(1)


def example_i2c_decode():
    """Decode I2C on CH1 (SDA) and CH2 (SCL)."""
    with SiglentSDS1104XU() as scope:
        scope.setup_i2c_decode(bus=1, sda_ch=1, scl_ch=2)
        # Trigger on I2C address match
        scope.setup_i2c_trigger(
            bus=1, condition="ADDR",
            address=0x50, direction="WRITE"
        )
        time.sleep(5)
        scope.decode_off(1)


def example_can_decode():
    """Decode CAN bus on CH1."""
    with SiglentSDS1104XU() as scope:
        scope.setup_can_decode(bus=1, src_ch=1, baud=500000)
        time.sleep(5)
        scope.decode_off(1)


def example_lin_decode():
    """Decode LIN bus on CH1."""
    with SiglentSDS1104XU() as scope:
        scope.setup_lin_decode(bus=1, src_ch=1, baud=19200, version="2.0")
        time.sleep(5)
        scope.decode_off(1)


# ─────────────────────────────────────────────────────────────────────
#  14. SAVE / RECALL SETUPS
# ─────────────────────────────────────────────────────────────────────

def example_save_recall():
    """Save and recall oscilloscope setups."""
    with SiglentSDS1104XU() as scope:
        # Save current setup to slot 1
        scope.save_setup(1)
        print("Setup saved to slot 1")

        # Make some changes
        scope.set_tdiv(500e-6)
        scope.set_vdiv(1, 2.0)
        time.sleep(2)

        # Recall original setup
        scope.recall_setup(1)
        print("Setup recalled from slot 1")


# ─────────────────────────────────────────────────────────────────────
#  15. RAW SCPI & INTERACTIVE
# ─────────────────────────────────────────────────────────────────────

def example_raw_scpi():
    """Send any SCPI command directly."""
    with SiglentSDS1104XU() as scope:
        # Queries
        print(scope.send_raw("*IDN?"))
        print(scope.send_raw("TDIV?"))
        print(scope.send_raw("C1:VDIV?"))
        print(scope.send_raw("SARA?"))

        # Commands (no response)
        scope.send_raw("C1:VDIV 2V")
        scope.send_raw("TDIV 1MS")


def example_interactive():
    """Launch interactive SCPI terminal."""
    interactive_mode()  # USB (default)


# ─────────────────────────────────────────────────────────────────────
#  17. LIMIT / ALARM MONITORING
# ─────────────────────────────────────────────────────────────────────

def example_limit_monitor_basic():
    """Monitor a single parameter with alarm limits."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        # Watch CH1 frequency: alarm if outside 990-1010 Hz
        alarms = scope.limit_monitor(
            ch=1, param="FREQ",
            low=990, high=1010,
            interval=0.5,       # sample every 500 ms
            duration=30,         # run for 30 seconds
            log_file="freq_monitor.csv"
        )
        print(f"\nTotal alarms: {len(alarms)}")


def example_limit_monitor_with_callback():
    """Monitor with a custom alarm handler."""
    def alarm_handler(record):
        """Called on every limit violation."""
        print(f"  >>> CUSTOM HANDLER: {record['param']}="
              f"{record['value']:.4g} at {record['timestamp']}")
        # Add your own actions here:
        # - Send email / Slack notification
        # - Toggle a GPIO pin
        # - Log to a database
        # - Stop a test

    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)
        scope.limit_monitor(
            ch=1, param="RMS",
            low=0.5, high=2.5,
            interval=1.0, duration=20,
            on_alarm=alarm_handler
        )


def example_limit_monitor_multi():
    """Monitor multiple parameters at once."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        monitors = [
            {"ch": 1, "param": "FREQ", "low": 990, "high": 1010},
            {"ch": 1, "param": "PKPK", "low": 3.0, "high": 3.6},
            {"ch": 1, "param": "RMS",  "low": 0.8, "high": 1.5},
        ]
        alarms = scope.limit_monitor_multi(
            monitors, interval=1.0, duration=30,
            log_file="multi_monitor.csv"
        )


def example_limit_monitor_background():
    """Run monitoring in background while doing other work."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        # Start background monitor
        monitor_thread = scope.limit_monitor_background(
            ch=1, param="FREQ",
            low=990, high=1010,
            interval=2.0, duration=60,
            log_file="background_monitor.csv"
        )

        # Do other work while monitoring runs
        print("Monitor running in background...")
        for i in range(5):
            rms = scope.measure_value(1, "RMS")
            print(f"  Foreground work: RMS={rms:.4f}V")
            time.sleep(3)

        monitor_thread.join()
        print("Background monitor completed.")


# ─────────────────────────────────────────────────────────────────────
#  18. AUTOMATED CHARACTERIZATION (PARAMETER SWEEP)
# ─────────────────────────────────────────────────────────────────────

def example_sweep_vdiv():
    """Sweep vertical scale and measure signal quality at each step."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        results = scope.sweep_vdiv(
            ch=1,
            vdiv_list=[0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
            params=["PKPK", "RMS", "MEAN", "FREQ"],
            settle_time=1.5
        )
        # Plot RMS vs V/div
        scope.plot_sweep(results, "vdiv", "RMS",
                         title="RMS vs V/div", x_log=True)


def example_sweep_tdiv():
    """Sweep timebase and observe frequency measurement stability."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        results = scope.sweep_tdiv(
            ch=1,
            tdiv_list=[100e-9, 500e-9, 1e-6, 5e-6, 10e-6,
                       50e-6, 100e-6, 500e-6, 1e-3],
            params=["FREQ", "PKPK", "RISE"],
            settle_time=1.5
        )
        scope.plot_sweep(results, "tdiv", "FREQ",
                         title="Frequency vs Timebase", x_log=True)


def example_sweep_trigger_level():
    """Sweep trigger level to find optimal triggering point."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        import numpy as np
        levels = np.linspace(-2.0, 2.0, 20).tolist()
        results = scope.sweep_trigger_level(
            ch=1, levels=levels,
            params=["FREQ", "PKPK", "DUTY"],
            settle_time=1.0
        )
        scope.plot_sweep(results, "trig_level", "FREQ",
                         title="Frequency vs Trigger Level")


def example_sweep_custom():
    """Custom sweep: vary probe attenuation and measure."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        # Sweep offset voltage and measure
        results = scope.sweep_custom(
            set_func=lambda v: scope.set_offset(1, v),
            values=[-2.0, -1.0, 0.0, 1.0, 2.0],
            ch=1,
            params=["MEAN", "PKPK", "RMS"],
            settle_time=1.0,
            label="offset_v"
        )


def example_full_characterization():
    """Complete channel characterization across V/div and T/div."""
    with SiglentSDS1104XU() as scope:
        scope.auto_setup()
        time.sleep(1)

        result = scope.characterize_channel(
            ch=1,
            vdiv_list=[0.05, 0.1, 0.2, 0.5, 1, 2, 5],
            tdiv_list=[100e-9, 1e-6, 10e-6, 100e-6, 1e-3, 10e-3],
            settle_time=1.5,
            output_file="ch1_characterization.json"
        )


# ─────────────────────────────────────────────────────────────────────
#  19. BODE PLOT (FREQUENCY RESPONSE)
# ─────────────────────────────────────────────────────────────────────

def example_bode_with_scope_awg():
    """Bode plot using the scope's built-in AWG (if available)."""
    with SiglentSDS1104XU() as scope:
        # CH1 = DUT input, CH2 = DUT output
        scope.configure_channel(1, vdiv=1.0, coupling="A1M")
        scope.configure_channel(2, vdiv=0.5, coupling="A1M")

        results = scope.bode_plot(
            input_ch=1, output_ch=2,
            freq_start=100,        # 100 Hz
            freq_stop=1e6,         # 1 MHz
            points_per_decade=10,
            settle_time=0.5,
            output_file="bode_data.csv"
        )
        scope.plot_bode(results, title="DUT Frequency Response")


def example_bode_with_external_siggen():
    """Bode plot using an external signal generator via SCPI."""
    import socket

    # Example: control a Siglent SDG series generator
    def set_siggen_freq(freq_hz):
        """Send frequency command to external signal generator."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(("192.168.4.52", 5025))  # siggen IP
        sock.sendall(f"C1:BSWV FRQ,{freq_hz}\n".encode())
        sock.close()

    with SiglentSDS1104XU() as scope:
        scope.configure_channel(1, vdiv=1.0, coupling="A1M")
        scope.configure_channel(2, vdiv=0.5, coupling="A1M")

        results = scope.bode_plot(
            input_ch=1, output_ch=2,
            freq_start=10,
            freq_stop=10e6,
            points_per_decade=15,
            siggen_set_freq=set_siggen_freq,
            settle_time=0.8,
            output_file="bode_external.csv"
        )
        scope.plot_bode(results, title="Filter Response (External SigGen)")


def example_bode_amplifier():
    """Characterize an amplifier's frequency response."""
    with SiglentSDS1104XU() as scope:
        # Use 10x probes
        scope.configure_channel(1, vdiv=0.5, coupling="A1M", probe=10)
        scope.configure_channel(2, vdiv=2.0, coupling="A1M", probe=10)

        results = scope.bode_plot(
            input_ch=1, output_ch=2,
            freq_start=20,         # 20 Hz (audio range start)
            freq_stop=20e3,        # 20 kHz (audio range end)
            points_per_decade=20,  # fine resolution
            settle_time=1.0,
            auto_scale=True,
            output_file="amplifier_bode.csv"
        )
        scope.plot_bode(results, title="Audio Amplifier Frequency Response")


# ─────────────────────────────────────────────────────────────────────
#  20. EYE DIAGRAM ANALYSIS
# ─────────────────────────────────────────────────────────────────────

def example_eye_diagram_1mbps():
    """Eye diagram for a 1 Mbps serial signal."""
    with SiglentSDS1104XU() as scope:
        scope.configure_channel(1, vdiv=0.5, coupling="D1M")
        scope.set_tdiv(500e-9)   # ~2 UI visible

        eye = scope.capture_eye_diagram(
            ch=1,
            bit_rate=1e6,           # 1 Mbps
            num_acquisitions=100,
            bits_displayed=2
        )
        if eye:
            scope.plot_eye_diagram(eye, title="1 Mbps Eye Diagram")


def example_eye_diagram_uart():
    """Eye diagram for a 115200 baud UART signal."""
    with SiglentSDS1104XU() as scope:
        scope.configure_channel(1, vdiv=1.0, coupling="D1M")

        eye = scope.capture_eye_diagram(
            ch=1,
            bit_rate=115200,
            num_acquisitions=50,
            bits_displayed=2
        )
        if eye:
            scope.plot_eye_diagram(eye, title="UART 115200 Eye Diagram")
            print(f"\nEye Height: {eye['eye_height_v']*1e3:.1f} mV")
            print(f"Eye Width:  {eye['eye_width_s']*1e9:.1f} ns "
                  f"({eye['eye_width_ui']*100:.1f}% UI)")
            print(f"Q-Factor:   {eye['q_factor']:.2f}")
            print(f"Est. BER:   {eye['estimated_ber']:.2E}")


def example_eye_diagram_high_speed():
    """Eye diagram for a higher-speed signal (10 Mbps)."""
    with SiglentSDS1104XU() as scope:
        scope.configure_channel(1, vdiv=0.2, coupling="D50", bw="FULL")
        scope.set_acquire_mode("SAMPLING")

        eye = scope.capture_eye_diagram(
            ch=1,
            bit_rate=10e6,
            num_acquisitions=200,
            bits_displayed=3
        )
        if eye:
            scope.plot_eye_diagram(eye, title="10 Mbps Eye Diagram")


# ─────────────────────────────────────────────────────────────────────
#  21. JITTER ANALYSIS
# ─────────────────────────────────────────────────────────────────────

def example_jitter_clock():
    """Jitter analysis on a clock signal."""
    with SiglentSDS1104XU() as scope:
        scope.configure_channel(1, vdiv=1.0, coupling="D1M")
        scope.auto_setup()
        time.sleep(1)

        jitter = scope.analyze_jitter(
            ch=1,
            num_acquisitions=50,
            threshold=None,         # auto-detect
            edge="rising",
            output_file="jitter_data.csv"
        )
        if jitter:
            scope.plot_jitter(jitter, title="Clock Jitter Analysis")


def example_jitter_serial_data():
    """Jitter analysis on a serial data stream."""
    with SiglentSDS1104XU() as scope:
        scope.configure_channel(1, vdiv=0.5, coupling="D1M")
        scope.set_tdiv(1e-6)

        jitter = scope.analyze_jitter(
            ch=1,
            num_acquisitions=100,
            threshold=1.5,          # fixed threshold
            edge="both",            # analyze all edges
            output_file="serial_jitter.csv"
        )
        if jitter:
            scope.plot_jitter(jitter, title="Serial Data Jitter")
            print(f"\nPeriod Jitter RMS: "
                  f"{jitter['period_jitter_rms_s']*1e12:.1f} ps")
            print(f"C2C Jitter RMS:    "
                  f"{jitter['c2c_jitter_rms_s']*1e12:.1f} ps")
            print(f"TIE RMS:           "
                  f"{jitter['tie_rms_s']*1e12:.1f} ps")


def example_jitter_pll_output():
    """Characterize PLL output jitter."""
    with SiglentSDS1104XU() as scope:
        scope.configure_channel(1, vdiv=0.5, coupling="A1M", bw="FULL")
        scope.set_acquire_mode("HIGH_RES")  # maximize timing resolution
        scope.set_memory_size("14M")         # maximum memory depth
        scope.set_tdiv(10e-9)

        jitter = scope.analyze_jitter(
            ch=1,
            num_acquisitions=200,   # many acquisitions for statistics
            edge="rising",
            output_file="pll_jitter.csv"
        )
        if jitter:
            scope.plot_jitter(jitter, title="PLL Output Jitter")
            # Check if Gaussian (random jitter dominant)
            if abs(jitter.get("kurtosis", 0)) < 1:
                print("Jitter appears GAUSSIAN (random jitter dominant)")
            else:
                print("Jitter appears NON-GAUSSIAN "
                      "(deterministic jitter present)")


# ─────────────────────────────────────────────────────────────────────
#  22. POWER INTEGRITY ANALYSIS
# ─────────────────────────────────────────────────────────────────────

def example_power_rail_3v3():
    """Full power integrity analysis of a 3.3V rail."""
    with SiglentSDS1104XU() as scope:
        scope.configure_channel(1, vdiv=0.5, coupling="D1M", probe=1)
        scope.set_tdiv(10e-6)  # 10 µs/div to capture switching ripple

        pi = scope.analyze_power_integrity(
            ch=1,
            nominal_voltage=3.3,
            num_acquisitions=20,
            output_file="pi_3v3_report.json"
        )
        scope.plot_power_integrity(pi)


def example_power_rail_5v():
    """Full power integrity analysis of a 5V rail."""
    with SiglentSDS1104XU() as scope:
        scope.configure_channel(1, vdiv=1.0, coupling="D1M")
        scope.set_tdiv(100e-6)

        pi = scope.analyze_power_integrity(
            ch=1,
            nominal_voltage=5.0,
            num_acquisitions=30,
            output_file="pi_5v_report.json"
        )
        scope.plot_power_integrity(pi)


def example_power_rail_1v2():
    """Analyze a 1.2V core rail (common in FPGAs/processors)."""
    with SiglentSDS1104XU() as scope:
        # Low voltage rail needs sensitive settings
        scope.configure_channel(1, vdiv=0.05, coupling="D1M",
                                offset=-1.2, probe=1)
        scope.set_tdiv(1e-6)
        scope.set_acquire_mode("HIGH_RES")
        scope.set_bw_limit(1, "20M")  # filter HF noise

        pi = scope.analyze_power_integrity(
            ch=1,
            nominal_voltage=1.2,
            num_acquisitions=50,
            output_file="pi_1v2_core.json"
        )
        scope.plot_power_integrity(pi)


def example_quick_power_check():
    """Quick pass/fail check on multiple power rails."""
    with SiglentSDS1104XU() as scope:
        scope.channel_on(1)
        scope.channel_on(2)
        scope.channel_on(3)

        # Check 3 rails in sequence
        rails = [
            (1, 3.3, 5.0, 50),   # CH1: 3.3V, 5% tol, 50mV ripple max
            (2, 5.0, 3.0, 100),   # CH2: 5.0V, 3% tol, 100mV ripple max
            (3, 1.8, 5.0, 30),    # CH3: 1.8V, 5% tol, 30mV ripple max
        ]

        all_pass = True
        for ch, nominal, tol, ripple in rails:
            scope.set_vdiv(ch, nominal / 4)
            scope.set_offset(ch, -nominal)
            time.sleep(0.5)
            ok = scope.quick_power_check(ch, nominal, tol, ripple)
            if not ok:
                all_pass = False

        print(f"\nOverall: {'ALL PASS' if all_pass else 'FAIL'}")


def example_power_transient_response():
    """Capture power rail transient response (load step)."""
    with SiglentSDS1104XU() as scope:
        # Configure for transient capture
        scope.configure_channel(1, vdiv=0.1, coupling="D1M")
        scope.set_tdiv(100e-6)

        # Set up trigger to catch the transient
        scope.setup_edge_trigger(1, level=3.2, slope="NEG", mode="SINGLE")
        scope.single()

        print("Waiting for load transient...")
        if scope.wait_for_trigger(timeout=30):
            print("Transient captured!")
            pi = scope.analyze_power_integrity(
                ch=1,
                nominal_voltage=3.3,
                num_acquisitions=1,
                output_file="transient_response.json"
            )
            scope.plot_power_integrity(pi)
            scope.screenshot_png("transient_capture.png")
        else:
            print("Timeout - no transient detected")


# ─────────────────────────────────────────────────────────────────────
#  23. COMPLETE WORKFLOW EXAMPLE
# ─────────────────────────────────────────────────────────────────────

def example_full_workflow():
    """End-to-end workflow: setup -> measure -> capture -> export."""
    with SiglentSDS1104XU() as scope:  # USB auto-detect
        # 1. Reset and configure
        scope.reset()
        time.sleep(2)

        # 2. Configure channels
        scope.configure_channel(1, vdiv=1.0, coupling="D1M", probe=10)
        scope.configure_channel(2, vdiv=0.5, coupling="A1M", probe=1)
        scope.channel_off(3)
        scope.channel_off(4)

        # 3. Set timebase
        scope.set_tdiv(1e-3)          # 1 ms/div
        scope.set_memory_size("14M")  # max memory

        # 4. Configure trigger
        scope.setup_edge_trigger(1, level=1.5, slope="POS", mode="AUTO")
        scope.set_trig_holdoff(10e-6)

        # 5. Set acquisition mode
        scope.set_acquire_mode("AVERAGE")
        scope.set_average_count(16)

        # 6. Run and wait for stable display
        scope.run()
        time.sleep(3)

        # 7. Take measurements
        scope.print_report(1)
        scope.print_report(2)

        # 8. Capture screenshot
        scope.screenshot_png("full_workflow_capture.png")

        # 9. Download waveforms
        scope.save_waveform_csv(1, "ch1_data.csv")
        scope.save_waveform_csv(2, "ch2_data.csv")

        # 10. Plot
        scope.plot_multi_channel([1, 2])

        # 11. FFT analysis
        scope.plot_fft(1)

        print("\nWorkflow complete! Files saved.")


# ─────────────────────────────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scope examples runner.")
    parser.add_argument("--run-all", action="store_true",
                        help="Run all examples sequentially.")
    parser.add_argument("--only", nargs="*", default=None,
                        help="Run only the specified example names.")
    parser.add_argument("--skip", nargs="*", default=None,
                        help="Skip the specified example names.")
    parser.add_argument("--interface", default="usb",
                        help="Default interface for run-all (usb/lan).")
    parser.add_argument("--ip", default=SiglentSDS1104XU.DEFAULT_IP)
    parser.add_argument("--port", type=int, default=SiglentSDS1104XU.DEFAULT_PORT)
    parser.add_argument("--lan-mode", default="socket",
                        help="LAN mode: socket or visa.")
    parser.add_argument("--resource", default=None,
                        help="Explicit VISA resource (USB or LAN VISA).")
    args = parser.parse_args()

    examples = _example_items()
    example_names = [name for name, _ in examples]

    if args.run_all or args.only:
        if args.only:
            selected = [(n, f) for n, f in examples if n in args.only]
        else:
            selected = examples
        if args.skip:
            selected = [(n, f) for n, f in selected if n not in args.skip]

        # Rebind the class name so examples use the requested defaults.
        globals()["SiglentSDS1104XU"] = _bind_scope_defaults(
            args.interface, args.ip, args.port, args.lan_mode, args.resource
        )

        for name, fn in selected:
            print(f"\n=== {name} ===")
            try:
                fn()
            except Exception as exc:
                print(f"[ERROR] {name}: {exc}")
        raise SystemExit(0)

    print("Available examples:")
    for i, name in enumerate(example_names, 1):
        doc = eval(f"{name}.__doc__").strip()
        print(f"  {i:2d}. {name:35s} - {doc}")

    print(f"\nRun any example:     example_connect()")
    print(f"Full workflow:       example_full_workflow()")
    print(f"Ripple/noise:        example_ripple_noise()")
    print(f"Limit monitoring:    example_limit_monitor_basic()")
    print(f"Bode plot:           example_bode_with_scope_awg()")
    print(f"Eye diagram:         example_eye_diagram_1mbps()")
    print(f"Jitter analysis:     example_jitter_clock()")
    print(f"Power integrity:     example_power_rail_3v3()")
    print(f"Interactive:         example_interactive()")
