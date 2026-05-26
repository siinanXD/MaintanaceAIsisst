"""Static demo seed definitions."""

MACHINE_DEFINITIONS = [
    ("CNC-Fräse 01", "Aluminium-Gehäuse", 3),
    ("CNC-Drehmaschine 02", "Präzisionswellen", 2),
    ("Hydraulikpresse 03", "Blechformteile", 2),
    ("Spritzgussanlage 04", "Kunststoffclips", 4),
    ("Montagelinie 05", "Sensorbaugruppen", 6),
    ("Förderband Linie A", "Materialfluss Produktion A", 1),
    ("Verpackungsanlage 06", "Versandfertige Sets", 3),
    ("Kompressorstation 07", "Druckluftversorgung", 1),
    ("Prüfstand 08", "End-of-Line-Prüfung", 2),
    ("Roboterzelle 09", "Automatisierte Bestückung", 2),
    ("Laserbeschrifter 10", "Typenschilder", 1),
    ("Waschanlage 11", "Bauteilreinigung", 2),
]

MACHINE_OPERATION_STATE = {
    "cnc-frase-01": ("critical", "limited", 1),
    "hydraulikpresse-03": ("critical", "maintenance", 0),
    "spritzgussanlage-04": ("high", "running", 2),
    "montagelinie-05": ("high", "running", None),
    "forderband-linie-a": ("high", "limited", 3),
    "kompressorstation-07": ("critical", "running", None),
    "prufstand-08": ("normal", "running", None),
    "roboterzelle-09": ("high", "running", 2),
    "laserbeschrifter-10": ("normal", "limited", 6),
}

# ---------------------------------------------------------------------------
# Lagermaterial
# ---------------------------------------------------------------------------

INVENTORY_DEFINITIONS = [
    # (Name, Einzelpreis, Bestand, Hersteller, Maschinenname)
    ("Aluminiumprofil 40×40", 18.90, 420, "Item Industrietechnik", "CNC-Fräse 01"),
    ("Hartmetall-Fräser 8 mm", 42.50, 36, "Hoffmann Group", "CNC-Fräse 01"),
    ("Kühlschmierstoff 20 l", 96.00, 18, "Castrol", "CNC-Fräse 01"),
    ("Drehmeissel CNMG", 12.80, 90, "Sandvik Coromant", "CNC-Drehmaschine 02"),
    ("Präzisionslager 6205", 7.40, 240, "SKF", "CNC-Drehmaschine 02"),
    ("Hydrauliköl HLP 46", 68.00, 22, "Fuchs", "Hydraulikpresse 03"),
    ("Dichtungssatz Presse", 115.00, 0, "Parker", "Hydraulikpresse 03"),
    ("Granulat PA6 schwarz", 3.70, 2600, "BASF", "Spritzgussanlage 04"),
    ("Heizkabel 230 V", 54.90, 2, "Hotset", "Spritzgussanlage 04"),
    ("Greiferfinger Set", 88.00, 16, "Schunk", "Montagelinie 05"),
    ("M8 Sensor induktiv", 24.70, 3, "Sick", "Montagelinie 05"),
    ("Fördergurt PU 1200×600", 310.00, 1, "Habasit", "Förderband Linie A"),
    ("Antriebsrolle 60 mm", 74.20, 12, "Interroll", "Förderband Linie A"),
    ("Karton 400×300×200", 1.15, 1800, "Smurfit Kappa", "Verpackungsanlage 06"),
    ("Etikettenrolle 100×60", 9.80, 75, "Avery Dennison", "Verpackungsanlage 06"),
    ("Druckluftfilter G1/2", 33.50, 1, "Atlas Copco", "Kompressorstation 07"),
    ("Keilriemen XPZ 1000", 18.30, 30, "Optibelt", "Kompressorstation 07"),
    ("Prüfadapter 24 V", 129.00, 10, "Phoenix Contact", "Prüfstand 08"),
    ("Messleitung 2 m", 11.90, 110, "Staubli", "Prüfstand 08"),
    ("Vakuumsauger 30 mm", 6.80, 160, "Festo", "Roboterzelle 09"),
    ("Servo-Kabel 5 m", 47.50, 35, "Igus", "Roboterzelle 09"),
    ("Laser-Schutzglas", 145.00, 0, "Trumpf", "Laserbeschrifter 10"),
    ("Reinigungskonzentrat 10 l", 52.00, 26, "Henkel", "Waschanlage 11"),
    ("Edelstahlkorb klein", 39.90, 42, "Keller & Kalmbach", "Waschanlage 11"),
    # Zusätzliche kritische Positionen
    ("O-Ring-Satz 120-teilig", 28.60, 2, "Eriks", "Hydraulikpresse 03"),
    ("Sicherungsautomat C16", 12.40, 4, "Siemens", "Kompressorstation 07"),
    ("Schmierfett 400 g", 9.80, 5, "SKF", "CNC-Drehmaschine 02"),
    ("Schutzschlauch 1 m", 6.30, 3, "Igus", "Montagelinie 05"),
    ("Klemmblock 4 mm²", 1.90, 8, "Wago", "Prüfstand 08"),
]

INVENTORY_POLICY = {
    "dichtungssatz-presse": (2, "critical", 9),
    "hydraulikol-hlp-46": (6, "high", 5),
    "o-ring-satz-120-teilig": (5, "critical", 4),
    "m8-sensor-induktiv": (8, "high", 3),
    "druckluftfilter-g1-2": (4, "critical", 6),
    "laser-schutzglas": (1, "critical", 12),
    "heizkabel-230-v": (3, "high", 7),
    "vakuumsauger-30-mm": (40, "normal", 2),
    "servo-kabel-5-m": (12, "high", 8),
    "klemmblock-4-mm2": (20, "normal", 2),
}

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
