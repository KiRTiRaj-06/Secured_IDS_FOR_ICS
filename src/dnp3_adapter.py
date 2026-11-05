"""DNP3 data source boundary for the DNP3-to-MQTT gateway.

The gateway only needs normalized point snapshots. Keeping the library calls in
this module lets the rest of the system remain stable if the DNP3 library API
or deployment method changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Dnp3Settings:
    host: str
    port: int
    master_address: int
    outstation_address: int


class Dnp3Client(Protocol):
    def read_analog_points(self) -> dict[int, float]: ...


class UnsupportedDnp3Client:
    """Clear failure mode until a compatible binding is installed in the image."""

    def __init__(self, settings: Dnp3Settings) -> None:
        self.settings = settings

    def read_analog_points(self) -> dict[int, float]:
        raise RuntimeError(
            "No DNP3 binding is installed. Set DNP3_PROVIDER=voltron after adding "
            "a tested dnp3-python build, or use the synthetic simulator for the MQTT slice."
        )


class VoltronDnp3Client:
    """Adapter for VOLTTRON dnp3-python's public master API.

    The exact package must be verified against the target Linux image before
    enabling this provider. This class intentionally fails with useful context
    if the installed package API differs from its documented form.
    """

    def __init__(self, settings: Dnp3Settings) -> None:
        self.settings = settings

    def read_analog_points(self) -> dict[int, float]:
        try:
            from dnp3demo import master as dnp3_master  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("DNP3_PROVIDER=voltron requires the dnp3-python package in the gateway image") from exc
        try:
            values = dnp3_master.read_analog_inputs(
                host=self.settings.host,
                port=self.settings.port,
                master_id=self.settings.master_address,
                outstation_id=self.settings.outstation_address,
            )
        except AttributeError as exc:
            raise RuntimeError(
                "The installed dnp3-python API does not expose the expected polling function. "
                "Update only VoltronDnp3Client after validating the package examples."
            ) from exc
        return {int(index): float(value) for index, value in values.items()}


def settings_from_environment() -> Dnp3Settings:
    return Dnp3Settings(
        host=os.getenv("DNP3_HOST", "dnp3-outstation"),
        port=int(os.getenv("DNP3_PORT", "20000")),
        master_address=int(os.getenv("DNP3_MASTER_ADDRESS", "2")),
        outstation_address=int(os.getenv("DNP3_OUTSTATION_ADDRESS", "1")),
    )


def create_client() -> Dnp3Client:
    settings = settings_from_environment()
    provider = os.getenv("DNP3_PROVIDER", "unsupported").lower()
    if provider == "voltron":
        return VoltronDnp3Client(settings)
    return UnsupportedDnp3Client(settings)
