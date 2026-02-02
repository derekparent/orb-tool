"""Fuel consumption tracking and calculation service."""

from datetime import datetime, timedelta, timezone
from typing import TypedDict

UTC = timezone.utc


class ConsumptionStats(TypedDict):
    """Consumption statistics."""

    total_gallons: float
    average_daily: float
    days_tracked: int
    min_daily: float
    max_daily: float


class FuelStatus(TypedDict):
    """Current fuel status."""

    active_tank_pair: str | None
    total_consumption_gallons: float
    average_daily_gallons: float
    days_tracked: int
    last_ticket_date: str | None


# Available service tank pairs (Port/Starboard pairs)
SERVICE_TANK_PAIRS = ["7", "9", "11", "13", "14", "18"]


class FuelService:
    """Service for fuel consumption calculations."""

    @staticmethod
    def calculate_consumption(meter_start: float, meter_end: float) -> float:
        """
        Calculate fuel consumption from meter readings.

        Args:
            meter_start: Starting meter reading (gallons)
            meter_end: Ending meter reading (gallons)

        Returns:
            Consumption in gallons

        Raises:
            ValueError: If meter_end < meter_start (invalid reading)
        """
        consumption = meter_end - meter_start
        if consumption < 0:
            raise ValueError(
                f"Invalid meter readings: end ({meter_end}) cannot be less than start ({meter_start})"
            )
        return round(consumption, 2)

    @staticmethod
    def calculate_stats(tickets: list) -> ConsumptionStats:
        """
        Calculate consumption statistics from a list of fuel tickets.

        Args:
            tickets: List of DailyFuelTicket objects

        Returns:
            ConsumptionStats with aggregated data
        """
        if not tickets:
            return ConsumptionStats(
                total_gallons=0.0,
                average_daily=0.0,
                days_tracked=0,
                min_daily=0.0,
                max_daily=0.0,
            )

        consumptions = [t.consumption_gallons for t in tickets]
        total = sum(consumptions)
        days = len(tickets)

        return ConsumptionStats(
            total_gallons=round(total, 2),
            average_daily=round(total / days, 2) if days > 0 else 0.0,
            days_tracked=days,
            min_daily=round(min(consumptions), 2),
            max_daily=round(max(consumptions), 2),
        )

    @staticmethod
    def calculate_consumption_rate(
        tickets: list, period_days: int = 7
    ) -> float:
        """
        Calculate average daily consumption rate over a period.

        Args:
            tickets: List of DailyFuelTicket objects (should be filtered to period)
            period_days: Number of days in the period

        Returns:
            Average gallons per day
        """
        if not tickets:
            return 0.0

        total = sum(t.consumption_gallons for t in tickets)
        return round(total / period_days, 2)

    @staticmethod
    def get_available_tank_pairs() -> list[dict]:
        """
        Get list of available service tank pairs.

        Returns:
            List of tank pair info dictionaries
        """
        return [
            {"id": pair, "display": f"#{pair} P/S", "description": f"Tank #{pair} Port/Starboard"}
            for pair in SERVICE_TANK_PAIRS
        ]

    @staticmethod
    def validate_tank_pair(tank_pair: str) -> bool:
        """Check if tank pair is valid."""
        return tank_pair in SERVICE_TANK_PAIRS

    @staticmethod
    def get_period_tickets(
        tickets: list, start_date: datetime, end_date: datetime
    ) -> list:
        """
        Filter tickets to a specific date range.

        Args:
            tickets: All tickets
            start_date: Period start
            end_date: Period end

        Returns:
            Filtered list of tickets
        """
        return [
            t for t in tickets
            if start_date <= t.ticket_date <= end_date
        ]

    @staticmethod
    def get_weekly_summary(tickets: list) -> dict:
        """
        Get summary of last 7 days of fuel consumption.

        Args:
            tickets: List of DailyFuelTicket objects

        Returns:
            Weekly summary dict
        """
        if not tickets:
            return {
                "period": "Last 7 days",
                "total_gallons": 0.0,
                "average_daily": 0.0,
                "tickets_count": 0,
            }

        # Get tickets from last 7 days
        # DB stores naive UTC datetimes, so compare as naive
        now = datetime.now(UTC).replace(tzinfo=None)
        week_ago = now - timedelta(days=7)
        weekly_tickets = [t for t in tickets if t.ticket_date >= week_ago]

        if not weekly_tickets:
            return {
                "period": "Last 7 days",
                "total_gallons": 0.0,
                "average_daily": 0.0,
                "tickets_count": 0,
            }

        total = sum(t.consumption_gallons for t in weekly_tickets)

        return {
            "period": "Last 7 days",
            "total_gallons": round(total, 2),
            "average_daily": round(total / 7, 2),
            "tickets_count": len(weekly_tickets),
        }
