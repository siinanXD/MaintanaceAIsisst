"""Realistic demo data for development and demos."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_

from app.departments.services import DEFAULT_DEPARTMENTS, ensure_default_departments
from app.extensions import db
from app.models import (
    Department,
    Employee,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    Machine,
    Priority,
    Role,
    Task,
    TaskStatus,
    User,
)
from app.permissions import upsert_default_permissions
from app.services.document_service import generate_maintenance_report


DEMO_PASSWORD = "Demo1234!"
COMPANY_DOMAIN = "fertigungs-gmbh.de"

# ---------------------------------------------------------------------------
# Stammdaten Mitarbeiter
# ---------------------------------------------------------------------------

EMPLOYEE_DATA = [
    # (Personalnummer, Vorname, Nachname, Geb., Straße, PLZ, Stadt, Abteilung, Schichtmodell, Schicht, Team, EG, Qualifikationen)
    ("MA-0001", "Thomas",   "Hoffmann",  date(1978,  3, 12), "Ruhrstraße 14",          "44135", "Dortmund",  "Instandhaltung", "3-Schicht",   "Früh",   1, "EG 8",  "SPS-Programmierung, Schaltschrankbau, Elektrofachkraft"),
    ("MA-0002", "Sandra",   "Becker",    date(1985,  7, 23), "Kirchweg 5",             "44787", "Bochum",    "Instandhaltung", "3-Schicht",   "Spät",   1, "EG 7",  "Hydraulik, Pneumatik, Schweißen MAG"),
    ("MA-0003", "Kevin",    "Schulze",   date(1991,  1,  8), "Hauptstraße 82",         "45127", "Essen",     "Instandhaltung", "3-Schicht",   "Nacht",  2, "EG 6",  "Antriebstechnik, Frequenzumrichter, SPS-Basis"),
    ("MA-0004", "Miriam",   "Krause",    date(1982, 11,  3), "Lindenallee 27",         "58095", "Hagen",     "Instandhaltung", "3-Schicht",   "Früh",   2, "EG 7",  "Mess- und Regelungstechnik, Kalibrierung"),
    ("MA-0005", "Oliver",   "Petersen",  date(1975,  4, 17), "Bahnhofstraße 3",        "42103", "Wuppertal", "Instandhaltung", "2-Schicht",   "Früh",   3, "EG 9",  "Elektrofachkraft, Betriebsmittelbau, VDE-Prüfung"),
    ("MA-0006", "Fatima",   "Yilmaz",    date(1989,  9,  5), "Westfalenring 44",       "44135", "Dortmund",  "Instandhaltung", "2-Schicht",   "Spät",   3, "EG 6",  "Pneumatik, Wartungsplanung, 5S-Auditor"),
    ("MA-0007", "Markus",   "Wagner",    date(1980,  6, 30), "Schillerstraße 11",      "44787", "Bochum",    "Instandhaltung", "Tagschicht",  "Frei",   4, "EG 9",  "Robotik, KUKA-Programmierung, Sicherheitstechnik"),
    ("MA-0008", "Julia",    "Neumann",   date(1994,  2, 14), "Bergmannstraße 8",       "45127", "Essen",     "Instandhaltung", "3-Schicht",   "Nacht",  4, "EG 6",  "Elektrische Prüftechnik, Messprotokoll"),
    ("MA-0009", "Dirk",     "Hartmann",  date(1973,  8, 22), "Am Förderturm 17",       "44135", "Dortmund",  "Produktion",     "3-Schicht",   "Früh",   1, "EG 6",  "CNC-Drehen, Fräsen, Messmittelkunde"),
    ("MA-0010", "Ayse",     "Demir",     date(1987, 12,  1), "Kohlenpottweg 33",       "44787", "Bochum",    "Produktion",     "3-Schicht",   "Spät",   1, "EG 5",  "Rüsten CNC, Erstmuster, Qualitätsprüfung"),
    ("MA-0011", "Patrick",  "Müller",    date(1992,  5, 19), "Industrieweg 6",         "45127", "Essen",     "Produktion",     "3-Schicht",   "Nacht",  2, "EG 5",  "Spritzguss, Werkzeugwechsel, Kanban"),
    ("MA-0012", "Claudia",  "Werner",    date(1984, 10,  7), "Hochofenstraße 21",      "58095", "Hagen",     "Produktion",     "3-Schicht",   "Früh",   2, "EG 6",  "Montagelinie, Einrichtung, Lean Basics"),
    ("MA-0013", "Stefan",   "Braun",     date(1979,  3, 25), "Zechensiedlung 4",       "42103", "Wuppertal", "Produktion",     "3-Schicht",   "Spät",   3, "EG 5",  "Foerderband, Staplerführerschein, Sichtkontrolle"),
    ("MA-0014", "Melanie",  "Koch",      date(1996,  7, 11), "Schachtstraße 9",        "44135", "Dortmund",  "Produktion",     "3-Schicht",   "Nacht",  3, "EG 5",  "Verpackung, Etikettiersystem, 5S"),
    ("MA-0015", "Tobias",   "Zimmermann",date(1983,  1,  4), "Ruhrdeich 55",           "44787", "Bochum",    "Produktion",     "Wochenendteam","Früh",  4, "EG 6",  "Roboterzelle, Vakuumtechnik, Probelauf"),
    ("MA-0016", "Nicole",   "Lange",     date(1990,  4, 28), "Steinkohlenallee 13",    "45127", "Essen",     "Produktion",     "2-Schicht",   "Früh",   4, "EG 5",  "Qualitätsprüfung, Erstmuster, SPC"),
    ("MA-0017", "Andreas",  "Schmitz",   date(1977,  9, 16), "Kanalstraße 38",         "58095", "Hagen",     "Produktion",     "2-Schicht",   "Spät",   5, "EG 6",  "CNC-Fräsen, Messmaschinenführer, Lean"),
    ("MA-0018", "Lena",     "Wolf",      date(1995, 11, 22), "Prosper-Platz 2",        "42103", "Wuppertal", "Produktion",     "3-Schicht",   "Früh",   5, "EG 5",  "Montagelinie, Sichtkontrolle, Schichtübergabe"),
    ("MA-0019", "Carsten",  "Richter",   date(1986,  6,  3), "Hüttenstraße 47",        "44135", "Dortmund",  "Logistik",       "Tagschicht",  "Frei",   6, "EG 5",  "Staplerführerschein, Kranbedienung, Lagerlogistik"),
    ("MA-0020", "Sabine",   "Klein",     date(1981,  2, 18), "Am Viadukt 8",           "44787", "Bochum",    "Logistik",       "2-Schicht",   "Früh",   6, "EG 4",  "Wareneingang, Buchung SAP, Inventur"),
    ("MA-0021", "Daniel",   "Schäfer",   date(1993,  8,  9), "Bergbaustraße 71",       "45127", "Essen",     "Logistik",       "2-Schicht",   "Spät",   7, "EG 4",  "Kommissionierung, Etikettierung, Versand"),
    ("MA-0022", "Tanja",    "König",     date(1988, 12, 27), "Zeche-Nord-Str. 5",      "58095", "Hagen",     "Logistik",       "Tagschicht",  "Frei",   7, "EG 5",  "Staplerführerschein, Gefahrgutbeauftragter"),
    ("MA-0023", "Michael",  "Fischer",   date(1976,  5,  6), "Gußstahlstraße 29",      "42103", "Wuppertal", "Qualität",       "Tagschicht",  "Frei",   8, "EG 8",  "Qualitätsmanagement, Reklamationsbearbeitung, Auditor"),
    ("MA-0024", "Kerstin",  "Herrmann",  date(1983, 10, 14), "Altenessener Str. 62",   "45127", "Essen",     "Qualität",       "2-Schicht",   "Früh",   8, "EG 7",  "SPC, Messmittelkunde, FMEA"),
    ("MA-0025", "Jens",     "Schwarz",   date(1990,  3, 31), "Nordsternstraße 17",     "44135", "Dortmund",  "Qualität",       "2-Schicht",   "Spät",   8, "EG 7",  "Erstmuster, Mess- und Prüftechnik, CMM-Bedienung"),
    ("MA-0026", "Petra",    "Weiß",      date(1978,  7, 20), "Victoriastraße 3",       "44787", "Bochum",    "Verwaltung",     "Tagschicht",  "Frei",   9, "EG 8",  "Einkauf, SAP MM, Rahmenverträge"),
    ("MA-0027", "Frank",    "Lorenz",    date(1972,  1, 15), "Obere Schmidtstraße 44", "45127", "Essen",     "Verwaltung",     "Tagschicht",  "Frei",   9, "EG 9",  "Kostenrechnung, Controlling, DATEV"),
    ("MA-0028", "Ines",     "Meyer",     date(1985,  6,  8), "Glückaufstraße 16",      "58095", "Hagen",     "Verwaltung",     "Tagschicht",  "Frei",   9, "EG 7",  "Personalwesen, Entgeltabrechnung, Sozialrecht"),
    ("MA-0029", "Ralf",     "Bergmann",  date(1981, 11, 25), "Lothringenstraße 9",     "42103", "Wuppertal", "IT",             "Tagschicht",  "Frei",  10, "EG 9",  "Windows Server, VMware, Active Directory"),
    ("MA-0030", "Sonja",    "Brandt",    date(1993,  4, 10), "Hiberniastraße 23",      "44135", "Dortmund",  "IT",             "Tagschicht",  "Frei",  10, "EG 8",  "Netzwerk, Firewall, WLAN-Administration"),
]

# ---------------------------------------------------------------------------
# Benutzerdefinitionen (verknüpft mit Mitarbeitern via Personalnummer)
# ---------------------------------------------------------------------------

USER_DEFINITIONS = [
    # (username, email, role, dept_name, employee_personnel_number)
    ("admin",                 "admin@fertigungs-gmbh.de",                  "master_admin",     None,             None),
    ("thomas.hoffmann",       "thomas.hoffmann@fertigungs-gmbh.de",        "instandhaltung",   "Instandhaltung", "MA-0001"),
    ("sandra.becker",         "sandra.becker@fertigungs-gmbh.de",          "instandhaltung",   "Instandhaltung", "MA-0002"),
    ("kevin.schulze",         "kevin.schulze@fertigungs-gmbh.de",          "instandhaltung",   "Instandhaltung", "MA-0003"),
    ("markus.wagner",         "markus.wagner@fertigungs-gmbh.de",          "instandhaltung",   "Instandhaltung", "MA-0007"),
    ("dirk.hartmann",         "dirk.hartmann@fertigungs-gmbh.de",          "produktion",       "Produktion",     "MA-0009"),
    ("ayse.demir",            "ayse.demir@fertigungs-gmbh.de",             "produktion",       "Produktion",     "MA-0010"),
    ("patrick.mueller",       "patrick.mueller@fertigungs-gmbh.de",        "produktion",       "Produktion",     "MA-0011"),
    ("claudia.werner",        "claudia.werner@fertigungs-gmbh.de",         "produktion",       "Produktion",     "MA-0012"),
    ("stefan.braun",          "stefan.braun@fertigungs-gmbh.de",           "produktion",       "Produktion",     "MA-0013"),
    ("petra.weiss",           "petra.weiss@fertigungs-gmbh.de",            "verwaltung",       "Verwaltung",     "MA-0026"),
    ("frank.lorenz",          "frank.lorenz@fertigungs-gmbh.de",           "verwaltung",       "Verwaltung",     "MA-0027"),
    ("ines.meyer",            "ines.meyer@fertigungs-gmbh.de",             "personalabteilung","Verwaltung",     "MA-0028"),
    ("michael.fischer",       "michael.fischer@fertigungs-gmbh.de",        "verwaltung",       "Verwaltung",     "MA-0023"),
    ("ralf.bergmann",         "ralf.bergmann@fertigungs-gmbh.de",          "it",               "IT",             "MA-0029"),
    ("sonja.brandt",          "sonja.brandt@fertigungs-gmbh.de",           "it",               "IT",             "MA-0030"),
    ("carsten.richter",       "carsten.richter@fertigungs-gmbh.de",        "produktion",       "Produktion",     "MA-0019"),
    ("miriam.krause",         "miriam.krause@fertigungs-gmbh.de",          "instandhaltung",   "Instandhaltung", "MA-0004"),
    ("oliver.petersen",       "oliver.petersen@fertigungs-gmbh.de",        "instandhaltung",   "Instandhaltung", "MA-0005"),
    ("tobias.zimmermann",     "tobias.zimmermann@fertigungs-gmbh.de",      "produktion",       "Produktion",     "MA-0015"),
]

# ---------------------------------------------------------------------------
# Maschinen
# ---------------------------------------------------------------------------

MACHINE_DEFINITIONS = [
    ("CNC-Fräse 01",          "Aluminium-Gehäuse",          3),
    ("CNC-Drehmaschine 02",   "Präzisionswellen",            2),
    ("Hydraulikpresse 03",    "Blechformteile",              2),
    ("Spritzgussanlage 04",   "Kunststoffclips",             4),
    ("Montagelinie 05",       "Sensorbaugruppen",            6),
    ("Förderband Linie A",    "Materialfluss Produktion A",  1),
    ("Verpackungsanlage 06",  "Versandfertige Sets",         3),
    ("Kompressorstation 07",  "Druckluftversorgung",         1),
    ("Prüfstand 08",          "End-of-Line-Prüfung",         2),
    ("Roboterzelle 09",       "Automatisierte Bestückung",   2),
    ("Laserbeschrifter 10",   "Typenschilder",               1),
    ("Waschanlage 11",        "Bauteilreinigung",            2),
]

# ---------------------------------------------------------------------------
# Lagermaterial
# ---------------------------------------------------------------------------

INVENTORY_DEFINITIONS = [
    # (Name, Einzelpreis, Bestand, Hersteller, Maschinenname)
    ("Aluminiumprofil 40×40",        18.90,  420, "Item Industrietechnik",  "CNC-Fräse 01"),
    ("Hartmetall-Fräser 8 mm",       42.50,   36, "Hoffmann Group",         "CNC-Fräse 01"),
    ("Kühlschmierstoff 20 l",        96.00,   18, "Castrol",                "CNC-Fräse 01"),
    ("Drehmeissel CNMG",             12.80,   90, "Sandvik Coromant",       "CNC-Drehmaschine 02"),
    ("Präzisionslager 6205",          7.40,  240, "SKF",                    "CNC-Drehmaschine 02"),
    ("Hydrauliköl HLP 46",           68.00,   22, "Fuchs",                  "Hydraulikpresse 03"),
    ("Dichtungssatz Presse",        115.00,    0, "Parker",                 "Hydraulikpresse 03"),
    ("Granulat PA6 schwarz",          3.70, 2600, "BASF",                   "Spritzgussanlage 04"),
    ("Heizkabel 230 V",              54.90,    2, "Hotset",                 "Spritzgussanlage 04"),
    ("Greiferfinger Set",            88.00,   16, "Schunk",                 "Montagelinie 05"),
    ("M8 Sensor induktiv",           24.70,    3, "Sick",                   "Montagelinie 05"),
    ("Fördergurt PU 1200×600",      310.00,    1, "Habasit",                "Förderband Linie A"),
    ("Antriebsrolle 60 mm",          74.20,   12, "Interroll",              "Förderband Linie A"),
    ("Karton 400×300×200",            1.15, 1800, "Smurfit Kappa",          "Verpackungsanlage 06"),
    ("Etikettenrolle 100×60",         9.80,   75, "Avery Dennison",         "Verpackungsanlage 06"),
    ("Druckluftfilter G1/2",         33.50,    1, "Atlas Copco",            "Kompressorstation 07"),
    ("Keilriemen XPZ 1000",          18.30,   30, "Optibelt",               "Kompressorstation 07"),
    ("Prüfadapter 24 V",            129.00,   10, "Phoenix Contact",        "Prüfstand 08"),
    ("Messleitung 2 m",              11.90,  110, "Staubli",                "Prüfstand 08"),
    ("Vakuumsauger 30 mm",            6.80,  160, "Festo",                  "Roboterzelle 09"),
    ("Servo-Kabel 5 m",              47.50,   35, "Igus",                   "Roboterzelle 09"),
    ("Laser-Schutzglas",            145.00,    0, "Trumpf",                 "Laserbeschrifter 10"),
    ("Reinigungskonzentrat 10 l",    52.00,   26, "Henkel",                 "Waschanlage 11"),
    ("Edelstahlkorb klein",          39.90,   42, "Keller & Kalmbach",      "Waschanlage 11"),
    # Zusätzliche kritische Positionen
    ("O-Ring-Satz 120-teilig",       28.60,    2, "Eriks",                  "Hydraulikpresse 03"),
    ("Sicherungsautomat C16",        12.40,    4, "Siemens",                "Kompressorstation 07"),
    ("Schmierfett 400 g",             9.80,    5, "SKF",                    "CNC-Drehmaschine 02"),
    ("Schutzschlauch 1 m",            6.30,    3, "Igus",                   "Montagelinie 05"),
    ("Klemmblock 4 mm²",              1.90,    8, "Wago",                   "Prüfstand 08"),
]

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

TASK_DEFINITIONS = [
    # (titel, beschreibung, priorität, status, fälligkeit_tage, abteilung, maschine_name, worker_username)
    # Instandhaltung
    ("Hydraulikpresse 03 – Dichtigkeitsprüfung",
     "Sämtliche Hydraulikverbindungen und Zylinderanschlüsse auf Leckagen prüfen. "
     "Druckverlustmessung durchführen, Ergebnis in der Wartungsakte dokumentieren.",
     "urgent", "in_progress", 0, "Instandhaltung", "Hydraulikpresse 03", "thomas.hoffmann"),

    ("CNC-Fräse 01 – Spindellager tauschen",
     "Austausch des Hauptspindellagers nach 8.200 Betriebsstunden. "
     "Lager-Kit liegt in Lager vor, Ausfallzeit ca. 4 h einplanen.",
     "urgent", "open", 1, "Instandhaltung", "CNC-Fräse 01", None),

    ("Kompressorstation 07 – Ölwechsel und Filterwechsel",
     "Jährlicher Ölwechsel inkl. Öl- und Luftfilter. "
     "Betriebsstundenzähler notieren, Kondensatableiter prüfen.",
     "soon", "open", 3, "Instandhaltung", "Kompressorstation 07", None),

    ("Roboterzelle 09 – TCP-Kalibrierung nach Crash",
     "Nach Kollision mit Bauteil: Werkzeugmittelpunkt neu einmessen, "
     "alle Achsen auf mechanischen Schaden prüfen, Protokoll an Qualität.",
     "urgent", "done", -2, "Instandhaltung", "Roboterzelle 09", "markus.wagner"),

    ("Förderband Linie A – Gurtspannung prüfen",
     "Gurt visuell auf Risse und Verschleiß kontrollieren. "
     "Spannung mit Richtwert 200 N/m² vergleichen, ggf. nachspannen.",
     "soon", "in_progress", 1, "Instandhaltung", "Förderband Linie A", "sandra.becker"),

    ("Spritzgussanlage 04 – Heizkabel Heizzone 3 wechseln",
     "Heizzone 3 zeigt Ausfall bei 230 V Prüfung. "
     "Kabel-Set auf Lager, Tausch im Stillstand Spätschicht.",
     "urgent", "open", 0, "Instandhaltung", "Spritzgussanlage 04", None),

    ("Montagelinie 05 – Not-Halt-Kreis testen",
     "Jährliche Sicherheitsprüfung aller Not-Halt-Taster und Türkontakte. "
     "Schaltplan Rev. 4 verwenden, Nachweis für BG-Prüfung erstellen.",
     "normal", "open", 7, "Instandhaltung", "Montagelinie 05", None),

    ("Prüfstand 08 – Kontaktleisten reinigen und prüfen",
     "Oxidierte Kontakte auf Prüfadapter Nr. 3 und 7 gereinigt. "
     "Übergangswiderstand < 10 mΩ dokumentieren.",
     "normal", "done", -5, "Instandhaltung", "Prüfstand 08", "kevin.schulze"),

    ("Waschanlage 11 – Filtereinsatz tauschen",
     "Filtereinsatz nach 250 Betriebsstunden (Vorgabe Hersteller Henkel) wechseln. "
     "Konzentration im Waschbad nachmessen und ggf. korrigieren.",
     "normal", "open", 4, "Instandhaltung", "Waschanlage 11", None),

    ("Laserbeschrifter 10 – Absaugung reinigen",
     "Absaugkanal und Schutzglas visuell prüfen. "
     "Schutzglas gereinigt oder getauscht, Laserleistung nachmessen.",
     "soon", "in_progress", 2, "Instandhaltung", "Laserbeschrifter 10", "miriam.krause"),

    # Produktion
    ("CNC-Fräse 01 – Erstmuster Auftrag 4912 freigeben",
     "Erstmusterprüfbericht für Aluminium-Gehäuse Auftrag 4912 erstellen. "
     "Maße laut Zeichnung Rev. C prüfen, QS-Freigabe einholen.",
     "urgent", "in_progress", 0, "Produktion", "CNC-Fräse 01", "dirk.hartmann"),

    ("Montagelinie 05 – Rüstplan Typ W44 abstimmen",
     "Umrüstung von Typ W42 auf W44 für Nachtschicht vorbereiten. "
     "Greifer-Set aus Lager holen, Rüstblatt aushängen.",
     "soon", "open", 1, "Produktion", "Montagelinie 05", None),

    ("Spritzgussanlage 04 – Granulat PA6 nachfüllen",
     "Materialbehälter Anlage 04 unter 20 kg-Grenze. "
     "Silo-Station 3 befüllen, Chargenprotokoll in SAP buchen.",
     "soon", "done", -1, "Produktion", "Spritzgussanlage 04", "ayse.demir"),

    ("Verpackungsanlage 06 – Etikettierprogramm aktualisieren",
     "Neues Kundenlogo für Auftrag DE-5003 laden. "
     "Testdruck auf 5 Etiketten, Freigabe durch Schichtleiter.",
     "normal", "open", 3, "Produktion", "Verpackungsanlage 06", None),

    ("Förderband Linie A – Ausschussquote Frühschicht erfassen",
     "Ausschussteile zählen und Fehlerart kategorisieren. "
     "Erfassung im Shopfloor-Board bis Schichtende.",
     "normal", "done", -3, "Produktion", "Förderband Linie A", "stefan.braun"),

    ("Roboterzelle 09 – Vakuumsauger wechseln Station 2",
     "Vakuumsauger an Greiferstation 2 verschlissen (Haltekraft < 80 %). "
     "Set aus Lager entnehmen, Tausch im Stillstand.",
     "soon", "in_progress", 1, "Produktion", "Roboterzelle 09", "tobias.zimmermann"),

    ("CNC-Drehmaschine 02 – Präzisionswellen Losgröße 80",
     "Fertigungslos PW-2024-080 anlegen. "
     "Spannmittel-Wechsel, Nullpunkt einmessen, Erstmaß abnehmen.",
     "normal", "open", 5, "Produktion", "CNC-Drehmaschine 02", None),

    ("Montagelinie 05 – Kanban-Karten Sensoren prüfen",
     "Bestand an induktiven Sensoren am Kanban-Regal prüfen. "
     "Unterschreitung Meldebestand → Bestellkarte in Einkaufsbox.",
     "normal", "done", -4, "Produktion", "Montagelinie 05", "claudia.werner"),

    ("Verpackungsanlage 06 – Verpackungsmaterial Auftrag 5021",
     "Kartons 400×300×200 für Auftrag 5021 (240 Stück) bereitstellen. "
     "Lagerort B-04 prüfen, fehlende Menge nachbestellen.",
     "soon", "open", 2, "Produktion", "Verpackungsanlage 06", None),

    ("Prüfstand 08 – End-of-Line-Prüfung Schicht C dokumentieren",
     "Prüfergebnisse aller 48 Baugruppen aus Nachtschicht im System erfassen. "
     "3 NIO-Teile separat lagern und Rückmeldung an QS.",
     "normal", "open", 0, "Produktion", "Prüfstand 08", None),

    # Verwaltung
    ("Wartungsverträge Q2 – Ablauf prüfen",
     "Verträge für CNC-Fräse 01, Hydraulikpresse 03 und Roboterzelle 09 laufen im Juni aus. "
     "Verlängerungsangebote einholen und Vergabereport erstellen.",
     "soon", "open", 6, "Verwaltung", None, None),

    ("Ersatzteil-Rechnungen März klären",
     "3 Rechnungen von Parker, SKF und Igus ohne Bestellbezug. "
     "Kostenstellen-Zuordnung prüfen, Buchungsbeleg an Buchhaltung.",
     "normal", "in_progress", 2, "Verwaltung", None, "petra.weiss"),

    ("Lieferantenstammdaten aktualisieren",
     "Neue Bankdaten von Sandvik Coromant und Atlas Copco in SAP einpflegen. "
     "Änderungsbeleg unterschreiben lassen.",
     "normal", "done", -2, "Verwaltung", None, "frank.lorenz"),

    ("Monatsreport Anlagenverfügbarkeit April",
     "OEE-Kennzahlen aus Schichtprotokollen zusammenführen. "
     "Bericht bis 5. des Monats an Werksleitung.",
     "soon", "open", 4, "Verwaltung", None, None),

    ("Schulungsnachweise 2026 abgleichen",
     "Prüfen welche Mitarbeiter Wiederholungsschulung (UVV, Stapler, Ersthelfer) benötigen. "
     "Liste an Personalreferentin, Termine blockieren.",
     "normal", "open", 10, "Verwaltung", None, None),

    # IT
    ("Backup-Status Produktionsserver prüfen",
     "Backup-Job VM-PROD-01 schlug laut Monitoring 2× fehl. "
     "Log auswerten, freien Speicher prüfen, Backup manuell anstoßen.",
     "urgent", "in_progress", 0, "IT", None, "ralf.bergmann"),

    ("WLAN-Ausleuchtung Halle 2 nachmessen",
     "Schichtleiter meldet Verbindungsabbrüche am Tablet Linie A. "
     "Site-Survey mit NetSpot durchführen, Access Point Pos. anpassen.",
     "soon", "open", 3, "IT", None, None),

    ("VPN-Zugriff Rufbereitschaft testen",
     "Monatstest gemäß IT-Richtlinie: alle 5 Rufbereitschafts-Zugänge einwählen. "
     "Ergebnis im IT-Betriebshandbuch dokumentieren.",
     "normal", "done", -1, "IT", None, "sonja.brandt"),

    ("Scanner-Firmware Lager aktualisieren",
     "Honeywell-Scanner Lager A und B auf Firmware 3.2.1 bringen. "
     "Update-Paket liegt auf Netzlaufwerk \\\\srv01\\updates\\scanner bereit.",
     "normal", "open", 5, "IT", None, None),

    ("USV-Selbsttest auswerten",
     "Wöchentlicher Selbsttest der USV im Schaltschrank Halle 1. "
     "Batteriezustand und Laufzeit protokollieren, Wert < 8 min → Tausch melden.",
     "normal", "done", -6, "IT", None, "ralf.bergmann"),
]

# ---------------------------------------------------------------------------
# Fehlerkatalog
# ---------------------------------------------------------------------------

ERROR_DEFINITIONS = [
    # (fehlercode_suffix, titel, ursache, lösung, maschinenname)
    ("E-101", "Sensor liefert kein Signal",
     "Kabelbruch, verschmutzter Sensor oder falscher Einbauabstand.",
     "Sensor reinigen, Abstand laut Datenblatt prüfen, Kabel auf Durchgang messen.",
     "Montagelinie 05"),
    ("E-102", "Motor überlastet",
     "Blockierter Antrieb, erhöhte Lagerreibung oder falsche Umrichterparameter.",
     "Antrieb von Hand drehen, Lager abhorchen, I-max-Parameter prüfen.",
     "Förderband Linie A"),
    ("E-103", "Druck fällt ab",
     "Leckage an Schlauch oder Verschraubung, defektes Ventil oder Filter zugesetzt.",
     "Lecktest mit Sprühkreide, Ventilspule messen, Filter tauschen.",
     "Hydraulikpresse 03"),
    ("E-104", "Temperatur außerhalb Toleranz",
     "Heizkreis defekt, Kühlwasserdurchfluss zu gering oder Regler falsch parametriert.",
     "Heizzone per Messzange prüfen, Kühlkreis entlüften, Sollwert kontrollieren.",
     "Spritzgussanlage 04"),
    ("E-105", "Kommunikation zur Steuerung gestört",
     "Netzwerkfehler, SPS-Koppler überhitzt oder IP-Konflikt im Subnetz.",
     "Switch-Port LED prüfen, SPS-Diagnose aufrufen, IP-Tabelle sichten.",
     "CNC-Fräse 01"),
    ("E-106", "Not-Halt-Kreis offen",
     "Türkontakt nicht geschlossen, Not-Halt-Taster rastet nicht oder Sicherheitsrelais ausgefallen.",
     "Alle Schutztüren schließen, Taster entriegeln, Relaisausgänge messen.",
     "Montagelinie 05"),
    ("E-107", "Werkzeug nicht referenziert",
     "Referenzfahrt nach Stromausfall ausgeblieben oder Endschalter verschmutzt.",
     "Referenzfahrt starten, Endschalter reinigen, Positions-Offset kontrollieren.",
     "CNC-Fräse 01"),
    ("E-108", "Barcode nicht lesbar",
     "Etikett beschädigt, Scannerlinse verschmutzt oder Beleuchtung ausgefallen.",
     "Linse reinigen, Etikett neu drucken, LED-Beleuchtung prüfen.",
     "Verpackungsanlage 06"),
    ("E-109", "Vakuum zu niedrig",
     "Sauger verschlissen, Schlauch undicht oder Magnetventil klemmt.",
     "Sauger auf Risse prüfen, Druckverlusttest, Ventil durchschalten.",
     "Roboterzelle 09"),
    ("E-110", "Materialstau erkannt",
     "Bauteil verkippt in Führung, Bandlauf dejustiert oder Sensor zu nah.",
     "Stau beseitigen, Führungsbreite prüfen, Sensor nachjustieren.",
     "Förderband Linie A"),
    ("E-111", "Achse folgt Sollwert nicht",
     "Geberfehler, mechanische Verspannung oder Lagerspiel zu groß.",
     "Schlepp-Fehlergrenze auslesen, Geber tauschen, Mechanik nachprüfen.",
     "CNC-Drehmaschine 02"),
    ("E-112", "Ölstand niedrig",
     "Leckage am Zylinder oder Schlauch, normaler Verbrauch überschritten.",
     "Anlage sicher stoppen, Leckage lokalisieren, Öl nachfüllen.",
     "Hydraulikpresse 03"),
    ("E-113", "Prüfergebnis instabil",
     "Schlechte Kontaktierung, verschlissener Adapter oder Messleitung gebrochen.",
     "Kontakte reinigen, Leitungswiderstand messen, Adapter tauschen.",
     "Prüfstand 08"),
    ("E-114", "Absaugung meldet Unterdruck",
     "Filter zugesetzt, Klappe klemmt oder Schlauch geknickt.",
     "Filter reinigen oder tauschen, Klappe manuell öffnen, Schlauchführung prüfen.",
     "Laserbeschrifter 10"),
    ("E-115", "Rüstdaten fehlen",
     "Auftragsdaten noch nicht an Maschinensteuerung übertragen oder falsches Rezept gewählt.",
     "Auftrag im MES öffnen, Rezept manuell laden, Parametrierung bestätigen.",
     "CNC-Fräse 01"),
    ("E-116", "Druckluftqualität schlecht",
     "Trockner abgeschaltet, Kondensatableiter defekt oder Filter gesättigt.",
     "Taupunkt messen, Ableiter testen, Filter wechseln.",
     "Kompressorstation 07"),
    ("E-117", "Schutzzaun offen",
     "Türschalter defekt, Verriegelung klemmt oder Zuhaltung nicht bestromt.",
     "Schalter tauschen, Zuhaltespannung messen, Verriegelungsbolzen reinigen.",
     "Roboterzelle 09"),
    ("E-118", "Füllstand Material niedrig",
     "Nachfüllung vergessen oder Sensor liefert Fehlmeldung.",
     "Behälter befüllen, Sensor-Schwelle prüfen, Meldung quittieren.",
     "Spritzgussanlage 04"),
    ("E-119", "Kalibrierung abgelaufen",
     "Kalibrierintervall laut Prüfplan überschritten.",
     "Prüfmittel sperren, Kalibrierung beauftragen, Ergebnis einpflegen.",
     "Prüfstand 08"),
    ("E-120", "Qualitätsgrenze überschritten",
     "Verschlissenes Werkzeug, veränderte Rohmaterialcharge oder Prozess-Drift.",
     "Werkzeug tauschen, Charge sperren, Prozessparameter zurücksetzen.",
     "CNC-Fräse 01"),
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
    machines = _seed_machines()
    db.session.flush()
    _seed_inventory(machines)
    _link_employee_machines(employees, machines)
    _seed_errors(departments, machines)
    _seed_tasks(departments, users, machines)
    db.session.flush()
    _seed_documents(users)
    db.session.commit()
    return {
        "users": len(users),
        "employees": len(employees),
        "machines": len(machines),
        "inventory_materials": InventoryMaterial.query.count(),
        "tasks": Task.query.count(),
        "errors": ErrorEntry.query.count(),
        "documents": GeneratedDocument.query.count(),
        "password": DEMO_PASSWORD,
    }


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _departments_by_name():
    return {
        dep.name: dep
        for dep in Department.query.filter(Department.name.in_(DEFAULT_DEPARTMENTS)).all()
    }


def _seed_employees():
    employees = {}
    for row in EMPLOYEE_DATA:
        (personnel_number, first_name, last_name, birth_date,
         street, postal_code, city, department, shift_model,
         current_shift, team, salary_group, qualifications) = row

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
    users = {}
    for username, email, role_value, dept_name, emp_nr in USER_DEFINITIONS:
        user = User.query.filter(
            or_(User.username == username, User.email == email)
        ).first()
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


def _seed_machines():
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
        machines[name] = machine
    db.session.flush()
    return machines


def _link_employee_machines(employees, machines):
    machine_list = list(machines.values())
    for idx, emp in enumerate(employees.values()):
        machine = machine_list[idx % len(machine_list)]
        emp.favorite_machine = machine.name
        emp.favorite_machine_id = machine.id


def _seed_inventory(machines):
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
            material.quantity = quantity
            material.machine = machines.get(machine_name)


def _seed_errors(departments, machines):
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
            if existing:
                continue
            machine = machines.get(machine_name)
            entry = ErrorEntry(
                machine=machine_name,
                machine_id=machine.id if machine else None,
                error_code=error_code,
                title=title,
                description=(
                    f"{title} – aufgetreten im Bereich {dept_name}. "
                    "Störung absichern, Anlage prüfen, Maßnahme dokumentieren."
                ),
                possible_causes=cause,
                solution=solution,
                department=department,
            )
            db.session.add(entry)


def _seed_tasks(departments, users, machines):
    today = date.today()
    now = datetime.now(timezone.utc)

    priority_map = {"urgent": Priority.URGENT, "soon": Priority.SOON, "normal": Priority.NORMAL}
    status_map = {
        "open": TaskStatus.OPEN,
        "in_progress": TaskStatus.IN_PROGRESS,
        "done": TaskStatus.DONE,
    }
    creator = users.get("admin")

    for (title, description, prio_str, status_str, due_days,
         dept_name, machine_name, worker_username) in TASK_DEFINITIONS:

        department = departments.get(dept_name)
        existing = Task.query.filter_by(title=title, department=department).first()
        if existing:
            continue

        status = status_map[status_str]
        worker = users.get(worker_username) if worker_username else None

        task = Task(
            title=title,
            description=description,
            priority=priority_map[prio_str],
            status=status,
            due_date=today + timedelta(days=due_days),
            department=department,
            created_by=creator.id if creator else None,
        )

        if status == TaskStatus.IN_PROGRESS and worker:
            task.current_worker_id = worker.id
            task.started_at = now - timedelta(hours=abs(due_days) * 3 + 2)

        if status == TaskStatus.DONE and worker:
            task.current_worker_id = worker.id
            task.started_at = now - timedelta(days=abs(due_days) + 1)
            task.completed_by_id = worker.id
            task.completed_at = now - timedelta(days=abs(due_days))

        db.session.add(task)


def _seed_documents(users):
    creator = users.get("admin")
    completed_tasks = (
        Task.query.filter(Task.status == TaskStatus.DONE)
        .order_by(Task.id.asc())
        .limit(8)
        .all()
    )
    for task in completed_tasks:
        if GeneratedDocument.query.filter_by(task_id=task.id).first():
            continue
        machine_name = _machine_for_task(task)
        generate_maintenance_report(
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


def _machine_for_task(task):
    task_text = f"{task.title} {task.description}".lower()
    for name, _, _ in MACHINE_DEFINITIONS:
        if name.lower() in task_text:
            return name
        first_token = name.lower().split()[0]
        if len(first_token) > 4 and first_token in task_text:
            return name
    return MACHINE_DEFINITIONS[task.id % len(MACHINE_DEFINITIONS)][0]
