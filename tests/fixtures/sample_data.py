"""Sample data fixtures for integration tests."""

from datetime import datetime, UTC, timedelta


# ============================================================================
# Static Test Data
# ============================================================================

SAMPLE_HITCH_DATA = {
    "date": "2025-12-15T08:00:00",
    "vessel": "USNS Arrowhead",
    "location": "Gulf of Mexico",
    "charter": "MSC",
    "total_fuel_gallons": 125000.0,
    "fuel_on_log": 124500.0,
    "correction": 500.0,
    "draft_forward": {"feet": 22, "inches": 6},
    "draft_aft": {"feet": 24, "inches": 3},
    "slop_tanks": {
        "17p_oily_bilge": {"feet": 1, "inches": 6, "gallons": 750},
        "17s_dirty_oil": {"feet": 2, "inches": 3, "gallons": 1200},
    },
    "service_oils": {
        "15p_lube": 450.0,
        "15s_gear": 320.0,
        "16p_lube": 400.0,
        "16s_hyd": 280.0,
    },
    "fuel_tanks": [
        {"tank_number": "7", "side": "port", "sounding_feet": 8, "sounding_inches": 6, "gallons": 12500, "water_present": "None"},
        {"tank_number": "7", "side": "stbd", "sounding_feet": 8, "sounding_inches": 4, "gallons": 12300, "water_present": "None"},
        {"tank_number": "9", "side": "port", "sounding_feet": 7, "sounding_inches": 2, "gallons": 10500, "water_present": "Trace"},
        {"tank_number": "9", "side": "stbd", "sounding_feet": 7, "sounding_inches": 0, "gallons": 10200, "water_present": "None"},
        {"tank_number": "11", "side": "port", "sounding_feet": 6, "sounding_inches": 8, "gallons": 9800, "water_present": "None"},
        {"tank_number": "11", "side": "stbd", "sounding_feet": 6, "sounding_inches": 6, "gallons": 9600, "water_present": "None"},
        {"tank_number": "13", "side": "port", "sounding_feet": 9, "sounding_inches": 0, "gallons": 14000, "water_present": "None"},
        {"tank_number": "13", "side": "stbd", "sounding_feet": 8, "sounding_inches": 10, "gallons": 13800, "water_present": "None"},
        {"tank_number": "14", "side": "port", "sounding_feet": 8, "sounding_inches": 4, "gallons": 13000, "water_present": "None"},
        {"tank_number": "14", "side": "stbd", "sounding_feet": 8, "sounding_inches": 2, "gallons": 12800, "water_present": "Trace"},
        {"tank_number": "18", "side": "port", "is_day_tank": True, "gallons": 3000, "water_present": "None"},
        {"tank_number": "18", "side": "stbd", "is_day_tank": True, "gallons": 2800, "water_present": "None"},
    ],
    "engineer_name": "Chief Smith",
    "clear_data": True,
}


SAMPLE_FUEL_TICKET_DATA = {
    "ticket_date": "2025-12-16T08:00:00",
    "meter_start": 50000.0,
    "meter_end": 50250.5,
    "service_tank_pair": "13",
    "engineer_name": "Engineer Jones",
    "notes": "Normal operations",
}


SAMPLE_SOUNDING_DATA = {
    "recorded_at": "2025-12-22T10:00:00",
    "engineer_name": "Engineer Jones",
    "engineer_title": "1st Assistant Engineer",
    "tank_17p": {"feet": 1, "inches": 9},
    "tank_17s": {"feet": 2, "inches": 6},
}


SAMPLE_EQUIPMENT_UPDATE = {
    "status": "issue",
    "note": "High temperature warning on port main",
    "updated_by": "Engineer Jones",
}


SAMPLE_STATUS_EVENT = {
    "event_type": "sewage_pump",
    "event_date": "2025-12-18T14:30:00",
    "notes": "Pumped at dock - Houston",
    "engineer_name": "Engineer Jones",
}


# ============================================================================
# Factory Functions
# ============================================================================

def create_test_users(db, User, UserRole):
    """Create a set of test users with different roles.
    
    Returns:
        dict: Dictionary with 'chief', 'engineer', 'viewer' user objects.
    """
    users = {}
    
    # Chief Engineer (admin)
    chief = User(
        username="chief_test",
        email="chief@test.com",
        full_name="Chief Engineer Test",
        role=UserRole.CHIEF_ENGINEER,
    )
    chief.set_password("chief123")
    db.session.add(chief)
    users["chief"] = chief
    
    # Regular Engineer (write access)
    engineer = User(
        username="engineer_test",
        email="engineer@test.com",
        full_name="Engineer Test",
        role=UserRole.ENGINEER,
    )
    engineer.set_password("engineer123")
    db.session.add(engineer)
    users["engineer"] = engineer
    
    # Viewer (read-only)
    viewer = User(
        username="viewer_test",
        email="viewer@test.com",
        full_name="Viewer Test",
        role=UserRole.VIEWER,
    )
    viewer.set_password("viewer123")
    db.session.add(viewer)
    users["viewer"] = viewer
    
    db.session.commit()
    return users


def create_sample_hitch(db, HitchRecord, FuelTankSounding, WeeklySounding=None, OilLevel=None):
    """Create a sample hitch record with fuel tanks.
    
    Returns:
        HitchRecord: The created hitch record.
    """
    from datetime import datetime
    
    hitch = HitchRecord(
        vessel="USNS Arrowhead",
        date=datetime(2025, 12, 15, 8, 0, 0),
        location="Gulf of Mexico",
        charter="MSC",
        draft_forward_feet=22,
        draft_forward_inches=6,
        draft_aft_feet=24,
        draft_aft_inches=3,
        fuel_on_log=124500.0,
        correction=500.0,
        total_fuel_gallons=125000.0,
        lube_oil_15p=450.0,
        gear_oil_15s=320.0,
        lube_oil_16p=400.0,
        hyd_oil_16s=280.0,
        oily_bilge_17p_feet=1,
        oily_bilge_17p_inches=6,
        oily_bilge_17p_gallons=750.0,
        dirty_oil_17s_feet=2,
        dirty_oil_17s_inches=3,
        dirty_oil_17s_gallons=1200.0,
        engineer_name="Chief Smith",
        is_start=True,
    )
    db.session.add(hitch)
    db.session.flush()
    
    # Add fuel tank soundings
    fuel_tanks = [
        ("7", "port", 8, 6, 12500, False),
        ("7", "stbd", 8, 4, 12300, False),
        ("13", "port", 9, 0, 14000, False),
        ("13", "stbd", 8, 10, 13800, False),
        ("18", "port", None, None, 3000, True),
        ("18", "stbd", None, None, 2800, True),
    ]
    
    for tank_num, side, feet, inches, gallons, is_day in fuel_tanks:
        tank = FuelTankSounding(
            hitch_id=hitch.id,
            tank_number=tank_num,
            side=side,
            sounding_feet=feet,
            sounding_inches=inches,
            gallons=gallons,
            is_day_tank=is_day,
            water_present="None",
        )
        db.session.add(tank)
    
    db.session.commit()
    return hitch


def create_fuel_tickets(db, DailyFuelTicket, ServiceTankConfig, count=7):
    """Create a series of daily fuel tickets.
    
    Args:
        count: Number of days of tickets to create.
        
    Returns:
        list: List of created DailyFuelTicket objects.
    """
    from datetime import datetime, timedelta
    
    # Ensure service tank is active
    now = datetime.now(UTC)
    active_tank = ServiceTankConfig.query.filter_by(deactivated_at=None).first()
    if not active_tank:
        active_tank = ServiceTankConfig(
            tank_pair="13",
            activated_at=now,
        )
        db.session.add(active_tank)
        db.session.flush()
    
    tickets = []
    base_date = datetime(2025, 12, 16, 8, 0, 0)
    meter_reading = 50000.0
    
    for i in range(count):
        consumption = 220.0 + (i * 5)  # Varying consumption
        ticket = DailyFuelTicket(
            ticket_date=base_date + timedelta(days=i),
            meter_start=meter_reading,
            meter_end=meter_reading + consumption,
            consumption_gallons=consumption,
            service_tank_pair=active_tank.tank_pair,
            engineer_name="Engineer Jones",
            notes=f"Day {i + 1} operations",
        )
        db.session.add(ticket)
        tickets.append(ticket)
        meter_reading += consumption
    
    db.session.commit()
    return tickets


def create_weekly_sounding(db, WeeklySounding, ORBEntry, sounding_service=None, orb_service=None):
    """Create a weekly sounding with associated ORB entries.
    
    Returns:
        tuple: (WeeklySounding, list[ORBEntry])
    """
    from datetime import datetime
    
    # Use reasonable test values
    sounding = WeeklySounding(
        recorded_at=datetime(2025, 12, 22, 10, 0, 0),
        engineer_name="Engineer Jones",
        engineer_title="1st Assistant Engineer",
        tank_17p_feet=1,
        tank_17p_inches=9,
        tank_17p_gallons=800,
        tank_17p_m3=3.03,
        tank_17s_feet=2,
        tank_17s_inches=6,
        tank_17s_gallons=1350,
        tank_17s_m3=5.11,
    )
    db.session.add(sounding)
    db.session.flush()
    
    # Create Code C entry (dirty oil retention)
    entry_c = ORBEntry(
        entry_date=sounding.recorded_at,
        code="C",
        entry_text="12.1 Retention of oil residue in slop tank 17S. Capacity: 35.28 m³. Total quantity of retention: 5.11 m³.",
        sounding_id=sounding.id,
    )
    
    # Create Code I entry (bilge water)
    entry_i = ORBEntry(
        entry_date=sounding.recorded_at,
        code="I",
        entry_text="15.1 Manual sounding of bilge holding tank 17P. Capacity: 35.28 m³. Total quantity retained: 3.03 m³.",
        sounding_id=sounding.id,
    )
    
    db.session.add_all([entry_c, entry_i])
    db.session.commit()
    
    return sounding, [entry_c, entry_i]
