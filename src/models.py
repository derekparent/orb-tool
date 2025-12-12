"""Database models for Oil Record Book Tool."""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class WeeklySounding(db.Model):
    """Weekly slop tank sounding record."""

    __tablename__ = "weekly_soundings"

    id: int = db.Column(db.Integer, primary_key=True)
    recorded_at: datetime = db.Column(db.DateTime, nullable=False)
    engineer_name: str = db.Column(db.String(100), nullable=False)
    engineer_title: str = db.Column(db.String(50), nullable=False)

    # Tank 17P - Oily Water Tank (Code I)
    tank_17p_feet: int = db.Column(db.Integer, nullable=False)
    tank_17p_inches: int = db.Column(db.Integer, nullable=False)
    tank_17p_gallons: int = db.Column(db.Integer, nullable=False)
    tank_17p_m3: float = db.Column(db.Float, nullable=False)

    # Tank 17S - Dirty Oil Tank (Code C)
    tank_17s_feet: int = db.Column(db.Integer, nullable=False)
    tank_17s_inches: int = db.Column(db.Integer, nullable=False)
    tank_17s_gallons: int = db.Column(db.Integer, nullable=False)
    tank_17s_m3: float = db.Column(db.Float, nullable=False)

    # Metadata
    created_at: datetime = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "recorded_at": self.recorded_at.isoformat(),
            "engineer_name": self.engineer_name,
            "engineer_title": self.engineer_title,
            "tank_17p": {
                "feet": self.tank_17p_feet,
                "inches": self.tank_17p_inches,
                "gallons": self.tank_17p_gallons,
                "m3": self.tank_17p_m3,
            },
            "tank_17s": {
                "feet": self.tank_17s_feet,
                "inches": self.tank_17s_inches,
                "gallons": self.tank_17s_gallons,
                "m3": self.tank_17s_m3,
            },
            "created_at": self.created_at.isoformat(),
        }


class ORBEntry(db.Model):
    """Generated Oil Record Book entry."""

    __tablename__ = "orb_entries"

    id: int = db.Column(db.Integer, primary_key=True)
    entry_date: datetime = db.Column(db.DateTime, nullable=False)
    code: str = db.Column(db.String(1), nullable=False)  # C, I, A, B, etc.
    entry_text: str = db.Column(db.Text, nullable=False)

    # Link to source sounding if applicable
    sounding_id: int = db.Column(
        db.Integer, db.ForeignKey("weekly_soundings.id"), nullable=True
    )
    sounding = db.relationship("WeeklySounding", backref="orb_entries")

    # Metadata
    created_at: datetime = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "entry_date": self.entry_date.isoformat(),
            "code": self.code,
            "entry_text": self.entry_text,
            "sounding_id": self.sounding_id,
            "created_at": self.created_at.isoformat(),
        }


class ServiceTankConfig(db.Model):
    """Active service tank pair configuration."""

    __tablename__ = "service_tank_config"

    id: int = db.Column(db.Integer, primary_key=True)
    tank_pair: str = db.Column(db.String(10), nullable=False)  # e.g., "13", "14"
    activated_at: datetime = db.Column(db.DateTime, nullable=False)
    deactivated_at: datetime = db.Column(db.DateTime, nullable=True)
    notes: str = db.Column(db.String(200), nullable=True)

    # Metadata
    created_at: datetime = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )

    @property
    def is_active(self) -> bool:
        """Check if this tank pair is currently active."""
        return self.deactivated_at is None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "tank_pair": self.tank_pair,
            "tank_pair_display": f"#{self.tank_pair} P/S",
            "activated_at": self.activated_at.isoformat(),
            "deactivated_at": self.deactivated_at.isoformat() if self.deactivated_at else None,
            "is_active": self.is_active,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }


class DailyFuelTicket(db.Model):
    """Daily fuel consumption record from meter readings."""

    __tablename__ = "daily_fuel_tickets"

    id: int = db.Column(db.Integer, primary_key=True)
    ticket_date: datetime = db.Column(db.DateTime, nullable=False)

    # Meter readings (gallons)
    meter_start: float = db.Column(db.Float, nullable=False)
    meter_end: float = db.Column(db.Float, nullable=False)

    # Calculated consumption (gallons)
    consumption_gallons: float = db.Column(db.Float, nullable=False)

    # Active service tank at time of reading
    service_tank_pair: str = db.Column(db.String(10), nullable=False)

    # Engineer info
    engineer_name: str = db.Column(db.String(100), nullable=False)

    # Optional notes
    notes: str = db.Column(db.String(500), nullable=True)

    # Metadata
    created_at: datetime = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "ticket_date": self.ticket_date.isoformat(),
            "meter_start": self.meter_start,
            "meter_end": self.meter_end,
            "consumption_gallons": self.consumption_gallons,
            "service_tank_pair": self.service_tank_pair,
            "service_tank_display": f"#{self.service_tank_pair} P/S",
            "engineer_name": self.engineer_name,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }

