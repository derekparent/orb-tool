"""Secured API routes with input validation and rate limiting."""

from datetime import datetime, timezone
from functools import wraps
from typing import Dict, Any, Union

from flask import Blueprint, current_app, jsonify, request
from flask_wtf.csrf import validate_csrf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from wtforms import ValidationError

from models import (
    WeeklySounding, ORBEntry, DailyFuelTicket, ServiceTankConfig,
    StatusEvent, EquipmentStatus, OilLevel, HitchRecord, FuelTankSounding,
    EQUIPMENT_LIST, db
)
from services.sounding_service import SoundingService
from services.orb_service import ORBService
from services.fuel_service import FuelService
from services.ocr_service import parse_end_of_hitch_image
from security import (
    SecurityConfig, sanitize_input,
    TankLookupForm, WeeklySoundingForm, FuelTicketForm,
    ServiceTankConfigForm, StatusEventForm, EquipmentStatusForm,
    EquipmentBulkUpdateForm, ImageUploadForm, HitchStartForm,
    HitchEndForm, DataResetForm
)

UTC = timezone.utc

secure_api_bp = Blueprint("secure_api", __name__)

# Rate limiter - will be initialized when blueprint is registered
# Uses deferred init pattern for Flask factory apps
limiter = Limiter(key_func=get_remote_address)


def init_secure_api(app):
    """Initialize secure API with app context (call after registering blueprint)."""
    limiter.init_app(app)


def validate_form(form_class):
    """Decorator to validate form data and sanitize inputs."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Handle multipart form data (file uploads) differently
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                form = form_class()
            else:
                # Handle JSON data
                form = form_class(data=request.get_json() or {})

            if not form.validate():
                errors = {}
                for field_name, field_errors in form.errors.items():
                    errors[field_name] = field_errors
                return jsonify({"error": "Validation failed", "details": errors}), 400

            # Sanitize string inputs
            sanitized_data = {}
            for field_name, field_value in form.data.items():
                sanitized_data[field_name] = sanitize_input(field_value)

            # Add sanitized data to request context
            request.validated_data = sanitized_data
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_json():
    """Decorator to ensure request has JSON body."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "Content-Type must be application/json"}), 400
            if not request.get_json():
                return jsonify({"error": "JSON body required"}), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Import existing route functions from api.py
from routes.api import (
    get_sounding_service, get_orb_service
)


# --- Tank Info (READ-ONLY, no validation needed) ---

@secure_api_bp.route("/tanks", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_tanks():
    """Get available tanks and their metadata."""
    service = get_sounding_service()
    tanks = {}
    for tank_id in service.tank_ids:
        info = service.get_tank_info(tank_id)
        tanks[tank_id] = {
            "name": info["name"],
            "orb_code": info["orb_code"],
            "capacity_gallons": info["capacity_gallons"],
            "capacity_m3": info["capacity_m3"],
        }
    return jsonify(tanks)


@secure_api_bp.route("/tanks/<tank_id>/lookup", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def lookup_sounding(tank_id: str):
    """Look up volume for a sounding."""
    # For GET requests, validate query parameters directly
    feet = request.args.get("feet", type=int)
    inches = request.args.get("inches", type=int)

    if feet is None or inches is None:
        return jsonify({"error": "feet and inches required"}), 400

    # Validate parameter ranges
    if feet < 0 or feet > 50:
        return jsonify({"error": "feet must be between 0 and 50"}), 400
    if inches < 0 or inches > 11:
        return jsonify({"error": "inches must be between 0 and 11"}), 400

    try:
        service = get_sounding_service()
        result = service.lookup(tank_id, feet, inches)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# --- Weekly Soundings ---

@secure_api_bp.route("/soundings", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_soundings():
    """Get all weekly soundings, newest first."""
    soundings = WeeklySounding.query.order_by(
        WeeklySounding.recorded_at.desc()
    ).all()
    return jsonify([s.to_dict() for s in soundings])


@secure_api_bp.route("/soundings/latest", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_latest_sounding():
    """Get the most recent weekly sounding."""
    sounding = WeeklySounding.query.order_by(
        WeeklySounding.recorded_at.desc()
    ).first()
    if sounding:
        return jsonify(sounding.to_dict())
    return jsonify(None)


@secure_api_bp.route("/soundings", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_json()
@validate_form(WeeklySoundingForm)
def create_sounding():
    """Create a new weekly sounding and generate ORB entries."""
    data = request.validated_data

    try:
        # Look up volumes
        service = get_sounding_service()
        result_17p = service.lookup("17P", data["tank_17p_feet"], data["tank_17p_inches"])
        result_17s = service.lookup("17S", data["tank_17s_feet"], data["tank_17s_inches"])

        # Create sounding record
        sounding = WeeklySounding(
            recorded_at=data["recorded_at"],
            engineer_name=data["engineer_name"],
            engineer_title=data["engineer_title"],
            tank_17p_feet=result_17p["feet"],
            tank_17p_inches=result_17p["inches"],
            tank_17p_gallons=result_17p["gallons"],
            tank_17p_m3=result_17p["m3"],
            tank_17s_feet=result_17s["feet"],
            tank_17s_inches=result_17s["inches"],
            tank_17s_gallons=result_17s["gallons"],
            tank_17s_m3=result_17s["m3"],
        )
        db.session.add(sounding)
        db.session.flush()

        # Generate ORB entries
        orb_service = get_orb_service()
        code_c, code_i = orb_service.generate_weekly_entries(
            entry_date=data["recorded_at"],
            tank_17p_m3=result_17p["m3"],
            tank_17s_m3=result_17s["m3"],
            engineer_name=data["engineer_name"],
            engineer_title=data["engineer_title"],
        )

        entry_c = ORBEntry(
            entry_date=code_c["entry_date"],
            code=code_c["code"],
            entry_text=code_c["entry_text"],
            sounding_id=sounding.id,
        )
        entry_i = ORBEntry(
            entry_date=code_i["entry_date"],
            code=code_i["code"],
            entry_text=code_i["entry_text"],
            sounding_id=sounding.id,
        )
        db.session.add_all([entry_c, entry_i])
        db.session.commit()

        return jsonify({
            "sounding": sounding.to_dict(),
            "orb_entries": [entry_c.to_dict(), entry_i.to_dict()],
        }), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# --- Fuel Tickets ---

@secure_api_bp.route("/fuel-tickets", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_fuel_tickets():
    """Get all fuel tickets, newest first."""
    tickets = DailyFuelTicket.query.order_by(
        DailyFuelTicket.ticket_date.desc()
    ).all()
    return jsonify([t.to_dict() for t in tickets])


@secure_api_bp.route("/fuel-tickets", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_json()
@validate_form(FuelTicketForm)
def create_fuel_ticket():
    """Create a new daily fuel ticket."""
    data = request.validated_data

    try:
        # Get active service tank or use provided
        service_tank_pair = data.get("service_tank_pair")
        if not service_tank_pair:
            active = ServiceTankConfig.query.filter_by(deactivated_at=None).first()
            if active:
                service_tank_pair = active.tank_pair
            else:
                return jsonify({"error": "No active service tank configured. Set one first."}), 400

        # Calculate consumption
        consumption = FuelService.calculate_consumption(data["meter_start"], data["meter_end"])

        # Create ticket
        ticket = DailyFuelTicket(
            ticket_date=data["ticket_date"],
            meter_start=data["meter_start"],
            meter_end=data["meter_end"],
            consumption_gallons=consumption,
            service_tank_pair=service_tank_pair,
            engineer_name=data["engineer_name"],
            notes=data.get("notes"),
        )
        db.session.add(ticket)
        db.session.commit()

        return jsonify(ticket.to_dict()), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# --- Service Tank Configuration ---

@secure_api_bp.route("/service-tanks/active", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_json()
@validate_form(ServiceTankConfigForm)
def set_active_service_tank():
    """Set the active service tank pair."""
    data = request.validated_data

    try:
        now = datetime.now(UTC)

        # Deactivate current active tank
        current = ServiceTankConfig.query.filter_by(deactivated_at=None).first()
        if current:
            current.deactivated_at = now

        # Create new active config
        new_config = ServiceTankConfig(
            tank_pair=data["tank_pair"],
            activated_at=now,
            notes=data.get("notes"),
        )
        db.session.add(new_config)
        db.session.commit()

        return jsonify(new_config.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# --- OCR Upload (Special rate limiting) ---

@secure_api_bp.route("/hitch/parse-image", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_UPLOAD_PER_MINUTE)
@validate_form(ImageUploadForm)
def parse_hitch_image():
    """Parse an uploaded End of Hitch Sounding Form image."""
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Validate file size
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning

    if file_size > SecurityConfig.MAX_CONTENT_LENGTH:
        return jsonify({"error": "File too large. Maximum size is 16MB."}), 413

    # Read image data
    image_data = file.read()

    try:
        result = parse_end_of_hitch_image(image_data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"OCR failed: {str(e)}"}), 500


# --- Status Events ---

@secure_api_bp.route("/status-events", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_json()
@validate_form(StatusEventForm)
def create_status_event():
    """Create a new status event."""
    data = request.validated_data

    try:
        event = StatusEvent(
            event_type=data["event_type"],
            event_date=data["event_date"],
            notes=data.get("notes"),
            engineer_name=data.get("engineer_name"),
        )
        db.session.add(event)
        db.session.commit()

        return jsonify(event.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# --- Equipment Status ---

@secure_api_bp.route("/equipment/<equipment_id>", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_json()
@validate_form(EquipmentStatusForm)
def update_equipment_status(equipment_id: str):
    """Update equipment status."""
    # Validate equipment ID
    equip = next((e for e in EQUIPMENT_LIST if e["id"] == equipment_id), None)
    if not equip:
        return jsonify({"error": f"Unknown equipment: {equipment_id}"}), 404

    data = request.validated_data

    try:
        status = EquipmentStatus(
            equipment_id=equipment_id,
            status=data["status"],
            note=data.get("note"),
            updated_at=datetime.now(UTC),
            updated_by=data["updated_by"],
        )
        db.session.add(status)
        db.session.commit()

        return jsonify(status.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# --- Hitch Management ---

@secure_api_bp.route("/hitch/start", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_AUTH_PER_MINUTE)  # More restrictive for critical operations
@require_json()
@validate_form(HitchStartForm)
def start_new_hitch():
    """Start a new hitch with complete End of Hitch Sounding Form data."""
    data = request.validated_data
    json_data = request.get_json()  # Get original JSON for complex nested data

    try:
        # Parse date (handle multiple formats)
        date_str = data["date"]
        if "/" in date_str:
            # Handle MM/DD/YY format
            parts = date_str.split("/")
            if len(parts[2]) == 2:
                parts[2] = "20" + parts[2]
            hitch_date = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
        else:
            hitch_date = datetime.fromisoformat(
                date_str.replace("T", " ").split(".")[0]
            )

        # Clear existing data if requested
        if data.get("clear_data", True):
            # End any active hitch
            active_hitch = HitchRecord.query.filter_by(end_date=None, is_start=True).first()
            if active_hitch:
                active_hitch.end_date = datetime.now(UTC)

            # Clear operational tables
            FuelTankSounding.query.delete()
            DailyFuelTicket.query.delete()
            WeeklySounding.query.delete()
            ORBEntry.query.delete()
            StatusEvent.query.delete()
            EquipmentStatus.query.delete()
            OilLevel.query.delete()
            ServiceTankConfig.query.delete()

        # Parse nested data from original JSON (sanitized versions don't preserve structure)
        draft_fwd = json_data.get("draft_forward", {})
        draft_aft = json_data.get("draft_aft", {})
        slop = json_data.get("slop_tanks", {})
        oily_bilge = slop.get("17p_oily_bilge", {})
        dirty_oil = slop.get("17s_dirty_oil", {})
        service = json_data.get("service_oils", {})

        # Create hitch record
        hitch = HitchRecord(
            vessel=data.get("vessel", "USNS Arrowhead"),
            date=hitch_date,
            location=data.get("location"),
            charter=data.get("charter", "MSC"),
            draft_forward_feet=draft_fwd.get("feet"),
            draft_forward_inches=draft_fwd.get("inches"),
            draft_aft_feet=draft_aft.get("feet"),
            draft_aft_inches=draft_aft.get("inches"),
            fuel_on_log=data.get("fuel_on_log"),
            correction=data.get("correction"),
            total_fuel_gallons=data["total_fuel_gallons"],
            lube_oil_15p=service.get("15p_lube"),
            gear_oil_15s=service.get("15s_gear"),
            lube_oil_16p=service.get("16p_lube"),
            hyd_oil_16s=service.get("16s_hyd"),
            oily_bilge_17p_feet=oily_bilge.get("feet"),
            oily_bilge_17p_inches=oily_bilge.get("inches"),
            oily_bilge_17p_gallons=oily_bilge.get("gallons"),
            dirty_oil_17s_feet=dirty_oil.get("feet"),
            dirty_oil_17s_inches=dirty_oil.get("inches"),
            dirty_oil_17s_gallons=dirty_oil.get("gallons"),
            engineer_name=data.get("engineer_name"),
            is_start=True,
        )
        db.session.add(hitch)
        db.session.flush()

        # Add fuel tank soundings
        for tank_data in json_data.get("fuel_tanks", []):
            tank = FuelTankSounding(
                hitch_id=hitch.id,
                tank_number=tank_data["tank_number"],
                side=tank_data["side"],
                is_day_tank=tank_data.get("is_day_tank", False),
                sounding_feet=tank_data.get("sounding_feet"),
                sounding_inches=tank_data.get("sounding_inches"),
                water_present=tank_data.get("water_present", "None"),
                gallons=tank_data["gallons"],
            )
            db.session.add(tank)

        # Initialize equipment as Online
        for equip in EQUIPMENT_LIST:
            equipment_status = EquipmentStatus(
                equipment_id=equip["id"],
                status="online",
                updated_at=hitch_date,
                updated_by=data.get("engineer_name", "System"),
            )
            db.session.add(equipment_status)

        db.session.commit()

        return jsonify({
            "message": "New hitch started successfully",
            "hitch": hitch.to_dict(),
            "data_cleared": data.get("clear_data", True),
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# --- Data Reset (High security) ---

@secure_api_bp.route("/hitch/reset", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_AUTH_PER_MINUTE)
@require_json()
@validate_form(DataResetForm)
def reset_all_data():
    """Emergency reset - clears ALL data without creating new hitch."""
    try:
        # Clear all operational tables
        FuelTankSounding.query.delete()
        DailyFuelTicket.query.delete()
        WeeklySounding.query.delete()
        ORBEntry.query.delete()
        StatusEvent.query.delete()
        EquipmentStatus.query.delete()
        OilLevel.query.delete()
        ServiceTankConfig.query.delete()
        HitchRecord.query.delete()

        db.session.commit()

        return jsonify({"message": "All data cleared successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500
