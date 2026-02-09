"""API routes for Oil Record Book Tool."""

from datetime import datetime, timezone
from functools import wraps
from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from models import (
    WeeklySounding, ORBEntry, DailyFuelTicket, ServiceTankConfig,
    StatusEvent, EquipmentStatus, OilLevel, HitchRecord, FuelTankSounding,
    EQUIPMENT_LIST, db, UserRole
)
from app import limiter
from services.sounding_service import SoundingService
from services.orb_service import ORBService
from services.fuel_service import FuelService
from services.ocr_service import parse_end_of_hitch_image
from logging_config import get_logger, get_audit_logger
from security import (
    SecurityConfig, sanitize_input,
    WeeklySoundingForm, FuelTicketForm, ServiceTankConfigForm,
    StatusEventForm, EquipmentStatusForm, ImageUploadForm,
    HitchStartForm, HitchEndForm, DataResetForm
)

UTC = timezone.utc

api_bp = Blueprint("api", __name__)
logger = get_logger("orb_tool")


def _get_audit_logger():
    """Get audit logger from app context."""
    return getattr(current_app, "audit_logger", get_audit_logger())


def get_sounding_service() -> SoundingService:
    """Get or create sounding service instance."""
    if not hasattr(current_app, "_sounding_service"):
        current_app._sounding_service = SoundingService(
            current_app.config["SOUNDING_TABLES_PATH"]
        )
    return current_app._sounding_service


def get_orb_service() -> ORBService:
    """Get or create ORB service instance."""
    if not hasattr(current_app, "_orb_service"):
        current_app._orb_service = ORBService(get_sounding_service())
    return current_app._orb_service


def require_role(route_type: str):
    """Decorator to require specific role for API access."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.can_access_route(route_type):
                return jsonify({
                    "success": False,
                    "error": "Access denied. Insufficient privileges."
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def _flatten_sounding_data(data: dict) -> dict:
    """Flatten nested tank sounding format to flat form fields.

    Converts {"tank_17p": {"feet": 1, "inches": 6}} to
    {"tank_17p_feet": 1, "tank_17p_inches": 6}.
    """
    flat = dict(data)
    for key in ("tank_17p", "tank_17s"):
        if key in flat and isinstance(flat[key], dict):
            nested = flat.pop(key)
            flat[f"{key}_feet"] = nested.get("feet")
            flat[f"{key}_inches"] = nested.get("inches")
    return flat


def validate_form(form_class):
    """Decorator to validate form data and sanitize inputs."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.content_type and request.content_type.startswith('multipart/form-data'):
                form = form_class()
            else:
                from werkzeug.datastructures import MultiDict
                data = request.get_json() or {}
                if form_class is WeeklySoundingForm:
                    data = _flatten_sounding_data(data)
                # Use formdata= with MultiDict so WTForms sets raw_data
                # (needed for InputRequired validators on integer fields)
                md = MultiDict({k: str(v) for k, v in data.items() if v is not None and not isinstance(v, (dict, list))})
                form = form_class(formdata=md)

            if not form.validate():
                errors = {}
                for field_name, field_errors in form.errors.items():
                    errors[field_name] = field_errors
                return jsonify({"error": "Validation failed", "details": errors}), 400

            sanitized_data = {}
            for field_name, field_value in form.data.items():
                sanitized_data[field_name] = sanitize_input(field_value)

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
            if request.get_json(silent=True) is None:
                return jsonify({"error": "JSON body required"}), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# --- Health Check (for offline connectivity verification) ---


@api_bp.route("/health", methods=["GET", "HEAD"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def health_check():
    """Health check endpoint for connectivity verification.
    
    Used by offline.js to verify actual connectivity (navigator.onLine can be unreliable).
    Returns minimal response for efficiency on slow connections.
    """
    return jsonify({"status": "ok"}), 200


# --- Tank Info ---


@api_bp.route("/tanks", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("read")
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


@api_bp.route("/tanks/<tank_id>/lookup", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def lookup_sounding(tank_id: str):
    """Look up volume for a sounding."""
    feet = request.args.get("feet", type=int)
    inches = request.args.get("inches", type=int)

    if feet is None or inches is None:
        return jsonify({"error": "feet and inches required"}), 400

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


@api_bp.route("/soundings", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_soundings():
    """Get all weekly soundings, newest first."""
    soundings = WeeklySounding.query.order_by(
        WeeklySounding.recorded_at.desc()
    ).all()
    return jsonify([s.to_dict() for s in soundings])


@api_bp.route("/soundings/latest", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_latest_sounding():
    """Get the most recent weekly sounding."""
    sounding = WeeklySounding.query.order_by(
        WeeklySounding.recorded_at.desc()
    ).first()
    if sounding:
        return jsonify(sounding.to_dict())
    return jsonify(None)


@api_bp.route("/soundings", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("write")
@require_json()
@validate_form(WeeklySoundingForm)
def create_sounding():
    """
    Create a new weekly sounding and generate ORB entries.

    Expected JSON:
    {
        "recorded_at": "2025-12-12T10:00:00",
        "engineer_name": "John Smith",
        "engineer_title": "Chief Engineer",
        "tank_17p": {"feet": 1, "inches": 6},
        "tank_17s": {"feet": 2, "inches": 3}
    }

    Also accepts flat format from validated form:
    {
        "recorded_at": "2025-12-12T10:00:00",
        "engineer_name": "John Smith",
        "engineer_title": "Chief Engineer",
        "tank_17p_feet": 1, "tank_17p_inches": 6,
        "tank_17s_feet": 2, "tank_17s_inches": 3
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    # Support both nested format (original) and flat format (validated form)
    if "tank_17p" in data:
        tank_17p_feet = data["tank_17p"]["feet"]
        tank_17p_inches = data["tank_17p"]["inches"]
        tank_17s_feet = data["tank_17s"]["feet"]
        tank_17s_inches = data["tank_17s"]["inches"]
    else:
        tank_17p_feet = data.get("tank_17p_feet")
        tank_17p_inches = data.get("tank_17p_inches")
        tank_17s_feet = data.get("tank_17s_feet")
        tank_17s_inches = data.get("tank_17s_inches")

    try:
        # Parse date
        recorded_at = datetime.fromisoformat(data["recorded_at"])

        # Look up volumes
        service = get_sounding_service()
        result_17p = service.lookup(
            "17P", tank_17p_feet, tank_17p_inches
        )
        result_17s = service.lookup(
            "17S", tank_17s_feet, tank_17s_inches
        )

        # Create sounding record
        sounding = WeeklySounding(
            recorded_at=recorded_at,
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
        db.session.flush()  # Get ID before committing

        # Generate ORB entries
        orb_service = get_orb_service()
        code_c, code_i = orb_service.generate_weekly_entries(
            entry_date=recorded_at,
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

        # Audit log sounding creation
        audit = _get_audit_logger()
        audit.sounding_created(current_user.id, sounding.id, result_17p["m3"], result_17s["m3"])
        logger.info(f"Weekly sounding #{sounding.id} created by '{current_user.username}'")

        return jsonify({
            "sounding": sounding.to_dict(),
            "orb_entries": [entry_c.to_dict(), entry_i.to_dict()],
        }), 201

    except ValueError as e:
        db.session.rollback()
        logger.warning(f"Sounding creation failed: {e}")
        return jsonify({"error": str(e)}), 400
    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Sounding integrity error: {e}")
        return jsonify({"error": "Duplicate or constraint violation"}), 409
    except OperationalError as e:
        db.session.rollback()
        logger.exception("Database operational error during sounding creation")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error during sounding creation")
        return jsonify({"error": "Database error"}), 500


# --- ORB Entries ---


@api_bp.route("/orb-entries", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_orb_entries():
    """Get all ORB entries, newest first."""
    entries = ORBEntry.query.order_by(ORBEntry.entry_date.desc()).all()
    return jsonify([e.to_dict() for e in entries])


@api_bp.route("/orb-entries/<int:entry_id>", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_orb_entry(entry_id: int):
    """Get a specific ORB entry."""
    entry = ORBEntry.query.get_or_404(entry_id)
    return jsonify(entry.to_dict())


# --- Dashboard Stats ---


@api_bp.route("/dashboard/stats", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("read")
def get_dashboard_stats():
    """Get summary stats for dashboard."""
    latest = WeeklySounding.query.order_by(
        WeeklySounding.recorded_at.desc()
    ).first()

    total_soundings = WeeklySounding.query.count()
    total_orb_entries = ORBEntry.query.count()

    # Get previous sounding for delta calculation
    previous = None
    if latest:
        previous = WeeklySounding.query.filter(
            WeeklySounding.recorded_at < latest.recorded_at
        ).order_by(WeeklySounding.recorded_at.desc()).first()

    stats = {
        "total_soundings": total_soundings,
        "total_orb_entries": total_orb_entries,
        "latest_sounding": latest.to_dict() if latest else None,
        "previous_sounding": previous.to_dict() if previous else None,
    }

    # Calculate deltas if we have both
    if latest and previous:
        stats["deltas"] = {
            "tank_17p_gallons": latest.tank_17p_gallons - previous.tank_17p_gallons,
            "tank_17p_m3": round(latest.tank_17p_m3 - previous.tank_17p_m3, 2),
            "tank_17s_gallons": latest.tank_17s_gallons - previous.tank_17s_gallons,
            "tank_17s_m3": round(latest.tank_17s_m3 - previous.tank_17s_m3, 2),
        }

    return jsonify(stats)


# --- Service Tank Configuration ---


@api_bp.route("/service-tanks", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_service_tanks():
    """Get available service tank pairs."""
    return jsonify(FuelService.get_available_tank_pairs())


@api_bp.route("/service-tanks/active", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_active_service_tank():
    """Get currently active service tank pair."""
    active = ServiceTankConfig.query.filter_by(deactivated_at=None).first()
    if active:
        return jsonify(active.to_dict())
    return jsonify(None)


@api_bp.route("/service-tanks/active", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("write")
@require_json()
@validate_form(ServiceTankConfigForm)
def set_active_service_tank():
    """
    Set the active service tank pair.

    Expected JSON:
    {
        "tank_pair": "13",
        "notes": "Switching to tank 13 for hitch"
    }
    """
    data = request.get_json()
    if not data or "tank_pair" not in data:
        return jsonify({"error": "tank_pair required"}), 400

    tank_pair = data["tank_pair"]
    if not FuelService.validate_tank_pair(tank_pair):
        return jsonify({"error": f"Invalid tank pair: {tank_pair}"}), 400

    try:
        now = datetime.now(UTC)

        # Deactivate current active tank
        current = ServiceTankConfig.query.filter_by(deactivated_at=None).first()
        if current:
            current.deactivated_at = now

        # Create new active config
        new_config = ServiceTankConfig(
            tank_pair=tank_pair,
            activated_at=now,
            notes=data.get("notes"),
        )
        db.session.add(new_config)
        db.session.commit()

        return jsonify(new_config.to_dict()), 201

    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Service tank integrity error: {e}")
        return jsonify({"error": "Duplicate or constraint violation"}), 409
    except OperationalError as e:
        db.session.rollback()
        logger.exception("Database operational error during service tank update")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error during service tank update")
        return jsonify({"error": "Database error"}), 500


# --- Daily Fuel Tickets ---


@api_bp.route("/fuel-tickets", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_fuel_tickets():
    """Get all fuel tickets, newest first."""
    tickets = DailyFuelTicket.query.order_by(
        DailyFuelTicket.ticket_date.desc()
    ).all()
    return jsonify([t.to_dict() for t in tickets])


@api_bp.route("/fuel-tickets/latest", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_latest_fuel_ticket():
    """Get the most recent fuel ticket."""
    ticket = DailyFuelTicket.query.order_by(
        DailyFuelTicket.ticket_date.desc()
    ).first()
    if ticket:
        return jsonify(ticket.to_dict())
    return jsonify(None)


@api_bp.route("/fuel-tickets", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("write")
@require_json()
@validate_form(FuelTicketForm)
def create_fuel_ticket():
    """
    Create a new daily fuel ticket.

    Expected JSON:
    {
        "ticket_date": "2025-12-12T08:00:00",
        "meter_start": 12345.5,
        "meter_end": 12567.2,
        "service_tank_pair": "13",
        "engineer_name": "DP",
        "notes": "Normal operations"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ["ticket_date", "meter_start", "meter_end", "engineer_name"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    try:
        # Parse date
        ticket_date = datetime.fromisoformat(data["ticket_date"])

        # Get active service tank or use provided
        service_tank_pair = data.get("service_tank_pair")
        if not service_tank_pair:
            active = ServiceTankConfig.query.filter_by(deactivated_at=None).first()
            if active:
                service_tank_pair = active.tank_pair
            else:
                return jsonify({"error": "No active service tank configured. Set one first."}), 400

        if not FuelService.validate_tank_pair(service_tank_pair):
            return jsonify({"error": f"Invalid tank pair: {service_tank_pair}"}), 400

        # Calculate consumption
        meter_start = float(data["meter_start"])
        meter_end = float(data["meter_end"])
        consumption = FuelService.calculate_consumption(meter_start, meter_end)

        # Create ticket
        ticket = DailyFuelTicket(
            ticket_date=ticket_date,
            meter_start=meter_start,
            meter_end=meter_end,
            consumption_gallons=consumption,
            service_tank_pair=service_tank_pair,
            engineer_name=data["engineer_name"],
            notes=data.get("notes"),
        )
        db.session.add(ticket)
        db.session.commit()

        # Audit log fuel ticket creation
        audit = _get_audit_logger()
        audit.fuel_ticket_created(current_user.id, ticket.id, consumption)
        logger.info(f"Fuel ticket #{ticket.id} created: {consumption} gallons by '{current_user.username}'")

        return jsonify(ticket.to_dict()), 201

    except ValueError as e:
        db.session.rollback()
        logger.warning(f"Fuel ticket creation failed: {e}")
        return jsonify({"error": str(e)}), 400
    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Fuel ticket integrity error: {e}")
        return jsonify({"error": "Duplicate or constraint violation"}), 409
    except OperationalError as e:
        db.session.rollback()
        logger.exception("Database operational error during fuel ticket creation")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error during fuel ticket creation")
        return jsonify({"error": "Database error"}), 500


@api_bp.route("/fuel-tickets/stats", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_fuel_stats():
    """Get fuel consumption statistics."""
    tickets = DailyFuelTicket.query.order_by(
        DailyFuelTicket.ticket_date.desc()
    ).all()

    stats = FuelService.calculate_stats(tickets)
    weekly = FuelService.get_weekly_summary(tickets)

    # Get active tank
    active_tank = ServiceTankConfig.query.filter_by(deactivated_at=None).first()

    return jsonify({
        "all_time": stats,
        "weekly": weekly,
        "active_tank": active_tank.to_dict() if active_tank else None,
        "total_tickets": len(tickets),
        "latest_ticket": tickets[0].to_dict() if tickets else None,
    })


# --- Status Events (Sewage, Potable, etc.) ---


@api_bp.route("/status-events", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_status_events():
    """Get status events, optionally filtered by type."""
    event_type = request.args.get("type")
    query = StatusEvent.query.order_by(StatusEvent.event_date.desc())
    if event_type:
        query = query.filter_by(event_type=event_type)
    events = query.all()
    return jsonify([e.to_dict() for e in events])


@api_bp.route("/status-events/latest", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_latest_status_events():
    """Get the most recent event of each type."""
    event_types = ["sewage_pump", "potable_load"]
    result = {}
    for et in event_types:
        event = StatusEvent.query.filter_by(event_type=et).order_by(
            StatusEvent.event_date.desc()
        ).first()
        result[et] = event.to_dict() if event else None
    return jsonify(result)


@api_bp.route("/status-events", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("write")
@require_json()
@validate_form(StatusEventForm)
def create_status_event():
    """
    Create a new status event.

    Expected JSON:
    {
        "event_type": "sewage_pump",
        "event_date": "2025-12-15T10:00:00",
        "notes": "Pumped at dock",
        "engineer_name": "DP"
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ["event_type", "event_date"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    valid_types = ["sewage_pump", "potable_load"]
    if data["event_type"] not in valid_types:
        return jsonify({"error": f"Invalid event_type. Must be one of: {valid_types}"}), 400

    try:
        event_date = datetime.fromisoformat(data["event_date"])

        event = StatusEvent(
            event_type=data["event_type"],
            event_date=event_date,
            notes=data.get("notes"),
            engineer_name=data.get("engineer_name"),
        )
        db.session.add(event)
        db.session.commit()

        return jsonify(event.to_dict()), 201

    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Status event integrity error: {e}")
        return jsonify({"error": "Duplicate or constraint violation"}), 409
    except OperationalError as e:
        db.session.rollback()
        logger.exception("Database operational error during status event creation")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error during status event creation")
        return jsonify({"error": "Database error"}), 500


# --- Equipment Status ---


@api_bp.route("/equipment", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_equipment_list():
    """Get list of all equipment with current status."""
    result = []
    for equip in EQUIPMENT_LIST:
        # Get latest status for this equipment
        status = EquipmentStatus.query.filter_by(
            equipment_id=equip["id"]
        ).order_by(EquipmentStatus.updated_at.desc()).first()

        result.append({
            "id": equip["id"],
            "name": equip["name"],
            "status": status.status if status else "online",
            "note": status.note if status else None,
            "updated_at": status.updated_at.isoformat() if status else None,
            "updated_by": status.updated_by if status else None,
        })

    return jsonify(result)


@api_bp.route("/equipment/<equipment_id>", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_equipment_status(equipment_id: str):
    """Get current status for specific equipment."""
    equip = next((e for e in EQUIPMENT_LIST if e["id"] == equipment_id), None)
    if not equip:
        return jsonify({"error": f"Unknown equipment: {equipment_id}"}), 404

    status = EquipmentStatus.query.filter_by(
        equipment_id=equipment_id
    ).order_by(EquipmentStatus.updated_at.desc()).first()

    return jsonify({
        "id": equip["id"],
        "name": equip["name"],
        "status": status.status if status else "online",
        "note": status.note if status else None,
        "updated_at": status.updated_at.isoformat() if status else None,
        "updated_by": status.updated_by if status else None,
    })


@api_bp.route("/equipment/<equipment_id>", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("write")
@require_json()
@validate_form(EquipmentStatusForm)
def update_equipment_status(equipment_id: str):
    """
    Update equipment status.

    Expected JSON:
    {
        "status": "issue",
        "note": "High temp warning",
        "updated_by": "DP"
    }
    """
    equip = next((e for e in EQUIPMENT_LIST if e["id"] == equipment_id), None)
    if not equip:
        return jsonify({"error": f"Unknown equipment: {equipment_id}"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ["status", "updated_by"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    valid_statuses = ["online", "issue", "offline"]
    if data["status"] not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of: {valid_statuses}"}), 400

    # Require note for non-online status
    if data["status"] != "online" and not data.get("note"):
        return jsonify({"error": "Note required for issue/offline status"}), 400

    try:
        # Get previous status for audit logging
        prev_status = EquipmentStatus.query.filter_by(
            equipment_id=equipment_id
        ).order_by(EquipmentStatus.updated_at.desc()).first()
        old_status = prev_status.status if prev_status else None

        status = EquipmentStatus(
            equipment_id=equipment_id,
            status=data["status"],
            note=data.get("note"),
            updated_at=datetime.now(UTC),
            updated_by=data["updated_by"],
        )
        db.session.add(status)
        db.session.commit()

        # Audit log equipment status change
        audit = _get_audit_logger()
        audit.equipment_status_changed(current_user.id, equipment_id, old_status, data["status"])
        logger.info(f"Equipment '{equipment_id}' status changed: {old_status} -> {data['status']}")

        return jsonify(status.to_dict()), 201

    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Equipment status integrity error for '{equipment_id}': {e}")
        return jsonify({"error": "Duplicate or constraint violation"}), 409
    except OperationalError as e:
        db.session.rollback()
        logger.exception(f"Database operational error during equipment status update for '{equipment_id}'")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception(f"Database error during equipment status update for '{equipment_id}'")
        return jsonify({"error": "Database error"}), 500


@api_bp.route("/equipment/bulk", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("write")
def update_equipment_bulk():
    """
    Bulk update equipment statuses.

    Expected JSON:
    {
        "updates": [
            {"equipment_id": "PME", "status": "online", "note": null},
            {"equipment_id": "SSDG1", "status": "issue", "note": "Low oil pressure"}
        ],
        "updated_by": "DP"
    }
    """
    data = request.get_json()
    if not data or "updates" not in data or "updated_by" not in data:
        return jsonify({"error": "updates and updated_by required"}), 400

    try:
        now = datetime.now(UTC)
        results = []

        for update in data["updates"]:
            equip_id = update.get("equipment_id")
            equip = next((e for e in EQUIPMENT_LIST if e["id"] == equip_id), None)
            if not equip:
                continue

            status_val = update.get("status", "online")
            if status_val not in ["online", "issue", "offline"]:
                continue

            # Require note for non-online
            note = update.get("note")
            if status_val != "online" and not note:
                continue

            status = EquipmentStatus(
                equipment_id=equip_id,
                status=status_val,
                note=note,
                updated_at=now,
                updated_by=data["updated_by"],
            )
            db.session.add(status)
            results.append(status)

        db.session.commit()
        return jsonify({"updated": len(results)}), 201

    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Bulk equipment update integrity error: {e}")
        return jsonify({"error": "Duplicate or constraint violation"}), 409
    except OperationalError as e:
        db.session.rollback()
        logger.exception("Database operational error during bulk equipment update")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error during bulk equipment update")
        return jsonify({"error": "Database error"}), 500


# --- Full Dashboard Data ---


@api_bp.route("/dashboard/full", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("read")
def get_full_dashboard():
    """Get all dashboard data in one call."""
    # Slop tank soundings
    latest_sounding = WeeklySounding.query.order_by(
        WeeklySounding.recorded_at.desc()
    ).first()

    # Fuel stats
    tickets = DailyFuelTicket.query.order_by(
        DailyFuelTicket.ticket_date.desc()
    ).all()
    fuel_stats = FuelService.calculate_stats(tickets)
    fuel_weekly = FuelService.get_weekly_summary(tickets)
    active_tank = ServiceTankConfig.query.filter_by(deactivated_at=None).first()

    # Status events (sewage, potable)
    sewage = StatusEvent.query.filter_by(event_type="sewage_pump").order_by(
        StatusEvent.event_date.desc()
    ).first()
    potable = StatusEvent.query.filter_by(event_type="potable_load").order_by(
        StatusEvent.event_date.desc()
    ).first()

    # Equipment status
    equipment = []
    for equip in EQUIPMENT_LIST:
        status = EquipmentStatus.query.filter_by(
            equipment_id=equip["id"]
        ).order_by(EquipmentStatus.updated_at.desc()).first()
        equipment.append({
            "id": equip["id"],
            "name": equip["name"],
            "status": status.status if status else "online",
            "note": status.note if status else None,
        })

    # ORB entries count
    orb_count = ORBEntry.query.count()
    soundings_count = WeeklySounding.query.count()

    return jsonify({
        "slop_tanks": {
            "latest": latest_sounding.to_dict() if latest_sounding else None,
        },
        "fuel": {
            "stats": fuel_stats,
            "weekly": fuel_weekly,
            "active_tank": active_tank.to_dict() if active_tank else None,
            "latest_ticket": tickets[0].to_dict() if tickets else None,
        },
        "status_events": {
            "sewage": sewage.to_dict() if sewage else None,
            "potable": potable.to_dict() if potable else None,
        },
        "equipment": equipment,
        "counts": {
            "soundings": soundings_count,
            "orb_entries": orb_count,
            "fuel_tickets": len(tickets),
        },
    })


# --- OCR Parsing ---


@api_bp.route("/hitch/parse-image", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_UPLOAD_PER_MINUTE)
@require_role("admin")
@validate_form(ImageUploadForm)
def parse_hitch_image():
    """
    Parse an uploaded End of Hitch Sounding Form image.

    Accepts multipart/form-data with 'image' file.
    Returns extracted form data as JSON.
    """
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Validate file size
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > SecurityConfig.MAX_CONTENT_LENGTH:
        return jsonify({"error": "File too large. Maximum size is 16MB."}), 413

    # Read image data
    image_data = file.read()

    try:
        result = parse_end_of_hitch_image(image_data)
        return jsonify(result)
    except (OSError, IOError) as e:
        logger.exception("File I/O error during OCR parsing")
        return jsonify({"error": "Failed to process image file"}), 500
    except ValueError as e:
        logger.warning(f"OCR parsing value error: {e}")
        return jsonify({"error": "Invalid image data"}), 400
    except Exception as e:  # Unexpected non-DB error
        logger.exception("Unexpected error during OCR parsing")
        return jsonify({"error": "OCR processing failed"}), 500


# --- Hitch Management ---


@api_bp.route("/hitch/current", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_current_hitch():
    """Get the current active hitch."""
    hitch = HitchRecord.query.filter_by(end_date=None, is_start=True).order_by(
        HitchRecord.date.desc()
    ).first()
    if hitch:
        return jsonify(hitch.to_dict())
    return jsonify(None)


@api_bp.route("/hitch/<int:hitch_id>", methods=["GET"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
def get_hitch(hitch_id: int):
    """Get a specific hitch record with all details."""
    hitch = HitchRecord.query.get_or_404(hitch_id)
    return jsonify(hitch.to_dict())


@api_bp.route("/hitch/<int:hitch_id>", methods=["PUT"])
@limiter.limit(SecurityConfig.RATE_LIMIT_PER_MINUTE)
@require_role("admin")
def update_hitch(hitch_id: int):
    """Update an existing hitch record (for end-of-hitch editing)."""
    hitch = HitchRecord.query.get_or_404(hitch_id)
    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON body required"}), 400

    try:
        # Update simple fields
        for field in [
            "vessel", "location", "charter", "fuel_on_log", "correction",
            "total_fuel_gallons", "lube_oil_15p", "gear_oil_15s",
            "lube_oil_16p", "hyd_oil_16s", "engineer_name"
        ]:
            if field in data:
                setattr(hitch, field, data[field])

        # Update draft
        if "draft_forward" in data:
            hitch.draft_forward_feet = data["draft_forward"].get("feet")
            hitch.draft_forward_inches = data["draft_forward"].get("inches")
        if "draft_aft" in data:
            hitch.draft_aft_feet = data["draft_aft"].get("feet")
            hitch.draft_aft_inches = data["draft_aft"].get("inches")

        # Update slop tanks
        if "slop_tanks" in data:
            slop = data["slop_tanks"]
            if "17p_oily_bilge" in slop:
                ob = slop["17p_oily_bilge"]
                hitch.oily_bilge_17p_feet = ob.get("feet")
                hitch.oily_bilge_17p_inches = ob.get("inches")
                hitch.oily_bilge_17p_gallons = ob.get("gallons")
            if "17s_dirty_oil" in slop:
                do = slop["17s_dirty_oil"]
                hitch.dirty_oil_17s_feet = do.get("feet")
                hitch.dirty_oil_17s_inches = do.get("inches")
                hitch.dirty_oil_17s_gallons = do.get("gallons")

        # Update fuel tanks (replace all)
        if "fuel_tanks" in data:
            # Delete existing
            FuelTankSounding.query.filter_by(hitch_id=hitch.id).delete()

            # Add new
            for tank_data in data["fuel_tanks"]:
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

        db.session.commit()
        return jsonify(hitch.to_dict())

    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Hitch update integrity error: {e}")
        return jsonify({"error": "Duplicate or constraint violation"}), 409
    except OperationalError as e:
        db.session.rollback()
        logger.exception("Database operational error during hitch update")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error during hitch update")
        return jsonify({"error": "Database error"}), 500


@api_bp.route("/hitch/start", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_AUTH_PER_MINUTE)
@require_role("admin")
@require_json()
@validate_form(HitchStartForm)
def start_new_hitch():
    """
    Start a new hitch with complete End of Hitch Sounding Form data.

    Expected JSON matches the form structure - see parse_end_of_hitch_image output.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ["date", "total_fuel_gallons"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

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

        # Parse draft readings
        draft_fwd = data.get("draft_forward", {})
        draft_aft = data.get("draft_aft", {})

        # Parse slop tanks
        slop = data.get("slop_tanks", {})
        oily_bilge = slop.get("17p_oily_bilge", {})
        dirty_oil = slop.get("17s_dirty_oil", {})

        # Parse service oils
        service = data.get("service_oils", {})

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
        db.session.flush()  # Get ID before committing

        # Add fuel tank soundings
        for tank_data in data.get("fuel_tanks", []):
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

        # Initialize slop tank sounding only if user actually provided data
        # Check for non-null gallons values (more reliable than feet which could legitimately be 0)
        has_oily_bilge_data = oily_bilge.get("gallons") is not None and oily_bilge.get("gallons") > 0
        has_dirty_oil_data = dirty_oil.get("gallons") is not None and dirty_oil.get("gallons") > 0

        if has_oily_bilge_data or has_dirty_oil_data:
            sounding_service = get_sounding_service()
            oily_m3 = sounding_service.gallons_to_m3(oily_bilge.get("gallons") or 0)
            dirty_m3 = sounding_service.gallons_to_m3(dirty_oil.get("gallons") or 0)

            initial_sounding = WeeklySounding(
                recorded_at=hitch_date,
                engineer_name=data.get("engineer_name", "Baseline"),
                engineer_title="Previous Crew",
                tank_17p_feet=oily_bilge.get("feet") or 0,
                tank_17p_inches=oily_bilge.get("inches") or 0,
                tank_17p_gallons=int(oily_bilge.get("gallons") or 0),
                tank_17p_m3=oily_m3,
                tank_17s_feet=dirty_oil.get("feet") or 0,
                tank_17s_inches=dirty_oil.get("inches") or 0,
                tank_17s_gallons=int(dirty_oil.get("gallons") or 0),
                tank_17s_m3=dirty_m3,
            )
            db.session.add(initial_sounding)

        # Initialize oil levels
        if any([
            service.get("15p_lube"),
            service.get("15s_gear"),
            service.get("16p_lube"),
            service.get("16s_hyd"),
        ]):
            oil_level = OilLevel(
                recorded_at=hitch_date,
                tank_15p_lube=service.get("15p_lube"),
                tank_15s_gear=service.get("15s_gear"),
                tank_16p_lube=service.get("16p_lube"),
                tank_16s_hyd=service.get("16s_hyd"),
                source="hitch_baseline",
                engineer_name=data.get("engineer_name"),
            )
            db.session.add(oil_level)

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

        # Audit log hitch start
        data_cleared = data.get("clear_data", True)
        audit = _get_audit_logger()
        audit.hitch_started(current_user.id, hitch.id, data_cleared)
        logger.info(f"New hitch #{hitch.id} started by '{current_user.username}', data_cleared={data_cleared}")

        return jsonify({
            "message": "New hitch started successfully",
            "hitch": hitch.to_dict(),
            "data_cleared": data_cleared,
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Hitch start integrity error: {e}")
        return jsonify({"error": "Duplicate or constraint violation"}), 409
    except OperationalError as e:
        db.session.rollback()
        logger.exception("Database operational error during hitch start")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error during hitch start")
        return jsonify({"error": "Database error"}), 500


@api_bp.route("/hitch/end", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_AUTH_PER_MINUTE)
@require_role("admin")
@require_json()
@validate_form(HitchEndForm)
def create_end_of_hitch():
    """
    Create end-of-hitch record (for printing/handover).
    Creates a record with is_start=False for the handover documentation.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ["date", "total_fuel_gallons"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    try:
        # Parse date
        date_str = data["date"]
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts[2]) == 2:
                parts[2] = "20" + parts[2]
            hitch_date = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
        else:
            hitch_date = datetime.fromisoformat(
                date_str.replace("T", " ").split(".")[0]
            )

        # Parse fields
        draft_fwd = data.get("draft_forward", {})
        draft_aft = data.get("draft_aft", {})
        slop = data.get("slop_tanks", {})
        oily_bilge = slop.get("17p_oily_bilge", {})
        dirty_oil = slop.get("17s_dirty_oil", {})
        service = data.get("service_oils", {})

        # Create end-of-hitch record
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
            is_start=False,  # This is an end-of-hitch record
        )
        db.session.add(hitch)
        db.session.flush()

        # Add fuel tank soundings
        for tank_data in data.get("fuel_tanks", []):
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

        db.session.commit()

        # Audit log hitch end
        audit = _get_audit_logger()
        audit.hitch_ended(current_user.id, hitch.id)
        logger.info(f"End of hitch #{hitch.id} record created by '{current_user.username}'")

        return jsonify({
            "message": "End of hitch record created",
            "hitch": hitch.to_dict(),
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        logger.warning(f"Hitch end integrity error: {e}")
        return jsonify({"error": "Duplicate or constraint violation"}), 409
    except OperationalError as e:
        db.session.rollback()
        logger.exception("Database operational error during hitch end")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error during hitch end")
        return jsonify({"error": "Database error"}), 500


@api_bp.route("/hitch/reset", methods=["POST"])
@limiter.limit(SecurityConfig.RATE_LIMIT_AUTH_PER_MINUTE)
@require_role("admin")
@require_json()
@validate_form(DataResetForm)
def reset_all_data():
    """
    Emergency reset - clears ALL data without creating new hitch.
    Use with caution.
    """
    data = request.get_json() or {}

    if not data.get("confirm", False):
        return jsonify({
            "error": "Must confirm reset",
            "message": "Send {\"confirm\": true} to reset all data"
        }), 400

    try:
        # Track tables being cleared for audit
        tables_cleared = [
            "FuelTankSounding", "DailyFuelTicket", "WeeklySounding", "ORBEntry",
            "StatusEvent", "EquipmentStatus", "OilLevel", "ServiceTankConfig", "HitchRecord"
        ]

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

        # Audit log data reset (CRITICAL operation)
        audit = _get_audit_logger()
        audit.data_reset(current_user.id, tables_cleared)
        logger.warning(f"DATA RESET performed by '{current_user.username}' - all operational data cleared")

        return jsonify({"message": "All data cleared successfully"}), 200

    except OperationalError as e:
        db.session.rollback()
        logger.exception("Database operational error during data reset")
        return jsonify({"error": "Database temporarily unavailable"}), 503
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.exception("Database error during data reset")
        return jsonify({"error": "Database error"}), 500
