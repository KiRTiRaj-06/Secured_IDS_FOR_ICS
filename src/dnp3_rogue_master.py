"""Lab-only connection attempt used to demonstrate DNP3 source allowlisting."""

from __future__ import annotations

import os
import socket
from time import sleep


DNP3_HOST = os.getenv("DNP3_HOST", "dnp3-tap")
DNP3_PORT = int(os.getenv("DNP3_PORT", "20000"))
def main() -> None:
    with socket.create_connection((DNP3_HOST, DNP3_PORT), timeout=5):
        print("lab-only unapproved client connected to the DNP3 relay; no DNP3 request was sent", flush=True)
        sleep(1)


if __name__ == "__main__":
    main()
