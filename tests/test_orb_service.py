"""Tests for ORB entry generation service."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.orb_service import ORBService, ORBEntryData


class TestORBService:
    """Test ORB entry generation."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock sounding service
        self.mock_sounding_service = MagicMock()
        self.orb_service = ORBService(self.mock_sounding_service)

        # Mock tank info
        self.mock_tank_17s = {
            "name": "#17 Stbd Dirty Oil Tank",
            "orb_code": "C",
            "capacity_gallons": 1000,
            "capacity_m3": 3.79
        }

        self.mock_tank_17p = {
            "name": "#17 Port Oily Water Tank",
            "orb_code": "I",
            "capacity_gallons": 800,
            "capacity_m3": 3.03
        }

    def test_generate_code_c_entry(self):
        """Test Code C (Dirty Oil Tank) entry generation."""
        # Setup
        self.mock_sounding_service.get_tank_info.return_value = self.mock_tank_17s

        entry_date = datetime(2025, 1, 15, 14, 30)
        tank_m3 = 1.25
        engineer_name = "John Smith"
        engineer_title = "3rd Engineer"

        # Execute
        result = self.orb_service.generate_code_c(
            entry_date=entry_date,
            tank_m3=tank_m3,
            engineer_name=engineer_name,
            engineer_title=engineer_title
        )

        # Verify
        assert isinstance(result, dict)
        assert result["code"] == "C"
        assert result["entry_date"] == entry_date

        expected_text = """DATE: 15 JAN 2025
CODE: C

11.1 #17 Stbd Dirty Oil Tank (17S)
11.2 3.79 m³ capacity
11.3 1.25 m³ retained
11.4 N/A

John Smith, (3rd Engineer) 15 JAN 2025"""

        assert result["entry_text"] == expected_text
        self.mock_sounding_service.get_tank_info.assert_called_once_with("17S")

    def test_generate_code_i_entry(self):
        """Test Code I (Oily Water Tank) entry generation."""
        # Setup
        self.mock_sounding_service.get_tank_info.return_value = self.mock_tank_17p

        entry_date = datetime(2025, 2, 28, 10, 0)
        tank_m3 = 0.87
        engineer_name = "Jane Doe"
        engineer_title = "Chief Engineer"

        # Execute
        result = self.orb_service.generate_code_i(
            entry_date=entry_date,
            tank_m3=tank_m3,
            engineer_name=engineer_name,
            engineer_title=engineer_title
        )

        # Verify
        assert isinstance(result, dict)
        assert result["code"] == "I"
        assert result["entry_date"] == entry_date

        expected_text = """DATE: 28 FEB 2025
CODE: I

34.1 #17 Port Oily Water Tank (17P)
34.2 3.03 m³ capacity
34.3 0.87 m³ retained

Jane Doe, (Chief Engineer) 28 FEB 2025"""

        assert result["entry_text"] == expected_text
        self.mock_sounding_service.get_tank_info.assert_called_once_with("17P")

    def test_generate_weekly_entries(self):
        """Test generating both Code C and I entries together."""
        # Setup
        def mock_get_tank_info(tank_id):
            if tank_id == "17S":
                return self.mock_tank_17s
            elif tank_id == "17P":
                return self.mock_tank_17p
            else:
                raise ValueError(f"Unknown tank: {tank_id}")

        self.mock_sounding_service.get_tank_info.side_effect = mock_get_tank_info

        entry_date = datetime(2025, 3, 10, 16, 45)
        tank_17p_m3 = 1.15
        tank_17s_m3 = 2.33
        engineer_name = "Bob Wilson"
        engineer_title = "2nd Engineer"

        # Execute
        code_c, code_i = self.orb_service.generate_weekly_entries(
            entry_date=entry_date,
            tank_17p_m3=tank_17p_m3,
            tank_17s_m3=tank_17s_m3,
            engineer_name=engineer_name,
            engineer_title=engineer_title
        )

        # Verify Code C
        assert code_c["code"] == "C"
        assert code_c["entry_date"] == entry_date
        assert "2.33 m³ retained" in code_c["entry_text"]
        assert "17 Stbd Dirty Oil Tank" in code_c["entry_text"]

        # Verify Code I
        assert code_i["code"] == "I"
        assert code_i["entry_date"] == entry_date
        assert "1.15 m³ retained" in code_i["entry_text"]
        assert "17 Port Oily Water Tank" in code_i["entry_text"]

        # Verify service calls
        assert self.mock_sounding_service.get_tank_info.call_count == 2

    def test_date_formatting(self):
        """Test that dates are formatted correctly in different months."""
        # Setup
        self.mock_sounding_service.get_tank_info.return_value = self.mock_tank_17s

        test_dates = [
            (datetime(2025, 1, 1), "01 JAN 2025"),
            (datetime(2025, 12, 31), "31 DEC 2025"),
            (datetime(2025, 7, 15), "15 JUL 2025"),
            (datetime(2025, 11, 9), "09 NOV 2025")
        ]

        for test_date, expected_str in test_dates:
            result = self.orb_service.generate_code_c(
                entry_date=test_date,
                tank_m3=1.0,
                engineer_name="Test Engineer",
                engineer_title="Test Title"
            )

            assert expected_str in result["entry_text"]

    def test_numeric_precision(self):
        """Test that m³ values are formatted with correct precision."""
        # Setup
        self.mock_sounding_service.get_tank_info.return_value = self.mock_tank_17s

        test_values = [
            (1.2345, "1.23"),
            (0.1, "0.10"),
            (10.999, "11.00"),
            (0.0, "0.00")
        ]

        for tank_m3, expected_str in test_values:
            result = self.orb_service.generate_code_c(
                entry_date=datetime(2025, 1, 1),
                tank_m3=tank_m3,
                engineer_name="Test",
                engineer_title="Test"
            )

            assert f"{expected_str} m³ retained" in result["entry_text"]

    def test_orb_entry_data_type(self):
        """Test that return type matches ORBEntryData TypedDict."""
        # Setup
        self.mock_sounding_service.get_tank_info.return_value = self.mock_tank_17s

        result = self.orb_service.generate_code_c(
            entry_date=datetime(2025, 1, 1),
            tank_m3=1.0,
            engineer_name="Test",
            engineer_title="Test"
        )

        # Verify required keys exist
        assert "code" in result
        assert "entry_text" in result
        assert "entry_date" in result

        # Verify types
        assert isinstance(result["code"], str)
        assert isinstance(result["entry_text"], str)
        assert isinstance(result["entry_date"], datetime)

    def test_engineer_info_inclusion(self):
        """Test that engineer name and title are properly included."""
        # Setup
        self.mock_sounding_service.get_tank_info.return_value = self.mock_tank_17s

        engineer_name = "Christopher Martinez"
        engineer_title = "1st Assistant Engineer"

        result = self.orb_service.generate_code_c(
            entry_date=datetime(2025, 1, 1),
            tank_m3=1.0,
            engineer_name=engineer_name,
            engineer_title=engineer_title
        )

        # Should appear twice: once at end, once in parentheses
        text = result["entry_text"]
        assert engineer_name in text
        assert engineer_title in text
        assert f"({engineer_title})" in text