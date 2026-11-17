"""Source definition of the Demo 4 synthetic school modernization schedule (contract A).

Synthetic. Built for INFO 492 C coursework; not a real project's schedule.
build_data.py turns this into demo4/data/schedule.json and every export format.

Each row: (id, name, wbs code, original duration in working days, predecessors).
Predecessors use the CSV notation: "A1010" (FS, no lag), "A1010SS+5", "A1010FF+3", "A1010FS-2", "A1010SF".
"""

PROJECT_NAME = "Example School Modernization and Addition (synthetic)"
START = "2020-02-03"          # Notice to Proceed (contract A Section 3.1)
DATA_DATE = "2020-06-01"
CONTRACT_DAYS = 540           # contract A Section 3.2: Substantial Completion within 540 days after NTP

# Washington State legal holidays (RCW 1.16.050), observed dates, 2020 and 2021.
# A holiday on Sunday is observed Monday; on Saturday, the preceding Friday.
# Juneteenth became a Washington legal holiday in 2022, so it is not in this calendar.
HOLIDAYS = [
    "2020-01-01", "2020-01-20", "2020-02-17", "2020-05-25", "2020-07-03", "2020-09-07",
    "2020-11-11", "2020-11-26", "2020-11-27", "2020-12-25",
    "2021-01-01", "2021-01-18", "2021-02-15", "2021-05-31", "2021-07-05", "2021-09-06",
    "2021-11-11", "2021-11-25", "2021-11-26", "2021-12-24", "2021-12-31",
]

WBS = [
    ("MS", "Milestones"),
    ("MOB", "Mobilization"),
    ("ABT", "Abatement"),
    ("DEM", "Demolition"),
    ("STR", "Foundations and Structure"),
    ("ENV", "Envelope and Roofing"),
    ("MEP", "MEP Rough-In"),
    ("INT", "Interiors and Finishes"),
    ("SITE", "Sitework"),
    ("CX", "Commissioning"),
    ("CLO", "Closeout"),
]

ACTIVITIES = [
    # Milestones
    ("A1000", "Notice to Proceed", "MS", 0, []),
    ("A1090", "Substantial Completion", "MS", 0, ["A2260", "A2320", "A2330", "A2350", "A2360"]),
    # Mobilization
    ("A1100", "Mobilize site office and trailers", "MOB", 8, ["A1000"]),
    ("A1110", "Temporary fencing and site security", "MOB", 4, ["A1100SS+2"]),
    ("A1120", "Temporary power and utilities", "MOB", 6, ["A1100SS+3"]),
    ("A1130", "Submittal schedule and long-lead buyout", "MOB", 15, ["A1000"]),
    ("A1140", "Erosion control and construction entrance", "MOB", 3, ["A1110"]),
    ("A1150", "Temporary heat and dehumidification - addition", "MOB", 10, ["A1570", "A1690SF"]),
    # Abatement
    ("A1200", "Hazardous materials survey verification", "ABT", 5, ["A1100"]),
    ("A1210", "Abatement - Wing A classrooms", "ABT", 20, ["A1200", "A1120"]),
    ("A1220", "Abatement - Wing B admin and library", "ABT", 15, ["A1210"]),
    ("A1230", "Abatement - existing gym and commons", "ABT", 12, ["A1220"]),
    ("A1240", "Abatement clearance air testing", "ABT", 4, ["A1230"]),
    # Demolition
    ("A1300", "Interior demolition - Wing A", "DEM", 15, ["A1210"]),
    ("A1310", "Interior demolition - Wing B", "DEM", 12, ["A1220", "A1300"]),
    ("A1320", "Demolish existing gym (addition footprint)", "DEM", 15, ["A1240"]),
    ("A1330", "Structural openings and selective demolition - Wing A", "DEM", 10, ["A1300"]),
    ("A1340", "Haul-off and clear addition footprint", "DEM", 6, ["A1320"]),
    ("A1350", "Demolish existing paving and site utilities", "DEM", 10, ["A1340SS+2"]),
    # Foundations and structure
    ("A1400", "Excavation and shoring - addition", "STR", 12, ["A1340"]),
    ("A1410", "Underslab utilities - addition", "STR", 8, ["A1400"]),
    ("A1420", "Footings and foundation walls - addition", "STR", 25, ["A1400SS+6"]),
    ("A1430", "Slab on grade - addition", "STR", 10, ["A1420", "A1410"]),
    ("A1440", "Structural steel shop drawings and approval", "STR", 35, ["A1130SS+5"]),
    ("A1450", "Fabricate and deliver structural steel", "STR", 40, ["A1440"]),
    ("A1460", "Erect structural steel - addition", "STR", 25, ["A1430", "A1450"]),
    ("A1470", "Metal deck and elevated slab - addition", "STR", 15, ["A1460SS+10", "A1460FF+5"]),
    ("A1480", "Seismic upgrade - Wing A shear walls", "STR", 40, ["A1330"]),
    ("A1490", "Seismic upgrade - Wing B", "STR", 35, ["A1480", "A1310"]),
    # Envelope and roofing
    ("A1500", "Window and storefront submittals and fabrication", "ENV", 60, ["A1130SS+10"]),
    ("A1510", "Exterior framing and sheathing - addition", "ENV", 20, ["A1470SS+5"]),
    ("A1520", "Roofing - addition", "ENV", 18, ["A1470"]),
    ("A1530", "Windows and storefront - addition", "ENV", 15, ["A1510", "A1500"]),
    ("A1540", "Exterior cladding - addition", "ENV", 30, ["A1530SS+5"]),
    ("A1550", "Reroof existing building", "ENV", 25, ["A1480", "A1490SS+10"]),
    ("A1560", "Window replacement - existing building", "ENV", 25, ["A1490", "A1500"]),
    ("A1570", "Addition dry-in", "ENV", 0, ["A1520", "A1530"]),
    ("A1580", "Exterior painting and sealants - existing building", "ENV", 15, ["A1560"]),
    # MEP rough-in
    ("A1600", "Procure switchgear and air handling units", "MEP", 80, ["A1130"]),
    ("A1610", "MEP rough-in - Wing A", "MEP", 40, ["A1480"]),
    ("A1620", "MEP rough-in - Wing B", "MEP", 35, ["A1490", "A1610SS+10"]),
    ("A1630", "MEP rough-in - addition", "MEP", 35, ["A1570"]),
    ("A1640", "Fire sprinkler rough-in - addition", "MEP", 20, ["A1630SS+10"]),
    ("A1650", "Set rooftop units and air handlers", "MEP", 8, ["A1600", "A1520", "A1550"]),
    ("A1660", "Main switchgear and electrical service", "MEP", 12, ["A1600", "A1430"]),
    ("A1670", "Fire sprinkler rough-in - existing building", "MEP", 35, ["A1610SS+5"]),
    ("A1680", "In-wall and above-ceiling inspections - existing building", "MEP", 5, ["A1610", "A1620", "A1670"]),
    ("A1685", "In-wall and above-ceiling inspections - addition", "MEP", 5, ["A1630", "A1640"]),
    ("A1690", "Energize permanent power", "MEP", 3, ["A1660", "A1650"]),
    # Interiors and finishes
    ("A1700", "Framing and drywall - Wing A", "INT", 35, ["A1680"]),
    ("A1710", "Framing and drywall - Wing B", "INT", 30, ["A1680", "A1700SS+10"]),
    ("A1720", "Framing and drywall - addition", "INT", 30, ["A1685"]),
    ("A1730", "Ceilings - existing building", "INT", 30, ["A1750SS+10", "A1750FF+5"]),
    ("A1740", "Ceilings - addition", "INT", 20, ["A1760"]),
    ("A1750", "Painting - existing building", "INT", 35, ["A1700", "A1710SS+10"]),
    ("A1760", "Painting - addition", "INT", 20, ["A1720"]),
    ("A1770", "Flooring - existing building", "INT", 30, ["A1730"]),
    ("A1780", "Casework and millwork - existing building", "INT", 25, ["A1770SS+5"]),
    ("A1790", "Flooring - addition classrooms", "INT", 15, ["A1740"]),
    ("A1800", "Gym wood floor", "INT", 20, ["A1740", "A1150"]),
    ("A1810", "Casework and millwork - addition", "INT", 15, ["A1790"]),
    ("A1820", "MEP trim and fixtures - existing building", "INT", 30, ["A1730", "A1780SS+5"]),
    ("A1830", "MEP trim and fixtures - addition", "INT", 20, ["A1740", "A1810SS+5"]),
    ("A1840", "Doors, hardware and specialties - existing building", "INT", 15, ["A1770"]),
    ("A1850", "Doors, hardware and specialties - addition", "INT", 15, ["A1790"]),
    ("A1860", "Gym equipment and bleachers", "INT", 10, ["A1800"]),
    ("A1870", "Interior signage", "INT", 5, ["A1840", "A1850"]),
    ("A1880", "Elevator installation - addition", "INT", 35, ["A1470", "A1630SS+10"]),
    ("A1890", "Owner furniture delivery and install", "INT", 15, ["A1770", "A1790"]),
    # Sitework
    ("A2100", "Site utilities - storm and sewer", "SITE", 20, ["A1350"]),
    ("A2110", "Site electrical and lighting conduit", "SITE", 12, ["A2100SS+5"]),
    ("A2120", "Fire lane and bus loop paving", "SITE", 15, ["A2100", "A1540"]),
    ("A2130", "Curbs, sidewalks and flatwork", "SITE", 20, ["A2120", "A2110"]),
    ("A2140", "Playground and play surfacing", "SITE", 15, ["A2130SS+5"]),
    ("A2150", "Landscaping and irrigation", "SITE", 20, ["A2130", "A1540"]),
    ("A2160", "Site fencing, gates and signage", "SITE", 10, ["A2130"]),
    ("A2170", "Striping and final site cleanup", "SITE", 5, ["A2150", "A2160", "A2140"]),
    # Commissioning
    ("A2200", "Test and balance HVAC", "CX", 15, ["A1820", "A1830", "A1690"]),
    ("A2210", "Fire alarm and sprinkler acceptance testing", "CX", 5, ["A1820", "A1830"]),
    ("A2220", "Functional performance testing and controls", "CX", 15, ["A2200SS+5", "A2200FF+3"]),
    ("A2230", "Elevator inspection and permit", "CX", 5, ["A1880"]),
    ("A2240", "Envelope water testing and commissioning", "CX", 5, ["A1540", "A1580"]),
    ("A2250", "Fire marshal and building official final inspections", "CX", 5, ["A2210", "A2220", "A2230", "A2240"]),
    ("A2260", "Certificate of occupancy", "CX", 0, ["A2250"]),
    # Closeout
    ("A2300", "Punch list - existing building", "CLO", 15, ["A1840", "A1820"]),
    ("A2310", "Punch list - addition", "CLO", 15, ["A1850", "A1860", "A1830"]),
    ("A2320", "O&M manuals and warranties", "CLO", 20, ["A2200SS+5"]),
    ("A2330", "Owner training", "CLO", 5, ["A2220"]),
    ("A2340", "Final cleaning", "CLO", 8, ["A2300", "A2310"]),
    ("A2350", "Record drawings", "CLO", 15, ["A2310SS+5"]),
    ("A2360", "Owner move-in readiness walkthrough", "CLO", 2, ["A2340", "A1890", "A2170", "A1870"]),
]

# One date constraint: the Owner's furniture vendor cannot deliver before June 1, 2021.
CONSTRAINTS = {"A1890": {"type": "SNET", "date": "2021-06-01"}}

# Progress at the data date. Activities planned to finish before the data date are complete; those
# planned to straddle it are in progress. These adjust the as-planned dates to make the update realistic
# (working days added to the actual finish or to the remaining duration).
SLIPS = {"A1220": 2, "A1300": 1, "A1440": 3}
