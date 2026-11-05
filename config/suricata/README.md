# Suricata Rules

`local.rules` is a small project-owned rule set for laboratory visibility. It must be loaded through a Suricata configuration that includes this directory. Use signature IDs in the private `9000000` range only within this project and change them if they conflict with a lab deployment.

The offline PCAP script mounts this file into the Suricata container and loads it with `-S /rules/local.rules`; `--init-errors-fatal` makes an invalid local rule fail the run instead of silently disabling signatures.

Suricata handles signature detection and EVE JSON logging. DNP3 command authorization remains the Zeek/ICSNPP plus policy-normalization responsibility because it requires the command source and operation context.
