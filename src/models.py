"""Database models for Oil Record Book Tool."""

from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt
from enum import Enum

db = SQLAlchemy()
UTC = timezone.utc


class UserRole(Enum):
    """User roles for access control."""
    CHIEF_ENGINEER = "chief_engineer"
    ENGINEER = "engineer"
    VIEWER = "viewer"


class User(UserMixin, db.Model):
    """User authentication and authorization."""

    __tablename__ = "users"

    id: int = db.Column(db.Integer, primary_key=True)
    username: str = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email: str = db.Column(db.String(120), unique=True, nullable=True)
    password_hash: str = db.Column(db.String(256), nullable=False)
    role: str = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.ENGINEER)
    full_name: str = db.Column(db.String(120), nullable=True)
    is_active: bool = db.Column(db.Boolean, default=True, nullable=False)

    # Session persistence
    last_login: datetime = db.Column(db.DateTime, nullable=True)

    # Metadata
    created_at: datetime = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: datetime = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC)
    )

    def set_password(self, password: str) -> None:
        """Hash and set password using bcrypt."""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, password: str) -> bool:
        """Check password against stored hash."""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def has_role(self, role: UserRole) -> bool:
        """Check if user has specific role."""
        return self.role == role

    def can_access_route(self, route_type: str) -> bool:
        """Check if user can access a specific route type."""
        if not self.is_active:
            return False

        # Everyone can read
        if route_type == "read":
            return True

        # Only Chief Engineer and Engineer can write
        if route_type == "write":
            return self.role in [UserRole.CHIEF_ENGINEER, UserRole.ENGINEER]

        # Only Chief Engineer can do admin operations (start hitch, manage users)
        if route_type == "admin":
            return self.role == UserRole.CHIEF_ENGINEER

        return False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


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
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC)
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
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC)
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
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC)
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
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC)
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


# Equipment list constant
EQUIPMENT_LIST = [
    {"id": "PME", "name": "Port Main Engine"},
    {"id": "PRG", "name": "Port Reduction Gear"},
    {"id": "SME", "name": "STBD Main Engine"},
    {"id": "SRG", "name": "STBD Reduction Gear"},
    {"id": "SSDG1", "name": "Generator #1"},
    {"id": "SSDG2", "name": "Generator #2"},
    {"id": "SSDG3", "name": "Generator #3"},
    {"id": "T1", "name": "FWD Bow Thruster"},
    {"id": "T2", "name": "AFT Bow Thruster"},
    {"id": "T3", "name": "Stern Thruster"},
]


class StatusEvent(db.Model):
    """Quick status events (sewage pump, potable load, etc.)."""

    __tablename__ = "status_events"

    id: int = db.Column(db.Integer, primary_key=True)
    event_type: str = db.Column(db.String(50), nullable=False)  # 'sewage_pump', 'potable_load'
    event_date: datetime = db.Column(db.DateTime, nullable=False)
    notes: str = db.Column(db.String(500), nullable=True)
    engineer_name: str = db.Column(db.String(100), nullable=True)

    # Metadata
    created_at: datetime = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "event_date": self.event_date.isoformat(),
            "notes": self.notes,
            "engineer_name": self.engineer_name,
            "created_at": self.created_at.isoformat(),
        }


class EquipmentStatus(db.Model):
    """Equipment status tracking."""

    __tablename__ = "equipment_status"

    id: int = db.Column(db.Integer, primary_key=True)
    equipment_id: str = db.Column(db.String(10), nullable=False)  # 'PME', 'SSDG1', etc.
    status: str = db.Column(db.String(20), nullable=False)  # 'online', 'issue', 'offline'
    note: str = db.Column(db.String(500), nullable=True)
    updated_at: datetime = db.Column(db.DateTime, nullable=False)
    updated_by: str = db.Column(db.String(100), nullable=False)

    # Metadata
    created_at: datetime = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        # Find equipment name
        equip = next((e for e in EQUIPMENT_LIST if e["id"] == self.equipment_id), None)
        name = equip["name"] if equip else self.equipment_id

        return {
            "id": self.id,
            "equipment_id": self.equipment_id,
            "equipment_name": name,
            "status": self.status,
            "note": self.note,
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat(),
        }


class OilLevel(db.Model):
    """Service oil tank level tracking."""

    __tablename__ = "oil_levels"

    id: int = db.Column(db.Integer, primary_key=True)
    recorded_at: datetime = db.Column(db.DateTime, nullable=False)

    # Tank levels (gallons)
    tank_15p_lube: float = db.Column(db.Float, nullable=True)
    tank_15s_gear: float = db.Column(db.Float, nullable=True)
    tank_16p_lube: float = db.Column(db.Float, nullable=True)
    tank_16s_hyd: float = db.Column(db.Float, nullable=True)

    # Source of data
    source: str = db.Column(db.String(50), nullable=True)  # 'fuel_ticket', 'manual', 'hitch_start'
    engineer_name: str = db.Column(db.String(100), nullable=True)

    # Metadata
    created_at: datetime = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "recorded_at": self.recorded_at.isoformat(),
            "tank_15p_lube": self.tank_15p_lube,
            "tank_15s_gear": self.tank_15s_gear,
            "tank_16p_lube": self.tank_16p_lube,
            "tank_16s_hyd": self.tank_16s_hyd,
            "source": self.source,
            "engineer_name": self.engineer_name,
            "created_at": self.created_at.isoformat(),
        }


class FuelTankSounding(db.Model):
    """Individual fuel tank sounding record."""

    __tablename__ = "fuel_tank_soundings"

    id: int = db.Column(db.Integer, primary_key=True)
    hitch_id: int = db.Column(
        db.Integer, db.ForeignKey("hitch_records.id"), nullable=False
    )

    tank_number: str = db.Column(db.String(10), nullable=False)  # "7", "9", "11", "13", "14", "18"
    side: str = db.Column(db.String(4), nullable=False)  # "port" or "stbd"
    is_day_tank: bool = db.Column(db.Boolean, default=False)  # True for #18

    sounding_feet: int = db.Column(db.Integer, nullable=True)
    sounding_inches: int = db.Column(db.Integer, nullable=True)
    water_present: str = db.Column(db.String(20), default="None")  # "None", "Trace", etc.
    gallons: float = db.Column(db.Float, nullable=False)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        tank_label = f"#{self.tank_number} {'Stbd' if self.side == 'stbd' else 'Port'}"
        if self.is_day_tank:
            tank_label += " Day Tank"
        return {
            "id": self.id,
            "tank_number": self.tank_number,
            "side": self.side,
            "tank_label": tank_label,
            "is_day_tank": self.is_day_tank,
            "sounding_feet": self.sounding_feet,
            "sounding_inches": self.sounding_inches,
            "water_present": self.water_present,
            "gallons": self.gallons,
        }


class HitchRecord(db.Model):
    """Complete End of Hitch Sounding Form record."""

    __tablename__ = "hitch_records"

    id: int = db.Column(db.Integer, primary_key=True)

    # Header info
    vessel: str = db.Column(db.String(100), default="USNS Arrowhead")
    date: datetime = db.Column(db.DateTime, nullable=False)
    location: str = db.Column(db.String(100), nullable=True)
    charter: str = db.Column(db.String(50), default="MSC")

    # Draft readings (separate feet/inches)
    draft_forward_feet: int = db.Column(db.Integer, nullable=True)
    draft_forward_inches: int = db.Column(db.Integer, nullable=True)
    draft_aft_feet: int = db.Column(db.Integer, nullable=True)
    draft_aft_inches: int = db.Column(db.Integer, nullable=True)

    # Fuel reconciliation
    fuel_on_log: float = db.Column(db.Float, nullable=True)
    correction: float = db.Column(db.Float, nullable=True)
    total_fuel_gallons: float = db.Column(db.Float, nullable=False)

    # Service oil tanks (gallons only - no soundings)
    lube_oil_15p: float = db.Column(db.Float, nullable=True)
    gear_oil_15s: float = db.Column(db.Float, nullable=True)
    lube_oil_16p: float = db.Column(db.Float, nullable=True)
    hyd_oil_16s: float = db.Column(db.Float, nullable=True)

    # Slop tanks (soundings + gallons)
    oily_bilge_17p_feet: int = db.Column(db.Integer, nullable=True)
    oily_bilge_17p_inches: int = db.Column(db.Integer, nullable=True)
    oily_bilge_17p_gallons: float = db.Column(db.Float, nullable=True)

    dirty_oil_17s_feet: int = db.Column(db.Integer, nullable=True)
    dirty_oil_17s_inches: int = db.Column(db.Integer, nullable=True)
    dirty_oil_17s_gallons: float = db.Column(db.Float, nullable=True)

    # Engineer info
    engineer_name: str = db.Column(db.String(100), nullable=True)

    # Hitch tracking
    is_start: bool = db.Column(db.Boolean, default=True)  # True = start of hitch, False = end
    end_date: datetime = db.Column(db.DateTime, nullable=True)  # When hitch ended

    # Metadata
    created_at: datetime = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relationships
    fuel_tanks = db.relationship(
        "FuelTankSounding",
        backref="hitch",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "vessel": self.vessel,
            "date": self.date.isoformat() if self.date else None,
            "location": self.location,
            "charter": self.charter,
            "draft_forward": {
                "feet": self.draft_forward_feet,
                "inches": self.draft_forward_inches,
            },
            "draft_aft": {
                "feet": self.draft_aft_feet,
                "inches": self.draft_aft_inches,
            },
            "fuel_on_log": self.fuel_on_log,
            "correction": self.correction,
            "total_fuel_gallons": self.total_fuel_gallons,
            "service_oils": {
                "15p_lube": self.lube_oil_15p,
                "15s_gear": self.gear_oil_15s,
                "16p_lube": self.lube_oil_16p,
                "16s_hyd": self.hyd_oil_16s,
            },
            "slop_tanks": {
                "17p_oily_bilge": {
                    "feet": self.oily_bilge_17p_feet,
                    "inches": self.oily_bilge_17p_inches,
                    "gallons": self.oily_bilge_17p_gallons,
                },
                "17s_dirty_oil": {
                    "feet": self.dirty_oil_17s_feet,
                    "inches": self.dirty_oil_17s_inches,
                    "gallons": self.dirty_oil_17s_gallons,
                },
            },
            "fuel_tanks": [t.to_dict() for t in self.fuel_tanks],
            "engineer_name": self.engineer_name,
            "is_start": self.is_start,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat(),
        }
