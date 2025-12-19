"""OCR service for parsing End of Hitch Sounding forms using Google Cloud Vision."""

import re
from typing import Any

from google.cloud import vision


def parse_end_of_hitch_image(image_data: bytes) -> dict[str, Any]:
    """
    Parse an End of Hitch Sounding Form image using Google Cloud Vision OCR.

    Args:
        image_data: Raw image bytes (JPEG, PNG, HEIC, etc.)

    Returns:
        Parsed form data as dictionary
    """
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_data)

    # Use document text detection for better table recognition
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise Exception(f"Vision API error: {response.error.message}")

    full_text = response.full_text_annotation.text

    # Parse the OCR text into structured data
    return _parse_form_text(full_text)


def _parse_form_text(text: str) -> dict[str, Any]:
    """Parse raw OCR text into structured form data."""
    result: dict[str, Any] = {
        "vessel": None,
        "date": None,
        "location": None,
        "charter": None,
        "draft_forward": {"feet": None, "inches": None},
        "draft_aft": {"feet": None, "inches": None},
        "fuel_on_log": None,
        "correction": None,
        "fuel_tanks": [],
        "service_oils": {
            "15p_lube": None,
            "15s_gear": None,
            "16p_lube": None,
            "16s_hyd": None,
        },
        "slop_tanks": {
            "17p_oily_bilge": {"feet": None, "inches": None, "gallons": None},
            "17s_dirty_oil": {"feet": None, "inches": None, "gallons": None},
        },
        "total_fuel_gallons": None,
        "engineer_name": None,
        "raw_text": text,  # Include raw text for debugging
    }

    lines = text.split("\n")

    # Header parsing
    for line in lines:
        line_lower = line.lower()

        # Vessel
        if "vessel:" in line_lower or "usns" in line_lower:
            match = re.search(r"(?:vessel:\s*)?(\bUSNS\s+\w+)", line, re.IGNORECASE)
            if match:
                result["vessel"] = match.group(1).strip()

        # Date - look for patterns like 12/16/25
        if "date:" in line_lower or re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", line):
            match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", line)
            if match:
                result["date"] = match.group(1)

        # Location
        if "location:" in line_lower:
            match = re.search(r"location:\s*(.+?)(?:\s*charter|$)", line, re.IGNORECASE)
            if match:
                result["location"] = match.group(1).strip()

        # Charter
        if "charter:" in line_lower:
            match = re.search(r"charter:\s*(\w+)", line, re.IGNORECASE)
            if match:
                result["charter"] = match.group(1).strip()

        # Draft Forward - handle "Foreward" typo and "Forward"
        if "foreward" in line_lower or "forward" in line_lower:
            match = re.search(r"(\d{1,2})'\s*(\d{1,2})\"?", line)
            if match:
                result["draft_forward"]["feet"] = int(match.group(1))
                result["draft_forward"]["inches"] = int(match.group(2))

        # Draft Aft
        if "aft:" in line_lower or "aft " in line_lower:
            match = re.search(r"(\d{1,2})'\s*(\d{1,2})\"?", line)
            if match:
                result["draft_aft"]["feet"] = int(match.group(1))
                result["draft_aft"]["inches"] = int(match.group(2))

        # Fuel on Log
        if "fuel on log" in line_lower:
            match = re.search(r"([\d,]+)", line.replace(",", ""))
            if match:
                result["fuel_on_log"] = float(match.group(1).replace(",", ""))

        # Correction - may be in parentheses for negative
        if "correction" in line_lower:
            match = re.search(r"\(?\s*([\d,]+)\s*\)?", line)
            if match:
                val = float(match.group(1).replace(",", ""))
                # Check if it's in parentheses (negative)
                if "(" in line:
                    val = -val
                result["correction"] = val

        # Total Onboard
        if "total onboard" in line_lower:
            match = re.search(r"([\d,]+)", line)
            if match:
                result["total_fuel_gallons"] = float(match.group(1).replace(",", ""))

        # Engineer name
        if "performing sounding" in line_lower or "engineer" in line_lower:
            # Look for name on same line or extract from context
            match = re.search(r"sounding:\s*(\w+(?:\s+\w+)?)", line, re.IGNORECASE)
            if match:
                result["engineer_name"] = match.group(1).strip()

    # Parse fuel tank table
    # The form has rows like: #7 Port | 2 | 6 | None | 7,122
    # OCR may return this in various formats, so we try multiple patterns

    # Pattern for tank rows - more flexible matching
    tank_pattern = re.compile(
        r"#?(\d+)\s+(Port|Stbd)(?:\s+Day\s+Tank)?\s+(\d+)\s+(\d+)\s+(None|Trace|\w+)\s+([\d,]+)",
        re.IGNORECASE,
    )

    for match in tank_pattern.finditer(text):
        tank_num = match.group(1)
        side = match.group(2).lower()
        is_day = "day" in match.group(0).lower()
        result["fuel_tanks"].append(
            {
                "tank_number": tank_num,
                "side": side,
                "is_day_tank": is_day,
                "sounding_feet": int(match.group(3)),
                "sounding_inches": int(match.group(4)),
                "water_present": match.group(5),
                "gallons": float(match.group(6).replace(",", "")),
            }
        )

    # Alternative pattern: Try to find tanks in a more line-by-line approach
    if not result["fuel_tanks"]:
        for line in lines:
            # Look for lines starting with #7, #9, etc.
            match = re.match(
                r"#?(\d+)\s+(Port|Stbd)", line, re.IGNORECASE
            )
            if match and match.group(1) in ["7", "9", "11", "13", "14", "18"]:
                # Try to extract numbers from the rest of the line
                numbers = re.findall(r"[\d,]+", line[match.end() :])
                if len(numbers) >= 3:
                    is_day = "day" in line.lower()
                    water = "None"
                    if "trace" in line.lower():
                        water = "Trace"
                    result["fuel_tanks"].append(
                        {
                            "tank_number": match.group(1),
                            "side": match.group(2).lower(),
                            "is_day_tank": is_day,
                            "sounding_feet": int(numbers[0]),
                            "sounding_inches": int(numbers[1]),
                            "water_present": water,
                            "gallons": float(numbers[-1].replace(",", "")),
                        }
                    )

    # Parse service oils
    # Pattern: #15 Port Lube Oil | | 300 gal
    service_patterns = [
        (r"#?15\s+Port\s+Lube\s+Oil.*?(\d+)\s*(?:gal)?", "15p_lube"),
        (r"#?15\s+Stbd\s+Gear\s+Oil.*?(\d+)\s*(?:gal)?", "15s_gear"),
        (r"#?16\s+Port\s+Lube\s+Oil.*?(\d+)\s*(?:gal)?", "16p_lube"),
        (r"#?16\s+Stbd\s+Hyd\.?\s+Oil.*?(\d+)\s*(?:gal)?", "16s_hyd"),
    ]

    for pattern, key in service_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["service_oils"][key] = float(match.group(1))

    # Parse slop tanks
    # Pattern: #17 Port Oily Bilge | 0 | 7 | 137 gal
    slop_patterns = [
        (
            r"#?17\s+Port\s+Oily\s+Bilge[^\d]*(\d+)[^\d]+(\d+)[^\d]+([\d,]+)",
            "17p_oily_bilge",
        ),
        (
            r"#?17\s+Stbd\s+Dirty\s+Oil[^\d]*(\d+)[^\d]+(\d+)[^\d]+([\d,]+)",
            "17s_dirty_oil",
        ),
    ]

    for pattern, key in slop_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["slop_tanks"][key] = {
                "feet": int(match.group(1)),
                "inches": int(match.group(2)),
                "gallons": float(match.group(3).replace(",", "")),
            }

    return result

