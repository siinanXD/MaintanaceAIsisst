"""Realistic demo data for development and demos."""

import re
from datetime import UTC, date, datetime, timedelta
from io import BytesIO

from sqlalchemy import or_
from werkzeug.datastructures import FileStorage

from app.departments.services import DEFAULT_DEPARTMENTS, ensure_default_departments
from app.extensions import db
from app.models import (
    AssistantTrainingEntry,
    Department,
    Employee,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    KnowledgeChunk,
    KnowledgeDocument,
    Machine,
    MachineManual,
    MaintenancePlan,
    Priority,
    Role,
    ShiftHandover,
    Task,
    TaskStatus,
    User,
)
from app.permissions import upsert_default_permissions
from app.services.document_service import generate_maintenance_report, upload_machine_manual
from app.services.knowledge_service import reindex_stale_knowledge
from app.services.maintenance_tag_service import seed_maintenance_tag_library

DEMO_PASSWORD = "Demo1234!"
COMPANY_DOMAIN = "fertigungs-gmbh.de"

# ---------------------------------------------------------------------------
# Stammdaten Mitarbeiter
# ---------------------------------------------------------------------------

EMPLOYEE_DATA = [
    # (
    #     Personalnummer, Vorname, Nachname, Geb., Straße, PLZ, Stadt,
    #     Abteilung, Schichtmodell, Schicht, Team, EG, Qualifikationen
    # )
    (
        "MA-0001",
        "Thomas",
        "Hoffmann",
        date(1978, 3, 12),
        "Ruhrstraße 14",
        "44135",
        "Dortmund",
        "Instandhaltung",
        "3-Schicht",
        "Früh",
        1,
        "EG 8",
        "SPS-Programmierung, Schaltschrankbau, Elektrofachkraft",
    ),
    (
        "MA-0002",
        "Sandra",
        "Becker",
        date(1985, 7, 23),
        "Kirchweg 5",
        "44787",
        "Bochum",
        "Instandhaltung",
        "3-Schicht",
        "Spät",
        1,
        "EG 7",
        "Hydraulik, Pneumatik, Schweißen MAG",
    ),
    (
        "MA-0003",
        "Kevin",
        "Schulze",
        date(1991, 1, 8),
        "Hauptstraße 82",
        "45127",
        "Essen",
        "Instandhaltung",
        "3-Schicht",
        "Nacht",
        2,
        "EG 6",
        "Antriebstechnik, Frequenzumrichter, SPS-Basis",
    ),
    (
        "MA-0004",
        "Miriam",
        "Krause",
        date(1982, 11, 3),
        "Lindenallee 27",
        "58095",
        "Hagen",
        "Instandhaltung",
        "3-Schicht",
        "Früh",
        2,
        "EG 7",
        "Mess- und Regelungstechnik, Kalibrierung",
    ),
    (
        "MA-0005",
        "Oliver",
        "Petersen",
        date(1975, 4, 17),
        "Bahnhofstraße 3",
        "42103",
        "Wuppertal",
        "Instandhaltung",
        "2-Schicht",
        "Früh",
        3,
        "EG 9",
        "Elektrofachkraft, Betriebsmittelbau, VDE-Prüfung",
    ),
    (
        "MA-0006",
        "Fatima",
        "Yilmaz",
        date(1989, 9, 5),
        "Westfalenring 44",
        "44135",
        "Dortmund",
        "Instandhaltung",
        "2-Schicht",
        "Spät",
        3,
        "EG 6",
        "Pneumatik, Wartungsplanung, 5S-Auditor",
    ),
    (
        "MA-0007",
        "Markus",
        "Wagner",
        date(1980, 6, 30),
        "Schillerstraße 11",
        "44787",
        "Bochum",
        "Instandhaltung",
        "Tagschicht",
        "Frei",
        4,
        "EG 9",
        "Robotik, KUKA-Programmierung, Sicherheitstechnik",
    ),
    (
        "MA-0008",
        "Julia",
        "Neumann",
        date(1994, 2, 14),
        "Bergmannstraße 8",
        "45127",
        "Essen",
        "Instandhaltung",
        "3-Schicht",
        "Nacht",
        4,
        "EG 6",
        "Elektrische Prüftechnik, Messprotokoll",
    ),
    (
        "MA-0009",
        "Dirk",
        "Hartmann",
        date(1973, 8, 22),
        "Am Förderturm 17",
        "44135",
        "Dortmund",
        "Produktion",
        "3-Schicht",
        "Früh",
        1,
        "EG 6",
        "CNC-Drehen, Fräsen, Messmittelkunde",
    ),
    (
        "MA-0010",
        "Ayse",
        "Demir",
        date(1987, 12, 1),
        "Kohlenpottweg 33",
        "44787",
        "Bochum",
        "Produktion",
        "3-Schicht",
        "Spät",
        1,
        "EG 5",
        "Rüsten CNC, Erstmuster, Qualitätsprüfung",
    ),
    (
        "MA-0011",
        "Patrick",
        "Müller",
        date(1992, 5, 19),
        "Industrieweg 6",
        "45127",
        "Essen",
        "Produktion",
        "3-Schicht",
        "Nacht",
        2,
        "EG 5",
        "Spritzguss, Werkzeugwechsel, Kanban",
    ),
    (
        "MA-0012",
        "Claudia",
        "Werner",
        date(1984, 10, 7),
        "Hochofenstraße 21",
        "58095",
        "Hagen",
        "Produktion",
        "3-Schicht",
        "Früh",
        2,
        "EG 6",
        "Montagelinie, Einrichtung, Lean Basics",
    ),
    (
        "MA-0013",
        "Stefan",
        "Braun",
        date(1979, 3, 25),
        "Zechensiedlung 4",
        "42103",
        "Wuppertal",
        "Produktion",
        "3-Schicht",
        "Spät",
        3,
        "EG 5",
        "Foerderband, Staplerführerschein, Sichtkontrolle",
    ),
    (
        "MA-0014",
        "Melanie",
        "Koch",
        date(1996, 7, 11),
        "Schachtstraße 9",
        "44135",
        "Dortmund",
        "Produktion",
        "3-Schicht",
        "Nacht",
        3,
        "EG 5",
        "Verpackung, Etikettiersystem, 5S",
    ),
    (
        "MA-0015",
        "Tobias",
        "Zimmermann",
        date(1983, 1, 4),
        "Ruhrdeich 55",
        "44787",
        "Bochum",
        "Produktion",
        "Wochenendteam",
        "Früh",
        4,
        "EG 6",
        "Roboterzelle, Vakuumtechnik, Probelauf",
    ),
    (
        "MA-0016",
        "Nicole",
        "Lange",
        date(1990, 4, 28),
        "Steinkohlenallee 13",
        "45127",
        "Essen",
        "Produktion",
        "2-Schicht",
        "Früh",
        4,
        "EG 5",
        "Qualitätsprüfung, Erstmuster, SPC",
    ),
    (
        "MA-0017",
        "Andreas",
        "Schmitz",
        date(1977, 9, 16),
        "Kanalstraße 38",
        "58095",
        "Hagen",
        "Produktion",
        "2-Schicht",
        "Spät",
        5,
        "EG 6",
        "CNC-Fräsen, Messmaschinenführer, Lean",
    ),
    (
        "MA-0018",
        "Lena",
        "Wolf",
        date(1995, 11, 22),
        "Prosper-Platz 2",
        "42103",
        "Wuppertal",
        "Produktion",
        "3-Schicht",
        "Früh",
        5,
        "EG 5",
        "Montagelinie, Sichtkontrolle, Schichtübergabe",
    ),
    (
        "MA-0019",
        "Carsten",
        "Richter",
        date(1986, 6, 3),
        "Hüttenstraße 47",
        "44135",
        "Dortmund",
        "Logistik",
        "Tagschicht",
        "Frei",
        6,
        "EG 5",
        "Staplerführerschein, Kranbedienung, Lagerlogistik",
    ),
    (
        "MA-0020",
        "Sabine",
        "Klein",
        date(1981, 2, 18),
        "Am Viadukt 8",
        "44787",
        "Bochum",
        "Logistik",
        "2-Schicht",
        "Früh",
        6,
        "EG 4",
        "Wareneingang, Buchung SAP, Inventur",
    ),
    (
        "MA-0021",
        "Daniel",
        "Schäfer",
        date(1993, 8, 9),
        "Bergbaustraße 71",
        "45127",
        "Essen",
        "Logistik",
        "2-Schicht",
        "Spät",
        7,
        "EG 4",
        "Kommissionierung, Etikettierung, Versand",
    ),
    (
        "MA-0022",
        "Tanja",
        "König",
        date(1988, 12, 27),
        "Zeche-Nord-Str. 5",
        "58095",
        "Hagen",
        "Logistik",
        "Tagschicht",
        "Frei",
        7,
        "EG 5",
        "Staplerführerschein, Gefahrgutbeauftragter",
    ),
    (
        "MA-0023",
        "Michael",
        "Fischer",
        date(1976, 5, 6),
        "Gußstahlstraße 29",
        "42103",
        "Wuppertal",
        "Qualität",
        "Tagschicht",
        "Frei",
        8,
        "EG 8",
        "Qualitätsmanagement, Reklamationsbearbeitung, Auditor",
    ),
    (
        "MA-0024",
        "Kerstin",
        "Herrmann",
        date(1983, 10, 14),
        "Altenessener Str. 62",
        "45127",
        "Essen",
        "Qualität",
        "2-Schicht",
        "Früh",
        8,
        "EG 7",
        "SPC, Messmittelkunde, FMEA",
    ),
    (
        "MA-0025",
        "Jens",
        "Schwarz",
        date(1990, 3, 31),
        "Nordsternstraße 17",
        "44135",
        "Dortmund",
        "Qualität",
        "2-Schicht",
        "Spät",
        8,
        "EG 7",
        "Erstmuster, Mess- und Prüftechnik, CMM-Bedienung",
    ),
    (
        "MA-0026",
        "Petra",
        "Weiß",
        date(1978, 7, 20),
        "Victoriastraße 3",
        "44787",
        "Bochum",
        "Verwaltung",
        "Tagschicht",
        "Frei",
        9,
        "EG 8",
        "Einkauf, SAP MM, Rahmenverträge",
    ),
    (
        "MA-0027",
        "Frank",
        "Lorenz",
        date(1972, 1, 15),
        "Obere Schmidtstraße 44",
        "45127",
        "Essen",
        "Verwaltung",
        "Tagschicht",
        "Frei",
        9,
        "EG 9",
        "Kostenrechnung, Controlling, DATEV",
    ),
    (
        "MA-0028",
        "Ines",
        "Meyer",
        date(1985, 6, 8),
        "Glückaufstraße 16",
        "58095",
        "Hagen",
        "Verwaltung",
        "Tagschicht",
        "Frei",
        9,
        "EG 7",
        "Personalwesen, Entgeltabrechnung, Sozialrecht",
    ),
    (
        "MA-0029",
        "Ralf",
        "Bergmann",
        date(1981, 11, 25),
        "Lothringenstraße 9",
        "42103",
        "Wuppertal",
        "IT",
        "Tagschicht",
        "Frei",
        10,
        "EG 9",
        "Windows Server, VMware, Active Directory",
    ),
    (
        "MA-0030",
        "Sonja",
        "Brandt",
        date(1993, 4, 10),
        "Hiberniastraße 23",
        "44135",
        "Dortmund",
        "IT",
        "Tagschicht",
        "Frei",
        10,
        "EG 8",
        "Netzwerk, Firewall, WLAN-Administration",
    ),
]

# ---------------------------------------------------------------------------
# Benutzerdefinitionen (verknüpft mit Mitarbeitern via Personalnummer)
# ---------------------------------------------------------------------------

USER_DEFINITIONS = [
    # (username, email, role, dept_name, employee_personnel_number)
    ("admin", "admin@fertigungs-gmbh.de", "master_admin", None, None),
    (
        "thomas.hoffmann",
        "thomas.hoffmann@fertigungs-gmbh.de",
        "instandhaltung",
        "Instandhaltung",
        "MA-0001",
    ),
    (
        "sandra.becker",
        "sandra.becker@fertigungs-gmbh.de",
        "instandhaltung",
        "Instandhaltung",
        "MA-0002",
    ),
    (
        "kevin.schulze",
        "kevin.schulze@fertigungs-gmbh.de",
        "instandhaltung",
        "Instandhaltung",
        "MA-0003",
    ),
    (
        "markus.wagner",
        "markus.wagner@fertigungs-gmbh.de",
        "instandhaltung",
        "Instandhaltung",
        "MA-0007",
    ),
    ("dirk.hartmann", "dirk.hartmann@fertigungs-gmbh.de", "produktion", "Produktion", "MA-0009"),
    ("ayse.demir", "ayse.demir@fertigungs-gmbh.de", "produktion", "Produktion", "MA-0010"),
    (
        "patrick.mueller",
        "patrick.mueller@fertigungs-gmbh.de",
        "produktion",
        "Produktion",
        "MA-0011",
    ),
    ("claudia.werner", "claudia.werner@fertigungs-gmbh.de", "produktion", "Produktion", "MA-0012"),
    ("stefan.braun", "stefan.braun@fertigungs-gmbh.de", "produktion", "Produktion", "MA-0013"),
    ("petra.weiss", "petra.weiss@fertigungs-gmbh.de", "verwaltung", "Verwaltung", "MA-0026"),
    ("frank.lorenz", "frank.lorenz@fertigungs-gmbh.de", "verwaltung", "Verwaltung", "MA-0027"),
    ("ines.meyer", "ines.meyer@fertigungs-gmbh.de", "personalabteilung", "Verwaltung", "MA-0028"),
    (
        "michael.fischer",
        "michael.fischer@fertigungs-gmbh.de",
        "verwaltung",
        "Verwaltung",
        "MA-0023",
    ),
    ("ralf.bergmann", "ralf.bergmann@fertigungs-gmbh.de", "it", "IT", "MA-0029"),
    ("sonja.brandt", "sonja.brandt@fertigungs-gmbh.de", "it", "IT", "MA-0030"),
    (
        "carsten.richter",
        "carsten.richter@fertigungs-gmbh.de",
        "produktion",
        "Produktion",
        "MA-0019",
    ),
    (
        "miriam.krause",
        "miriam.krause@fertigungs-gmbh.de",
        "instandhaltung",
        "Instandhaltung",
        "MA-0004",
    ),
    (
        "oliver.petersen",
        "oliver.petersen@fertigungs-gmbh.de",
        "instandhaltung",
        "Instandhaltung",
        "MA-0005",
    ),
    (
        "tobias.zimmermann",
        "tobias.zimmermann@fertigungs-gmbh.de",
        "produktion",
        "Produktion",
        "MA-0015",
    ),
]

# ---------------------------------------------------------------------------
# Maschinen
# ---------------------------------------------------------------------------

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

TASK_DEFINITIONS = [
    # (
    #     titel, beschreibung, priorität, status, fälligkeit_tage,
    #     abteilung, maschine_name, worker_username
    # )
    # Instandhaltung
    (
        "Hydraulikpresse 03 – Dichtigkeitsprüfung",
        "Sämtliche Hydraulikverbindungen und Zylinderanschlüsse auf Leckagen prüfen. "
        "Druckverlustmessung durchführen, Ergebnis in der Wartungsakte dokumentieren.",
        "urgent",
        "in_progress",
        0,
        "Instandhaltung",
        "Hydraulikpresse 03",
        "thomas.hoffmann",
    ),
    (
        "CNC-Fräse 01 – Spindellager tauschen",
        "Austausch des Hauptspindellagers nach 8.200 Betriebsstunden. "
        "Lager-Kit liegt in Lager vor, Ausfallzeit ca. 4 h einplanen.",
        "urgent",
        "open",
        1,
        "Instandhaltung",
        "CNC-Fräse 01",
        None,
    ),
    (
        "Kompressorstation 07 – Ölwechsel und Filterwechsel",
        "Jährlicher Ölwechsel inkl. Öl- und Luftfilter. "
        "Betriebsstundenzähler notieren, Kondensatableiter prüfen.",
        "soon",
        "open",
        3,
        "Instandhaltung",
        "Kompressorstation 07",
        None,
    ),
    (
        "Roboterzelle 09 – TCP-Kalibrierung nach Crash",
        "Nach Kollision mit Bauteil: Werkzeugmittelpunkt neu einmessen, "
        "alle Achsen auf mechanischen Schaden prüfen, Protokoll an Qualität.",
        "urgent",
        "done",
        -2,
        "Instandhaltung",
        "Roboterzelle 09",
        "markus.wagner",
    ),
    (
        "Förderband Linie A – Gurtspannung prüfen",
        "Gurt visuell auf Risse und Verschleiß kontrollieren. "
        "Spannung mit Richtwert 200 N/m² vergleichen, ggf. nachspannen.",
        "soon",
        "in_progress",
        1,
        "Instandhaltung",
        "Förderband Linie A",
        "sandra.becker",
    ),
    (
        "Spritzgussanlage 04 – Heizkabel Heizzone 3 wechseln",
        "Heizzone 3 zeigt Ausfall bei 230 V Prüfung. "
        "Kabel-Set auf Lager, Tausch im Stillstand Spätschicht.",
        "urgent",
        "open",
        0,
        "Instandhaltung",
        "Spritzgussanlage 04",
        None,
    ),
    (
        "Montagelinie 05 – Not-Halt-Kreis testen",
        "Jährliche Sicherheitsprüfung aller Not-Halt-Taster und Türkontakte. "
        "Schaltplan Rev. 4 verwenden, Nachweis für BG-Prüfung erstellen.",
        "normal",
        "open",
        7,
        "Instandhaltung",
        "Montagelinie 05",
        None,
    ),
    (
        "Prüfstand 08 – Kontaktleisten reinigen und prüfen",
        "Oxidierte Kontakte auf Prüfadapter Nr. 3 und 7 gereinigt. "
        "Übergangswiderstand < 10 mΩ dokumentieren.",
        "normal",
        "done",
        -5,
        "Instandhaltung",
        "Prüfstand 08",
        "kevin.schulze",
    ),
    (
        "Waschanlage 11 – Filtereinsatz tauschen",
        "Filtereinsatz nach 250 Betriebsstunden (Vorgabe Hersteller Henkel) wechseln. "
        "Konzentration im Waschbad nachmessen und ggf. korrigieren.",
        "normal",
        "open",
        4,
        "Instandhaltung",
        "Waschanlage 11",
        None,
    ),
    (
        "Laserbeschrifter 10 – Absaugung reinigen",
        "Absaugkanal und Schutzglas visuell prüfen. "
        "Schutzglas gereinigt oder getauscht, Laserleistung nachmessen.",
        "soon",
        "in_progress",
        2,
        "Instandhaltung",
        "Laserbeschrifter 10",
        "miriam.krause",
    ),
    # Produktion
    (
        "CNC-Fräse 01 – Erstmuster Auftrag 4912 freigeben",
        "Erstmusterprüfbericht für Aluminium-Gehäuse Auftrag 4912 erstellen. "
        "Maße laut Zeichnung Rev. C prüfen, QS-Freigabe einholen.",
        "urgent",
        "in_progress",
        0,
        "Produktion",
        "CNC-Fräse 01",
        "dirk.hartmann",
    ),
    (
        "Montagelinie 05 – Rüstplan Typ W44 abstimmen",
        "Umrüstung von Typ W42 auf W44 für Nachtschicht vorbereiten. "
        "Greifer-Set aus Lager holen, Rüstblatt aushängen.",
        "soon",
        "open",
        1,
        "Produktion",
        "Montagelinie 05",
        None,
    ),
    (
        "Spritzgussanlage 04 – Granulat PA6 nachfüllen",
        "Materialbehälter Anlage 04 unter 20 kg-Grenze. "
        "Silo-Station 3 befüllen, Chargenprotokoll in SAP buchen.",
        "soon",
        "done",
        -1,
        "Produktion",
        "Spritzgussanlage 04",
        "ayse.demir",
    ),
    (
        "Verpackungsanlage 06 – Etikettierprogramm aktualisieren",
        "Neues Kundenlogo für Auftrag DE-5003 laden. "
        "Testdruck auf 5 Etiketten, Freigabe durch Schichtleiter.",
        "normal",
        "open",
        3,
        "Produktion",
        "Verpackungsanlage 06",
        None,
    ),
    (
        "Förderband Linie A – Ausschussquote Frühschicht erfassen",
        "Ausschussteile zählen und Fehlerart kategorisieren. "
        "Erfassung im Shopfloor-Board bis Schichtende.",
        "normal",
        "done",
        -3,
        "Produktion",
        "Förderband Linie A",
        "stefan.braun",
    ),
    (
        "Roboterzelle 09 – Vakuumsauger wechseln Station 2",
        "Vakuumsauger an Greiferstation 2 verschlissen (Haltekraft < 80 %). "
        "Set aus Lager entnehmen, Tausch im Stillstand.",
        "soon",
        "in_progress",
        1,
        "Produktion",
        "Roboterzelle 09",
        "tobias.zimmermann",
    ),
    (
        "CNC-Drehmaschine 02 – Präzisionswellen Losgröße 80",
        "Fertigungslos PW-2024-080 anlegen. "
        "Spannmittel-Wechsel, Nullpunkt einmessen, Erstmaß abnehmen.",
        "normal",
        "open",
        5,
        "Produktion",
        "CNC-Drehmaschine 02",
        None,
    ),
    (
        "Montagelinie 05 – Kanban-Karten Sensoren prüfen",
        "Bestand an induktiven Sensoren am Kanban-Regal prüfen. "
        "Unterschreitung Meldebestand → Bestellkarte in Einkaufsbox.",
        "normal",
        "done",
        -4,
        "Produktion",
        "Montagelinie 05",
        "claudia.werner",
    ),
    (
        "Verpackungsanlage 06 – Verpackungsmaterial Auftrag 5021",
        "Kartons 400×300×200 für Auftrag 5021 (240 Stück) bereitstellen. "
        "Lagerort B-04 prüfen, fehlende Menge nachbestellen.",
        "soon",
        "open",
        2,
        "Produktion",
        "Verpackungsanlage 06",
        None,
    ),
    (
        "Prüfstand 08 – End-of-Line-Prüfung Schicht C dokumentieren",
        "Prüfergebnisse aller 48 Baugruppen aus Nachtschicht im System erfassen. "
        "3 NIO-Teile separat lagern und Rückmeldung an QS.",
        "normal",
        "open",
        0,
        "Produktion",
        "Prüfstand 08",
        None,
    ),
    # Verwaltung
    (
        "Wartungsverträge Q2 – Ablauf prüfen",
        "Verträge für CNC-Fräse 01, Hydraulikpresse 03 und Roboterzelle 09 laufen im Juni aus. "
        "Verlängerungsangebote einholen und Vergabereport erstellen.",
        "soon",
        "open",
        6,
        "Verwaltung",
        None,
        None,
    ),
    (
        "Ersatzteil-Rechnungen März klären",
        "3 Rechnungen von Parker, SKF und Igus ohne Bestellbezug. "
        "Kostenstellen-Zuordnung prüfen, Buchungsbeleg an Buchhaltung.",
        "normal",
        "in_progress",
        2,
        "Verwaltung",
        None,
        "petra.weiss",
    ),
    (
        "Lieferantenstammdaten aktualisieren",
        "Neue Bankdaten von Sandvik Coromant und Atlas Copco in SAP einpflegen. "
        "Änderungsbeleg unterschreiben lassen.",
        "normal",
        "done",
        -2,
        "Verwaltung",
        None,
        "frank.lorenz",
    ),
    (
        "Monatsreport Anlagenverfügbarkeit April",
        "OEE-Kennzahlen aus Schichtprotokollen zusammenführen. "
        "Bericht bis 5. des Monats an Werksleitung.",
        "soon",
        "open",
        4,
        "Verwaltung",
        None,
        None,
    ),
    (
        "Schulungsnachweise 2026 abgleichen",
        "Prüfen welche Mitarbeiter Wiederholungsschulung (UVV, Stapler, Ersthelfer) benötigen. "
        "Liste an Personalreferentin, Termine blockieren.",
        "normal",
        "open",
        10,
        "Verwaltung",
        None,
        None,
    ),
    # IT
    (
        "Backup-Status Produktionsserver prüfen",
        "Backup-Job VM-PROD-01 schlug laut Monitoring 2× fehl. "
        "Log auswerten, freien Speicher prüfen, Backup manuell anstoßen.",
        "urgent",
        "in_progress",
        0,
        "IT",
        None,
        "ralf.bergmann",
    ),
    (
        "WLAN-Ausleuchtung Halle 2 nachmessen",
        "Schichtleiter meldet Verbindungsabbrüche am Tablet Linie A. "
        "Site-Survey mit NetSpot durchführen, Access Point Pos. anpassen.",
        "soon",
        "open",
        3,
        "IT",
        None,
        None,
    ),
    (
        "VPN-Zugriff Rufbereitschaft testen",
        "Monatstest gemäß IT-Richtlinie: alle 5 Rufbereitschafts-Zugänge einwählen. "
        "Ergebnis im IT-Betriebshandbuch dokumentieren.",
        "normal",
        "done",
        -1,
        "IT",
        None,
        "sonja.brandt",
    ),
    (
        "Scanner-Firmware Lager aktualisieren",
        "Honeywell-Scanner Lager A und B auf Firmware 3.2.1 bringen. "
        "Update-Paket liegt auf Netzlaufwerk \\\\srv01\\updates\\scanner bereit.",
        "normal",
        "open",
        5,
        "IT",
        None,
        None,
    ),
    (
        "USV-Selbsttest auswerten",
        "Wöchentlicher Selbsttest der USV im Schaltschrank Halle 1. "
        "Batteriezustand und Laufzeit protokollieren, Wert < 8 min → Tausch melden.",
        "normal",
        "done",
        -6,
        "IT",
        None,
        "ralf.bergmann",
    ),
]

# ---------------------------------------------------------------------------
# Fehlerkatalog
# ---------------------------------------------------------------------------

ERROR_DEFINITIONS = [
    # (fehlercode_suffix, titel, ursache, lösung, maschinenname)
    (
        "E-101",
        "Sensor liefert kein Signal",
        "Kabelbruch, verschmutzter Sensor oder falscher Einbauabstand.",
        "Sensor reinigen, Abstand laut Datenblatt prüfen, Kabel auf Durchgang messen.",
        "Montagelinie 05",
    ),
    (
        "E-102",
        "Motor überlastet",
        "Blockierter Antrieb, erhöhte Lagerreibung oder falsche Umrichterparameter.",
        "Antrieb von Hand drehen, Lager abhorchen, I-max-Parameter prüfen.",
        "Förderband Linie A",
    ),
    (
        "E-103",
        "Druck fällt ab",
        "Leckage an Schlauch oder Verschraubung, defektes Ventil oder Filter zugesetzt.",
        "Lecktest mit Sprühkreide, Ventilspule messen, Filter tauschen.",
        "Hydraulikpresse 03",
    ),
    (
        "E-104",
        "Temperatur außerhalb Toleranz",
        "Heizkreis defekt, Kühlwasserdurchfluss zu gering oder Regler falsch parametriert.",
        "Heizzone per Messzange prüfen, Kühlkreis entlüften, Sollwert kontrollieren.",
        "Spritzgussanlage 04",
    ),
    (
        "E-105",
        "Kommunikation zur Steuerung gestört",
        "Netzwerkfehler, SPS-Koppler überhitzt oder IP-Konflikt im Subnetz.",
        "Switch-Port LED prüfen, SPS-Diagnose aufrufen, IP-Tabelle sichten.",
        "CNC-Fräse 01",
    ),
    (
        "E-106",
        "Not-Halt-Kreis offen",
        "Türkontakt nicht geschlossen, Not-Halt-Taster rastet nicht oder "
        "Sicherheitsrelais ausgefallen.",
        "Alle Schutztüren schließen, Taster entriegeln, Relaisausgänge messen.",
        "Montagelinie 05",
    ),
    (
        "E-107",
        "Werkzeug nicht referenziert",
        "Referenzfahrt nach Stromausfall ausgeblieben oder Endschalter verschmutzt.",
        "Referenzfahrt starten, Endschalter reinigen, Positions-Offset kontrollieren.",
        "CNC-Fräse 01",
    ),
    (
        "E-108",
        "Barcode nicht lesbar",
        "Etikett beschädigt, Scannerlinse verschmutzt oder Beleuchtung ausgefallen.",
        "Linse reinigen, Etikett neu drucken, LED-Beleuchtung prüfen.",
        "Verpackungsanlage 06",
    ),
    (
        "E-109",
        "Vakuum zu niedrig",
        "Sauger verschlissen, Schlauch undicht oder Magnetventil klemmt.",
        "Sauger auf Risse prüfen, Druckverlusttest, Ventil durchschalten.",
        "Roboterzelle 09",
    ),
    (
        "E-110",
        "Materialstau erkannt",
        "Bauteil verkippt in Führung, Bandlauf dejustiert oder Sensor zu nah.",
        "Stau beseitigen, Führungsbreite prüfen, Sensor nachjustieren.",
        "Förderband Linie A",
    ),
    (
        "E-111",
        "Achse folgt Sollwert nicht",
        "Geberfehler, mechanische Verspannung oder Lagerspiel zu groß.",
        "Schlepp-Fehlergrenze auslesen, Geber tauschen, Mechanik nachprüfen.",
        "CNC-Drehmaschine 02",
    ),
    (
        "E-112",
        "Ölstand niedrig",
        "Leckage am Zylinder oder Schlauch, normaler Verbrauch überschritten.",
        "Anlage sicher stoppen, Leckage lokalisieren, Öl nachfüllen.",
        "Hydraulikpresse 03",
    ),
    (
        "E-113",
        "Prüfergebnis instabil",
        "Schlechte Kontaktierung, verschlissener Adapter oder Messleitung gebrochen.",
        "Kontakte reinigen, Leitungswiderstand messen, Adapter tauschen.",
        "Prüfstand 08",
    ),
    (
        "E-114",
        "Absaugung meldet Unterdruck",
        "Filter zugesetzt, Klappe klemmt oder Schlauch geknickt.",
        "Filter reinigen oder tauschen, Klappe manuell öffnen, Schlauchführung prüfen.",
        "Laserbeschrifter 10",
    ),
    (
        "E-115",
        "Rüstdaten fehlen",
        "Auftragsdaten noch nicht an Maschinensteuerung übertragen oder falsches Rezept gewählt.",
        "Auftrag im MES öffnen, Rezept manuell laden, Parametrierung bestätigen.",
        "CNC-Fräse 01",
    ),
    (
        "E-116",
        "Druckluftqualität schlecht",
        "Trockner abgeschaltet, Kondensatableiter defekt oder Filter gesättigt.",
        "Taupunkt messen, Ableiter testen, Filter wechseln.",
        "Kompressorstation 07",
    ),
    (
        "E-117",
        "Schutzzaun offen",
        "Türschalter defekt, Verriegelung klemmt oder Zuhaltung nicht bestromt.",
        "Schalter tauschen, Zuhaltespannung messen, Verriegelungsbolzen reinigen.",
        "Roboterzelle 09",
    ),
    (
        "E-118",
        "Füllstand Material niedrig",
        "Nachfüllung vergessen oder Sensor liefert Fehlmeldung.",
        "Behälter befüllen, Sensor-Schwelle prüfen, Meldung quittieren.",
        "Spritzgussanlage 04",
    ),
    (
        "E-119",
        "Kalibrierung abgelaufen",
        "Kalibrierintervall laut Prüfplan überschritten.",
        "Prüfmittel sperren, Kalibrierung beauftragen, Ergebnis einpflegen.",
        "Prüfstand 08",
    ),
    (
        "E-120",
        "Qualitätsgrenze überschritten",
        "Verschlissenes Werkzeug, veränderte Rohmaterialcharge oder Prozess-Drift.",
        "Werkzeug tauschen, Charge sperren, Prozessparameter zurücksetzen.",
        "CNC-Fräse 01",
    ),
]


MAINTENANCE_PLAN_DEFINITIONS = [
    (
        "Hydraulikpresse 03 - Hydraulikdruck und Leckagecheck",
        "Druckhaltepruefung bei 180 bar, Schlauchpakete sichtpruefen, "
        "Dichtungssatz und O-Ring-Bestand vor Stillstand kontrollieren.",
        30,
        2,
        "urgent",
        "Instandhaltung",
        "hydraulikpresse-03",
        True,
    ),
    (
        "Kompressorstation 07 - Druckluftqualitaet und Filter",
        "Taupunkt, Kondensatableiter und Druckluftfilter G1/2 pruefen. "
        "Bei Taupunkt > 3 Grad C Trockner reinigen und Leckagesuche starten.",
        14,
        4,
        "soon",
        "Instandhaltung",
        "kompressorstation-07",
        True,
    ),
    (
        "Montagelinie 05 - Sicherheitskreis und Sensorik",
        "Not-Halt, Tuerkontakte, induktive M8 Sensoren und Verriegelungen testen. "
        "Abweichungen direkt im Schichtbuch dokumentieren.",
        90,
        8,
        "normal",
        "Instandhaltung",
        "montagelinie-05",
        True,
    ),
    (
        "Roboterzelle 09 - Greifer, Vakuum und TCP",
        "Sauger, Vakuumkreis und TCP nach Kollisionen pruefen. "
        "Haltekraft je Station messen und Greiferfinger sichtpruefen.",
        21,
        1,
        "soon",
        "Produktion",
        "roboterzelle-09",
        True,
    ),
    (
        "Pruefstand 08 - Kontaktleisten und Kalibrierung",
        "Kontaktwiderstand der Adapter messen, Kalibrierstatus pruefen und "
        "NIO-Haeufungen mit QS abgleichen.",
        60,
        12,
        "normal",
        "Produktion",
        "prufstand-08",
        True,
    ),
]

ACTIVE_ERROR_STATES = {
    ("Instandhaltung", "E-101"): {
        "status": "open",
        "severity": "critical",
        "cause_category": "Sensorik",
        "impact": "Linie muss überwacht laufen, Ausschussrisiko erhöht.",
        "downtime_minutes": 35,
        "production_loss_minutes": 50,
        "repeat_count": 2,
        "seen_hours": 2,
    },
    ("Instandhaltung", "E-103"): {
        "status": "in_progress",
        "severity": "high",
        "cause_category": "Hydraulik",
        "impact": "Taktzeit reduziert, Wartungsfenster erforderlich.",
        "downtime_minutes": 20,
        "production_loss_minutes": 30,
        "repeat_count": 1,
        "seen_hours": 5,
    },
    ("Produktion", "E-104"): {
        "status": "open",
        "severity": "high",
        "cause_category": "Mechanik",
        "impact": "Qualitätsfreigabe ausstehend.",
        "downtime_minutes": 0,
        "production_loss_minutes": 15,
        "repeat_count": 1,
        "seen_hours": 1,
    },
}

MANUAL_DEFINITIONS = [
    (
        "hydraulikpresse-03",
        "Instandhaltung",
        "hydraulikpresse-03-betriebsanweisung.txt",
        "Betriebsanweisung Hydraulikpresse 03",
        (
            "Maschine: Hydraulikpresse 03\n"
            "Fehlercodes: INS-E-103, INS-E-112\n"
            "Hydraulikdruckverlust: Anlage sichern, Druck abbauen, Lecktest "
            "mit Spruehkreide durchfuehren, Filterzustand pruefen und "
            "Dichtungssatz Presse bereitlegen.\n"
            "Freigabe erst nach 10 Minuten Druckhaltepruefung ohne sichtbare "
            "Leckage und dokumentiertem Oelstand.\n"
        ),
    ),
    (
        "spritzgussanlage-04",
        "Instandhaltung",
        "spritzgussanlage-04-heizzonen.txt",
        "Servicehinweis Spritzgussanlage 04",
        (
            "Maschine: Spritzgussanlage 04\n"
            "Fehlercodes: INS-E-104, PRO-E-118\n"
            "Bei Temperaturabweichung Heizzone einzeln freischalten, "
            "Heizkabel 230 V mit Messzange pruefen und Kuehlwasserdurchfluss "
            "kontrollieren. Material PA6 erst nach stabiler Zone freigeben.\n"
        ),
    ),
    (
        "kompressorstation-07",
        "Instandhaltung",
        "kompressorstation-07-druckluft.txt",
        "Wartungsanweisung Kompressorstation 07",
        (
            "Maschine: Kompressorstation 07\n"
            "Fehlercode: INS-E-116\n"
            "Druckluftqualitaet: Taupunkt messen, Kondensatableiter ausloesen, "
            "Druckluftfilter G1/2 wechseln und Leckagen im Ringnetz markieren.\n"
        ),
    ),
]

SHIFT_HANDOVER_DEFINITIONS = [
    (
        "Instandhaltung",
        0,
        "Frueh",
        "open",
        "thomas.hoffmann",
        "Hydraulikpresse 03 wegen Druckverlust nur im reduzierten Takt betreiben.",
        "Task Hydraulikpresse 03 - Dichtigkeitspruefung laeuft; Material Dichtungssatz fehlt.",
        "Hydraulikpresse 03: Oelstand stabil, aber Leckage an Ventilblock V3 wahrscheinlich.",
        "Spaetschicht soll INS-E-103 pruefen und O-Ring-Satz aus Lager nachfordern.",
    ),
    (
        "Produktion",
        0,
        "Spaet",
        "open",
        "ayse.demir",
        "Spritzgussanlage 04 hatte drei Temperaturwarnungen in Heizzone 3.",
        "Granulat PA6 ist nachgefuellt; Heizkabel-Tausch fuer Stillstand eingeplant.",
        "Spritzgussanlage 04: Rezept W44 stabil, Ausschussquote leicht erhoeht.",
        "Nachtschicht soll erste 20 Teile messen und QS bei Drift informieren.",
    ),
    (
        "Verwaltung",
        -1,
        "Frueh",
        "completed",
        "petra.weiss",
        "Kritische Ersatzteile fuer Hydraulikpresse 03 und Laserbeschrifter 10 priorisiert.",
        "Dichtungssatz Presse ist Bestand 0; Parker-Bestellung eskaliert.",
        "Verpackungsanlage 06 Material fuer Auftrag 5021 bereitgestellt.",
        "Wareneingang soll Laser-Schutzglas direkt an Instandhaltung melden.",
    ),
]

TRAINING_DEFINITIONS = [
    (
        "Demo: Hydraulikdruckverlust strukturiert beantworten",
        "Wie loese ich Hydraulikdruckverlust an Hydraulikpresse 03?",
        (
            "Nur mit Quellen antworten. Prioritaet haben Fehler INS-E-103, "
            "Manual Hydraulikpresse 03 und offene Tasks. Immer erst Anlage "
            "sichern, Druck abbauen, Lecktest, Filter und Ventilblock pruefen."
        ),
        "Hydraulikpresse 03, Druck faellt ab, INS-E-103, Dichtungssatz Presse, O-Ring",
        "demo_ai",
        "Instandhaltung",
        95,
        True,
    ),
    (
        "Demo: Kritische Maschine identifizieren",
        "Welche Maschine ist aktuell kritisch?",
        (
            "Kritisch sind Maschinen mit critical/high Criticality, laufenden "
            "urgent Tasks, aktuellen Schichtuebergaben oder fehlenden Ersatzteilen."
        ),
        "kritische Maschine, urgent Tasks, Hydraulikpresse 03, Kompressorstation 07",
        "demo_ai",
        "Produktion",
        85,
        True,
    ),
    (
        "Demo: Ersatzteilrisiko erklaeren",
        "Welche Ersatzteile blockieren Wartung an Hydraulikpresse 03?",
        (
            "Nenne nur sichtbare Lagerpositionen. Dichtungssatz Presse und "
            "O-Ring-Satz sind fuer Hydraulikdruckverlust relevant; Bestand, "
            "Mindestbestand und Lieferzeit erwaehnen."
        ),
        "Ersatzteil, Mindestbestand, Dichtungssatz Presse, O-Ring-Satz, Hydraulikpresse",
        "demo_ai",
        "Verwaltung",
        80,
        True,
    ),
    (
        "Demo: Schichtuebergabe zusammenfassen",
        "Was wurde in der letzten Schicht zu Spritzgussanlage 04 gemeldet?",
        (
            "Schichtuebergaben knapp zusammenfassen und offene naechste Schritte "
            "aus next_notes nennen. Keine Mitarbeitenden-Details ausgeben."
        ),
        "Schichtuebergabe, Spritzgussanlage 04, Heizzone 3, Nachtschicht, QS",
        "demo_ai",
        "Produktion",
        78,
        True,
    ),
]


# ---------------------------------------------------------------------------
# Öffentliche Seeding-Funktion
# ---------------------------------------------------------------------------


def seed_demo_data():
    """Create a complete, repeatable demo dataset."""
    ensure_default_departments()
    departments = _departments_by_name()
    employees = _seed_employees()
    db.session.flush()
    users = _seed_users(departments, employees)
    db.session.flush()
    for user in users.values():
        upsert_default_permissions(user)
    tag_summary = seed_maintenance_tag_library(
        created_by=users["admin"].id if users.get("admin") else None,
    )
    machines = _seed_machines()
    db.session.flush()
    _seed_inventory(machines)
    _link_employee_machines(employees, machines)
    _seed_errors(departments, machines)
    _seed_maintenance_plans(departments, users, machines)
    _seed_tasks(departments, users, machines)
    db.session.flush()
    _seed_documents(users)
    _seed_machine_manuals(users, machines)
    _seed_shift_handovers(users)
    _seed_training_entries(users)
    db.session.commit()
    knowledge_summary = reindex_stale_knowledge()
    return {
        "users": len(users),
        "employees": len(employees),
        "machines": len(machines),
        "inventory_materials": InventoryMaterial.query.count(),
        "maintenance_plans": MaintenancePlan.query.count(),
        "tasks": Task.query.count(),
        "errors": ErrorEntry.query.count(),
        "documents": GeneratedDocument.query.count(),
        "machine_manuals": MachineManual.query.count(),
        "shift_handovers": ShiftHandover.query.count(),
        "training_entries": AssistantTrainingEntry.query.count(),
        "knowledge_documents": KnowledgeDocument.query.count(),
        "knowledge_chunks": KnowledgeChunk.query.count(),
        "knowledge_documents_reindexed": knowledge_summary["indexed"],
        "maintenance_tag_entries": tag_summary["created"],
        "password": DEMO_PASSWORD,
    }


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _departments_by_name():
    """Return default departments indexed by name."""
    return {
        dep.name: dep
        for dep in Department.query.filter(Department.name.in_(DEFAULT_DEPARTMENTS)).all()
    }


def _seed_employees():
    """Create missing demo employees and return them by personnel number."""
    employees = {}
    for row in EMPLOYEE_DATA:
        (
            personnel_number,
            first_name,
            last_name,
            birth_date,
            street,
            postal_code,
            city,
            department,
            shift_model,
            current_shift,
            team,
            salary_group,
            qualifications,
        ) = row

        emp = Employee.query.filter_by(personnel_number=personnel_number).first()
        if not emp:
            emp = Employee(
                personnel_number=personnel_number,
                name=f"{first_name} {last_name}",
                birth_date=birth_date,
                street=street,
                postal_code=postal_code,
                city=city,
                department=department,
                shift_model=shift_model,
                current_shift=current_shift,
                team=team,
                salary_group=salary_group,
                qualifications=qualifications,
            )
            db.session.add(emp)
        employees[personnel_number] = emp
    return employees


def _seed_users(departments, employees):
    """Create missing demo users and link them to employees."""
    users = {}
    for username, email, role_value, dept_name, emp_nr in USER_DEFINITIONS:
        user = User.query.filter(or_(User.username == username, User.email == email)).first()
        if not user:
            user = User(
                username=username,
                email=email,
                role=Role(role_value),
                department=departments.get(dept_name),
                is_active=True,
            )
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
        if emp_nr and emp_nr in employees:
            user.employee = employees[emp_nr]
        users[username] = user
    return users


def _demo_key(value):
    """Return a stable ASCII key for demo lookup tables."""
    normalized = str(value or "").strip().lower()
    replacements = {
        "ä": "a",
        "ö": "o",
        "ü": "u",
        "ß": "ss",
        "Ä": "a",
        "Ö": "o",
        "Ü": "u",
        "×": "x",
        "²": "2",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    return normalized.strip("-")


def _machine_by_key(machines, machine_key):
    """Return a seeded machine by normalized demo key."""
    for machine_name, machine in machines.items():
        if _demo_key(machine_name) == machine_key:
            return machine
    return None


def _seed_machines():
    """Create missing demo machines and return them by name."""
    machines = {}
    for name, produced_item, required_employees in MACHINE_DEFINITIONS:
        machine = Machine.query.filter_by(name=name).first()
        if not machine:
            machine = Machine(
                name=name,
                produced_item=produced_item,
                required_employees=required_employees,
            )
            db.session.add(machine)
        criticality, status, downtime_days = MACHINE_OPERATION_STATE.get(
            _demo_key(name),
            ("normal", "running", None),
        )
        machine.produced_item = produced_item
        machine.required_employees = required_employees
        machine.criticality = criticality
        machine.status = status
        machine.last_downtime_at = (
            datetime.now(UTC) - timedelta(days=downtime_days) if downtime_days is not None else None
        )
        machines[name] = machine
    db.session.flush()
    return machines


def _link_employee_machines(employees, machines):
    """Assign deterministic favorite machines to demo employees."""
    machine_list = list(machines.values())
    for idx, emp in enumerate(employees.values()):
        machine = machine_list[idx % len(machine_list)]
        emp.favorite_machine = machine.name
        emp.favorite_machine_id = machine.id


def _seed_inventory(machines):
    """Create or update demo inventory materials."""
    for name, unit_cost, quantity, manufacturer, machine_name in INVENTORY_DEFINITIONS:
        material = InventoryMaterial.query.filter_by(name=name, manufacturer=manufacturer).first()
        if not material:
            material = InventoryMaterial(
                name=name,
                unit_cost=unit_cost,
                quantity=quantity,
                manufacturer=manufacturer,
                machine=machines.get(machine_name),
            )
            db.session.add(material)
        else:
            material.unit_cost = unit_cost
            material.quantity = quantity
            material.manufacturer = manufacturer
            material.machine = machines.get(machine_name)
        min_quantity, criticality, lead_time_days = INVENTORY_POLICY.get(
            _demo_key(name),
            (0, "normal", 0),
        )
        material.min_quantity = min_quantity
        material.criticality = criticality
        material.lead_time_days = lead_time_days


def _seed_errors(departments, machines):
    """Create demo error catalog entries for each default department."""
    now = datetime.now(UTC)
    for dept_name in ("Instandhaltung", "Produktion", "IT", "Verwaltung"):
        department = departments.get(dept_name)
        if not department:
            continue
        prefix = dept_name[:3].upper()
        for error_code_base, title, cause, solution, machine_name in ERROR_DEFINITIONS:
            error_code = f"{prefix}-{error_code_base}"
            existing = ErrorEntry.query.filter_by(
                error_code=error_code, department=department
            ).first()
            machine = machines.get(machine_name)
            if not existing:
                existing = ErrorEntry(
                    error_code=error_code,
                    department=department,
                )
                db.session.add(existing)
            existing.machine = machine_name
            existing.machine_id = machine.id if machine else None
            existing.title = title
            existing.description = (
                f"{title} – aufgetreten im Bereich {dept_name}. "
                "Störung absichern, Anlage prüfen, Maßnahme dokumentieren."
            )
            existing.possible_causes = cause
            existing.solution = solution
            _apply_demo_error_state(existing, dept_name, error_code_base, now)


def _apply_demo_error_state(entry, department_name, error_code_base, now):
    """Apply repeatable active/catalog state to a seeded error entry."""
    state = ACTIVE_ERROR_STATES.get((department_name, error_code_base))
    if state:
        entry.status = state["status"]
        entry.severity = state["severity"]
        entry.cause_category = state["cause_category"]
        entry.impact = state["impact"]
        entry.downtime_minutes = state["downtime_minutes"]
        entry.production_loss_minutes = state["production_loss_minutes"]
        entry.repeat_count = state["repeat_count"]
        entry.last_seen_at = now - timedelta(hours=state["seen_hours"])
        entry.closed_at = None
        return
    entry.status = "closed"
    entry.severity = "medium"
    entry.cause_category = ""
    entry.impact = ""
    entry.downtime_minutes = 0
    entry.production_loss_minutes = 0
    entry.repeat_count = 0
    entry.last_seen_at = None
    entry.closed_at = entry.closed_at or now - timedelta(days=14)


def _seed_maintenance_plans(departments, users, machines):
    """Create recurring maintenance plans linked to departments and machines."""
    priority_map = {"urgent": Priority.URGENT, "soon": Priority.SOON, "normal": Priority.NORMAL}
    creator = users.get("admin")
    if not creator:
        return
    today = date.today()
    for (
        title,
        description,
        interval_days,
        due_days,
        priority,
        dept_name,
        machine_key,
        is_active,
    ) in MAINTENANCE_PLAN_DEFINITIONS:
        department = departments.get(dept_name)
        machine = _machine_by_key(machines, machine_key)
        if not department:
            continue
        plan = MaintenancePlan.query.filter_by(
            title=title,
            department=department,
        ).first()
        if not plan:
            plan = MaintenancePlan(
                title=title,
                department=department,
                created_by=creator.id,
                interval_days=interval_days,
                next_due_date=today + timedelta(days=due_days),
            )
            db.session.add(plan)
        plan.description = description
        plan.interval_days = interval_days
        plan.next_due_date = today + timedelta(days=due_days)
        plan.priority = priority_map[priority]
        plan.is_active = is_active
        plan.machine = machine


def _seed_tasks(departments, users, machines):
    """Create demo tasks across departments and workflow states."""
    today = date.today()
    now = datetime.now(UTC)

    priority_map = {"urgent": Priority.URGENT, "soon": Priority.SOON, "normal": Priority.NORMAL}
    status_map = {
        "open": TaskStatus.OPEN,
        "in_progress": TaskStatus.IN_PROGRESS,
        "done": TaskStatus.DONE,
    }
    creator = users.get("admin")

    for (
        title,
        description,
        prio_str,
        status_str,
        due_days,
        dept_name,
        _machine_name,
        worker_username,
    ) in TASK_DEFINITIONS:
        department = departments.get(dept_name)
        existing = Task.query.filter_by(title=title, department=department).first()
        status = status_map[status_str]
        worker = users.get(worker_username) if worker_username else None

        task = existing or Task(title=title, department=department)
        task.description = description
        task.priority = priority_map[prio_str]
        task.status = status
        task.due_date = today + timedelta(days=due_days)
        task.department = department
        if not existing:
            task.created_by = creator.id if creator else None

        task.current_worker_id = None
        task.completed_by_id = None
        task.started_at = None
        task.completed_at = None

        if status == TaskStatus.IN_PROGRESS and worker:
            task.current_worker_id = worker.id
            task.started_at = now - timedelta(hours=abs(due_days) * 3 + 2)

        if status == TaskStatus.DONE and worker:
            task.current_worker_id = worker.id
            task.started_at = now - timedelta(days=abs(due_days) + 1)
            task.completed_by_id = worker.id
            task.completed_at = now - timedelta(days=abs(due_days))

        _apply_task_operational_details(task, prio_str, status_str, due_days)
        if not existing:
            db.session.add(task)


def _apply_task_operational_details(task, priority_name, status_name, due_days):
    """Add realistic planning, effort and blocker metadata to a demo task."""
    base_minutes = {"urgent": 180, "soon": 120, "normal": 75}[priority_name]
    task.planned_minutes = base_minutes
    if status_name == "done":
        task.actual_minutes = max(30, base_minutes + (abs(due_days) * 8) - 12)
    elif status_name == "in_progress":
        task.actual_minutes = max(15, round(base_minutes * 0.45))
    else:
        task.actual_minutes = 0
    if "Dichtungssatz" in task.description or "Lager-Kit" in task.description:
        task.blocked_reason = "Wartet auf Ersatzteilfreigabe oder Materialbereitstellung."
    elif task.priority == Priority.URGENT and task.status == TaskStatus.OPEN:
        task.blocked_reason = "Stillstandsfenster muss mit Produktion abgestimmt werden."
    else:
        task.blocked_reason = ""
    task.reopened_count = 1 if task.status == TaskStatus.IN_PROGRESS and due_days <= 0 else 0


def _seed_documents(users):
    """Generate demo maintenance reports for completed tasks."""
    creator = users.get("admin")
    completed_tasks = (
        Task.query.filter(Task.status == TaskStatus.DONE).order_by(Task.id.asc()).limit(8).all()
    )
    for task in completed_tasks:
        existing = GeneratedDocument.query.filter_by(task_id=task.id).first()
        if existing:
            _enrich_generated_document(existing, creator)
            continue
        machine_name = _machine_for_task(task)
        document = generate_maintenance_report(
            task,
            creator,
            {
                "machine": machine_name,
                "cause": "Planmäßige Wartung oder gemeldete Störung laut Schichtbuch.",
                "action": (
                    "Prüfung durchgeführt, Befund dokumentiert, "
                    "Verschleißteile getauscht und Anlage freigegeben."
                ),
                "result": "Anlage läuft im Sollbereich, alle Grenzwerte eingehalten.",
                "notes": "Nächste Fälligkeitstermin in Wartungskalender eingetragen.",
            },
        )
        _enrich_generated_document(document, creator)


def _enrich_generated_document(document, user):
    """Attach review-ready demo metadata to a generated maintenance document."""
    document.status = "approved"
    document.summary_status = "completed"
    document.summary = (
        f"Freigegebener Wartungsbericht fuer {document.machine or 'Anlage'}; "
        "Massnahme abgeschlossen, Befund und Folgepruefung dokumentiert."
    )
    document.quality_score = 88
    document.quality_status = "checked"
    document.quality_checked_at = datetime.now(UTC)
    if user:
        document.approved_by = user.id
        document.approved_at = datetime.now(UTC)
        document.approval_comment = "Demo-Freigabe: vollstaendig und nachvollziehbar."


def _seed_machine_manuals(users, machines):
    """Create compact machine manuals that can be indexed by RAG."""
    creator = users.get("admin") or next(iter(users.values()), None)
    if not creator:
        return
    for machine_key, department, filename, title, content in MANUAL_DEFINITIONS:
        existing = MachineManual.query.filter_by(original_filename=filename).first()
        if existing:
            existing.title = title
            existing.department = department
            existing.summary = content.splitlines()[0] if content else title
            existing.summary_status = "completed"
            existing.analysis = _manual_analysis_text(title, content)
            existing.analysis_status = "completed"
            continue
        machine = _machine_by_key(machines, machine_key)
        file_storage = FileStorage(
            stream=BytesIO(content.encode("utf-8")),
            filename=filename,
            content_type="text/plain",
        )
        upload_machine_manual(
            file_storage,
            creator,
            machine_id=machine.id if machine else None,
            department=department,
        )
        manual = MachineManual.query.filter_by(original_filename=filename).first()
        if manual:
            manual.title = title
            manual.summary = content.splitlines()[0] if content else title
            manual.summary_status = "completed"
            manual.analysis = _manual_analysis_text(title, content)
            manual.analysis_status = "completed"


def _manual_analysis_text(title, content):
    """Return a short local analysis for seeded manuals."""
    return (
        f"{title}: Demo-Manual mit relevanten Fehlercodes, Sicherheitsfolge, "
        f"Ersatzteilhinweisen und freigegebenen Pruefschritten. Inhalt: {content[:500]}"
    )


def _seed_shift_handovers(users):
    """Create realistic digital shift handover records."""
    today = date.today()
    for (
        department,
        day_offset,
        shift_type,
        status,
        username,
        content,
        open_tasks,
        machine_notes,
        next_notes,
    ) in SHIFT_HANDOVER_DEFINITIONS:
        shift_date = today + timedelta(days=day_offset)
        existing = ShiftHandover.query.filter_by(
            department=department,
            shift_date=shift_date,
            shift_type=shift_type,
        ).first()
        user = users.get(username)
        if not existing:
            existing = ShiftHandover(
                department=department,
                shift_date=shift_date,
                shift_type=shift_type,
            )
            db.session.add(existing)
        existing.status = status
        existing.handed_over_by = user.id if user else None
        existing.handed_over_at = datetime.now(UTC) if status == "completed" else None
        existing.content = content
        existing.open_tasks = open_tasks
        existing.machine_notes = machine_notes
        existing.next_notes = next_notes


def _seed_training_entries(users):
    """Create curated demo assistant training entries for source-backed questions."""
    creator = users.get("admin")
    for (
        title,
        question,
        answer,
        keywords,
        category,
        department,
        priority,
        is_active,
    ) in TRAINING_DEFINITIONS:
        entry = AssistantTrainingEntry.query.filter_by(
            title=title,
            category=category,
        ).first()
        if not entry:
            entry = AssistantTrainingEntry(
                title=title,
                category=category,
                created_by=creator.id if creator else None,
            )
            db.session.add(entry)
        entry.question = question
        entry.answer = answer
        entry.keywords = keywords
        entry.department = department
        entry.priority = priority
        entry.is_active = is_active


def _machine_for_task(task):
    """Infer the most likely machine name for a demo task."""
    task_text = f"{task.title} {task.description}".lower()
    for name, _, _ in MACHINE_DEFINITIONS:
        if name.lower() in task_text:
            return name
        first_token = name.lower().split()[0]
        if len(first_token) > 4 and first_token in task_text:
            return name
    return MACHINE_DEFINITIONS[task.id % len(MACHINE_DEFINITIONS)][0]
