"""Software DNP3 outstation that exposes one changing analog tank-level point.

This is an isolated laboratory device. It does not control physical equipment.
"""

from __future__ import annotations

import os
from time import sleep

from dnp3_python.dnp3station.outstation_new import MyOutStationNew
from pydnp3 import opendnp3


HOST = os.getenv("DNP3_BIND_HOST", "0.0.0.0")
PORT = int(os.getenv("DNP3_PORT", "20000"))
MASTER_ADDRESS = int(os.getenv("DNP3_MASTER_ADDRESS", "2"))
OUTSTATION_ADDRESS = int(os.getenv("DNP3_OUTSTATION_ADDRESS", "1"))
INTERVAL = max(0.5, float(os.getenv("DNP3_POINT_INTERVAL", "2.0")))


def main() -> None:
    outstation = MyOutStationNew(
        outstation_ip=HOST,
        port=PORT,
        master_id=MASTER_ADDRESS,
        outstation_id=OUTSTATION_ADDRESS,
    )
    outstation.start()
    level = 45.0
    direction = 1.0
    try:
        while True:
            outstation.apply_update(opendnp3.Analog(value=level), index=0)
            print(f"DNP3 analog input 0 = {level:.1f}%", flush=True)
            level += direction * 2.5
            if level >= 80.0 or level <= 25.0:
                direction *= -1.0
            sleep(INTERVAL)
    finally:
        outstation.shutdown()


if __name__ == "__main__":
    main()
