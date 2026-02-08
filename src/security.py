"""Security configuration and validation forms."""

from datetime import datetime
from typing import Dict, List, Optional, Union

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, FloatField, IntegerField, DateTimeField,
    SelectField, TextAreaField, BooleanField, ValidationError
)
from wtforms.validators import (
    DataRequired, InputRequired, Length, NumberRange,
    Optional as OptionalValidator, Regexp, Email
)
from markupsafe import Markup, escape


class SecurityConfig:
    """Security configuration constants."""

    # Rate limiting
    RATE_LIMIT_PER_MINUTE = "60/minute"
    RATE_LIMIT_PER_HOUR = "1000/hour"
    RATE_LIMIT_AUTH_PER_MINUTE = "5/minute"
    RATE_LIMIT_UPLOAD_PER_MINUTE = "10/minute"

    # Request limits
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    MAX_FORM_MEMORY_SIZE = 2 * 1024 * 1024  # 2MB

    # CORS settings
    CORS_ORIGINS = ["http://localhost:5001", "https://localhost:5001"]
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS = ["Content-Type", "Authorization", "X-CSRFToken"]

    # Security headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "SAMEORIGIN",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    }

    # CSP (Content Security Policy)
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )


def sanitize_input(value: Union[str, None]) -> Union[str, None]:
    """Sanitize user input to prevent XSS attacks."""
    if value is None:
        return None
    if isinstance(value, str):
        return escape(value)
    return value


def validate_tank_id(form, field):
    """Custom validator for tank IDs."""
    valid_tanks = ["17P", "17S", "15P", "15S", "16P", "16S"]
    if field.data and field.data.upper() not in valid_tanks:
        raise ValidationError(f"Invalid tank ID. Must be one of: {', '.join(valid_tanks)}")


def validate_tank_pair(form, field):
    """Custom validator for tank pairs."""
    valid_pairs = ["13", "14", "15", "16"]
    if field.data and str(field.data) not in valid_pairs:
        raise ValidationError(f"Invalid tank pair. Must be one of: {', '.join(valid_pairs)}")


def validate_equipment_id(form, field):
    """Custom validator for equipment IDs."""
    from models import EQUIPMENT_LIST
    valid_ids = [eq["id"] for eq in EQUIPMENT_LIST]
    if field.data and field.data not in valid_ids:
        raise ValidationError(f"Invalid equipment ID. Must be one of: {', '.join(valid_ids)}")


class TankLookupForm(FlaskForm):
    """Form for tank sounding lookup."""
    feet = IntegerField(
        "Feet",
        validators=[InputRequired(), NumberRange(min=0, max=50)],
        description="Tank sounding in feet"
    )
    inches = IntegerField(
        "Inches",
        validators=[InputRequired(), NumberRange(min=0, max=11)],
        description="Tank sounding in inches"
    )


class WeeklySoundingForm(FlaskForm):
    """Form for weekly sounding submission."""
    recorded_at = DateTimeField(
        "Recorded At",
        validators=[DataRequired()],
        format="%Y-%m-%dT%H:%M:%S",
        description="When the sounding was recorded"
    )
    engineer_name = StringField(
        "Engineer Name",
        validators=[
            DataRequired(),
            Length(min=2, max=100),
            Regexp(r'^[a-zA-Z\s.-]+$', message="Name can only contain letters, spaces, periods, and hyphens")
        ],
        description="Name of the engineer recording the sounding"
    )
    engineer_title = StringField(
        "Engineer Title",
        validators=[
            DataRequired(),
            Length(min=2, max=100),
            Regexp(r'^[a-zA-Z0-9\s.-]+$', message="Title can only contain letters, numbers, spaces, periods, and hyphens")
        ],
        description="Title of the engineer"
    )
    tank_17p_feet = IntegerField(
        "Tank 17P Feet",
        validators=[InputRequired(), NumberRange(min=0, max=50)],
        description="Tank 17P sounding in feet"
    )
    tank_17p_inches = IntegerField(
        "Tank 17P Inches",
        validators=[InputRequired(), NumberRange(min=0, max=11)],
        description="Tank 17P sounding in inches"
    )
    tank_17s_feet = IntegerField(
        "Tank 17S Feet",
        validators=[InputRequired(), NumberRange(min=0, max=50)],
        description="Tank 17S sounding in feet"
    )
    tank_17s_inches = IntegerField(
        "Tank 17S Inches",
        validators=[InputRequired(), NumberRange(min=0, max=11)],
        description="Tank 17S sounding in inches"
    )


class FuelTicketForm(FlaskForm):
    """Form for daily fuel ticket submission."""
    ticket_date = DateTimeField(
        "Ticket Date",
        validators=[DataRequired()],
        format="%Y-%m-%dT%H:%M:%S",
        description="Date of the fuel ticket"
    )
    meter_start = FloatField(
        "Meter Start",
        validators=[DataRequired(), NumberRange(min=0, max=999999.9)],
        description="Starting meter reading"
    )
    meter_end = FloatField(
        "Meter End",
        validators=[DataRequired(), NumberRange(min=0, max=999999.9)],
        description="Ending meter reading"
    )
    service_tank_pair = SelectField(
        "Service Tank Pair",
        choices=[("13", "Tank 13"), ("14", "Tank 14"), ("15", "Tank 15"), ("16", "Tank 16")],
        validators=[OptionalValidator()],
        description="Service tank pair being used"
    )
    engineer_name = StringField(
        "Engineer Name",
        validators=[
            DataRequired(),
            Length(min=2, max=100),
            Regexp(r'^[a-zA-Z\s.-]+$', message="Name can only contain letters, spaces, periods, and hyphens")
        ],
        description="Name of the engineer"
    )
    notes = TextAreaField(
        "Notes",
        validators=[OptionalValidator(), Length(max=500)],
        description="Optional notes"
    )

    def validate_meter_end(form, field):
        """Ensure meter end is greater than meter start."""
        if form.meter_start.data and field.data:
            if field.data <= form.meter_start.data:
                raise ValidationError("Meter end must be greater than meter start")


class ServiceTankConfigForm(FlaskForm):
    """Form for service tank configuration."""
    tank_pair = SelectField(
        "Tank Pair",
        choices=[("13", "Tank 13"), ("14", "Tank 14"), ("15", "Tank 15"), ("16", "Tank 16")],
        validators=[DataRequired()],
        description="Tank pair to activate"
    )
    notes = TextAreaField(
        "Notes",
        validators=[OptionalValidator(), Length(max=500)],
        description="Optional notes about the tank switch"
    )


class StatusEventForm(FlaskForm):
    """Form for status event submission."""
    event_type = SelectField(
        "Event Type",
        choices=[("sewage_pump", "Sewage Pump"), ("potable_load", "Potable Load")],
        validators=[DataRequired()],
        description="Type of status event"
    )
    event_date = DateTimeField(
        "Event Date",
        validators=[DataRequired()],
        format="%Y-%m-%dT%H:%M:%S",
        description="When the event occurred"
    )
    engineer_name = StringField(
        "Engineer Name",
        validators=[
            OptionalValidator(),
            Length(min=2, max=100),
            Regexp(r'^[a-zA-Z\s.-]+$', message="Name can only contain letters, spaces, periods, and hyphens")
        ],
        description="Name of the engineer"
    )
    notes = TextAreaField(
        "Notes",
        validators=[OptionalValidator(), Length(max=500)],
        description="Optional notes"
    )


class EquipmentStatusForm(FlaskForm):
    """Form for equipment status update."""
    status = SelectField(
        "Status",
        choices=[("online", "Online"), ("issue", "Issue"), ("offline", "Offline")],
        validators=[DataRequired()],
        description="Equipment status"
    )
    note = TextAreaField(
        "Note",
        validators=[OptionalValidator(), Length(max=500)],
        description="Note about the status (required for issue/offline)"
    )
    updated_by = StringField(
        "Updated By",
        validators=[
            DataRequired(),
            Length(min=2, max=100),
            Regexp(r'^[a-zA-Z\s.-]+$', message="Name can only contain letters, spaces, periods, and hyphens")
        ],
        description="Name of person updating status"
    )

    def validate_note(form, field):
        """Require note for non-online status."""
        if form.status.data in ["issue", "offline"] and not field.data:
            raise ValidationError("Note is required for issue or offline status")


class EquipmentBulkUpdateForm(FlaskForm):
    """Form for bulk equipment status updates."""
    updated_by = StringField(
        "Updated By",
        validators=[
            DataRequired(),
            Length(min=2, max=100),
            Regexp(r'^[a-zA-Z\s.-]+$', message="Name can only contain letters, spaces, periods, and hyphens")
        ],
        description="Name of person updating statuses"
    )


class ImageUploadForm(FlaskForm):
    """Form for image upload (OCR)."""
    image = FileField(
        "Image",
        validators=[
            FileRequired(),
            FileAllowed(["jpg", "jpeg", "png", "pdf"], "Only JPG, PNG, or PDF files allowed")
        ],
        description="End of hitch form image (JPG, PNG, or PDF)"
    )


class HitchStartForm(FlaskForm):
    """Form for starting a new hitch."""
    date = StringField(
        "Date",
        validators=[DataRequired()],
        description="Hitch date (MM/DD/YY or ISO format)"
    )
    vessel = StringField(
        "Vessel",
        validators=[
            OptionalValidator(),
            Length(max=100),
            Regexp(r'^[a-zA-Z0-9\s.-]+$', message="Vessel name contains invalid characters")
        ],
        description="Vessel name"
    )
    location = StringField(
        "Location",
        validators=[
            OptionalValidator(),
            Length(max=200),
            Regexp(r'^[a-zA-Z0-9\s.,/-]+$', message="Location contains invalid characters")
        ],
        description="Current location"
    )
    charter = StringField(
        "Charter",
        validators=[
            OptionalValidator(),
            Length(max=100),
            Regexp(r'^[a-zA-Z0-9\s.-]+$', message="Charter contains invalid characters")
        ],
        description="Charter company"
    )
    total_fuel_gallons = FloatField(
        "Total Fuel (Gallons)",
        validators=[DataRequired(), NumberRange(min=0, max=500000)],
        description="Total fuel in gallons"
    )
    fuel_on_log = FloatField(
        "Fuel on Log",
        validators=[OptionalValidator(), NumberRange(min=0, max=500000)],
        description="Fuel shown on log"
    )
    correction = FloatField(
        "Correction",
        validators=[OptionalValidator(), NumberRange(min=-10000, max=10000)],
        description="Fuel correction amount"
    )
    engineer_name = StringField(
        "Engineer Name",
        validators=[
            OptionalValidator(),
            Length(min=2, max=100),
            Regexp(r'^[a-zA-Z\s.-]+$', message="Name can only contain letters, spaces, periods, and hyphens")
        ],
        description="Engineer name"
    )
    clear_data = BooleanField(
        "Clear Existing Data",
        default=True,
        description="Clear existing operational data when starting new hitch"
    )


class HitchEndForm(FlaskForm):
    """Form for ending a hitch."""
    date = StringField(
        "Date",
        validators=[DataRequired()],
        description="End of hitch date"
    )
    vessel = StringField(
        "Vessel",
        validators=[
            OptionalValidator(),
            Length(max=100),
            Regexp(r'^[a-zA-Z0-9\s.-]+$', message="Vessel name contains invalid characters")
        ],
        description="Vessel name"
    )
    location = StringField(
        "Location",
        validators=[
            OptionalValidator(),
            Length(max=200),
            Regexp(r'^[a-zA-Z0-9\s.,/-]+$', message="Location contains invalid characters")
        ],
        description="Current location"
    )
    total_fuel_gallons = FloatField(
        "Total Fuel (Gallons)",
        validators=[DataRequired(), NumberRange(min=0, max=500000)],
        description="Total fuel in gallons"
    )
    engineer_name = StringField(
        "Engineer Name",
        validators=[
            OptionalValidator(),
            Length(min=2, max=100),
            Regexp(r'^[a-zA-Z\s.-]+$', message="Name can only contain letters, spaces, periods, and hyphens")
        ],
        description="Engineer name"
    )


class DataResetForm(FlaskForm):
    """Form for data reset confirmation."""
    confirm = BooleanField(
        "Confirm Reset",
        validators=[DataRequired()],
        description="I understand this will delete all data"
    )

    def validate_confirm(form, field):
        """Ensure user confirms the reset."""
        if not field.data:
            raise ValidationError("You must confirm the reset")