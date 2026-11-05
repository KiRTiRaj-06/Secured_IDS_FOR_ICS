# Security Baseline

The default `config/mosquitto.conf` exists only for the private, internal Docker development network. It permits anonymous MQTT so the first local telemetry slice can be assembled without committing credentials.

Before demonstration outside that private network:

1. Replace the broker configuration with `config/mosquitto-secure.conf`.
2. Create a local Mosquitto password file and mount it at `/mosquitto/config/passwords`; exclude it from Git.
3. Create a lab certificate authority and broker certificate, mount them under `/mosquitto/certs`, and exclude private keys from Git.
4. Use port `8883` and configure gateway, detector, and subscribers to verify the CA certificate.
5. Give the gateway a publish-only account for `ot/lab/telemetry`; give the detector a subscribe-only account; reserve control topics for the simulated master identity.
6. Keep the Docker network marked `internal`, avoid publishing broker or IDS ports to the host, and restrict Wazuh dashboard access to the private lab management network.
7. Store secrets only in a local `.env` file, a local password file, or a secrets manager. Do not put them in Compose YAML, scenario files, packet captures, or screenshots.

The IDS remains passive. No detector, Zeek script, Suricata rule, Wazuh rule, or ML result is authorized to issue a DNP3 control command or block process traffic in this project.
