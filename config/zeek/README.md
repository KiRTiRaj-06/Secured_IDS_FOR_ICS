# Zeek Configuration

`local.zeek` loads the ICSNPP DNP3 package and enables JSON logs. The offline PCAP workflow installs the package through Zeek Package Manager and invokes `icsnpp-dnp3` directly, so this file is primarily for a later persistent sensor deployment.

The relevant output files are `dnp3.log`, `dnp3_control.log`, and `dnp3_objects.log`. The normalization code consumes `dnp3_control.log` when available and falls back to `dnp3.log` for unauthorized DNP3 control detection.
