# AtomX Prerequisites Checklist

Before running AtomX on a new PC, confirm the following:

1) NI-VISA Runtime installed
   - Required for TCPIP::...::INSTR VISA instruments.
   - Alternative: pyvisa-py backend (slower, no vendor drivers).

2) PCAN-Basic Driver installed (for PCAN interfaces)
   - Required for python-can PCAN backend.
   - Verify device shows in Windows Device Manager.

3) USB-Serial drivers installed
   - Required for DC Load / RS485 devices (COM ports).
   - Verify COM port appears in Device Manager.

4) Instrument network reachability
   - PC and instruments on the same subnet.
   - Firewalls allow TCP traffic to instrument IPs.

5) Correct IP/COM mapping in config profiles
   - Update `config_profiles/profiles.json` for each lab PC.
   - Select the right profile in the Configuration tab.
