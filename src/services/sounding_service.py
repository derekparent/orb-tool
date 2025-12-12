"""Sounding table lookup and conversion service."""

import json
from pathlib import Path
from typing import TypedDict


class SoundingResult(TypedDict):
    """Result of a sounding lookup."""

    feet: int
    inches: int
    gallons: int
    m3: float


class TankInfo(TypedDict):
    """Tank metadata."""

    name: str
    orb_code: str
    capacity_gallons: int
    capacity_m3: float


class SoundingService:
    """Service for tank sounding lookups and conversions."""

    CONVERSION_FACTOR = 0.00378541  # gallons to m³

    def __init__(self, tables_path: Path | str) -> None:
        """Load sounding tables from JSON file."""
        with open(tables_path) as f:
            data = json.load(f)

        self._metadata = data["metadata"]
        self._tanks = data["tanks"]

        # Build lookup dictionaries for fast access
        self._lookup: dict[str, dict[tuple[int, int], int]] = {}
        for tank_id, tank_data in self._tanks.items():
            self._lookup[tank_id] = {
                (s["feet"], s["inches"]): s["gallons"]
                for s in tank_data["soundings"]
            }

    def get_tank_info(self, tank_id: str) -> TankInfo:
        """Get tank metadata."""
        tank = self._tanks[tank_id]
        return TankInfo(
            name=tank["name"],
            orb_code=tank["orb_code"],
            capacity_gallons=tank["capacity_gallons"],
            capacity_m3=tank["capacity_m3"],
        )

    def lookup(self, tank_id: str, feet: int, inches: int) -> SoundingResult:
        """
        Look up volume for a given sounding.

        Args:
            tank_id: Tank identifier (e.g., "17P", "17S")
            feet: Feet component of sounding
            inches: Inches component of sounding (0-11)

        Returns:
            SoundingResult with gallons and m³ values

        Raises:
            ValueError: If sounding not found in table
        """
        if tank_id not in self._lookup:
            raise ValueError(f"Unknown tank: {tank_id}")

        key = (feet, inches)
        if key not in self._lookup[tank_id]:
            raise ValueError(
                f"Sounding {feet}' {inches}\" not found in table for tank {tank_id}"
            )

        gallons = self._lookup[tank_id][key]
        m3 = round(gallons * self.CONVERSION_FACTOR, 2)

        return SoundingResult(feet=feet, inches=inches, gallons=gallons, m3=m3)

    def gallons_to_m3(self, gallons: int | float) -> float:
        """Convert gallons to cubic meters."""
        return round(gallons * self.CONVERSION_FACTOR, 2)

    def get_available_soundings(self, tank_id: str) -> list[tuple[int, int]]:
        """Get list of valid (feet, inches) combinations for a tank."""
        if tank_id not in self._lookup:
            raise ValueError(f"Unknown tank: {tank_id}")
        return sorted(self._lookup[tank_id].keys())

    @property
    def tank_ids(self) -> list[str]:
        """Get list of available tank IDs."""
        return list(self._tanks.keys())

