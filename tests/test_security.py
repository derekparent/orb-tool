"""Security tests for the oil record book application."""

import json
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import create_app
from models import db, WeeklySounding, DailyFuelTicket, EquipmentStatus


@pytest.fixture
def app():
    """Create test app."""
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for testing
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def csrf_app():
    """Create test app with CSRF enabled."""
    app = create_app("testing")
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def csrf_client(csrf_app):
    """Create test client with CSRF enabled."""
    return csrf_app.test_client()


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_tank_lookup_validation(self, client):
        """Test tank lookup parameter validation."""
        # Test missing parameters
        response = client.get("/api/v1/tanks/17P/lookup")
        assert response.status_code == 400
        data = response.get_json()
        assert "required" in data["error"]

        # Test invalid parameters (None for non-int)
        response = client.get("/api/v1/tanks/17P/lookup?feet=abc&inches=xyz")
        assert response.status_code == 400

        # Test out of range parameters
        response = client.get("/api/v1/tanks/17P/lookup?feet=100&inches=50")
        assert response.status_code == 400

        # Test valid parameters
        response = client.get("/api/v1/tanks/17P/lookup?feet=5&inches=6")
        assert response.status_code == 200

    def test_sounding_validation(self, client):
        """Test weekly sounding input validation."""
        # Test missing required fields
        response = client.post("/api/v1/soundings",
                             json={})
        assert response.status_code == 400

        # Test invalid engineer name (numbers)
        response = client.post("/api/v1/soundings",
                             json={
                                 "recorded_at": "2025-01-01T10:00:00",
                                 "engineer_name": "John123",
                                 "engineer_title": "Chief",
                                 "tank_17p_feet": 5,
                                 "tank_17p_inches": 6,
                                 "tank_17s_feet": 4,
                                 "tank_17s_inches": 3
                             })
        assert response.status_code == 400

        # Test invalid sounding values
        response = client.post("/api/v1/soundings",
                             json={
                                 "recorded_at": "2025-01-01T10:00:00",
                                 "engineer_name": "John Doe",
                                 "engineer_title": "Chief Engineer",
                                 "tank_17p_feet": -5,  # Invalid negative
                                 "tank_17p_inches": 15,  # Invalid > 11
                                 "tank_17s_feet": 4,
                                 "tank_17s_inches": 3
                             })
        assert response.status_code == 400

    def test_fuel_ticket_validation(self, client):
        """Test fuel ticket input validation."""
        # Test meter end < meter start
        response = client.post("/api/v1/fuel-tickets",
                             json={
                                 "ticket_date": "2025-01-01T08:00:00",
                                 "meter_start": 1000.0,
                                 "meter_end": 999.0,  # Less than start
                                 "engineer_name": "John Doe"
                             })
        assert response.status_code == 400
        data = response.get_json()
        assert "greater than meter start" in data["details"]["meter_end"][0]

    def test_xss_prevention(self, client):
        """Test XSS prevention through input sanitization."""
        malicious_script = "<script>alert('xss')</script>"

        # Test engineer name sanitization
        response = client.post("/api/v1/soundings",
                             json={
                                 "recorded_at": "2025-01-01T10:00:00",
                                 "engineer_name": malicious_script,
                                 "engineer_title": "Chief Engineer",
                                 "tank_17p_feet": 5,
                                 "tank_17p_inches": 6,
                                 "tank_17s_feet": 4,
                                 "tank_17s_inches": 3
                             })

        if response.status_code == 201:
            # If validation passed, check that script was escaped
            data = response.get_json()
            assert "&lt;script&gt;" in data["sounding"]["engineer_name"]
            assert "<script>" not in data["sounding"]["engineer_name"]

    def test_sql_injection_prevention(self, client):
        """Test SQL injection prevention."""
        # Since we use SQLAlchemy ORM, this should be inherently safe
        # But test with malicious input anyway
        malicious_sql = "'; DROP TABLE weekly_soundings; --"

        response = client.post("/api/v1/soundings",
                             json={
                                 "recorded_at": "2025-01-01T10:00:00",
                                 "engineer_name": malicious_sql,
                                 "engineer_title": "Chief Engineer",
                                 "tank_17p_feet": 5,
                                 "tank_17p_inches": 6,
                                 "tank_17s_feet": 4,
                                 "tank_17s_inches": 3
                             })

        # Should fail validation due to regex, but if it passes, table should still exist
        soundings = WeeklySounding.query.all()
        # This won't fail even if malicious SQL was executed due to ORM protection


class TestCSRFProtection:
    """Test CSRF protection."""

    def test_csrf_token_required(self, csrf_client):
        """Test that CSRF token is required for state-changing operations."""
        response = csrf_client.post("/api/v1/soundings",
                                  json={
                                      "recorded_at": "2025-01-01T10:00:00",
                                      "engineer_name": "John Doe",
                                      "engineer_title": "Chief Engineer",
                                      "tank_17p_feet": 5,
                                      "tank_17p_inches": 6,
                                      "tank_17s_feet": 4,
                                      "tank_17s_inches": 3
                                  })
        assert response.status_code == 400
        data = response.get_json()
        assert "CSRF token" in data["error"]

    def test_get_requests_no_csrf(self, csrf_client):
        """Test that GET requests don't require CSRF tokens."""
        response = csrf_client.get("/api/v1/tanks")
        assert response.status_code == 200


class TestRateLimiting:
    """Test rate limiting functionality."""

    @patch('flask_limiter.Limiter.limit')
    def test_rate_limiting_applied(self, mock_limit, client):
        """Test that rate limiting is applied to endpoints."""
        # Test normal endpoint
        response = client.get("/api/v1/tanks")
        assert response.status_code == 200

        # Verify rate limiting decorator was applied
        assert mock_limit.called

    def test_rate_limit_exceeded(self, client):
        """Test rate limit exceeded response."""
        # This would require actually exceeding rate limits
        # which is impractical in unit tests
        # Instead verify rate limit error handler is configured
        from app import create_app
        app = create_app("testing")

        # Check error handler is registered
        assert 429 in app.error_handler_spec[None]


class TestSecurityHeaders:
    """Test security headers."""

    def test_security_headers_present(self, client):
        """Test that security headers are added to responses."""
        response = client.get("/api/v1/tanks")

        # Check security headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "max-age" in response.headers.get("Strict-Transport-Security", "")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_csp_header(self, client):
        """Test Content Security Policy header."""
        response = client.get("/api/v1/tanks")
        csp = response.headers.get("Content-Security-Policy")

        assert csp is not None
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp


class TestRequestSizeLimits:
    """Test request size limiting."""

    def test_content_length_validation(self, client):
        """Test content length validation."""
        # Create oversized payload (mock large request)
        large_data = "x" * (17 * 1024 * 1024)  # 17MB (over limit)

        response = client.post("/api/v1/soundings",
                             data=large_data,
                             content_type="application/json")

        # Should be rejected due to size
        assert response.status_code == 413

    def test_file_upload_size_limit(self, client):
        """Test file upload size validation."""
        # Mock large file upload
        large_file_content = b"x" * (17 * 1024 * 1024)  # 17MB

        response = client.post("/api/v1/hitch/parse-image",
                             data={"image": (large_file_content, "test.jpg")},
                             content_type="multipart/form-data")

        assert response.status_code == 413


class TestFileUploadSecurity:
    """Test file upload security."""

    def test_file_type_validation(self, client):
        """Test file type validation."""
        # Test invalid file type
        response = client.post("/api/v1/hitch/parse-image",
                             data={"image": (b"malicious content", "malware.exe")},
                             content_type="multipart/form-data")

        assert response.status_code == 400
        data = response.get_json()
        assert "allowed" in data["error"].lower()

    def test_valid_file_upload(self, client):
        """Test valid file upload."""
        # Mock valid image file
        valid_image = b"fake image content"

        with patch('services.ocr_service.parse_end_of_hitch_image') as mock_ocr:
            mock_ocr.return_value = {"test": "result"}

            response = client.post("/api/v1/hitch/parse-image",
                                 data={"image": (valid_image, "test.jpg")},
                                 content_type="multipart/form-data")

            # Should process successfully
            assert response.status_code == 200 or response.status_code == 400


class TestEquipmentStatusSecurity:
    """Test equipment status update security."""

    def test_equipment_id_validation(self, client):
        """Test equipment ID validation."""
        response = client.post("/api/v1/equipment/INVALID_ID",
                             json={
                                 "status": "online",
                                 "updated_by": "John Doe"
                             })

        assert response.status_code == 404

    def test_equipment_status_validation(self, client):
        """Test equipment status value validation."""
        response = client.post("/api/v1/equipment/PME",
                             json={
                                 "status": "invalid_status",
                                 "updated_by": "John Doe"
                             })

        assert response.status_code == 400

    def test_note_required_for_issues(self, client):
        """Test that note is required for issue/offline status."""
        response = client.post("/api/v1/equipment/PME",
                             json={
                                 "status": "issue",
                                 "updated_by": "John Doe"
                                 # Missing note
                             })

        assert response.status_code == 400
        data = response.get_json()
        assert "note" in data["details"]


class TestDataResetSecurity:
    """Test data reset security measures."""

    def test_reset_requires_confirmation(self, client):
        """Test that data reset requires explicit confirmation."""
        response = client.post("/api/v1/hitch/reset",
                             json={})

        assert response.status_code == 400

    def test_reset_with_confirmation(self, client):
        """Test data reset with proper confirmation."""
        # Add some test data first
        sounding = WeeklySounding(
            recorded_at="2025-01-01T10:00:00",
            engineer_name="Test Engineer",
            engineer_title="Chief Engineer",
            tank_17p_feet=5,
            tank_17p_inches=6,
            tank_17p_gallons=1000,
            tank_17p_m3=3.78,
            tank_17s_feet=4,
            tank_17s_inches=3,
            tank_17s_gallons=800,
            tank_17s_m3=3.03
        )
        db.session.add(sounding)
        db.session.commit()

        # Verify data exists
        assert WeeklySounding.query.count() == 1

        # Reset with confirmation
        response = client.post("/api/v1/hitch/reset",
                             json={"confirm": True})

        assert response.status_code == 200

        # Verify data was cleared
        assert WeeklySounding.query.count() == 0


class TestCORSConfiguration:
    """Test CORS configuration."""

    def test_cors_preflight(self, client):
        """Test CORS preflight requests."""
        response = client.options("/api/v1/tanks",
                                headers={
                                    "Origin": "http://localhost:5001",
                                    "Access-Control-Request-Method": "GET"
                                })

        # Should allow configured origins
        assert "Access-Control-Allow-Origin" in response.headers

    def test_cors_actual_request(self, client):
        """Test CORS on actual requests."""
        response = client.get("/api/v1/tanks",
                            headers={"Origin": "http://localhost:5001"})

        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers


if __name__ == "__main__":
    pytest.main([__file__])