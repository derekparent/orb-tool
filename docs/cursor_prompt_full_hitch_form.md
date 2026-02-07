# Cursor Agent Prompt: Complete End of Hitch Form with OCR

## Context
Flask app at `/Users/dp/Projects/orb-tool/`. We need to:
1. Expand the data model to capture ALL fields from the End of Hitch Sounding Form
2. Add Google Cloud Vision OCR to auto-fill the form from a photo
3. Enable editing and printing the form at end of hitch

The form has these sections:
- **Header**: Vessel, Date, Location, Charter, Draft Fwd/Aft, Fuel on Log, Correction
- **Fuel Tanks**: 12 tanks (#7, #9, #11, #13, #14, #18 - Port & Stbd each) with soundings (ft/in), water present, and gallons
- **Service Tanks**: #15P Lube, #15S Gear, #16P Lube, #16S Hyd (gallons only)
- **Slop Tanks**: #17P Oily Bilge, #17S Dirty Oil (sounding + gallons)
- **Footer**: Engineer name, signature

## Task 1: Expand Data Model

### Update `src/models.py`

Replace the existing `HitchRecord` class with this expanded version:

```python
class FuelTankSounding(db.Model):
    """Individual fuel tank sounding record."""
    
    __tablename__ = "fuel_tank_soundings"
    
    id: int = db.Column(db.Integer, primary_key=True)
    hitch_id: int = db.Column(db.Integer, db.ForeignKey("hitch_records.id"), nullable=False)
    
    tank_number: str = db.Column(db.String(10), nullable=False)  # "7", "9", "11", "13", "14", "18"
    side: str = db.Column(db.String(4), nullable=False)  # "port" or "stbd"
    is_day_tank: bool = db.Column(db.Boolean, default=False)  # True for #18
    
    sounding_feet: int = db.Column(db.Integer, nullable=True)
    sounding_inches: int = db.Column(db.Integer, nullable=True)
    water_present: str = db.Column(db.String(20), default="None")  # "None", "Trace", etc.
    gallons: float = db.Column(db.Float, nullable=False)
    
    def to_dict(self) -> dict:
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
    
    # Draft readings
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
    created_at: datetime = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    fuel_tanks = db.relationship("FuelTankSounding", backref="hitch", lazy=True,
                                  cascade="all, delete-orphan")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vessel": self.vessel,
            "date": self.date.isoformat() if self.date else None,
            "location": self.location,
            "charter": self.charter,
            "draft_forward": f"{self.draft_forward_feet}' {self.draft_forward_inches}\"" if self.draft_forward_feet is not None else None,
            "draft_aft": f"{self.draft_aft_feet}' {self.draft_aft_inches}\"" if self.draft_aft_feet is not None else None,
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
```

## Task 2: Add Google Cloud Vision OCR Service

### Install dependency

Add to `requirements.txt`:
```
google-cloud-vision>=3.5.0
```

### Create `.env` entry (if not exists)
```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

Or set the environment variable to point to your GCP service account JSON.

### Create `src/services/ocr_service.py`

```python
"""OCR service for parsing End of Hitch Sounding forms using Google Cloud Vision."""

import re
from google.cloud import vision


def parse_end_of_hitch_image(image_data: bytes) -> dict:
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


def _parse_form_text(text: str) -> dict:
    """Parse raw OCR text into structured form data."""
    result = {
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
    }
    
    lines = text.split('\n')
    
    # Header parsing
    for line in lines:
        line_lower = line.lower()
        
        # Vessel
        if 'vessel:' in line_lower or 'usns' in line_lower:
            match = re.search(r'(?:vessel:\s*)?(\bUSNS\s+\w+)', line, re.IGNORECASE)
            if match:
                result["vessel"] = match.group(1).strip()
        
        # Date
        if 'date:' in line_lower:
            match = re.search(r'date:\s*(\d{1,2}/\d{1,2}/\d{2,4})', line, re.IGNORECASE)
            if match:
                result["date"] = match.group(1)
        
        # Location
        if 'location:' in line_lower:
            match = re.search(r'location:\s*(.+?)(?:\s*charter|$)', line, re.IGNORECASE)
            if match:
                result["location"] = match.group(1).strip()
        
        # Charter
        if 'charter:' in line_lower:
            match = re.search(r'charter:\s*(\w+)', line, re.IGNORECASE)
            if match:
                result["charter"] = match.group(1).strip()
        
        # Draft Forward
        if 'foreward' in line_lower or 'forward' in line_lower:
            match = re.search(r"(\d{1,2})'\s*(\d{1,2})\"?", line)
            if match:
                result["draft_forward"]["feet"] = int(match.group(1))
                result["draft_forward"]["inches"] = int(match.group(2))
        
        # Draft Aft
        if 'aft:' in line_lower:
            match = re.search(r"(\d{1,2})'\s*(\d{1,2})\"?", line)
            if match:
                result["draft_aft"]["feet"] = int(match.group(1))
                result["draft_aft"]["inches"] = int(match.group(2))
        
        # Fuel on Log
        if 'fuel on log' in line_lower:
            match = re.search(r'([\d,]+)', line.replace(',', ''))
            if match:
                result["fuel_on_log"] = float(match.group(1).replace(',', ''))
        
        # Correction
        if 'correction' in line_lower:
            match = re.search(r'\(?\s*([\d,]+)\s*\)?', line)
            if match:
                val = float(match.group(1).replace(',', ''))
                # Check if it's in parentheses (negative)
                if '(' in line:
                    val = -val
                result["correction"] = val
        
        # Total Onboard
        if 'total onboard' in line_lower:
            match = re.search(r'([\d,]+)', line.replace(',', ''))
            if match:
                result["total_fuel_gallons"] = float(match.group(1).replace(',', ''))
        
        # Engineer name
        if 'performing sounding' in line_lower or 'engineer' in line_lower:
            # Look for name on same line or next line
            match = re.search(r'sounding:\s*(\w+\s+\w+)', line, re.IGNORECASE)
            if match:
                result["engineer_name"] = match.group(1).strip()
    
    # Parse fuel tank table
    # Pattern: #7 Port | 2 | 6 | None | 7,122
    tank_pattern = re.compile(
        r'#(\d+)\s+(Port|Stbd)(?:\s+Day\s+Tank)?\s+(\d+)\s+(\d+)\s+(None|Trace|\w+)\s+([\d,]+)',
        re.IGNORECASE
    )
    
    for match in tank_pattern.finditer(text):
        tank_num = match.group(1)
        side = match.group(2).lower()
        is_day = 'day' in match.group(0).lower()
        result["fuel_tanks"].append({
            "tank_number": tank_num,
            "side": side,
            "is_day_tank": is_day,
            "sounding_feet": int(match.group(3)),
            "sounding_inches": int(match.group(4)),
            "water_present": match.group(5),
            "gallons": float(match.group(6).replace(',', '')),
        })
    
    # Parse service oils
    # Pattern: #15 Port Lube Oil | | 300 gal
    service_patterns = [
        (r'#15\s+Port\s+Lube\s+Oil.*?(\d+)\s*gal', '15p_lube'),
        (r'#15\s+Stbd\s+Gear\s+Oil.*?(\d+)\s*gal', '15s_gear'),
        (r'#16\s+Port\s+Lube\s+Oil.*?(\d+)\s*gal', '16p_lube'),
        (r'#16\s+Stbd\s+Hyd\.?\s+Oil.*?(\d+)\s*gal', '16s_hyd'),
    ]
    
    for pattern, key in service_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["service_oils"][key] = float(match.group(1))
    
    # Parse slop tanks
    # Pattern: #17 Port Oily Bilge | 0 | 7 | 137 gal
    slop_patterns = [
        (r'#17\s+Port\s+Oily\s+Bilge\s+(\d+)\s+(\d+)\s+([\d,]+)\s*gal', '17p_oily_bilge'),
        (r'#17\s+Stbd\s+Dirty\s+Oil\s+(\d+)\s+(\d+)\s+([\d,]+)\s*gal', '17s_dirty_oil'),
    ]
    
    for pattern, key in slop_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["slop_tanks"][key] = {
                "feet": int(match.group(1)),
                "inches": int(match.group(2)),
                "gallons": float(match.group(3).replace(',', '')),
            }
    
    return result
```

## Task 3: Add API Endpoints

### Update `src/routes/api.py`

Add at top:
```python
from services.ocr_service import parse_end_of_hitch_image
from models import FuelTankSounding
```

Add these endpoints:

```python
# --- OCR Parsing ---

@api_bp.route("/hitch/parse-image", methods=["POST"])
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
    
    # Read image data
    image_data = file.read()
    
    try:
        result = parse_end_of_hitch_image(image_data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"OCR failed: {str(e)}"}), 500


# --- Update start_new_hitch to accept full form data ---

@api_bp.route("/hitch/start", methods=["POST"])
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
        if '/' in date_str:
            # Handle MM/DD/YY format
            parts = date_str.split('/')
            if len(parts[2]) == 2:
                parts[2] = '20' + parts[2]
            hitch_date = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
        else:
            hitch_date = datetime.fromisoformat(date_str.replace('T', ' ').split('.')[0])
        
        # Clear existing data if requested
        if data.get("clear_data", True):
            # End any active hitch
            active_hitch = HitchRecord.query.filter_by(end_date=None, is_start=True).first()
            if active_hitch:
                active_hitch.end_date = datetime.utcnow()
            
            # Clear operational tables
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
        
        # Initialize slop tank sounding
        if oily_bilge.get("feet") is not None and dirty_oil.get("feet") is not None:
            sounding_service = get_sounding_service()
            oily_m3 = sounding_service.gallons_to_m3(oily_bilge.get("gallons", 0))
            dirty_m3 = sounding_service.gallons_to_m3(dirty_oil.get("gallons", 0))
            
            initial_sounding = WeeklySounding(
                recorded_at=hitch_date,
                engineer_name=data.get("engineer_name", "Baseline"),
                engineer_title="Previous Crew",
                tank_17p_feet=oily_bilge.get("feet", 0),
                tank_17p_inches=oily_bilge.get("inches", 0),
                tank_17p_gallons=oily_bilge.get("gallons", 0),
                tank_17p_m3=oily_m3,
                tank_17s_feet=dirty_oil.get("feet", 0),
                tank_17s_inches=dirty_oil.get("inches", 0),
                tank_17s_gallons=dirty_oil.get("gallons", 0),
                tank_17s_m3=dirty_m3,
            )
            db.session.add(initial_sounding)
        
        # Initialize oil levels
        if any([service.get("15p_lube"), service.get("15s_gear"), 
                service.get("16p_lube"), service.get("16s_hyd")]):
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
        
        return jsonify({
            "message": "New hitch started successfully",
            "hitch": hitch.to_dict(),
            "data_cleared": data.get("clear_data", True),
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@api_bp.route("/hitch/<int:hitch_id>", methods=["GET"])
def get_hitch(hitch_id: int):
    """Get a specific hitch record with all details."""
    hitch = HitchRecord.query.get_or_404(hitch_id)
    return jsonify(hitch.to_dict())


@api_bp.route("/hitch/<int:hitch_id>", methods=["PUT"])
def update_hitch(hitch_id: int):
    """Update an existing hitch record (for end-of-hitch editing)."""
    hitch = HitchRecord.query.get_or_404(hitch_id)
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    
    try:
        # Update simple fields
        for field in ["vessel", "location", "charter", "fuel_on_log", "correction",
                      "total_fuel_gallons", "lube_oil_15p", "gear_oil_15s",
                      "lube_oil_16p", "hyd_oil_16s", "engineer_name"]:
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
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@api_bp.route("/hitch/end", methods=["POST"])
def create_end_of_hitch():
    """
    Create end-of-hitch record (for printing/handover).
    Copies current hitch and marks as end record.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    
    # Same structure as start_new_hitch but with is_start=False
    # This creates the record that will be printed for Gold crew
    
    try:
        # ... same parsing logic as start_new_hitch ...
        # Create with is_start=False
        hitch = HitchRecord(
            # ... all fields ...
            is_start=False,
        )
        # ... add fuel tanks, commit ...
        
        return jsonify({
            "message": "End of hitch record created",
            "hitch": hitch.to_dict(),
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500
```

## Task 4: Update Template for OCR Upload

### Replace `templates/new_hitch.html`

```html
{% extends "base.html" %}
{% block title %}Start New Hitch - Engine Room{% endblock %}

{% block content %}
<div class="new-hitch-page">
    <header class="page-header">
        <h1>Start New Hitch</h1>
        <p class="page-subtitle">Import baseline from previous crew</p>
    </header>

    <!-- Image Upload Section -->
    <div class="upload-section">
        <div class="upload-card" id="upload-card">
            <input type="file" id="image-input" accept="image/*" capture="environment" hidden>
            <button type="button" class="btn btn-secondary btn-lg btn-block" id="upload-btn">
                📷 Upload End of Hitch Form
            </button>
            <p class="upload-hint">Take a photo or select an image to auto-fill</p>
        </div>
        <div class="upload-preview" id="upload-preview" style="display: none;">
            <img id="preview-image" src="" alt="Preview">
            <div class="preview-actions">
                <button type="button" class="btn btn-primary" id="parse-btn">Extract Data</button>
                <button type="button" class="btn btn-secondary" id="clear-btn">Clear</button>
            </div>
        </div>
        <div class="upload-status" id="upload-status" style="display: none;">
            <div class="spinner"></div>
            <span>Analyzing image...</span>
        </div>
    </div>

    <div class="divider">
        <span>or enter manually</span>
    </div>

    <div class="warning-card">
        <div class="warning-icon">⚠️</div>
        <div class="warning-text">
            <strong>This will clear all existing data</strong>
            <p>All fuel tickets, soundings, and ORB entries will be deleted.</p>
        </div>
    </div>

    <form id="hitch-form" class="form">
        <!-- Header Section -->
        <div class="form-section">
            <h3 class="section-title">Header Info</h3>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Vessel</label>
                    <input type="text" id="vessel" class="form-input" value="USNS Arrowhead">
                </div>
                <div class="form-group">
                    <label class="form-label">Date</label>
                    <input type="date" id="date" class="form-input" required>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Location</label>
                    <input type="text" id="location" class="form-input" placeholder="Port Angeles, WA">
                </div>
                <div class="form-group">
                    <label class="form-label">Charter</label>
                    <input type="text" id="charter" class="form-input" value="MSC">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Draft Forward</label>
                    <div class="draft-input">
                        <input type="number" id="draft-fwd-feet" class="form-input small" placeholder="13" min="0" max="30">
                        <span>'</span>
                        <input type="number" id="draft-fwd-inches" class="form-input small" placeholder="7" min="0" max="11">
                        <span>"</span>
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Draft Aft</label>
                    <div class="draft-input">
                        <input type="number" id="draft-aft-feet" class="form-input small" placeholder="13" min="0" max="30">
                        <span>'</span>
                        <input type="number" id="draft-aft-inches" class="form-input small" placeholder="8" min="0" max="11">
                        <span>"</span>
                    </div>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Fuel on Log</label>
                    <input type="number" id="fuel-on-log" class="form-input" placeholder="104532">
                </div>
                <div class="form-group">
                    <label class="form-label">Correction</label>
                    <input type="number" id="correction" class="form-input" placeholder="-523">
                </div>
            </div>
        </div>

        <!-- Fuel Tanks Section -->
        <div class="form-section">
            <h3 class="section-title">⛽ Fuel Tanks</h3>
            <div class="fuel-tank-grid" id="fuel-tanks-container">
                <!-- Will be populated by JS -->
            </div>
            <div class="total-row">
                <strong>Total Onboard:</strong>
                <span id="total-fuel-display">0</span> gallons
                <input type="hidden" id="total-fuel" required>
            </div>
        </div>

        <!-- Service Oils Section -->
        <div class="form-section">
            <h3 class="section-title">🛢️ Service Oils (gallons)</h3>
            <div class="oil-grid">
                <div class="oil-input">
                    <label>#15P Lube</label>
                    <input type="number" id="lube-15p" class="form-input" placeholder="300">
                </div>
                <div class="oil-input">
                    <label>#15S Gear</label>
                    <input type="number" id="gear-15s" class="form-input" placeholder="279">
                </div>
                <div class="oil-input">
                    <label>#16P Lube</label>
                    <input type="number" id="lube-16p" class="form-input" placeholder="304">
                </div>
                <div class="oil-input">
                    <label>#16S Hyd</label>
                    <input type="number" id="hyd-16s" class="form-input" placeholder="305">
                </div>
            </div>
        </div>

        <!-- Slop Tanks Section -->
        <div class="form-section">
            <h3 class="section-title">🚱 Slop Tanks</h3>
            <div class="slop-grid">
                <div class="slop-tank">
                    <label>#17P Oily Bilge</label>
                    <div class="sounding-input">
                        <input type="number" id="oily-bilge-feet" class="form-input small" placeholder="0" min="0" max="3">
                        <span>'</span>
                        <input type="number" id="oily-bilge-inches" class="form-input small" placeholder="7" min="0" max="11">
                        <span>"</span>
                        <input type="number" id="oily-bilge-gallons" class="form-input" placeholder="137">
                        <span>gal</span>
                    </div>
                </div>
                <div class="slop-tank">
                    <label>#17S Dirty Oil</label>
                    <div class="sounding-input">
                        <input type="number" id="dirty-oil-feet" class="form-input small" placeholder="1" min="0" max="3">
                        <span>'</span>
                        <input type="number" id="dirty-oil-inches" class="form-input small" placeholder="3" min="0" max="11">
                        <span>"</span>
                        <input type="number" id="dirty-oil-gallons" class="form-input" placeholder="462">
                        <span>gal</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Engineer Section -->
        <div class="form-section">
            <label class="form-label">Engineer Performing Soundings</label>
            <input type="text" id="engineer-name" class="form-input" placeholder="Aaron Frahm">
        </div>

        <button type="submit" class="btn btn-danger btn-lg btn-block" id="submit-btn">
            Clear Data & Start New Hitch
        </button>
    </form>
</div>
{% endblock %}

{% block scripts %}
<script>
// Fuel tank configuration
const FUEL_TANKS = [
    { number: "7", side: "port", label: "#7 Port" },
    { number: "7", side: "stbd", label: "#7 Stbd" },
    { number: "9", side: "port", label: "#9 Port" },
    { number: "9", side: "stbd", label: "#9 Stbd" },
    { number: "11", side: "port", label: "#11 Port" },
    { number: "11", side: "stbd", label: "#11 Stbd" },
    { number: "13", side: "port", label: "#13 Port" },
    { number: "13", side: "stbd", label: "#13 Stbd" },
    { number: "14", side: "port", label: "#14 Port" },
    { number: "14", side: "stbd", label: "#14 Stbd" },
    { number: "18", side: "port", label: "#18 Port Day Tank", isDayTank: true },
    { number: "18", side: "stbd", label: "#18 Stbd Day Tank", isDayTank: true },
];

document.addEventListener('DOMContentLoaded', () => {
    // Set default date
    document.getElementById('date').value = new Date().toISOString().split('T')[0];
    
    // Build fuel tank inputs
    buildFuelTankInputs();
    
    // Upload handlers
    const uploadBtn = document.getElementById('upload-btn');
    const imageInput = document.getElementById('image-input');
    const uploadCard = document.getElementById('upload-card');
    const uploadPreview = document.getElementById('upload-preview');
    const uploadStatus = document.getElementById('upload-status');
    const previewImage = document.getElementById('preview-image');
    const parseBtn = document.getElementById('parse-btn');
    const clearBtn = document.getElementById('clear-btn');
    
    uploadBtn.addEventListener('click', () => imageInput.click());
    
    imageInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                previewImage.src = e.target.result;
                uploadCard.style.display = 'none';
                uploadPreview.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    });
    
    clearBtn.addEventListener('click', () => {
        imageInput.value = '';
        uploadPreview.style.display = 'none';
        uploadCard.style.display = 'block';
    });
    
    parseBtn.addEventListener('click', async () => {
        const file = imageInput.files[0];
        if (!file) return;
        
        uploadPreview.style.display = 'none';
        uploadStatus.style.display = 'flex';
        
        const formData = new FormData();
        formData.append('image', file);
        
        try {
            const response = await fetch('/api/hitch/parse-image', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.error) {
                alert('OCR Error: ' + data.error);
                uploadStatus.style.display = 'none';
                uploadPreview.style.display = 'block';
                return;
            }
            
            fillFormFromOCR(data);
            
            uploadStatus.style.display = 'none';
            uploadCard.style.display = 'block';
            uploadCard.innerHTML = '<div class="upload-success">✓ Form data extracted - review below</div>';
            
        } catch (e) {
            console.error('Parse failed:', e);
            alert('Failed to parse image. Please enter data manually.');
            uploadStatus.style.display = 'none';
            uploadPreview.style.display = 'block';
        }
    });
    
    // Form submission
    document.getElementById('hitch-form').addEventListener('submit', handleSubmit);
});

function buildFuelTankInputs() {
    const container = document.getElementById('fuel-tanks-container');
    
    FUEL_TANKS.forEach((tank, idx) => {
        const id = `tank-${tank.number}-${tank.side}`;
        container.innerHTML += `
            <div class="fuel-tank-row" data-tank="${tank.number}" data-side="${tank.side}" data-day="${tank.isDayTank || false}">
                <span class="tank-label">${tank.label}</span>
                <input type="number" id="${id}-feet" class="form-input tiny" placeholder="0" min="0" max="20">
                <span>'</span>
                <input type="number" id="${id}-inches" class="form-input tiny" placeholder="0" min="0" max="11">
                <span>"</span>
                <select id="${id}-water" class="form-select small">
                    <option value="None">None</option>
                    <option value="Trace">Trace</option>
                </select>
                <input type="number" id="${id}-gallons" class="form-input" placeholder="0" 
                       onchange="updateTotalFuel()">
                <span>gal</span>
            </div>
        `;
    });
}

function updateTotalFuel() {
    let total = 0;
    FUEL_TANKS.forEach(tank => {
        const id = `tank-${tank.number}-${tank.side}`;
        const gallons = parseFloat(document.getElementById(`${id}-gallons`).value) || 0;
        total += gallons;
    });
    document.getElementById('total-fuel-display').textContent = total.toLocaleString();
    document.getElementById('total-fuel').value = total;
}

function fillFormFromOCR(data) {
    // Header
    if (data.vessel) document.getElementById('vessel').value = data.vessel;
    if (data.date) {
        // Convert MM/DD/YY to YYYY-MM-DD
        const parts = data.date.split('/');
        if (parts.length === 3) {
            let year = parts[2];
            if (year.length === 2) year = '20' + year;
            document.getElementById('date').value = `${year}-${parts[0].padStart(2,'0')}-${parts[1].padStart(2,'0')}`;
        }
    }
    if (data.location) document.getElementById('location').value = data.location;
    if (data.charter) document.getElementById('charter').value = data.charter;
    
    // Draft
    if (data.draft_forward) {
        document.getElementById('draft-fwd-feet').value = data.draft_forward.feet || '';
        document.getElementById('draft-fwd-inches').value = data.draft_forward.inches || '';
    }
    if (data.draft_aft) {
        document.getElementById('draft-aft-feet').value = data.draft_aft.feet || '';
        document.getElementById('draft-aft-inches').value = data.draft_aft.inches || '';
    }
    
    // Fuel reconciliation
    if (data.fuel_on_log) document.getElementById('fuel-on-log').value = data.fuel_on_log;
    if (data.correction) document.getElementById('correction').value = data.correction;
    
    // Fuel tanks
    if (data.fuel_tanks) {
        data.fuel_tanks.forEach(tank => {
            const id = `tank-${tank.tank_number}-${tank.side}`;
            const feetEl = document.getElementById(`${id}-feet`);
            if (feetEl) {
                feetEl.value = tank.sounding_feet || '';
                document.getElementById(`${id}-inches`).value = tank.sounding_inches || '';
                document.getElementById(`${id}-water`).value = tank.water_present || 'None';
                document.getElementById(`${id}-gallons`).value = tank.gallons || '';
            }
        });
        updateTotalFuel();
    }
    
    // Service oils
    if (data.service_oils) {
        const oils = data.service_oils;
        if (oils['15p_lube']) document.getElementById('lube-15p').value = oils['15p_lube'];
        if (oils['15s_gear']) document.getElementById('gear-15s').value = oils['15s_gear'];
        if (oils['16p_lube']) document.getElementById('lube-16p').value = oils['16p_lube'];
        if (oils['16s_hyd']) document.getElementById('hyd-16s').value = oils['16s_hyd'];
    }
    
    // Slop tanks
    if (data.slop_tanks) {
        const slop = data.slop_tanks;
        if (slop['17p_oily_bilge']) {
            document.getElementById('oily-bilge-feet').value = slop['17p_oily_bilge'].feet || '';
            document.getElementById('oily-bilge-inches').value = slop['17p_oily_bilge'].inches || '';
            document.getElementById('oily-bilge-gallons').value = slop['17p_oily_bilge'].gallons || '';
        }
        if (slop['17s_dirty_oil']) {
            document.getElementById('dirty-oil-feet').value = slop['17s_dirty_oil'].feet || '';
            document.getElementById('dirty-oil-inches').value = slop['17s_dirty_oil'].inches || '';
            document.getElementById('dirty-oil-gallons').value = slop['17s_dirty_oil'].gallons || '';
        }
    }
    
    // Engineer
    if (data.engineer_name) document.getElementById('engineer-name').value = data.engineer_name;
}

async function handleSubmit(e) {
    e.preventDefault();
    
    if (!confirm('This will DELETE all existing data and start fresh. Are you sure?')) {
        return;
    }
    
    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = 'Starting...';
    
    // Collect fuel tank data
    const fuelTanks = [];
    FUEL_TANKS.forEach(tank => {
        const id = `tank-${tank.number}-${tank.side}`;
        const gallons = parseFloat(document.getElementById(`${id}-gallons`).value);
        if (gallons) {
            fuelTanks.push({
                tank_number: tank.number,
                side: tank.side,
                is_day_tank: tank.isDayTank || false,
                sounding_feet: parseInt(document.getElementById(`${id}-feet`).value) || 0,
                sounding_inches: parseInt(document.getElementById(`${id}-inches`).value) || 0,
                water_present: document.getElementById(`${id}-water`).value,
                gallons: gallons,
            });
        }
    });
    
    const data = {
        vessel: document.getElementById('vessel').value,
        date: document.getElementById('date').value,
        location: document.getElementById('location').value || null,
        charter: document.getElementById('charter').value,
        draft_forward: {
            feet: parseInt(document.getElementById('draft-fwd-feet').value) || null,
            inches: parseInt(document.getElementById('draft-fwd-inches').value) || null,
        },
        draft_aft: {
            feet: parseInt(document.getElementById('draft-aft-feet').value) || null,
            inches: parseInt(document.getElementById('draft-aft-inches').value) || null,
        },
        fuel_on_log: parseFloat(document.getElementById('fuel-on-log').value) || null,
        correction: parseFloat(document.getElementById('correction').value) || null,
        total_fuel_gallons: parseFloat(document.getElementById('total-fuel').value) || 0,
        fuel_tanks: fuelTanks,
        service_oils: {
            '15p_lube': parseFloat(document.getElementById('lube-15p').value) || null,
            '15s_gear': parseFloat(document.getElementById('gear-15s').value) || null,
            '16p_lube': parseFloat(document.getElementById('lube-16p').value) || null,
            '16s_hyd': parseFloat(document.getElementById('hyd-16s').value) || null,
        },
        slop_tanks: {
            '17p_oily_bilge': {
                feet: parseInt(document.getElementById('oily-bilge-feet').value) || 0,
                inches: parseInt(document.getElementById('oily-bilge-inches').value) || 0,
                gallons: parseFloat(document.getElementById('oily-bilge-gallons').value) || 0,
            },
            '17s_dirty_oil': {
                feet: parseInt(document.getElementById('dirty-oil-feet').value) || 0,
                inches: parseInt(document.getElementById('dirty-oil-inches').value) || 0,
                gallons: parseFloat(document.getElementById('dirty-oil-gallons').value) || 0,
            },
        },
        engineer_name: document.getElementById('engineer-name').value || null,
        clear_data: true,
    };
    
    try {
        const response = await fetch('/api/hitch/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            alert('New hitch started successfully!');
            window.location.href = '/';
        } else {
            const error = await response.json();
            alert('Error: ' + error.error);
        }
    } catch (e) {
        console.error('Failed:', e);
        alert('Network error. Please try again.');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Clear Data & Start New Hitch';
    }
}
</script>
{% endblock %}
```

## Task 5: Add CSS

Append to `static/css/style.css`:

```css
/* Fuel Tank Grid */
.fuel-tank-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
}

.fuel-tank-row {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    padding: var(--space-xs);
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
}

.fuel-tank-row .tank-label {
    width: 120px;
    font-size: 0.875rem;
    font-weight: 500;
}

.form-input.tiny {
    width: 50px;
    text-align: center;
}

.form-input.small {
    width: 70px;
}

.form-select.small {
    width: 80px;
}

.total-row {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: var(--space-sm);
    padding: var(--space-md);
    background: var(--bg-card);
    border-radius: var(--radius-md);
    margin-top: var(--space-md);
    font-size: 1.125rem;
}

#total-fuel-display {
    font-weight: 700;
    color: var(--accent-primary);
}

/* Draft/Sounding Inputs */
.draft-input, .sounding-input {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
}

/* Slop Grid */
.slop-grid {
    display: flex;
    flex-direction: column;
    gap: var(--space-md);
}

.slop-tank label {
    display: block;
    margin-bottom: var(--space-xs);
    font-weight: 500;
}

/* Form Row */
.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-md);
}

@media (max-width: 600px) {
    .form-row {
        grid-template-columns: 1fr;
    }
    
    .fuel-tank-row {
        flex-wrap: wrap;
    }
    
    .fuel-tank-row .tank-label {
        width: 100%;
        margin-bottom: var(--space-xs);
    }
}

/* Upload Section */
.upload-section {
    margin-bottom: var(--space-lg);
}

.upload-card {
    background: var(--bg-card);
    border: 2px dashed var(--border-default);
    border-radius: var(--radius-lg);
    padding: var(--space-xl);
    text-align: center;
}

.upload-hint {
    font-size: 0.875rem;
    color: var(--text-muted);
    margin-top: var(--space-sm);
}

.upload-preview {
    background: var(--bg-card);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: var(--space-md);
}

.upload-preview img {
    width: 100%;
    max-height: 300px;
    object-fit: contain;
    border-radius: var(--radius-md);
    margin-bottom: var(--space-md);
}

.preview-actions {
    display: flex;
    gap: var(--space-sm);
}

.preview-actions .btn {
    flex: 1;
}

.upload-status {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-md);
    padding: var(--space-xl);
    background: var(--bg-card);
    border-radius: var(--radius-lg);
}

.spinner {
    width: 24px;
    height: 24px;
    border: 3px solid var(--border-default);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.upload-success {
    color: var(--accent-success);
    font-size: 1.125rem;
    font-weight: 600;
}

.divider {
    display: flex;
    align-items: center;
    gap: var(--space-md);
    margin: var(--space-lg) 0;
    color: var(--text-muted);
    font-size: 0.875rem;
}

.divider::before,
.divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border-default);
}

.section-title {
    font-size: 1rem;
    margin-bottom: var(--space-md);
    color: var(--text-primary);
}
```

## Task 6: Database Migration

Since we're adding a new table and modifying HitchRecord, you'll need to reset the DB or migrate:

```bash
# Option 1: Reset (dev only)
rm data/orb.db
flask run  # Will recreate tables

# Option 2: Manual migration
sqlite3 data/orb.db <<EOF
CREATE TABLE IF NOT EXISTS fuel_tank_soundings (
    id INTEGER PRIMARY KEY,
    hitch_id INTEGER NOT NULL,
    tank_number TEXT NOT NULL,
    side TEXT NOT NULL,
    is_day_tank BOOLEAN DEFAULT 0,
    sounding_feet INTEGER,
    sounding_inches INTEGER,
    water_present TEXT DEFAULT 'None',
    gallons REAL NOT NULL,
    FOREIGN KEY (hitch_id) REFERENCES hitch_records(id)
);

-- Add new columns to hitch_records
ALTER TABLE hitch_records ADD COLUMN vessel TEXT DEFAULT 'USNS Arrowhead';
ALTER TABLE hitch_records ADD COLUMN charter TEXT DEFAULT 'MSC';
ALTER TABLE hitch_records ADD COLUMN draft_forward_feet INTEGER;
ALTER TABLE hitch_records ADD COLUMN draft_forward_inches INTEGER;
ALTER TABLE hitch_records ADD COLUMN draft_aft_feet INTEGER;
ALTER TABLE hitch_records ADD COLUMN draft_aft_inches INTEGER;
ALTER TABLE hitch_records ADD COLUMN is_start BOOLEAN DEFAULT 1;
EOF
```

## Testing

1. **Manual test the OCR endpoint:**
```bash
curl -X POST http://localhost:5001/api/hitch/parse-image \
  -F "image=@/path/to/end_of_hitch_form.jpg"
```

2. **Test full form submission:**
```bash
curl -X POST http://localhost:5001/api/hitch/start \
  -H "Content-Type: application/json" \
  -d '{
    "vessel": "USNS Arrowhead",
    "date": "12/16/25",
    "location": "Port Angeles, WA",
    "charter": "MSC",
    "draft_forward": {"feet": 13, "inches": 7},
    "draft_aft": {"feet": 13, "inches": 8},
    "fuel_on_log": 104532,
    "correction": -523,
    "total_fuel_gallons": 105055,
    "fuel_tanks": [
      {"tank_number": "7", "side": "port", "sounding_feet": 2, "sounding_inches": 6, "water_present": "None", "gallons": 7122},
      {"tank_number": "7", "side": "stbd", "sounding_feet": 2, "sounding_inches": 6, "water_present": "None", "gallons": 7122}
    ],
    "service_oils": {
      "15p_lube": 300,
      "15s_gear": 279,
      "16p_lube": 304,
      "16s_hyd": 305
    },
    "slop_tanks": {
      "17p_oily_bilge": {"feet": 0, "inches": 7, "gallons": 137},
      "17s_dirty_oil": {"feet": 1, "inches": 3, "gallons": 462}
    },
    "engineer_name": "Aaron Frahm",
    "clear_data": true
  }'
```

## Commit Message
```
feat: complete End of Hitch form with OCR and full data capture

- Add FuelTankSounding model for individual tank records
- Expand HitchRecord to capture all form fields
- Add Google Cloud Vision OCR service
- Add /api/hitch/parse-image endpoint
- Update new_hitch.html with full form and OCR upload
- Support edit/print at end of hitch
```

## Next Steps (Future Tasks)
1. Add print/PDF generation for end-of-hitch form
2. Add fueling workflow (when you fuel, enter new data)
3. Add handover package generation
