"""Canonical (fictional) demo scenario content for KAVACH AI.

All content below is FICTIONAL and describes the imaginary "KAVACH DEMO REFINERY".
It is shared by the DB seed, the RAG knowledge base, and the agent orchestrator so
the whole demo is internally consistent.
"""
from __future__ import annotations

FACILITY = "KAVACH DEMO REFINERY"
UNIT = "Unit 4"

EQUIPMENT = [
    {"id": "P-101", "type": "pump", "name": "Feed Pump P-101"},
    {"id": "P-102", "type": "pump", "name": "Backup Feed Pump P-102"},
    {"id": "V-204", "type": "valve", "name": "Control Valve V-204"},
    {"id": "T-101", "type": "tank", "name": "Storage Tank T-101"},
    {"id": "HX-301", "type": "heat_exchanger", "name": "Heat Exchanger HX-301"},
]

# Demo documents (metadata). Actual files are produced by generate_demo_data.py.
DEMO_DOCUMENTS = [
    {"name": "Unit 4 Plant P&ID", "filename": "plant_pid.png",
     "doc_type": "pid", "pages": 1,
     "summary": "Piping & Instrumentation Diagram for Unit 4 (P-101/P-102/V-204/T-101/HX-301)."},
    {"name": "Inspection Report 2026", "filename": "inspection_report.pdf",
     "doc_type": "report", "pages": 12,
     "summary": "Annual mechanical integrity inspection findings for Unit 4."},
    {"name": "Equipment Manual", "filename": "equipment_manual.pdf",
     "doc_type": "manual", "pages": 20,
     "summary": "OEM operating and maintenance manual for Unit 4 rotating equipment."},
    {"name": "Engineering Calculation", "filename": "engineering_calculation.pdf",
     "doc_type": "calculation", "pages": 6,
     "summary": "Wall-thickness and remaining-life calculation for P-101 discharge line."},
    {"name": "Sample Internal Code", "filename": "sample_internal_code.py",
     "doc_type": "code", "pages": 1,
     "summary": "Fictional internal utility script for inspection-data ingestion."},
]

# Knowledge base source texts (fictional). Used to build the RAG index.
KNOWLEDGE_TEXTS = {
    "Inspection_Report_2026.pdf": (
        "KAVACH DEMO REFINERY - Unit 4 Annual Mechanical Integrity Inspection, 2026. "
        "Page 7: Minor corrosion observed near the outlet section of feed pump P-101; "
        "wall thickness measured at 6.8 mm against a nominal 8.0 mm. Recommend follow-up "
        "ultrasonic thickness survey within 90 days. Page 8: Control valve V-204 actuator "
        "shows sluggish response; stem packing to be replaced at next turnaround. Page 9: "
        "Storage tank T-101 floor plates within acceptable limits. Heat exchanger HX-301 "
        "tube bundle fouling factor trending upward but acceptable."
    ),
    "Equipment_Manual.pdf": (
        "OEM Equipment Manual (fictional) - Feed Pump P-101 and P-102 are horizontal "
        "centrifugal pumps rated 120 m3/h at 45 m head. Recommended minimum wall thickness "
        "for discharge piping is 6.4 mm. Control valve V-204 is a globe valve; recommended "
        "packing replacement interval is 24 months. Heat exchanger HX-301 shell-and-tube, "
        "design pressure 18 bar."
    ),
    "Engineering_Calculation.pdf": (
        "Engineering calculation (fictional) for P-101 discharge line. Corrosion rate "
        "estimated at 0.3 mm/year. With measured 6.8 mm and minimum allowable 6.4 mm, the "
        "remaining life is approximately 1.3 years. Recommend scheduling repair or "
        "replacement before next inspection cycle. Safety factor applied per ASME B31.3 "
        "(illustrative only)."
    ),
    "Plant_PID.png": (
        "P&ID description (fictional): Feed enters Unit 4 through pump P-101 with backup "
        "pump P-102, passes control valve V-204 into storage tank T-101, then to heat "
        "exchanger HX-301. Instrumentation includes flow transmitter FT-101 and pressure "
        "indicator PI-204."
    ),
}

# Deterministic findings for the demo run.
FINDINGS = [
    {
        "title": "Potential corrosion detected around P-101 outlet",
        "description": ("Ultrasonic and visual inspection indicate wall-thickness loss near "
                        "the P-101 discharge outlet, approaching the minimum allowable limit."),
        "severity": "high",
        "confidence": 92.0,
        "equipment_id": "P-101",
        "needs_review": 0,
        "evidence": [
            {"source": "Inspection_Report_2026.pdf", "page": 7,
             "excerpt": "Minor corrosion observed near the outlet section of feed pump P-101; "
                        "wall thickness measured at 6.8 mm against a nominal 8.0 mm.",
             "confidence": 92.0},
            {"source": "Engineering_Calculation.pdf", "page": 3,
             "excerpt": "With measured 6.8 mm and minimum allowable 6.4 mm, remaining life is "
                        "approximately 1.3 years.",
             "confidence": 88.0},
        ],
    },
    {
        "title": "Control valve V-204 actuator sluggish response",
        "description": ("Valve V-204 exhibits delayed actuation; stem packing degradation is the "
                        "likely cause per OEM guidance."),
        "severity": "medium",
        "confidence": 86.0,
        "equipment_id": "V-204",
        "needs_review": 0,
        "evidence": [
            {"source": "Inspection_Report_2026.pdf", "page": 8,
             "excerpt": "Control valve V-204 actuator shows sluggish response; stem packing to "
                        "be replaced at next turnaround.",
             "confidence": 86.0},
            {"source": "Equipment_Manual.pdf", "page": 14,
             "excerpt": "Control valve V-204 recommended packing replacement interval is 24 months.",
             "confidence": 83.0},
        ],
    },
    {
        "title": "HX-301 fouling factor trending upward (needs human review)",
        "description": ("Heat exchanger HX-301 shows an upward fouling trend. Currently within "
                        "limits but the trend is ambiguous and flagged for reviewer attention."),
        "severity": "low",
        "confidence": 82.0,
        "equipment_id": "HX-301",
        "needs_review": 1,
        "evidence": [
            {"source": "Inspection_Report_2026.pdf", "page": 9,
             "excerpt": "Heat exchanger HX-301 tube bundle fouling factor trending upward but "
                        "acceptable.",
             "confidence": 82.0},
        ],
    },
    {
        "title": "P-102 backup pump confirmed available",
        "description": "Backup feed pump P-102 inspected and confirmed in standby-ready condition.",
        "severity": "info",
        "confidence": 96.0,
        "equipment_id": "P-102",
        "needs_review": 0,
        "evidence": [
            {"source": "Equipment_Manual.pdf", "page": 5,
             "excerpt": "Feed Pump P-101 and P-102 are horizontal centrifugal pumps rated "
                        "120 m3/h at 45 m head.",
             "confidence": 96.0},
        ],
    },
]

VERIFICATION_SCORE = 94.0
EVIDENCE_BACKED = "8/9"
