"""End-to-end integration tests for Oil Record Book Tool.

These tests verify complete workflows across multiple API endpoints,
ensuring data integrity and correct business logic through full user journeys.

Run with: pytest tests/test_integration.py -v -m integration
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

UTC = timezone.utc

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models import (
    db, User, UserRole, WeeklySounding, ORBEntry, DailyFuelTicket,
    ServiceTankConfig, StatusEvent, EquipmentStatus, OilLevel,
    HitchRecord, FuelTankSounding, EQUIPMENT_LIST
)


# ============================================================================
# Helper Functions
# ============================================================================

def login_user(client, user_info):
    """Log in a user via session manipulation."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_info['id'])
        sess['_fresh'] = True


def api_post(client, endpoint, data):
    """POST JSON to API endpoint."""
    return client.post(
        f"/api{endpoint}",
        data=json.dumps(data),
        content_type="application/json"
    )


def api_get(client, endpoint):
    """GET from API endpoint."""
    return client.get(f"/api{endpoint}")


# ============================================================================
# Test: Complete Hitch Lifecycle
# ============================================================================

@pytest.mark.integration
class TestHitchLifecycle:
    """Test complete hitch workflow: start → operations → end → reset."""
    
    def test_full_hitch_cycle(self, integration_client, all_users, integration_app):
        """Test starting a hitch, daily operations, and ending the hitch."""
        client = integration_client
        login_user(client, all_users['chief'])
        
        with integration_app.app_context():
            # 1. Start new hitch with baseline data
            hitch_data = {
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
                    {"tank_number": "13", "side": "port", "sounding_feet": 9, "sounding_inches": 0, "gallons": 14000, "water_present": "None"},
                    {"tank_number": "13", "side": "stbd", "sounding_feet": 8, "sounding_inches": 10, "gallons": 13800, "water_present": "None"},
                ],
                "engineer_name": "Chief Smith",
                "clear_data": True,
            }
            
            response = api_post(client, "/hitch/start", hitch_data)
            assert response.status_code == 201
            result = response.get_json()
            assert result["message"] == "New hitch started successfully"
            hitch_id = result["hitch"]["id"]
            
            # Verify baseline data created
            assert HitchRecord.query.count() == 1
            assert WeeklySounding.query.count() == 1  # Baseline sounding
            assert OilLevel.query.count() == 1
            assert EquipmentStatus.query.count() == 10  # All equipment initialized
            
            # 2. Set active service tank
            response = api_post(client, "/service-tanks/active", {
                "tank_pair": "13",
                "notes": "Starting with tank 13 pair"
            })
            assert response.status_code == 201
            
            # 3. Add daily fuel tickets (simulating a week of operations)
            for day in range(7):
                ticket_data = {
                    "ticket_date": f"2025-12-{16 + day}T08:00:00",
                    "meter_start": 50000.0 + (day * 250),
                    "meter_end": 50000.0 + ((day + 1) * 250),
                    "service_tank_pair": "13",
                    "engineer_name": "Engineer Jones",
                    "notes": f"Day {day + 1} operations"
                }
                response = api_post(client, "/fuel-tickets", ticket_data)
                assert response.status_code == 201
            
            assert DailyFuelTicket.query.count() == 7
            
            # 4. Record weekly sounding
            sounding_data = {
                "recorded_at": "2025-12-22T10:00:00",
                "engineer_name": "Engineer Jones",
                "engineer_title": "1st Assistant Engineer",
                "tank_17p": {"feet": 1, "inches": 9},
                "tank_17s": {"feet": 2, "inches": 6},
            }
            response = api_post(client, "/soundings", sounding_data)
            assert response.status_code == 201
            result = response.get_json()
            
            # Verify ORB entries created
            assert len(result["orb_entries"]) == 2
            assert WeeklySounding.query.count() == 2  # Baseline + new
            assert ORBEntry.query.count() == 2
            
            # 5. Log status events
            sewage_event = {
                "event_type": "sewage_pump",
                "event_date": "2025-12-18T14:30:00",
                "notes": "Pumped at dock",
                "engineer_name": "Engineer Jones"
            }
            response = api_post(client, "/status-events", sewage_event)
            assert response.status_code == 201
            
            potable_event = {
                "event_type": "potable_load",
                "event_date": "2025-12-20T10:00:00",
                "notes": "Loaded 5000 gal",
                "engineer_name": "Engineer Jones"
            }
            response = api_post(client, "/status-events", potable_event)
            assert response.status_code == 201
            
            # 6. Update equipment status
            response = api_post(client, "/equipment/PME", {
                "status": "issue",
                "note": "High temp warning",
                "updated_by": "Engineer Jones"
            })
            assert response.status_code == 201
            
            # 7. Get full dashboard (verify all data accessible)
            response = api_get(client, "/dashboard/full")
            assert response.status_code == 200
            dashboard = response.get_json()
            
            assert dashboard["counts"]["soundings"] == 2
            assert dashboard["counts"]["fuel_tickets"] == 7
            assert dashboard["counts"]["orb_entries"] == 2
            assert dashboard["fuel"]["active_tank"]["tank_pair"] == "13"
            assert dashboard["status_events"]["sewage"] is not None
            assert dashboard["status_events"]["potable"] is not None
            
            # Find PME in equipment list
            pme = next(e for e in dashboard["equipment"] if e["id"] == "PME")
            assert pme["status"] == "issue"
            
            # 8. Create end-of-hitch record
            end_hitch_data = {
                "date": "2025-12-28T08:00:00",
                "vessel": "USNS Arrowhead",
                "total_fuel_gallons": 118000.0,
                "slop_tanks": {
                    "17p_oily_bilge": {"feet": 2, "inches": 0, "gallons": 900},
                    "17s_dirty_oil": {"feet": 2, "inches": 9, "gallons": 1500},
                },
                "fuel_tanks": [
                    {"tank_number": "7", "side": "port", "gallons": 10000, "water_present": "None"},
                    {"tank_number": "13", "side": "port", "gallons": 12000, "water_present": "None"},
                ],
                "engineer_name": "Chief Smith",
            }
            response = api_post(client, "/hitch/end", end_hitch_data)
            assert response.status_code == 201
            
            # Verify end record created
            assert HitchRecord.query.count() == 2
            end_record = HitchRecord.query.filter_by(is_start=False).first()
            assert end_record is not None
            assert end_record.total_fuel_gallons == 118000.0
    
    def test_hitch_reset_clears_all_data(self, integration_client, all_users, integration_app):
        """Test that reset clears all operational data."""
        client = integration_client
        login_user(client, all_users['chief'])
        
        with integration_app.app_context():
            # Create some data first
            hitch_data = {
                "date": "2025-12-15T08:00:00",
                "total_fuel_gallons": 125000.0,
                "clear_data": True,
            }
            response = api_post(client, "/hitch/start", hitch_data)
            assert response.status_code == 201
            
            # Verify data exists
            assert HitchRecord.query.count() >= 1
            
            # Reset all data
            response = api_post(client, "/hitch/reset", {"confirm": True})
            assert response.status_code == 200
            
            # Verify all data cleared
            assert HitchRecord.query.count() == 0
            assert DailyFuelTicket.query.count() == 0
            assert WeeklySounding.query.count() == 0
            assert ORBEntry.query.count() == 0
            assert StatusEvent.query.count() == 0
            assert EquipmentStatus.query.count() == 0
            assert OilLevel.query.count() == 0
            assert ServiceTankConfig.query.count() == 0
    
    def test_reset_requires_confirmation(self, integration_client, all_users, integration_app):
        """Test that reset without confirmation is rejected."""
        client = integration_client
        login_user(client, all_users['chief'])
        
        with integration_app.app_context():
            response = api_post(client, "/hitch/reset", {})
            assert response.status_code == 400
            assert "confirm" in response.get_json()["error"].lower()


# ============================================================================
# Test: Fuel Consumption Tracking
# ============================================================================

@pytest.mark.integration
class TestFuelConsumptionTracking:
    """Test fuel consumption workflow: tank selection → tickets → stats."""
    
    def test_fuel_tracking_workflow(self, integration_client, all_users, integration_app):
        """Test complete fuel tracking workflow."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # 1. Set active service tank
            response = api_post(client, "/service-tanks/active", {
                "tank_pair": "13",
                "notes": "Starting fuel tracking test"
            })
            assert response.status_code == 201
            
            # 2. Create first fuel ticket
            response = api_post(client, "/fuel-tickets", {
                "ticket_date": "2025-12-16T08:00:00",
                "meter_start": 50000.0,
                "meter_end": 50250.0,
                "engineer_name": "Test Engineer",
            })
            assert response.status_code == 201
            ticket1 = response.get_json()
            assert ticket1["consumption_gallons"] == 250.0
            assert ticket1["service_tank_pair"] == "13"
            
            # 3. Create more tickets
            for i in range(1, 5):
                response = api_post(client, "/fuel-tickets", {
                    "ticket_date": f"2025-12-{16 + i}T08:00:00",
                    "meter_start": 50000.0 + (i * 250),
                    "meter_end": 50000.0 + ((i + 1) * 250),
                    "engineer_name": "Test Engineer",
                })
                assert response.status_code == 201
            
            # 4. Check fuel stats
            response = api_get(client, "/fuel-tickets/stats")
            assert response.status_code == 200
            stats = response.get_json()
            
            assert stats["total_tickets"] == 5
            assert stats["all_time"]["total_gallons"] == 1250.0  # 5 * 250
            assert stats["all_time"]["average_daily"] == 250.0
            assert stats["active_tank"]["tank_pair"] == "13"
            
            # 5. Switch to different tank pair
            response = api_post(client, "/service-tanks/active", {
                "tank_pair": "14",
                "notes": "Switching to tank 14"
            })
            assert response.status_code == 201
            
            # Verify old tank deactivated
            response = api_get(client, "/service-tanks/active")
            active = response.get_json()
            assert active["tank_pair"] == "14"
            
            # 6. Add ticket with new tank
            response = api_post(client, "/fuel-tickets", {
                "ticket_date": "2025-12-21T08:00:00",
                "meter_start": 51250.0,
                "meter_end": 51500.0,
                "engineer_name": "Test Engineer",
            })
            assert response.status_code == 201
            new_ticket = response.get_json()
            assert new_ticket["service_tank_pair"] == "14"
    
    def test_fuel_ticket_requires_active_tank_or_explicit(self, integration_client, all_users, integration_app):
        """Test that fuel ticket fails without active tank unless specified."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # Ensure no active tank
            ServiceTankConfig.query.delete()
            db.session.commit()
            
            # Try to create ticket without specifying tank
            response = api_post(client, "/fuel-tickets", {
                "ticket_date": "2025-12-16T08:00:00",
                "meter_start": 50000.0,
                "meter_end": 50250.0,
                "engineer_name": "Test Engineer",
            })
            assert response.status_code == 400
            assert "active service tank" in response.get_json()["error"].lower()
            
            # Now with explicit tank - should work
            response = api_post(client, "/fuel-tickets", {
                "ticket_date": "2025-12-16T08:00:00",
                "meter_start": 50000.0,
                "meter_end": 50250.0,
                "service_tank_pair": "13",
                "engineer_name": "Test Engineer",
            })
            assert response.status_code == 201
    
    def test_latest_ticket_autofill(self, integration_client, all_users, integration_app):
        """Test that latest ticket can be retrieved for meter reading auto-fill."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # Set up tank and create ticket
            api_post(client, "/service-tanks/active", {"tank_pair": "13"})
            api_post(client, "/fuel-tickets", {
                "ticket_date": "2025-12-16T08:00:00",
                "meter_start": 50000.0,
                "meter_end": 50250.0,
                "engineer_name": "Test Engineer",
            })
            
            # Get latest for auto-fill
            response = api_get(client, "/fuel-tickets/latest")
            assert response.status_code == 200
            latest = response.get_json()
            
            # Next ticket should start where last ended
            assert latest["meter_end"] == 50250.0


# ============================================================================
# Test: Slop Tank ORB Entry Generation
# ============================================================================

@pytest.mark.integration
class TestORBEntryGeneration:
    """Test ORB entry generation from weekly soundings."""
    
    def test_code_c_and_i_generation(self, integration_client, all_users, integration_app):
        """Test that Code C and I entries are correctly generated."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # Create sounding
            sounding_data = {
                "recorded_at": "2025-12-22T10:00:00",
                "engineer_name": "Engineer Jones",
                "engineer_title": "1st Assistant Engineer",
                "tank_17p": {"feet": 1, "inches": 9},
                "tank_17s": {"feet": 2, "inches": 6},
            }
            response = api_post(client, "/soundings", sounding_data)
            assert response.status_code == 201
            result = response.get_json()
            
            # Verify both entries created
            entries = result["orb_entries"]
            assert len(entries) == 2
            
            codes = {e["code"] for e in entries}
            assert "C" in codes, "Code C entry not generated"
            assert "I" in codes, "Code I entry not generated"
            
            # Verify Code C content (dirty oil retained)
            code_c = next(e for e in entries if e["code"] == "C")
            assert "17S" in code_c["entry_text"] or "17s" in code_c["entry_text"].lower()
            assert "retained" in code_c["entry_text"].lower()
            
            # Verify Code I content (oily water)
            code_i = next(e for e in entries if e["code"] == "I")
            assert "17P" in code_i["entry_text"] or "17p" in code_i["entry_text"].lower()
            assert "retained" in code_i["entry_text"].lower()
    
    def test_sounding_creates_linked_entries(self, integration_client, all_users, integration_app):
        """Test that ORB entries are linked to their source sounding."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # Create sounding
            response = api_post(client, "/soundings", {
                "recorded_at": "2025-12-22T10:00:00",
                "engineer_name": "Engineer Jones",
                "engineer_title": "Chief Engineer",
                "tank_17p": {"feet": 2, "inches": 0},
                "tank_17s": {"feet": 3, "inches": 0},
            })
            assert response.status_code == 201
            result = response.get_json()
            
            sounding_id = result["sounding"]["id"]
            
            # Verify entries link back to sounding
            for entry in result["orb_entries"]:
                assert entry["sounding_id"] == sounding_id
            
            # Verify via database
            entries = ORBEntry.query.filter_by(sounding_id=sounding_id).all()
            assert len(entries) == 2
    
    def test_orb_entries_viewable(self, integration_client, all_users, integration_app):
        """Test that ORB entries are accessible via API."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # Create soundings with zero-padded dates
            test_dates = ["2025-12-08T10:00:00", "2025-12-15T10:00:00", "2025-12-22T10:00:00"]
            for week, date in enumerate(test_dates):
                response = api_post(client, "/soundings", {
                    "recorded_at": date,
                    "engineer_name": "Engineer Jones",
                    "engineer_title": "Chief Engineer",
                    "tank_17p": {"feet": 1, "inches": week},
                    "tank_17s": {"feet": 2, "inches": week},
                })
                assert response.status_code == 201, f"Failed to create sounding for {date}"
            
            # Get all ORB entries
            response = api_get(client, "/orb-entries")
            assert response.status_code == 200
            entries = response.get_json()
            
            # 3 weeks * 2 entries each = 6 entries
            assert len(entries) == 6, f"Expected 6 entries, got {len(entries)}: {[e['entry_date'] for e in entries]}"
            
            # Verify sorted newest first
            dates = [e["entry_date"] for e in entries]
            assert dates == sorted(dates, reverse=True)


# ============================================================================
# Test: Equipment Status Board
# ============================================================================

@pytest.mark.integration
class TestEquipmentStatusBoard:
    """Test equipment status tracking and updates."""
    
    def test_equipment_status_workflow(self, integration_client, all_users, integration_app):
        """Test updating and viewing equipment status."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # 1. Get initial equipment list (all should be "online" by default)
            response = api_get(client, "/equipment")
            assert response.status_code == 200
            equipment = response.get_json()
            
            assert len(equipment) == 10  # All equipment types
            
            # Default status when no records exist is "online"
            for item in equipment:
                assert item["status"] == "online"
            
            # 2. Update single equipment status
            response = api_post(client, "/equipment/PME", {
                "status": "issue",
                "note": "High temperature warning",
                "updated_by": "Engineer Jones"
            })
            assert response.status_code == 201
            
            # Verify update
            response = api_get(client, "/equipment/PME")
            pme = response.get_json()
            assert pme["status"] == "issue"
            assert pme["note"] == "High temperature warning"
            assert pme["updated_by"] == "Engineer Jones"
            
            # 3. Bulk update equipment
            response = api_post(client, "/equipment/bulk", {
                "updates": [
                    {"equipment_id": "SSDG1", "status": "offline", "note": "Scheduled maintenance"},
                    {"equipment_id": "SSDG2", "status": "online", "note": None},
                    {"equipment_id": "SME", "status": "issue", "note": "Oil leak detected"},
                ],
                "updated_by": "Chief Smith"
            })
            assert response.status_code == 201
            result = response.get_json()
            assert result["updated"] == 3
            
            # 4. Verify all updates via equipment list
            response = api_get(client, "/equipment")
            equipment = response.get_json()
            
            status_map = {e["id"]: e["status"] for e in equipment}
            assert status_map["PME"] == "issue"
            assert status_map["SSDG1"] == "offline"
            assert status_map["SME"] == "issue"
            assert status_map["SSDG2"] == "online"
    
    def test_equipment_status_requires_note_for_issues(self, integration_client, all_users, integration_app):
        """Test that issue/offline status requires a note."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # Try to set issue without note
            response = api_post(client, "/equipment/PME", {
                "status": "issue",
                "updated_by": "Engineer Jones"
            })
            assert response.status_code == 400
            assert "note required" in response.get_json()["error"].lower()
            
            # With note should work
            response = api_post(client, "/equipment/PME", {
                "status": "issue",
                "note": "Temperature high",
                "updated_by": "Engineer Jones"
            })
            assert response.status_code == 201
    
    def test_equipment_status_history(self, integration_client, all_users, integration_app):
        """Test that equipment status changes are tracked over time."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # Create multiple status updates
            statuses = [
                ("online", None),
                ("issue", "High temp"),
                ("offline", "Repair in progress"),
                ("online", None),
            ]
            
            for status, note in statuses:
                data = {"status": status, "updated_by": "Engineer"}
                if note:
                    data["note"] = note
                api_post(client, "/equipment/PME", data)
            
            # All records should exist in database
            records = EquipmentStatus.query.filter_by(equipment_id="PME").all()
            assert len(records) == 4
            
            # Latest via API should be final status
            response = api_get(client, "/equipment/PME")
            assert response.get_json()["status"] == "online"


# ============================================================================
# Test: Role-Based Access Control
# ============================================================================

@pytest.mark.integration
class TestRoleBasedAccessControl:
    """Test access control for different user roles."""
    
    def test_viewer_read_only(self, integration_client, all_users, integration_app):
        """Test that viewer role can only read, not write."""
        client = integration_client
        login_user(client, all_users['viewer'])
        
        with integration_app.app_context():
            # Read operations should work
            response = api_get(client, "/equipment")
            assert response.status_code == 200
            
            response = api_get(client, "/fuel-tickets")
            assert response.status_code == 200
            
            response = api_get(client, "/soundings")
            assert response.status_code == 200
            
            # Write operations should be denied
            response = api_post(client, "/equipment/PME", {
                "status": "issue",
                "note": "Test",
                "updated_by": "Viewer"
            })
            assert response.status_code == 403
            
            response = api_post(client, "/fuel-tickets", {
                "ticket_date": "2025-12-16T08:00:00",
                "meter_start": 50000.0,
                "meter_end": 50250.0,
                "service_tank_pair": "13",
                "engineer_name": "Viewer"
            })
            assert response.status_code == 403
    
    def test_engineer_write_access(self, integration_client, all_users, integration_app):
        """Test that engineer can read and write, but not admin operations."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # Read should work
            response = api_get(client, "/equipment")
            assert response.status_code == 200
            
            # Write should work
            response = api_post(client, "/service-tanks/active", {
                "tank_pair": "13"
            })
            assert response.status_code == 201
            
            response = api_post(client, "/fuel-tickets", {
                "ticket_date": "2025-12-16T08:00:00",
                "meter_start": 50000.0,
                "meter_end": 50250.0,
                "engineer_name": "Engineer"
            })
            assert response.status_code == 201
            
            # Admin operations should be denied
            response = api_post(client, "/hitch/start", {
                "date": "2025-12-15T08:00:00",
                "total_fuel_gallons": 125000.0
            })
            assert response.status_code == 403
            
            response = api_post(client, "/hitch/reset", {"confirm": True})
            assert response.status_code == 403
    
    def test_chief_full_access(self, integration_client, all_users, integration_app):
        """Test that chief engineer has full access."""
        client = integration_client
        login_user(client, all_users['chief'])
        
        with integration_app.app_context():
            # All operations should work
            response = api_get(client, "/equipment")
            assert response.status_code == 200
            
            response = api_post(client, "/service-tanks/active", {"tank_pair": "13"})
            assert response.status_code == 201
            
            response = api_post(client, "/hitch/start", {
                "date": "2025-12-15T08:00:00",
                "total_fuel_gallons": 125000.0
            })
            assert response.status_code == 201
            
            # Reset (admin only)
            response = api_post(client, "/hitch/reset", {"confirm": True})
            assert response.status_code == 200
    
    def test_unauthenticated_denied(self, integration_client, integration_app):
        """Test that unauthenticated requests are denied on protected routes."""
        client = integration_client
        
        with integration_app.app_context():
            # Protected write endpoint
            response = api_post(client, "/fuel-tickets", {
                "ticket_date": "2025-12-16T08:00:00",
                "meter_start": 50000.0,
                "meter_end": 50250.0,
                "service_tank_pair": "13",
                "engineer_name": "Anonymous"
            })
            # Should redirect to login or return 401
            assert response.status_code in [401, 302]


# ============================================================================
# Test: Data Integrity
# ============================================================================

@pytest.mark.integration
class TestDataIntegrity:
    """Test database constraints, relationships, and transactions."""
    
    def test_fuel_tank_cascade_delete(self, integration_client, all_users, integration_app):
        """Test that deleting a hitch cascades to fuel tank soundings."""
        client = integration_client
        login_user(client, all_users['chief'])
        
        with integration_app.app_context():
            # Create hitch with fuel tanks
            response = api_post(client, "/hitch/start", {
                "date": "2025-12-15T08:00:00",
                "total_fuel_gallons": 125000.0,
                "fuel_tanks": [
                    {"tank_number": "7", "side": "port", "gallons": 12500, "water_present": "None"},
                    {"tank_number": "7", "side": "stbd", "gallons": 12300, "water_present": "None"},
                ],
                "clear_data": False,
            })
            assert response.status_code == 201
            
            hitch_id = response.get_json()["hitch"]["id"]
            
            # Verify fuel tanks created
            tanks = FuelTankSounding.query.filter_by(hitch_id=hitch_id).all()
            assert len(tanks) == 2
            
            # Reset deletes the hitch
            response = api_post(client, "/hitch/reset", {"confirm": True})
            assert response.status_code == 200
            
            # Fuel tanks should be gone (cascade delete)
            tanks = FuelTankSounding.query.filter_by(hitch_id=hitch_id).all()
            assert len(tanks) == 0
    
    def test_orb_entry_sounding_relationship(self, integration_client, all_users, integration_app):
        """Test ORB entries maintain relationship to soundings."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            # Create sounding
            response = api_post(client, "/soundings", {
                "recorded_at": "2025-12-22T10:00:00",
                "engineer_name": "Engineer Jones",
                "engineer_title": "Chief Engineer",
                "tank_17p": {"feet": 2, "inches": 0},
                "tank_17s": {"feet": 3, "inches": 0},
            })
            sounding_id = response.get_json()["sounding"]["id"]
            
            # Verify relationship
            sounding = WeeklySounding.query.get(sounding_id)
            assert sounding is not None
            assert len(sounding.orb_entries) == 2
            
            for entry in sounding.orb_entries:
                assert entry.sounding_id == sounding_id
    
    def test_transaction_rollback_on_error(self, integration_client, all_users, integration_app):
        """Test that failed operations don't leave partial data."""
        client = integration_client
        login_user(client, all_users['engineer'])
        
        with integration_app.app_context():
            initial_count = DailyFuelTicket.query.count()
            
            # Try to create invalid ticket (should fail)
            response = api_post(client, "/fuel-tickets", {
                "ticket_date": "invalid-date",  # Invalid
                "meter_start": 50000.0,
                "meter_end": 50250.0,
                "service_tank_pair": "13",
                "engineer_name": "Test"
            })
            assert response.status_code in [400, 500]
            
            # Count should be unchanged
            assert DailyFuelTicket.query.count() == initial_count
    
    def test_unique_constraints(self, integration_client, all_users, integration_app):
        """Test unique constraint enforcement."""
        client = integration_client
        login_user(client, all_users['chief'])
        
        with integration_app.app_context():
            # Try to create duplicate user (if we have the endpoint)
            # This tests that database constraints are working
            user = User(
                username="unique_test",
                email="unique@test.com",
                role=UserRole.ENGINEER
            )
            user.set_password("test123")
            db.session.add(user)
            db.session.commit()
            
            # Try to add another with same username
            user2 = User(
                username="unique_test",  # Duplicate
                email="different@test.com",
                role=UserRole.ENGINEER
            )
            user2.set_password("test123")
            db.session.add(user2)
            
            with pytest.raises(Exception):  # Should raise IntegrityError
                db.session.commit()
            
            db.session.rollback()
    
    def test_data_consistency_across_operations(self, integration_client, all_users, integration_app):
        """Test data stays consistent through multiple operations."""
        client = integration_client
        login_user(client, all_users['chief'])
        
        with integration_app.app_context():
            # Start fresh
            api_post(client, "/hitch/reset", {"confirm": True})
            
            # Run a series of operations
            api_post(client, "/hitch/start", {
                "date": "2025-12-15T08:00:00",
                "total_fuel_gallons": 125000.0,
                "slop_tanks": {
                    "17p_oily_bilge": {"feet": 1, "inches": 0, "gallons": 500},
                    "17s_dirty_oil": {"feet": 1, "inches": 0, "gallons": 600},
                },
            })
            
            api_post(client, "/service-tanks/active", {"tank_pair": "13"})
            
            for i in range(5):
                api_post(client, "/fuel-tickets", {
                    "ticket_date": f"2025-12-{16+i}T08:00:00",
                    "meter_start": 50000 + (i * 200),
                    "meter_end": 50200 + (i * 200),
                    "engineer_name": "Test"
                })
            
            api_post(client, "/soundings", {
                "recorded_at": "2025-12-22T10:00:00",
                "engineer_name": "Test",
                "engineer_title": "Chief",
                "tank_17p": {"feet": 1, "inches": 6},
                "tank_17s": {"feet": 1, "inches": 9},
            })
            
            # Verify counts
            response = api_get(client, "/dashboard/full")
            dashboard = response.get_json()
            
            assert dashboard["counts"]["soundings"] == 2  # baseline + 1
            assert dashboard["counts"]["fuel_tickets"] == 5
            assert dashboard["counts"]["orb_entries"] == 2


# ============================================================================
# Test: Dashboard Data Aggregation
# ============================================================================

@pytest.mark.integration  
class TestDashboardAggregation:
    """Test that dashboard correctly aggregates all data."""
    
    def test_full_dashboard_returns_all_sections(self, integration_client, all_users, integration_app):
        """Test dashboard structure is complete."""
        client = integration_client
        login_user(client, all_users['chief'])
        
        with integration_app.app_context():
            # Set up some data
            api_post(client, "/hitch/start", {
                "date": "2025-12-15T08:00:00",
                "total_fuel_gallons": 125000.0,
                "slop_tanks": {
                    "17p_oily_bilge": {"feet": 1, "inches": 0, "gallons": 500},
                    "17s_dirty_oil": {"feet": 1, "inches": 0, "gallons": 600},
                },
            })
            api_post(client, "/service-tanks/active", {"tank_pair": "13"})
            api_post(client, "/fuel-tickets", {
                "ticket_date": "2025-12-16T08:00:00",
                "meter_start": 50000,
                "meter_end": 50250,
                "engineer_name": "Test"
            })
            api_post(client, "/status-events", {
                "event_type": "sewage_pump",
                "event_date": "2025-12-17T10:00:00"
            })
            
            # Get dashboard
            response = api_get(client, "/dashboard/full")
            assert response.status_code == 200
            dashboard = response.get_json()
            
            # Verify all sections present
            assert "slop_tanks" in dashboard
            assert "fuel" in dashboard
            assert "status_events" in dashboard
            assert "equipment" in dashboard
            assert "counts" in dashboard
            
            # Verify nested structure
            assert "latest" in dashboard["slop_tanks"]
            assert "stats" in dashboard["fuel"]
            assert "active_tank" in dashboard["fuel"]
            assert "sewage" in dashboard["status_events"]
            assert "potable" in dashboard["status_events"]


# ============================================================================
# Performance Tests (optional - run with pytest -m "integration and slow")
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
class TestPerformance:
    """Performance benchmarks for critical operations."""
    
    def test_dashboard_response_time(self, integration_client, all_users, integration_app):
        """Test dashboard loads in acceptable time."""
        import time
        
        client = integration_client
        login_user(client, all_users['chief'])
        
        with integration_app.app_context():
            # Set up realistic data volume
            api_post(client, "/hitch/start", {
                "date": "2025-12-15T08:00:00",
                "total_fuel_gallons": 125000.0,
            })
            api_post(client, "/service-tanks/active", {"tank_pair": "13"})
            
            # Create 30 days of fuel tickets
            for i in range(30):
                api_post(client, "/fuel-tickets", {
                    "ticket_date": f"2025-12-{(i % 28) + 1}T08:00:00" if i < 28 else f"2026-01-{i - 27}T08:00:00",
                    "meter_start": 50000 + (i * 250),
                    "meter_end": 50250 + (i * 250),
                    "engineer_name": "Test"
                })
            
            # Measure dashboard response
            start = time.time()
            response = api_get(client, "/dashboard/full")
            elapsed = time.time() - start
            
            assert response.status_code == 200
            assert elapsed < 0.5, f"Dashboard took {elapsed:.2f}s, expected < 0.5s"
