"""Seed Teamcenter PLM dummy data — Induction Motor assembly.

Populates:
  - plm_parts          (motor assembly + sub-components)
  - plm_bom_items      (BOM hierarchy)
  - sample_parts       (replaces/augments with motor parts)
  - sample_bill_of_materials (motor BOM)
  - sample_test_results (electrical + mechanical test results)

Run:  python -m scripts.seed_induction_motor_plm
"""
from __future__ import annotations

import sys
import os
import uuid
import json
import random
from datetime import datetime, timezone, timedelta, date

# Allow running from repo root or python_backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GRAPH_TRACE_LOAD_DOTENV", "true")

from core.db_session import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

RUN_ID = "tc-induction-motor-001"

# ─── Induction Motor Part Catalogue ─────────────────────────────────────────

PLM_PARTS = [
    # Top-level assembly
    {"part_number": "IM-3PH-7.5KW-001", "name": "Induction Motor 3Ph 7.5kW Assembly",
     "description": "3-Phase squirrel-cage induction motor, 7.5 kW, IE3 efficiency class",
     "classification": "Motor Assembly",
     "cad_file": "IM_7.5kW_ASM_rev4.SLDASM", "revision": "D", "status": "Released",
     "weight_kg": 68.0, "material": "Mixed", "voltage_v": 415, "frequency_hz": 50,
     "rpm_rated": 1450, "poles": 4, "efficiency_class": "IE3", "ip_rating": "IP55"},

    # Stator subassembly
    {"part_number": "IM-STATOR-001", "name": "Stator Assembly",
     "description": "Laminated silicon steel stator core with 3-phase winding",
     "classification": "Stator",
     "cad_file": "IM_Stator_ASM_rev3.SLDASM", "revision": "C", "status": "Released",
     "weight_kg": 22.5, "material": "Silicon Steel / Copper",
     "winding_configuration": "Star (Y)", "coil_pitch": 10, "turns_per_coil": 48},

    {"part_number": "IM-STATOR-CORE-001", "name": "Stator Core Lamination Stack",
     "description": "M270-50A silicon steel laminations, 0.5mm thick",
     "classification": "Stator Core",
     "cad_file": "IM_Stator_Core_rev2.SLDPRT", "revision": "B", "status": "Released",
     "weight_kg": 18.2, "material": "M270-50A Silicon Steel",
     "lamination_thickness_mm": 0.5, "stack_length_mm": 145, "od_mm": 245},

    {"part_number": "IM-STATOR-WINDING-001", "name": "Stator Winding (3-Phase)",
     "description": "Class F insulated copper winding, 48 coils",
     "classification": "Winding",
     "cad_file": None, "revision": "B", "status": "Released",
     "weight_kg": 3.8, "material": "Copper / Class F Insulation",
     "wire_diameter_mm": 1.06, "resistance_per_phase_ohm": 1.42},

    # Rotor subassembly
    {"part_number": "IM-ROTOR-001", "name": "Rotor Assembly (Squirrel Cage)",
     "description": "Die-cast aluminium squirrel cage rotor with shaft",
     "classification": "Rotor",
     "cad_file": "IM_Rotor_ASM_rev3.SLDASM", "revision": "C", "status": "Released",
     "weight_kg": 19.0, "material": "Silicon Steel / Aluminium",
     "rotor_bar_count": 34, "od_mm": 163.8, "air_gap_mm": 0.6},

    {"part_number": "IM-ROTOR-CORE-001", "name": "Rotor Core Lamination Stack",
     "description": "M270-50A laminations for rotor, die-cast Al bars",
     "classification": "Rotor Core",
     "cad_file": "IM_Rotor_Core_rev2.SLDPRT", "revision": "B", "status": "Released",
     "weight_kg": 14.3, "material": "M270-50A Silicon Steel / Al",
     "stack_length_mm": 145, "od_mm": 163.8},

    {"part_number": "IM-SHAFT-001", "name": "Motor Shaft",
     "description": "C45 steel shaft, IEC frame size 132M, keyway to BS 4235",
     "classification": "Shaft",
     "cad_file": "IM_Shaft_rev3.SLDPRT", "revision": "C", "status": "Released",
     "weight_kg": 4.2, "material": "C45 Carbon Steel",
     "shaft_diameter_mm": 38, "shaft_length_mm": 320, "keyway_std": "BS 4235"},

    # Bearing subassembly
    {"part_number": "IM-BEARING-DE-001", "name": "Drive-End Bearing",
     "description": "SKF 6309-2Z deep groove ball bearing, DE side",
     "classification": "Bearing",
     "cad_file": None, "revision": "A", "status": "Released",
     "weight_kg": 0.48, "material": "52100 Bearing Steel",
     "bearing_type": "Deep Groove Ball", "bore_mm": 45, "od_mm": 100,
     "dynamic_load_kN": 55.3, "supplier": "SKF", "part_ref": "6309-2Z"},

    {"part_number": "IM-BEARING-NDE-001", "name": "Non-Drive-End Bearing",
     "description": "SKF 6308-2Z deep groove ball bearing, NDE side",
     "classification": "Bearing",
     "cad_file": None, "revision": "A", "status": "Released",
     "weight_kg": 0.37, "material": "52100 Bearing Steel",
     "bearing_type": "Deep Groove Ball", "bore_mm": 40, "od_mm": 90,
     "dynamic_load_kN": 41.0, "supplier": "SKF", "part_ref": "6308-2Z"},

    # Frame / Housing
    {"part_number": "IM-FRAME-001", "name": "Motor Frame (IEC 132M)",
     "description": "Grey cast iron frame, IEC 132M, foot-mounted B3",
     "classification": "Frame",
     "cad_file": "IM_Frame_132M_rev2.SLDPRT", "revision": "B", "status": "Released",
     "weight_kg": 15.5, "material": "GG25 Grey Cast Iron",
     "frame_size": "IEC 132M", "mounting": "B3 Foot-mounted", "cooling": "IC411"},

    {"part_number": "IM-ENDSHIELD-DE-001", "name": "Drive-End End Shield",
     "description": "Aluminium alloy end shield, DE, with bearing housing",
     "classification": "End Shield",
     "cad_file": "IM_EndShield_DE_rev2.SLDPRT", "revision": "B", "status": "Released",
     "weight_kg": 2.1, "material": "AlSi9Cu3 Aluminium Alloy"},

    {"part_number": "IM-ENDSHIELD-NDE-001", "name": "Non-Drive-End End Shield",
     "description": "Aluminium alloy end shield, NDE, with fan housing",
     "classification": "End Shield",
     "cad_file": "IM_EndShield_NDE_rev2.SLDPRT", "revision": "B", "status": "Released",
     "weight_kg": 1.8, "material": "AlSi9Cu3 Aluminium Alloy"},

    # Cooling & Fan
    {"part_number": "IM-FAN-001", "name": "External Cooling Fan",
     "description": "Polypropylene axial fan, 12 blades, 230mm OD",
     "classification": "Fan",
     "cad_file": "IM_Fan_rev1.SLDPRT", "revision": "A", "status": "Released",
     "weight_kg": 0.35, "material": "Glass-filled Polypropylene",
     "blade_count": 12, "od_mm": 230},

    {"part_number": "IM-FAN-COVER-001", "name": "Fan Cover",
     "description": "Sheet steel fan cover, IP55 rated, M5 fixing",
     "classification": "Fan Cover",
     "cad_file": "IM_FanCover_rev1.SLDPRT", "revision": "A", "status": "Released",
     "weight_kg": 0.45, "material": "DC01 Sheet Steel"},

    # Terminal box
    {"part_number": "IM-TBOX-001", "name": "Terminal Box Assembly",
     "description": "Aluminium terminal box, M20/M25 cable entries, IP55",
     "classification": "Terminal Box",
     "cad_file": "IM_TerminalBox_rev2.SLDASM", "revision": "B", "status": "Released",
     "weight_kg": 0.85, "material": "AlSi9Cu3"},

    {"part_number": "IM-TBOX-BOARD-001", "name": "Terminal Board",
     "description": "6-terminal insulated board, rated 690V, 32A",
     "classification": "Terminal Board",
     "cad_file": None, "revision": "A", "status": "Released",
     "weight_kg": 0.12, "material": "Glass-filled Nylon",
     "voltage_rating_v": 690, "current_rating_a": 32},

    # Fasteners & seals
    {"part_number": "IM-SEAL-DE-001", "name": "Drive-End Shaft Seal",
     "description": "NBR lip seal, 38×62×10, single lip",
     "classification": "Seal",
     "cad_file": None, "revision": "A", "status": "Released",
     "weight_kg": 0.02, "material": "NBR",
     "shaft_dia_mm": 38, "type": "Single Lip Radial"},

    {"part_number": "IM-GREASE-001", "name": "Bearing Grease (Mobil Polyrex EM)",
     "description": "Polyurea-based grease for electric motor bearings, 50g",
     "classification": "Lubricant",
     "cad_file": None, "revision": "A", "status": "Released",
     "weight_kg": 0.05, "material": "Polyurea / Mineral Oil",
     "quantity_g": 50, "nlgi_grade": 2, "supplier": "ExxonMobil"},

    # Nameplate & labels
    {"part_number": "IM-NAMEPLATE-001", "name": "Motor Nameplate",
     "description": "Stainless steel nameplate, laser-engraved, IEC 60034-1",
     "classification": "Nameplate",
     "cad_file": None, "revision": "A", "status": "Released",
     "weight_kg": 0.01, "material": "316 Stainless Steel"},
]

# ─── BOM hierarchy ──────────────────────────────────────────────────────────

PLM_BOM = [
    # Top motor assembly
    ("IM-3PH-7.5KW-001", "IM-STATOR-001",       1.0),
    ("IM-3PH-7.5KW-001", "IM-ROTOR-001",        1.0),
    ("IM-3PH-7.5KW-001", "IM-FRAME-001",        1.0),
    ("IM-3PH-7.5KW-001", "IM-ENDSHIELD-DE-001", 1.0),
    ("IM-3PH-7.5KW-001", "IM-ENDSHIELD-NDE-001",1.0),
    ("IM-3PH-7.5KW-001", "IM-FAN-001",          1.0),
    ("IM-3PH-7.5KW-001", "IM-FAN-COVER-001",    1.0),
    ("IM-3PH-7.5KW-001", "IM-TBOX-001",         1.0),
    ("IM-3PH-7.5KW-001", "IM-BEARING-DE-001",   1.0),
    ("IM-3PH-7.5KW-001", "IM-BEARING-NDE-001",  1.0),
    ("IM-3PH-7.5KW-001", "IM-SEAL-DE-001",      1.0),
    ("IM-3PH-7.5KW-001", "IM-GREASE-001",       1.0),
    ("IM-3PH-7.5KW-001", "IM-NAMEPLATE-001",    1.0),
    # Stator subassembly
    ("IM-STATOR-001",    "IM-STATOR-CORE-001",  1.0),
    ("IM-STATOR-001",    "IM-STATOR-WINDING-001",1.0),
    # Rotor subassembly
    ("IM-ROTOR-001",     "IM-ROTOR-CORE-001",   1.0),
    ("IM-ROTOR-001",     "IM-SHAFT-001",        1.0),
    # Terminal box
    ("IM-TBOX-001",      "IM-TBOX-BOARD-001",   1.0),
]

# ─── Sample parts (uuid-keyed, matches sample_parts schema) ─────────────────

SAMPLE_PARTS_DATA = []
PART_UUID_MAP: dict[str, uuid.UUID] = {}

_categories = {
    "IM-3PH-7.5KW-001": "Motor Assembly",
    "IM-STATOR-001": "Stator",
    "IM-STATOR-CORE-001": "Stator Core",
    "IM-STATOR-WINDING-001": "Winding",
    "IM-ROTOR-001": "Rotor",
    "IM-ROTOR-CORE-001": "Rotor Core",
    "IM-SHAFT-001": "Shaft",
    "IM-BEARING-DE-001": "Bearing",
    "IM-BEARING-NDE-001": "Bearing",
    "IM-FRAME-001": "Frame",
    "IM-ENDSHIELD-DE-001": "End Shield",
    "IM-ENDSHIELD-NDE-001": "End Shield",
    "IM-FAN-001": "Fan",
    "IM-FAN-COVER-001": "Fan Cover",
    "IM-TBOX-001": "Terminal Box",
    "IM-TBOX-BOARD-001": "Terminal Board",
    "IM-SEAL-DE-001": "Seal",
    "IM-GREASE-001": "Lubricant",
    "IM-NAMEPLATE-001": "Nameplate",
}

_costs = {
    "IM-3PH-7.5KW-001": 1850.00, "IM-STATOR-001": 420.00, "IM-STATOR-CORE-001": 310.00,
    "IM-STATOR-WINDING-001": 95.00, "IM-ROTOR-001": 280.00, "IM-ROTOR-CORE-001": 195.00,
    "IM-SHAFT-001": 72.00, "IM-BEARING-DE-001": 38.50, "IM-BEARING-NDE-001": 29.00,
    "IM-FRAME-001": 215.00, "IM-ENDSHIELD-DE-001": 65.00, "IM-ENDSHIELD-NDE-001": 55.00,
    "IM-FAN-001": 18.00, "IM-FAN-COVER-001": 12.00, "IM-TBOX-001": 42.00,
    "IM-TBOX-BOARD-001": 9.50, "IM-SEAL-DE-001": 4.00, "IM-GREASE-001": 3.50,
    "IM-NAMEPLATE-001": 2.00,
}

now = datetime.now(timezone.utc)

for p in PLM_PARTS:
    pid = uuid.uuid4()
    PART_UUID_MAP[p["part_number"]] = pid
    SAMPLE_PARTS_DATA.append({
        "part_id": pid,
        "part_number": p["part_number"],
        "description": p["description"],
        "category": _categories.get(p["part_number"], "Component"),
        "weight": p.get("weight_kg"),
        "material": p.get("material"),
        "supplier_id": uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        "cost": _costs.get(p["part_number"]),
        "created_date": now - timedelta(days=random.randint(30, 365)),
        "modified_date": now - timedelta(days=random.randint(0, 30)),
    })

# ─── Sample BOM (uuid-keyed) ─────────────────────────────────────────────────

SAMPLE_BOM_DATA = []
for parent_pn, child_pn, qty in PLM_BOM:
    parent_id = PART_UUID_MAP.get(parent_pn)
    child_id  = PART_UUID_MAP.get(child_pn)
    if parent_id and child_id:
        SAMPLE_BOM_DATA.append({
            "bom_id": uuid.uuid4(),
            "parent_part_id": parent_id,
            "child_part_id":  child_id,
            "quantity": qty,
            "unit_of_measure": "EA",
            "position": f"P{random.randint(1,50):02d}",
            "effective_date": date(2024, 1, 1),
            "end_date": None,
            "revision": "D",
            "created_by": "eng.teamcenter",
        })

# ─── Test results ────────────────────────────────────────────────────────────

TEST_SPECS = [
    # (test_type, unit, nominal, tolerance_pct, pass_threshold_pct)
    ("Insulation Resistance",   "MΩ",   500,  None,  None),   # pass if > 100 MΩ
    ("Winding Resistance Ph-U", "Ω",    1.42, 5,     True),
    ("Winding Resistance Ph-V", "Ω",    1.42, 5,     True),
    ("Winding Resistance Ph-W", "Ω",    1.42, 5,     True),
    ("No-Load Current",         "A",    5.8,  10,    True),
    ("No-Load Power",           "W",    320,  10,    True),
    ("Locked Rotor Current",    "A",    54.2, 8,     True),
    ("Vibration (DE)",          "mm/s", 1.8,  None,  None),    # pass if < 4.5
    ("Vibration (NDE)",         "mm/s", 1.6,  None,  None),
    ("Bearing Temp (DE)",       "°C",   62,   None,  None),    # pass if < 90
    ("Bearing Temp (NDE)",      "°C",   58,   None,  None),
    ("Efficiency",              "%",    89.5, 2,     True),
    ("Power Factor",            "",     0.84, 3,     True),
    ("Shaft Runout",            "μm",   18,   None,  None),    # pass if < 50
]

OPERATORS = ["eng.smith", "eng.jones", "eng.patel", "eng.mueller", "eng.chen"]
EQUIPMENT_IDS = ["DY-3000", "IM-TESTER-01", "LCR-METER-02", "VIBE-ANALYSER-03", "TEMP-LOGGER-04"]

SAMPLE_TEST_DATA = []
motor_parts_uuid = list(PART_UUID_MAP.values())

# Generate 3 test runs × 19 parts × test types
for serial_no in range(1, 4):
    for pid in motor_parts_uuid:
        for tt, unit, nominal, tol, use_tolerance in TEST_SPECS:
            if use_tolerance and tol:
                spread = nominal * tol / 100.0
                val = round(nominal + random.uniform(-spread, spread), 4)
                # Inject ~8% failures
                if random.random() < 0.08:
                    val = round(nominal * random.uniform(1.12, 1.25), 4)
                pf = abs((val - nominal) / nominal * 100) <= tol
            else:
                # threshold-based
                if tt == "Insulation Resistance":
                    val = round(random.uniform(200, 2000), 1)
                    pf = val >= 100
                elif "Vibration" in tt:
                    val = round(random.uniform(0.5, 5.5), 2)
                    pf = val < 4.5
                elif "Bearing Temp" in tt:
                    val = round(random.uniform(45, 95), 1)
                    pf = val < 90
                elif "Shaft Runout" in tt:
                    val = round(random.uniform(5, 60), 1)
                    pf = val < 50
                else:
                    val = round(nominal + random.uniform(-nominal * 0.1, nominal * 0.1), 3)
                    pf = True

            SAMPLE_TEST_DATA.append({
                "test_id":          uuid.uuid4(),
                "part_id":          pid,
                "test_type":        tt,
                "measurement_value": val,
                "unit":             unit,
                "pass_fail":        bool(pf),
                "test_date":        now - timedelta(days=random.randint(0, 90),
                                                    hours=random.randint(0, 23)),
                "operator":         random.choice(OPERATORS),
                "equipment_id":     random.choice(EQUIPMENT_IDS),
                "notes":            None if pf else f"Out of spec — re-check {tt}",
            })


def _to_serializable(v):
    if isinstance(v, (uuid.UUID,)):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def seed(db):
    # ── plm_parts ──────────────────────────────
    db.execute(text("DELETE FROM plm_parts WHERE run_id = :r"), {"r": RUN_ID})
    for p in PLM_PARTS:
        raw = {k: v for k, v in p.items()}
        db.execute(text("""
            INSERT INTO plm_parts (run_id, part_number, name, description, classification, raw)
            VALUES (:run_id, :pn, :name, :desc, :cls, CAST(:raw AS json))
        """), {
            "run_id": RUN_ID,
            "pn":     p["part_number"],
            "name":   p["name"],
            "desc":   p["description"],
            "cls":    p["classification"],
            "raw":    json.dumps(raw),
        })
    print(f"  plm_parts:          {len(PLM_PARTS)} rows")

    # ── plm_bom_items ──────────────────────────
    db.execute(text("DELETE FROM plm_bom_items WHERE run_id = :r"), {"r": RUN_ID})
    for parent_pn, child_pn, qty in PLM_BOM:
        db.execute(text("""
            INSERT INTO plm_bom_items (run_id, parent_part_number, child_part_number, quantity, raw)
            VALUES (:run_id, :p, :c, :q, CAST(:raw AS json))
        """), {
            "run_id": RUN_ID,
            "p": parent_pn, "c": child_pn, "q": qty,
            "raw": json.dumps({"parent": parent_pn, "child": child_pn, "qty": qty}),
        })
    print(f"  plm_bom_items:      {len(PLM_BOM)} rows")

    # ── sample_parts ───────────────────────────
    # Delete children first (FK constraints), then parent sample_parts rows
    db.execute(text("DELETE FROM sample_test_results WHERE operator LIKE 'eng.%'"))
    db.execute(text("DELETE FROM sample_bill_of_materials WHERE revision = 'D'"))
    db.execute(text("DELETE FROM sample_parts WHERE part_number LIKE 'IM-%'"))
    for sp in SAMPLE_PARTS_DATA:
        db.execute(text("""
            INSERT INTO sample_parts
              (part_id, part_number, description, category, weight, material, supplier_id, cost, created_date, modified_date)
            VALUES
              (:part_id, :part_number, :description, :category, :weight, :material, :supplier_id, :cost, :created_date, :modified_date)
        """), {k: (str(v) if isinstance(v, uuid.UUID) else
                   v.isoformat() if isinstance(v, (datetime, date)) else v)
               for k, v in sp.items()})
    print(f"  sample_parts:       {len(SAMPLE_PARTS_DATA)} rows")

    # ── sample_bill_of_materials ────────────────
    for bom in SAMPLE_BOM_DATA:
        db.execute(text("""
            INSERT INTO sample_bill_of_materials
              (bom_id, parent_part_id, child_part_id, quantity, unit_of_measure, position, effective_date, end_date, revision, created_by)
            VALUES
              (:bom_id, :parent_part_id, :child_part_id, :quantity, :unit_of_measure, :position, :effective_date, :end_date, :revision, :created_by)
        """), {k: (str(v) if isinstance(v, uuid.UUID) else
                   v.isoformat() if isinstance(v, (datetime, date)) else v)
               for k, v in bom.items()})
    print(f"  sample_bill_of_materials: {len(SAMPLE_BOM_DATA)} rows")

    # ── sample_test_results ─────────────────────
    for tr in SAMPLE_TEST_DATA:
        db.execute(text("""
            INSERT INTO sample_test_results
              (test_id, part_id, test_type, measurement_value, unit, pass_fail, test_date, operator, equipment_id, notes)
            VALUES
              (:test_id, :part_id, :test_type, :measurement_value, :unit, :pass_fail, :test_date, :operator, :equipment_id, :notes)
        """), {k: (str(v) if isinstance(v, uuid.UUID) else
                   v.isoformat() if isinstance(v, (datetime, date)) else v)
               for k, v in tr.items()})
    print(f"  sample_test_results:{len(SAMPLE_TEST_DATA)} rows")

    db.commit()


if __name__ == "__main__":
    print("Seeding Teamcenter PLM induction motor data…")
    db = SessionLocal()
    try:
        seed(db)
        print("Done.")
    finally:
        db.close()
