from datetime import date, timedelta

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

FIRST_NAMES = [
    "Anna",
    "Ben",
    "Clara",
    "David",
    "Elif",
    "Felix",
    "Gina",
    "Hasan",
    "Iris",
    "Jonas",
    "Klara",
    "Leon",
    "Mara",
    "Nico",
    "Olivia",
    "Paul",
    "Rana",
    "Sofia",
    "Timo",
    "Yasmin",
]

LAST_NAMES = [
    "Schmidt",
    "Mueller",
    "Kaya",
    "Schneider",
    "Fischer",
    "Weber",
    "Wagner",
    "Becker",
    "Hoffmann",
    "Schulz",
    "Bauer",
    "Klein",
    "Wolf",
    "Neumann",
    "Krueger",
    "Hartmann",
    "Lange",
    "Werner",
    "Schmitz",
    "Braun",
]

MACHINE_DEFINITIONS = [
    ("CNC-Fraese 01", "Aluminium-Gehaeuse", 3),
    ("CNC-Drehmaschine 02", "Praezisionswellen", 2),
    ("Hydraulikpresse 03", "Blechformteile", 2),
    ("Spritzgussanlage 04", "Kunststoffclips", 4),
    ("Montagelinie 05", "Sensorbaugruppen", 6),
    ("Foerderband Linie A", "Materialfluss Produktion A", 1),
    ("Verpackungsanlage 06", "Versandfertige Sets", 3),
    ("Kompressorstation 07", "Druckluftversorgung", 1),
    ("Pruefstand 08", "End-of-Line-Pruefung", 2),
    ("Roboterzelle 09", "Automatisierte Bestueckung", 2),
    ("Laserbeschrifter 10", "Typenschilder", 1),
    ("Waschanlage 11", "Bauteilreinigung", 2),
]

INVENTORY_DEFINITIONS = [
    ("Aluminiumprofil 40x40", 18.90, 420, "Item Industrietechnik", "CNC-Fraese 01"),
    ("Hartmetall-Fraeser 8 mm", 42.50, 36, "Hoffmann Group", "CNC-Fraese 01"),
    ("Kuehlschmierstoff 20 l", 96.00, 18, "Castrol", "CNC-Fraese 01"),
    ("Drehmeissel CNMG", 12.80, 90, "Sandvik Coromant", "CNC-Drehmaschine 02"),
    ("Praezisionslager 6205", 7.40, 240, "SKF", "CNC-Drehmaschine 02"),
    ("Hydraulikoel HLP 46", 68.00, 22, "Fuchs", "Hydraulikpresse 03"),
    ("Dichtungssatz Presse", 115.00, 14, "Parker", "Hydraulikpresse 03"),
    ("Granulat PA6 schwarz", 3.70, 2600, "BASF", "Spritzgussanlage 04"),
    ("Heizband 230 V", 54.90, 28, "Hotset", "Spritzgussanlage 04"),
    ("Greiferfinger Set", 88.00, 16, "Schunk", "Montagelinie 05"),
    ("M8 Sensor induktiv", 24.70, 80, "Sick", "Montagelinie 05"),
    ("Foerdergurt PU", 310.00, 5, "Habasit", "Foerderband Linie A"),
    ("Antriebsrolle 60 mm", 74.20, 12, "Interroll", "Foerderband Linie A"),
    ("Karton 400x300x200", 1.15, 1800, "Smurfit Kappa", "Verpackungsanlage 06"),
    ("Etikettenrolle 100x60", 9.80, 75, "Avery Dennison", "Verpackungsanlage 06"),
    ("Druckluftfilter", 33.50, 24, "Atlas Copco", "Kompressorstation 07"),
    ("Keilriemen XPZ", 18.30, 30, "Optibelt", "Kompressorstation 07"),
    ("Pruefadapter 24 V", 129.00, 10, "Phoenix Contact", "Pruefstand 08"),
    ("Messleitung 2 m", 11.90, 110, "Staubli", "Pruefstand 08"),
    ("Vakuumsauger 30 mm", 6.80, 160, "Festo", "Roboterzelle 09"),
    ("Servo-Kabel 5 m", 47.50, 35, "Igus", "Roboterzelle 09"),
    ("Laser-Schutzglas", 145.00, 8, "Trumpf", "Laserbeschrifter 10"),
    ("Reinigungskonzentrat", 52.00, 26, "Henkel", "Waschanlage 11"),
    ("Edelstahlkorb klein", 39.90, 42, "Keller & Kalmbach", "Waschanlage 11"),
]

TASK_TITLES = {
    "IT": [
        "Backup-Status der Produktionsserver pruefen",
        "Tablet-Login fuer Linie A testen",
        "Netzwerkswitch im Schaltschrank dokumentieren",
        "Scanner-Firmware im Lager aktualisieren",
        "Benutzerrechte fuer neue Schichtleiter pruefen",
        "WLAN-Ausleuchtung in Halle 2 messen",
        "Dashboard-Ladezeiten analysieren",
        "Druckerqueue Versand bereinigen",
        "VPN-Zugriff fuer Rufbereitschaft testen",
        "USV-Selbsttest auswerten",
    ],
    "Verwaltung": [
        "Lieferantenstammdaten aktualisieren",
        "Wartungsvertraege fuer Q2 pruefen",
        "Bestellfreigaben nachziehen",
        "Rechnungsklaerung fuer Ersatzteile vorbereiten",
        "Audit-Unterlagen fuer Lagerbestand sammeln",
        "Besucherlisten fuer Werksfuehrung erstellen",
        "Schulungsnachweise abgleichen",
        "Kostenstellen fuer Instandhaltung pruefen",
        "Rahmenauftrag Hydraulikteile kontrollieren",
        "Monatsreport Anlagenverfuegbarkeit vorbereiten",
    ],
    "Instandhaltung": [
        "Hydraulikpresse auf Leckagen pruefen",
        "CNC-Fraese Spindellager abhoeren",
        "Foerderband Linie A nachspannen",
        "Kompressor Oelstand kontrollieren",
        "Roboterzelle Greifer kalibrieren",
        "Spritzgussanlage Heizkreis messen",
        "Pruefstand Kontakte reinigen",
        "Waschanlage Filtereinsatz tauschen",
        "Laserbeschrifter Absaugung pruefen",
        "Montagelinie Not-Halt-Kreis testen",
    ],
    "Produktion": [
        "Materialbereitstellung fuer Fruehschicht pruefen",
        "Erstteilfreigabe CNC-Fraese dokumentieren",
        "Ausschussquote Linie A erfassen",
        "Ruestplan Montagelinie abstimmen",
        "Verpackungsmaterial fuer Auftrag 4821 bereitstellen",
        "Schichtuebergabe Pruefstand vorbereiten",
        "Kanban-Karten fuer Kunststoffgranulat pruefen",
        "Reinigungsplan Spritzgussanlage abzeichnen",
        "Nacharbeit Sensorbaugruppen priorisieren",
        "Produktionskennzahlen im Board aktualisieren",
    ],
}

ERROR_TITLES = [
    (
        "E-101",
        "Sensor liefert kein Signal",
        "Kabelbruch, verschmutzter Sensor oder falscher Abstand",
    ),
    (
        "E-102",
        "Motor ueberlastet",
        "Blockierter Antrieb, Lagerreibung oder falsche Parametrierung",
    ),
    ("E-103", "Druck faellt ab", "Leckage, defektes Ventil oder Filter zugesetzt"),
    ("E-104", "Temperatur ausserhalb Toleranz", "Heizkreis, Kuehlung oder Regler pruefen"),
    (
        "E-105",
        "Kommunikation zur Steuerung gestoert",
        "Netzwerk, SPS-Koppler oder IP-Konflikt pruefen",
    ),
    (
        "E-106",
        "Not-Halt Kreis offen",
        "Tuerkontakt, Not-Halt-Taster oder Sicherheitsrelais pruefen",
    ),
    (
        "E-107",
        "Werkzeug nicht referenziert",
        "Referenzfahrt ausstehend oder Endschalter verschmutzt",
    ),
    ("E-108", "Barcode nicht lesbar", "Etikett, Scannerlinse oder Beleuchtung pruefen"),
    ("E-109", "Vakuum zu niedrig", "Sauger verschlissen, Schlauch undicht oder Ventil defekt"),
    ("E-110", "Materialstau erkannt", "Fuehrung, Bandlauf oder Sensorposition pruefen"),
    ("E-111", "Achse folgt Sollwert nicht", "Servo, Encoder oder Mechanik pruefen"),
    ("E-112", "Oelstand niedrig", "Nachfuellen und Anlage auf Leckage kontrollieren"),
    ("E-113", "Pruefergebnis instabil", "Kontaktierung, Adapter oder Messleitung pruefen"),
    ("E-114", "Absaugung meldet Unterdruck", "Filter, Klappe oder Schlauchsystem kontrollieren"),
    ("E-115", "Ruestdaten fehlen", "Auftragsdaten und Maschinenrezept synchronisieren"),
    ("E-116", "Druckluftqualitaet schlecht", "Filter, Trockner und Kondensatableiter pruefen"),
    ("E-117", "Schutzzaun offen", "Tuerschalter und Verriegelung kontrollieren"),
    ("E-118", "Fuellstand Material niedrig", "Nachfuellen und Sensor plausibilisieren"),
    ("E-119", "Kalibrierung abgelaufen", "Pruefmittel sperren und Kalibrierung starten"),
    ("E-120", "Qualitaetsgrenze ueberschritten", "Prozessparameter und Rohmaterial pruefen"),
]


def seed_demo_data():
    """Create a complete, repeatable demo dataset for the maintenance app."""
    ensure_default_departments()
    departments = _departments_by_name()
    users = _seed_users(departments)
    db.session.flush()
    for user in users:
        upsert_default_permissions(user)
    employees = _seed_employees()
    machines = _seed_machines()
    _seed_inventory(machines)
    _seed_tasks(departments, users)
    _seed_errors(departments)
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


def _departments_by_name():
    """Return all default departments indexed by their names."""
    return {
        department.name: department
        for department in Department.query.filter(Department.name.in_(DEFAULT_DEPARTMENTS)).all()
    }


def _seed_users(departments):
    """Create twenty demo login users across all application roles."""
    user_definitions = [
        ("master.admin", "master_admin", None),
        ("it.leitung", "it", "IT"),
        ("it.support", "it", "IT"),
        ("it.service", "it", "IT"),
        ("verwaltung.leitung", "verwaltung", "Verwaltung"),
        ("verwaltung.einkauf", "verwaltung", "Verwaltung"),
        ("verwaltung.office", "verwaltung", "Verwaltung"),
        ("instandhaltung.leitung", "instandhaltung", "Instandhaltung"),
        ("instandhaltung.mechanik", "instandhaltung", "Instandhaltung"),
        ("instandhaltung.elektrik", "instandhaltung", "Instandhaltung"),
        ("instandhaltung.schicht", "instandhaltung", "Instandhaltung"),
        ("produktion.leitung", "produktion", "Produktion"),
        ("produktion.schicht.a", "produktion", "Produktion"),
        ("produktion.schicht.b", "produktion", "Produktion"),
        ("produktion.schicht.c", "produktion", "Produktion"),
        ("produktion.qualitaet", "produktion", "Produktion"),
        ("personal.leitung", "personalabteilung", "Verwaltung"),
        ("personal.service", "personalabteilung", "Verwaltung"),
        ("lager.leitung", "verwaltung", "Verwaltung"),
        ("lager.service", "produktion", "Produktion"),
    ]
    users = []
    for username, role_value, department_name in user_definitions:
        user = User.query.filter(
            or_(User.username == username, User.email == f"{username}@demo.local")
        ).first()
        if not user:
            user = User(
                username=username,
                email=f"{username}@demo.local",
                role=Role(role_value),
                department=departments.get(department_name),
                is_active=True,
            )
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
        users.append(user)
    return users


def _seed_employees():
    """Create one hundred realistic employees with shift and qualification data."""
    cities = [
        ("Dortmund", "44135"),
        ("Bochum", "44787"),
        ("Essen", "45127"),
        ("Hagen", "58095"),
        ("Wuppertal", "42103"),
    ]
    departments = ["Produktion", "Instandhaltung", "Logistik", "Qualitaet", "Verwaltung"]
    shift_models = ["3-Schicht", "2-Schicht", "Tagschicht", "Wochenendteam"]
    qualifications = [
        "Staplerschein, Kranbedienung",
        "CNC-Grundlagen, Messmittel",
        "SPS-Basis, Elektrofachkraft unterwiesen",
        "Qualitaetspruefung, Erstteilfreigabe",
        "Lean Basics, 5S",
    ]
    employees = []
    for index in range(1, 101):
        personnel_number = f"MA-{index:04d}"
        employee = Employee.query.filter_by(personnel_number=personnel_number).first()
        if not employee:
            first_name = FIRST_NAMES[(index - 1) % len(FIRST_NAMES)]
            last_name = LAST_NAMES[(index - 1) % len(LAST_NAMES)]
            city, postal_code = cities[(index - 1) % len(cities)]
            employee = Employee(
                personnel_number=personnel_number,
                name=f"{first_name} {last_name}",
                birth_date=date(
                    1975 + (index % 25),
                    ((index - 1) % 12) + 1,
                    ((index - 1) % 27) + 1,
                ),
                city=city,
                street=f"Industriestrasse {index}",
                postal_code=postal_code,
                department=departments[(index - 1) % len(departments)],
                shift_model=shift_models[(index - 1) % len(shift_models)],
                current_shift=["Frueh", "Spaet", "Nacht", "Frei"][(index - 1) % 4],
                team=((index - 1) % 8) + 1,
                salary_group=f"EG {4 + (index % 6)}",
                qualifications=qualifications[(index - 1) % len(qualifications)],
                favorite_machine=MACHINE_DEFINITIONS[(index - 1) % len(MACHINE_DEFINITIONS)][0],
            )
            db.session.add(employee)
        employees.append(employee)
    return employees


def _seed_machines():
    """Create realistic production machines used by tasks, errors and inventory."""
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


def _seed_inventory(machines):
    """Create a realistic inventory with quantities, values, vendors and machine links."""
    demo_low_stock = {
        "Dichtungssatz Presse": 0,
        "Foerdergurt PU": 2,
        "M8 Sensor induktiv": 3,
        "Druckluftfilter": 1,
    }
    for name, unit_cost, quantity, manufacturer, machine_name in INVENTORY_DEFINITIONS:
        material = InventoryMaterial.query.filter_by(name=name, manufacturer=manufacturer).first()
        if not material:
            material = InventoryMaterial(
                name=name,
                unit_cost=unit_cost,
                quantity=demo_low_stock.get(name, quantity),
                manufacturer=manufacturer,
                machine=machines.get(machine_name),
            )
            db.session.add(material)
        else:
            material.quantity = demo_low_stock.get(name, material.quantity)
            material.machine = machines.get(machine_name)


def _seed_tasks(departments, users):
    """Create ten operational tasks for each default department."""
    creator = next(user for user in users if user.role == Role.MASTER_ADMIN)
    today = date.today()
    priorities = [Priority.URGENT, Priority.SOON, Priority.NORMAL, Priority.NORMAL]
    statuses = [TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.OPEN, TaskStatus.DONE]
    for department_name, titles in TASK_TITLES.items():
        department = departments[department_name]
        for index, title in enumerate(titles, start=1):
            existing = Task.query.filter_by(title=title, department=department).first()
            if existing:
                continue
            task = Task(
                title=title,
                description=(
                    f"Demo-Aufgabe fuer {department_name}. "
                    "Pruefen, dokumentieren und Rueckmeldung im System erfassen."
                ),
                priority=priorities[(index - 1) % len(priorities)],
                status=statuses[(index - 1) % len(statuses)],
                due_date=today + timedelta(days=(index % 10)),
                department=department,
                created_by=creator.id,
            )
            db.session.add(task)


def _seed_errors(departments):
    """Create twenty diagnostic error entries for each default department."""
    machine_names = [machine[0] for machine in MACHINE_DEFINITIONS]
    for department_name in TASK_TITLES:
        department = departments[department_name]
        prefix = department_name[:3].upper()
        for index, (base_code, title, cause) in enumerate(ERROR_TITLES, start=1):
            error_code = f"{prefix}-{base_code}"
            existing = ErrorEntry.query.filter_by(
                error_code=error_code,
                department=department,
            ).first()
            if existing:
                continue
            entry = ErrorEntry(
                machine=machine_names[(index - 1) % len(machine_names)],
                error_code=error_code,
                title=title,
                description=(
                    f"{title} im Bereich {department_name}. "
                    "Stoerung absichern, Anlage pruefen und Massnahme dokumentieren."
                ),
                possible_causes=cause,
                solution=(
                    "Anlage sicher stoppen, Sichtpruefung durchfuehren, Ursache beheben, "
                    "Probelauf starten und Ergebnis im Schichtbuch erfassen."
                ),
                department=department,
            )
            db.session.add(entry)


def _seed_documents(users):
    """Create generated maintenance reports for completed demo tasks."""
    creator = next(user for user in users if user.role == Role.MASTER_ADMIN)
    completed_tasks = (
        Task.query.filter(Task.status == TaskStatus.DONE)
        .order_by(Task.id.asc())
        .limit(12)
        .all()
    )
    for task in completed_tasks:
        existing_document = GeneratedDocument.query.filter_by(task_id=task.id).first()
        if existing_document:
            continue
        machine_name = _machine_name_for_task(task)
        generate_maintenance_report(
            task,
            creator,
            {
                "machine": machine_name,
                "cause": "Regelmaessige Demo-Wartung oder dokumentierte Stoerung.",
                "action": "Pruefung durchgefuehrt, Befund dokumentiert und Anlage freigegeben.",
                "result": "Anlage laeuft im Sollbereich.",
                "notes": "Naechste Kontrolle im Tagesplan vormerken.",
            },
        )


def _machine_name_for_task(task):
    """Return a machine name suitable for a demo task report."""
    task_text = f"{task.title} {task.description}".lower()
    for machine_name, _produced_item, _required_employees in MACHINE_DEFINITIONS:
        normalized_machine = machine_name.lower()
        if normalized_machine in task_text:
            return machine_name
        first_token = normalized_machine.split()[0]
        if len(first_token) > 4 and first_token in task_text:
            return machine_name
    return MACHINE_DEFINITIONS[task.id % len(MACHINE_DEFINITIONS)][0]
