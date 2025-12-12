"""ORB entry generation service."""

from datetime import datetime
from typing import TypedDict

from services.sounding_service import SoundingService


class ORBEntryData(TypedDict):
    """Generated ORB entry data."""

    code: str
    entry_text: str
    entry_date: datetime


class ORBService:
    """Service for generating MARPOL-compliant ORB entries."""

    def __init__(self, sounding_service: SoundingService) -> None:
        """Initialize with sounding service for tank metadata."""
        self._sounding = sounding_service

    def generate_code_c(
        self,
        entry_date: datetime,
        tank_m3: float,
        engineer_name: str,
        engineer_title: str,
    ) -> ORBEntryData:
        """
        Generate Code C entry (Dirty Oil Tank weekly inventory).

        Code C: Collection and Disposal of Oil Residues (Sludge)
        """
        tank_info = self._sounding.get_tank_info("17S")
        date_str = entry_date.strftime("%d %b %Y").upper()

        entry_text = f"""DATE: {date_str}
CODE: C

11.1 {tank_info['name']} (17S)
11.2 {tank_info['capacity_m3']:.2f} m³ capacity
11.3 {tank_m3:.2f} m³ retained
11.4 N/A

{engineer_name}, ({engineer_title}) {date_str}"""

        return ORBEntryData(code="C", entry_text=entry_text, entry_date=entry_date)

    def generate_code_i(
        self,
        entry_date: datetime,
        tank_m3: float,
        engineer_name: str,
        engineer_title: str,
    ) -> ORBEntryData:
        """
        Generate Code I entry (Oily Water Tank weekly inventory).

        Code I: Bilge Water Operations
        """
        tank_info = self._sounding.get_tank_info("17P")
        date_str = entry_date.strftime("%d %b %Y").upper()

        entry_text = f"""DATE: {date_str}
CODE: I

34.1 {tank_info['name']} (17P)
34.2 {tank_info['capacity_m3']:.2f} m³ capacity
34.3 {tank_m3:.2f} m³ retained

{engineer_name}, ({engineer_title}) {date_str}"""

        return ORBEntryData(code="I", entry_text=entry_text, entry_date=entry_date)

    def generate_weekly_entries(
        self,
        entry_date: datetime,
        tank_17p_m3: float,
        tank_17s_m3: float,
        engineer_name: str,
        engineer_title: str,
    ) -> tuple[ORBEntryData, ORBEntryData]:
        """
        Generate both Code C and Code I entries for weekly soundings.

        Returns:
            Tuple of (code_c_entry, code_i_entry)
        """
        code_c = self.generate_code_c(
            entry_date=entry_date,
            tank_m3=tank_17s_m3,
            engineer_name=engineer_name,
            engineer_title=engineer_title,
        )
        code_i = self.generate_code_i(
            entry_date=entry_date,
            tank_m3=tank_17p_m3,
            engineer_name=engineer_name,
            engineer_title=engineer_title,
        )
        return code_c, code_i

