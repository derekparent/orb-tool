"""Tests for fuel service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.fuel_service import FuelService, SERVICE_TANK_PAIRS


class TestFuelService:
    """Test fuel consumption calculations and utilities."""

    def test_calculate_consumption_valid(self):
        """Test valid consumption calculation."""
        result = FuelService.calculate_consumption(12345.0, 12567.2)
        assert result == 222.2

    def test_calculate_consumption_zero(self):
        """Test zero consumption (same readings)."""
        result = FuelService.calculate_consumption(1000.0, 1000.0)
        assert result == 0.0

    def test_calculate_consumption_invalid(self):
        """Test invalid consumption (end < start) raises error."""
        with pytest.raises(ValueError, match="Invalid meter readings"):
            FuelService.calculate_consumption(12567.2, 12345.0)

    def test_calculate_consumption_rounding(self):
        """Test consumption is properly rounded."""
        result = FuelService.calculate_consumption(100.0, 100.333)
        assert result == 0.33

    def test_calculate_stats_empty(self):
        """Test stats with no tickets."""
        stats = FuelService.calculate_stats([])
        assert stats["total_gallons"] == 0.0
        assert stats["average_daily"] == 0.0
        assert stats["days_tracked"] == 0
        assert stats["min_daily"] == 0.0
        assert stats["max_daily"] == 0.0

    def test_calculate_stats_single_ticket(self):
        """Test stats with single ticket."""
        ticket = MagicMock()
        ticket.consumption_gallons = 150.5
        
        stats = FuelService.calculate_stats([ticket])
        assert stats["total_gallons"] == 150.5
        assert stats["average_daily"] == 150.5
        assert stats["days_tracked"] == 1
        assert stats["min_daily"] == 150.5
        assert stats["max_daily"] == 150.5

    def test_calculate_stats_multiple_tickets(self):
        """Test stats with multiple tickets."""
        tickets = []
        for consumption in [100.0, 150.0, 200.0]:
            ticket = MagicMock()
            ticket.consumption_gallons = consumption
            tickets.append(ticket)
        
        stats = FuelService.calculate_stats(tickets)
        assert stats["total_gallons"] == 450.0
        assert stats["average_daily"] == 150.0
        assert stats["days_tracked"] == 3
        assert stats["min_daily"] == 100.0
        assert stats["max_daily"] == 200.0

    def test_get_available_tank_pairs(self):
        """Test available tank pairs list."""
        pairs = FuelService.get_available_tank_pairs()
        assert len(pairs) == 6
        assert pairs[0]["id"] == "7"
        assert pairs[0]["display"] == "#7 P/S"
        assert "13" in [p["id"] for p in pairs]
        assert "14" in [p["id"] for p in pairs]

    def test_validate_tank_pair_valid(self):
        """Test valid tank pair validation."""
        assert FuelService.validate_tank_pair("7") is True
        assert FuelService.validate_tank_pair("13") is True
        assert FuelService.validate_tank_pair("18") is True

    def test_validate_tank_pair_invalid(self):
        """Test invalid tank pair validation."""
        assert FuelService.validate_tank_pair("99") is False
        assert FuelService.validate_tank_pair("") is False
        assert FuelService.validate_tank_pair("ABC") is False

    def test_get_weekly_summary_empty(self):
        """Test weekly summary with no tickets."""
        summary = FuelService.get_weekly_summary([])
        assert summary["period"] == "Last 7 days"
        assert summary["total_gallons"] == 0.0
        assert summary["average_daily"] == 0.0
        assert summary["tickets_count"] == 0

    def test_get_weekly_summary_with_recent(self):
        """Test weekly summary with recent tickets."""
        now = datetime.utcnow()
        
        tickets = []
        for i in range(5):
            ticket = MagicMock()
            ticket.consumption_gallons = 100.0
            ticket.ticket_date = now - timedelta(days=i)
            tickets.append(ticket)
        
        summary = FuelService.get_weekly_summary(tickets)
        assert summary["tickets_count"] == 5
        assert summary["total_gallons"] == 500.0
        # Average over 7 days, not 5 tickets
        assert summary["average_daily"] == round(500.0 / 7, 2)

    def test_get_weekly_summary_excludes_old(self):
        """Test weekly summary excludes tickets older than 7 days."""
        now = datetime.utcnow()
        
        # Recent ticket
        recent = MagicMock()
        recent.consumption_gallons = 100.0
        recent.ticket_date = now - timedelta(days=2)
        
        # Old ticket (8 days ago)
        old = MagicMock()
        old.consumption_gallons = 500.0
        old.ticket_date = now - timedelta(days=8)
        
        summary = FuelService.get_weekly_summary([recent, old])
        assert summary["tickets_count"] == 1
        assert summary["total_gallons"] == 100.0

    def test_service_tank_pairs_constant(self):
        """Test service tank pairs constant."""
        assert "7" in SERVICE_TANK_PAIRS
        assert "9" in SERVICE_TANK_PAIRS
        assert "11" in SERVICE_TANK_PAIRS
        assert "13" in SERVICE_TANK_PAIRS
        assert "14" in SERVICE_TANK_PAIRS
        assert "18" in SERVICE_TANK_PAIRS
        assert len(SERVICE_TANK_PAIRS) == 6

