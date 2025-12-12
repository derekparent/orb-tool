"""Tests for sounding service."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.sounding_service import SoundingService


@pytest.fixture
def sounding_service():
    """Create sounding service with test data."""
    tables_path = Path(__file__).parent.parent / "data" / "sounding_tables.json"
    return SoundingService(tables_path)


class TestSoundingService:
    """Test sounding table lookups and conversions."""

    def test_lookup_17p_zero(self, sounding_service):
        """Test zero sounding returns zero volume."""
        result = sounding_service.lookup("17P", 0, 0)
        assert result["gallons"] == 0
        assert result["m3"] == 0.0

    def test_lookup_17p_max(self, sounding_service):
        """Test max sounding returns full capacity."""
        result = sounding_service.lookup("17P", 3, 0)
        assert result["gallons"] == 1607
        assert result["m3"] == 6.08

    def test_lookup_17s_midpoint(self, sounding_service):
        """Test midpoint sounding."""
        result = sounding_service.lookup("17S", 1, 6)
        assert result["gallons"] == 619
        assert result["m3"] == 2.34

    def test_lookup_invalid_tank(self, sounding_service):
        """Test invalid tank raises error."""
        with pytest.raises(ValueError, match="Unknown tank"):
            sounding_service.lookup("99X", 0, 0)

    def test_lookup_invalid_sounding(self, sounding_service):
        """Test out-of-range sounding raises error."""
        with pytest.raises(ValueError, match="not found"):
            sounding_service.lookup("17P", 5, 0)

    def test_gallons_to_m3(self, sounding_service):
        """Test gallon to m³ conversion."""
        result = sounding_service.gallons_to_m3(1000)
        assert result == 3.79

    def test_get_tank_info(self, sounding_service):
        """Test tank metadata retrieval."""
        info = sounding_service.get_tank_info("17P")
        assert info["name"] == "Oily Water Tank"
        assert info["orb_code"] == "I"
        assert info["capacity_gallons"] == 1607
        assert info["capacity_m3"] == 6.08

    def test_tank_ids(self, sounding_service):
        """Test available tank IDs."""
        ids = sounding_service.tank_ids
        assert "17P" in ids
        assert "17S" in ids

