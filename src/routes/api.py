"""API routes for Oil Record Book Tool."""

from datetime import datetime
from flask import Blueprint, current_app, jsonify, request

from models import WeeklySounding, ORBEntry, DailyFuelTicket, ServiceTankConfig, db
from services.sounding_service import SoundingService
from services.orb_service import ORBService
from services.fuel_service import FuelService

api_bp = Blueprint("api", __name__)


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


# --- Tank Info ---


@api_bp.route("/tanks", methods=["GET"])
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
def lookup_sounding(tank_id: str):
    """Look up volume for a sounding."""
    feet = request.args.get("feet", type=int)
    inches = request.args.get("inches", type=int)

    if feet is None or inches is None:
        return jsonify({"error": "feet and inches required"}), 400

    try:
        service = get_sounding_service()
        result = service.lookup(tank_id, feet, inches)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# --- Weekly Soundings ---


@api_bp.route("/soundings", methods=["GET"])
def get_soundings():
    """Get all weekly soundings, newest first."""
    soundings = WeeklySounding.query.order_by(
        WeeklySounding.recorded_at.desc()
    ).all()
    return jsonify([s.to_dict() for s in soundings])


@api_bp.route("/soundings/latest", methods=["GET"])
def get_latest_sounding():
    """Get the most recent weekly sounding."""
    sounding = WeeklySounding.query.order_by(
        WeeklySounding.recorded_at.desc()
    ).first()
    if sounding:
        return jsonify(sounding.to_dict())
    return jsonify(None)


@api_bp.route("/soundings", methods=["POST"])
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
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ["recorded_at", "engineer_name", "engineer_title", "tank_17p", "tank_17s"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    try:
        # Parse date
        recorded_at = datetime.fromisoformat(data["recorded_at"])

        # Look up volumes
        service = get_sounding_service()
        result_17p = service.lookup(
            "17P", data["tank_17p"]["feet"], data["tank_17p"]["inches"]
        )
        result_17s = service.lookup(
            "17S", data["tank_17s"]["feet"], data["tank_17s"]["inches"]
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


# --- ORB Entries ---


@api_bp.route("/orb-entries", methods=["GET"])
def get_orb_entries():
    """Get all ORB entries, newest first."""
    entries = ORBEntry.query.order_by(ORBEntry.entry_date.desc()).all()
    return jsonify([e.to_dict() for e in entries])


@api_bp.route("/orb-entries/<int:entry_id>", methods=["GET"])
def get_orb_entry(entry_id: int):
    """Get a specific ORB entry."""
    entry = ORBEntry.query.get_or_404(entry_id)
    return jsonify(entry.to_dict())


# --- Dashboard Stats ---


@api_bp.route("/dashboard/stats", methods=["GET"])
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
def get_service_tanks():
    """Get available service tank pairs."""
    return jsonify(FuelService.get_available_tank_pairs())


@api_bp.route("/service-tanks/active", methods=["GET"])
def get_active_service_tank():
    """Get currently active service tank pair."""
    active = ServiceTankConfig.query.filter_by(deactivated_at=None).first()
    if active:
        return jsonify(active.to_dict())
    return jsonify(None)


@api_bp.route("/service-tanks/active", methods=["POST"])
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
        now = datetime.utcnow()

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

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# --- Daily Fuel Tickets ---


@api_bp.route("/fuel-tickets", methods=["GET"])
def get_fuel_tickets():
    """Get all fuel tickets, newest first."""
    tickets = DailyFuelTicket.query.order_by(
        DailyFuelTicket.ticket_date.desc()
    ).all()
    return jsonify([t.to_dict() for t in tickets])


@api_bp.route("/fuel-tickets/latest", methods=["GET"])
def get_latest_fuel_ticket():
    """Get the most recent fuel ticket."""
    ticket = DailyFuelTicket.query.order_by(
        DailyFuelTicket.ticket_date.desc()
    ).first()
    if ticket:
        return jsonify(ticket.to_dict())
    return jsonify(None)


@api_bp.route("/fuel-tickets", methods=["POST"])
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

        return jsonify(ticket.to_dict()), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@api_bp.route("/fuel-tickets/stats", methods=["GET"])
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

