#!/usr/bin/env python3
"""Generate demo assets: a scanned-style inspection report PDF (image-only,
no text layer — to exercise OCR/vision), a P&ID sample image, and the local
knowledge base corpus (SOPs, manual, past correspondence)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
UPLOADS = ROOT / "workspace" / "uploads"
KB = ROOT / "workspace" / "kb"
UPLOADS.mkdir(parents=True, exist_ok=True)
KB.mkdir(parents=True, exist_ok=True)

FONT_PATHS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/Library/Fonts/Arial.ttf",
]

def font(size, bold=False):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

# ------------------------------------------- 1. scanned inspection report ---
PAGES = [
    """
MANGALORE REFINERY AND PETROCHEMICALS LIMITED
EQUIPMENT INSPECTION REPORT

Report No      : INSP-2026-0447
Equipment      : Crude Distillation Unit - Overhead Condenser E-101
Location       : CDU Section, Refinery Block B
Inspection Date: 14 August 2026
Inspector      : R. Shetty, Senior Inspection Engineer
Classification : CONFIDENTIAL - INTERNAL

1. SUMMARY OF FINDINGS

Visual and thickness survey of condenser E-101 shell and tube bundle
was carried out during the scheduled shutdown.

FINDING F-1: Shell wall thickness measured 8.2 mm against the minimum
required thickness of 8.8 mm. Localised thinning observed near the
shell inlet nozzle. This is BELOW the minimum allowable thickness.

FINDING F-2: Tube bundle leakage detected at 4 locations during the
hydro test at 12.5 bar. Pressure drop observed from 12.5 bar to
9.8 bar within 30 minutes. This exceeds the acceptance criterion of
less than 5 percent pressure loss per hour.

FINDING F-3: Inlet nozzle gasket seat corrosion, approximately 15
percent circumferential coverage. Gasket replacement is required.

FINDING F-4: Protective coating integrity on the exterior shell is
satisfactory. No action required.

2. RECOMMENDATIONS

R-1: Re-rate or replace shell section near inlet nozzle before
     the next operating cycle.       Priority: HIGH
R-2: Plug or replace the 4 leaking tubes.   Priority: HIGH
R-3: Machine and re-seat the inlet nozzle gasket face.
                                     Priority: MEDIUM
R-4: Continue routine external coating inspection.
                                     Priority: LOW

3. REFERENCES

Inspection carried out per Equipment Inspection SOP EMP-SOP-014 and
the Pressure Vessel Integrity Manual PV-MAN-02.
""",
    """
MANGALORE REFINERY AND PETROCHEMICALS LIMITED
EQUIPMENT INSPECTION REPORT - PAGE 2

Report No: INSP-2026-0447        Continued

4. THICKNESS MEASUREMENT LOG (extract)

Location        Reading   Min req   Status
Shell circum.1    8.2 mm    8.8 mm   UNACCEPTABLE
Shell circum.2    9.1 mm    8.8 mm   Acceptable
Shell circum.3    9.0 mm    8.8 mm   Acceptable
Head north        9.4 mm    8.8 mm   Acceptable
Head south        9.2 mm    8.8 mm   Acceptable

5. HYDRO TEST RECORD

Test medium: water. Test pressure: 12.5 bar. Hold time: 60 minutes.
Observed pressure after 30 minutes: 9.8 bar. Verdict: LEAK DETECTED.

6. PHOTOGRAPHS

Six photographs attached to the physical dossier (not included in
this scan).

7. INSPECTOR DECLARATION

The findings above are a true record of the inspection performed on
14 August 2026.

Signature: R. Shetty        Date: 14 Aug 2026
""",
]

def make_scan_page(text, page_no):
    W, H = 1654, 2339  # A4 at ~200dpi
    img = Image.new("RGB", (W, H), (247, 244, 238))
    d = ImageDraw.Draw(img)
    f_head, f_body = font(44, bold=True), font(30)
    y = 140
    for line in text.strip().split("\n"):
        if line.startswith("MANGALORE"):
            d.text((140, y), line, fill=(20, 20, 20), font=f_head)
            y += 78
        elif line.strip():
            d.text((140, y), line, fill=(35, 35, 35), font=f_body)
            y += 46
        else:
            y += 24
    d.rectangle([100, 80, W - 100, H - 80], outline=(60, 60, 60), width=3)
    # simulated scan artefacts
    for _ in range(1200):
        import random
        x, yv = random.randint(0, W - 1), random.randint(0, H - 1)
        d.point((x, yv), fill=(180, 175, 170))
    d.text((W - 400, H - 140), f"Page {page_no} of 2 (scanned)", fill=(90, 90, 90), font=font(24))
    return img

pages = [make_scan_page(t, i + 1) for i, t in enumerate(PAGES)]
scan_path = UPLOADS / "inspection_report.pdf"
pages[0].save(scan_path, save_all=True, append_images=pages[1:], resolution=200)
print("wrote", scan_path)

# --------------------------------------------------------- 2. P&ID image ---
W, H = 1800, 1100
img = Image.new("RGB", (W, H), (252, 252, 250))
d = ImageDraw.Draw(img)
fb, fs, fl = font(34, bold=True), font(24), font(22)

d.text((60, 40), "P&ID SAMPLE — CRUDE UNIT OVERHEAD SYSTEM (SIMPLIFIED)", fill=(20, 20, 20), font=fb)
d.line([60, 90, W - 60, 90], fill=(40, 40, 40), width=4)

def vessel(x, y, w, h, label, tag):
    d.ellipse([x + w * .1, y, x + w * .9 - 1, y + 40], outline=(30, 30, 30), width=4)
    d.rectangle([x + w * .1, y + 20, x + w * .9 - 1, y + h - 20], outline=(30, 30, 30), width=4)
    d.ellipse([x + w * .1, y + h - 40, x + w * .9 - 1, y + h], outline=(30, 30, 30), width=4)
    d.text((x + 10, y + h / 2 - 40), tag, fill=(0, 0, 0), font=fb)
    d.text((x, y + h + 14), label, fill=(60, 60, 60), font=fs)

def pump(x, y, tag):
    d.ellipse([x, y, x + 70, y + 70], outline=(30, 30, 30), width=4)
    d.polygon([(x + 70, y + 20), (x + 110, y + 35), (x + 70, y + 50)], outline=(30, 30, 30), width=3)
    d.text((x, y + 80), tag, fill=(0, 0, 0), font=fb)

def exchanger(x, y, tag):
    d.rectangle([x, y + 10, x + 150, y + 90], outline=(30, 30, 30), width=4)
    d.line([x, y + 10, x + 150, y + 90], fill=(30, 30, 30), width=2)
    d.line([x, y + 90, x + 150, y + 10], fill=(30, 30, 30), width=2)
    d.text((x + 40, y + 100), tag, fill=(0, 0, 0), font=fb)

def pipe(pts, label="", spec=""):
    d.line(pts, fill=(50, 80, 140), width=5)
    if label:
        mx, my = pts[len(pts)//2]
        d.text((mx + 8, my - 34), f"{label}  {spec}", fill=(50, 80, 140), font=fl)

def instrument(x, y, tag):
    d.ellipse([x, y, x + 56, y + 56], outline=(150, 60, 30), width=4)
    d.text((x + 12, y + 12), tag, fill=(150, 60, 30), font=fl)

vessel(140, 180, 240, 420, "Crude tower", "C-101")
exchanger(620, 200, "E-101")
vessel(950, 160, 220, 300, "Overhead drum", "V-101")
pump(1000, 620, "P-101A")
pump(1240, 620, "P-101B")

pipe([(380, 260), (620, 260)], "12\" OH line", "CS-150#")
pipe([(770, 260), (950, 260)], "10\" OVHD vapour", "CS-150#")
pipe([(1060, 460), (1060, 620)], "6\" condensate", "CS-150#")
pipe([(1110, 655), (1240, 655)], "spare", "CS-150#")
pipe([(620, 290), (500, 290), (500, 760)], "8\" reflux return", "CS-150#")

instrument(430, 200, "TI")
instrument(800, 190, "PI")
instrument(1035, 560, "LC")

d.text((60, H - 90), "NOTE: demonstration asset generated for the Sovereign Workbench demo — not an engineering document.",
       fill=(120, 60, 60), font=fl)
pid_path = UPLOADS / "pid_sample.png"
img.save(pid_path)
print("wrote", pid_path)

# ------------------------------------------------------- 3. knowledge base --
KB_DOCS = {
    "EMP-SOP-014_equipment_inspection_SOP.txt": """PROCEDURE EMP-SOP-014 — EQUIPMENT INSPECTION AND APPROVAL (Rev 7)

1. PURPOSE
This procedure defines how inspection findings are reviewed and how an
equipment approval note is issued after a statutory or shutdown inspection
at MRPL.

2. APPROVAL NOTE REQUIREMENTS
An approval note for returned-to-service decisions MUST contain:
  a. Equipment tag and report number.
  b. A statement of each finding with severity (UNACCEPTABLE / ACCEPTABLE).
  c. Cross-reference to the applicable acceptance criteria in PV-MAN-02.
  d. Conditions imposed before restart (repairs, re-rating, monitoring).
  e. The inspector name, date, and the approving authority signature block.

3. SEVERITY CLASSIFICATION
Any wall thickness below the minimum required thickness in PV-MAN-02 is
classified UNACCEPTABLE and the equipment must not return to service until
repaired or formally re-rated.
Any hydro test pressure loss greater than 5 percent per hour is classified
UNACCEPTABLE.

4. ESCALATION
Findings classified UNACCEPTABLE are escalated to the Inspection Manager
within 24 hours. Approval notes for UNACCEPTABLE findings require the
counter-signature of the Inspection Manager.

5. RECORDS
The signed approval note is filed with the inspection dossier and a copy is
sent to the Mechanical Records Office.
""",

    "PV-MAN-02_pressure_vessel_integrity_manual.txt": """PRESSURE VESSEL INTEGRITY MANUAL PV-MAN-02 (Rev 4)

SECTION 5 — MINIMUM THICKNESS AND CORROSION ALLOWANCE
5.1 The minimum required thickness of a pressure shell is the thickness
required by the design code PLUS corrosion allowance for the intended
service life. Operating below the minimum required thickness is prohibited.

5.2 For carbon steel shells in crude overhead service, the typical corrosion
allowance is 3.0 mm and the design life basis is 20 years. Where measured
thickness is below the minimum required thickness, the component must be
re-rated, repaired or replaced.

5.3 Re-rating requires a fitness-for-service calculation by the Engineering
Department and formal re-rating approval.

SECTION 8 — HYDROSTATIC TESTING
8.1 Hydro test acceptance: pressure loss shall not exceed 5 percent per
hour during the hold period. Any visible leakage is cause for immediate
rejection of the test.

8.2 Leaking tubes may be plugged provided the plugged tube count does not
exceed 10 percent of the total tube count per pass; otherwise retubing is
required.

SECTION 9 — GASKETS AND SEALING SURFACES
9.1 Gasket seating surfaces with corrosion coverage greater than 10 percent
of the sealing circumference shall be re-machined before a new gasket is
fitted.
""",

    "OPS-MAN-07_storage_tank_operations_manual.txt": """STORAGE TANK OPERATIONS MANUAL OPS-MAN-07 (Rev 9)

SECTION 3 — TEMPERATURE LIMITS
3.1 The maximum permitted product temperature in atmospheric storage tanks
containing crude and middle distillates is 90 degrees Celsius at the tank
bottom sensing point.

3.2 If the tank temperature exceeds 90 degrees Celsius, the operator must
immediately start the tank cooling water spray, stop any circulation or
heating medium flow, and inform the Shift In-charge.

3.3 Temperatures above 95 degrees Celsius for more than 15 minutes require
a Level-2 incident report per HSE-MAN-11, and the tank must be isolated for
inspection before it is returned to service.

SECTION 6 — ROOF SEAL AND VENTING
6.1 Floating roof seals are inspected quarterly; seal gaps exceeding
specified limits require tank withdrawal from service.
""",

    "correspondence_memo_E101_history.txt": """INTERNAL CORRESPONDENCE — MECHANICAL RECORDS (excerpt)

From: Mechanical Records Office
To: Inspection Section
Date: 03 March 2025
Subject: E-101 condenser history

E-101 (CDU overhead condenser) was last retubed in 2019. During the 2024
shutdown, minor inlet nozzle gasket seat corrosion was already noted at
approximately 8 percent circumferential coverage and left for monitoring.
Thickness readings in 2024 were around 9.3 mm near the shell inlet nozzle.
The shell is carbon steel with a 3.0 mm corrosion allowance, consistent
with PV-MAN-02 Section 5.2.

Please continue to trend the inlet nozzle region closely; the thinning rate
in that area has historically been the highest in this exchanger.
""",

    "HSE-MAN-11_incident_reporting.txt": """HSE MANUAL HSE-MAN-11 (Rev 3) — EXTRACT

LEVEL-2 INCIDENT REPORTING
A Level-2 incident includes any deviation from safe operating limits that
persists for more than 15 minutes, any loss of primary containment, and any
equipment operated outside its approved envelope. Level-2 incidents must be
reported within 24 hours using form HSE-QF-02 and require a formal cause
investigation before the affected equipment returns to service.
""",
}

for name, text in KB_DOCS.items():
    (KB / name).write_text(text)
    print("kb:", name)

print("DONE")
