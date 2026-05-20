"""Generate a synthetic industrial document dataset for RAG and OCR testing."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

try:
    from faker import Faker
except ImportError:  # pragma: no cover - exercised when Faker is not installed locally.
    Faker = None

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover - Pillow is a declared dependency.
    Image = None
    ImageDraw = None
    ImageFilter = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas
except ImportError as exc:  # pragma: no cover - reportlab is a declared dependency.
    raise RuntimeError("reportlab is required to generate industrial PDF datasets") from exc

COMPANY_NAME = "HanseWerk Industriekomponenten GmbH"
DEFAULT_OUTPUT = Path("data") / "industrial_rag_dataset"
DEFAULT_ZIP_NAME = "industrial_rag_dataset.zip"
DEPARTMENTS = (
    "Instandhaltung",
    "Elektrotechnik",
    "Produktion",
    "Mechanik",
    "Qualitaetssicherung",
    "Verwaltung",
    "Logistik",
)
POSITIONS = (
    "Instandhalter",
    "Elektroniker Betriebstechnik",
    "Anlagenbediener",
    "Mechaniker",
    "QS-Pruefer",
    "Teamleiter",
    "Logistikfachkraft",
    "Wartungsplaner",
)
QUALIFICATIONS = (
    "Elektrofachkraft",
    "Staplerschein",
    "SPS-Schulung S7/TIA",
    "Ersthelfer",
    "Brandschutzhelfer",
    "Hydraulikschulung",
    "Pneumatikschulung",
    "Sicherheitsunterweisung",
)
MACHINES = (
    "Foerderband Linie A",
    "Kompressorstation 07",
    "Schaltschrank S4",
    "Kuehlmittelpumpe P-12",
    "Motor M-230",
    "Lueftereinheit L-08",
    "Hydraulikaggregat HA-3",
    "Sensorik Station 5",
    "Frequenzumrichter FU-17",
    "Roboterzelle 09",
    "Verpackungsmaschine VPM-2",
    "Hydraulikpresse 03",
    "Spritzgussanlage 04",
)
FIRST_NAMES = (
    "Max",
    "Leon",
    "Lena",
    "Anna",
    "Sofia",
    "Mia",
    "Jonas",
    "Tim",
    "Felix",
    "Noah",
    "Emilia",
    "Lea",
    "Laura",
    "Nina",
    "Paul",
    "Ben",
    "Sarah",
    "Hannah",
)
LAST_NAMES = (
    "Mueller",
    "Schneider",
    "Fischer",
    "Weber",
    "Meyer",
    "Wagner",
    "Becker",
    "Schulz",
    "Hoffmann",
    "Schaefer",
    "Koch",
    "Bauer",
    "Richter",
    "Klein",
    "Wolf",
    "Neumann",
)
STREETS = (
    "Industriestrasse",
    "Werkweg",
    "Hafenallee",
    "Muehlenkamp",
    "Bahnhofstrasse",
    "Rosenweg",
)
CITIES = ("Hamburg", "Bremen", "Hannover", "Luebeck", "Kiel", "Oldenburg")
CHECKS_ELECTRICAL = (
    "Isolationswiderstand gemessen",
    "Schutzleiterwiderstand geprueft",
    "Klemmen auf festen Sitz kontrolliert",
    "Thermografie am Schaltschrank durchgefuehrt",
    "FU-Parameter mit Sollwertliste verglichen",
)
CHECKS_MECHANICAL = (
    "Lagerspiel geprueft",
    "Riemenspannung eingestellt",
    "Kupplung ausgerichtet",
    "Schraubverbindungen nachgezogen",
    "Leckagekontrolle durchgefuehrt",
)
DEFECTS = (
    "leichte Oelspur am Anschlussblock",
    "erhoehte Vibration im Lagerbereich",
    "Kabelverschraubung nicht vollstaendig dicht",
    "Filterelement verschmutzt",
    "Temperatur unter Last grenzwertig",
    "keine wesentlichen Maengel festgestellt",
)


@dataclass(frozen=True)
class EmployeeRecord:
    """Structured metadata for one synthetic employee."""

    personnel_number: str
    first_name: str
    last_name: str
    address: str
    birth_date: date
    department: str
    position: str
    salary_eur: int
    start_date: date
    vacation_days: int
    working_hours: str
    probation_months: int
    shift_model: str
    qualifications: tuple[str, ...]
    machine_approvals: tuple[str, ...]
    manager: str

    @property
    def full_name(self) -> str:
        """Return the employee's display name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def slug(self) -> str:
        """Return a stable filesystem slug for the employee."""
        return f"{slugify(self.full_name)}_{slugify(self.personnel_number)}"


@dataclass(frozen=True)
class MaintenanceReportRecord:
    """Structured metadata for one synthetic maintenance report."""

    report_number: str
    report_date: date
    machine: str
    area: str
    technician: str
    electrical_checks: tuple[str, ...]
    mechanical_checks: tuple[str, ...]
    measured_values: dict[str, str]
    defects: tuple[str, ...]
    recommendations: tuple[str, ...]
    priority: str
    status: str
    next_maintenance: date
    summary: str
    scanned: bool


@dataclass
class GeneratedFile:
    """Metadata for one generated file."""

    path: str
    document_type: str
    department: str
    owner: str = ""
    personnel_number: str = ""
    machine: str = ""
    report_number: str = ""
    scanned: bool = False
    tags: list[str] = field(default_factory=list)


class FallbackGermanFaker:
    """Small deterministic fallback when Faker is not installed."""

    def __init__(self, rng: random.Random):
        """Store the deterministic random generator."""
        self.rng = rng

    def first_name(self) -> str:
        """Return a German-like first name."""
        return self.rng.choice(FIRST_NAMES)

    def last_name(self) -> str:
        """Return a German-like last name."""
        return self.rng.choice(LAST_NAMES)

    def street_address(self) -> str:
        """Return a German-like street address."""
        return f"{self.rng.choice(STREETS)} {self.rng.randint(1, 148)}"

    def postcode(self) -> str:
        """Return a synthetic postcode."""
        return str(self.rng.randint(20000, 29999))

    def city(self) -> str:
        """Return a German city."""
        return self.rng.choice(CITIES)

    def date_of_birth(self) -> date:
        """Return a plausible employee birth date."""
        start = date(1964, 1, 1)
        return start + timedelta(days=self.rng.randint(0, 12000))


def main() -> None:
    """Parse CLI arguments and generate the requested dataset."""
    args = parse_args()
    result = generate_industrial_document_dataset(
        output=args.output,
        employee_count=args.employees,
        maintenance_report_count=args.maintenance_reports,
        seed=args.seed,
        clean=args.clean,
        zip_name=args.zip_name,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    """Return parsed CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic industrial PDFs for RAG/OCR testing."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--employees", type=int, default=50)
    parser.add_argument("--maintenance-reports", type=int, default=100)
    parser.add_argument("--seed", type=int, default=4242)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--zip-name", default=DEFAULT_ZIP_NAME)
    return parser.parse_args()


def generate_industrial_document_dataset(
    output: Path | str = DEFAULT_OUTPUT,
    employee_count: int = 50,
    maintenance_report_count: int = 100,
    seed: int = 4242,
    clean: bool = False,
    zip_name: str = DEFAULT_ZIP_NAME,
) -> dict:
    """Generate all PDFs, metadata files, CSV exports, README and ZIP archive."""
    output_path = Path(output)
    validate_generation_args(employee_count, maintenance_report_count)
    if clean and output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    fake = create_fake_data_provider(rng, seed)
    employees = generate_employees(employee_count, rng, fake)
    reports = generate_maintenance_reports(maintenance_report_count, employees, rng)
    generated_files = []

    generated_files.extend(write_employee_documents(output_path, employees, rng))
    generated_files.extend(write_maintenance_reports(output_path, reports, rng))
    write_employees_csv(output_path / "employees.csv", employees)
    write_maintenance_reports_csv(output_path / "maintenance_reports.csv", reports)
    write_metadata(output_path / "metadata.json", employees, reports, generated_files, seed)
    write_readme(output_path / "README.md", employees, reports, generated_files)
    zip_path = create_dataset_zip(output_path, zip_name)
    return {
        "output": str(output_path),
        "zip_path": str(zip_path),
        "employees": len(employees),
        "maintenance_reports": len(reports),
        "pdf_files": len([item for item in generated_files if item.path.endswith(".pdf")]),
        "support_files": 4,
    }


def validate_generation_args(employee_count: int, maintenance_report_count: int) -> None:
    """Validate dataset size arguments."""
    if employee_count < 1:
        raise ValueError("employee_count must be at least 1")
    if maintenance_report_count < 1:
        raise ValueError("maintenance_report_count must be at least 1")


def create_fake_data_provider(rng: random.Random, seed: int):
    """Return Faker's German provider or a deterministic internal fallback."""
    if Faker is None:
        return FallbackGermanFaker(rng)
    faker = Faker("de_DE")
    faker.seed_instance(seed)
    return faker


def generate_employees(count: int, rng: random.Random, fake) -> list[EmployeeRecord]:
    """Return synthetic employees with overlapping names and permissions."""
    employees = []
    for index in range(count):
        first_name = fake.first_name()
        last_name = fake.last_name()
        department = DEPARTMENTS[index % len(DEPARTMENTS)]
        position = rng.choice(POSITIONS)
        start_date = date(2015, 1, 1) + timedelta(days=rng.randint(0, 3300))
        qualifications = tuple(rng.sample(QUALIFICATIONS, rng.randint(1, 3)))
        approvals = tuple(rng.sample(MACHINES, rng.randint(2, 5)))
        address = f"{fake.street_address()}, {fake.postcode()} {fake.city()}"
        employees.append(
            EmployeeRecord(
                personnel_number=f"HW-{2020 + index:04d}",
                first_name=first_name,
                last_name=last_name,
                address=address,
                birth_date=fake.date_of_birth(),
                department=department,
                position=position,
                salary_eur=rng.randrange(34500, 74500, 250),
                start_date=start_date,
                vacation_days=rng.choice((28, 29, 30, 31)),
                working_hours=rng.choice(
                    (
                        "37,5 Stunden/Woche",
                        "40 Stunden/Woche",
                        "35 Stunden/Woche im Schichtmodell",
                    )
                ),
                probation_months=rng.choice((3, 6)),
                shift_model=rng.choice(("Frueh/Spaet", "3-Schicht", "Tagschicht")),
                qualifications=qualifications,
                machine_approvals=approvals,
                manager=rng.choice(("Meister Krause", "Meister Nguyen", "Meister Albrecht")),
            )
        )
    return employees


def generate_maintenance_reports(
    count: int,
    employees: list[EmployeeRecord],
    rng: random.Random,
) -> list[MaintenanceReportRecord]:
    """Return synthetic maintenance reports with realistic overlapping content."""
    reports = []
    technicians = [item.full_name for item in employees if item.department != "Verwaltung"]
    for index in range(1, count + 1):
        machine = rng.choice(MACHINES)
        report_date = date.today() - timedelta(days=rng.randint(0, 540))
        priority = rng.choice(("niedrig", "normal", "hoch", "kritisch"))
        status = rng.choice(("offen", "in Arbeit", "abgeschlossen", "Wiedervorlage"))
        defect_items = tuple(rng.sample(DEFECTS, rng.randint(1, 3)))
        reports.append(
            MaintenanceReportRecord(
                report_number=f"WB-{report_date.year}-{index:04d}",
                report_date=report_date,
                machine=machine,
                area=rng.choice(("Halle 1", "Halle 2", "Endmontage", "Logistik", "Prueffeld")),
                technician=rng.choice(technicians or ["Max Mueller"]),
                electrical_checks=tuple(rng.sample(CHECKS_ELECTRICAL, rng.randint(2, 4))),
                mechanical_checks=tuple(rng.sample(CHECKS_MECHANICAL, rng.randint(2, 4))),
                measured_values=maintenance_measurements(machine, rng),
                defects=defect_items,
                recommendations=recommendations_for_defects(defect_items, rng),
                priority=priority,
                status=status,
                next_maintenance=report_date + timedelta(days=rng.choice((14, 30, 60, 90))),
                summary=maintenance_summary(machine, defect_items, priority),
                scanned=index % 4 == 0 or rng.random() < 0.08,
            )
        )
    return reports


def write_employee_documents(
    output_path: Path,
    employees: list[EmployeeRecord],
    rng: random.Random,
) -> list[GeneratedFile]:
    """Write all employee-related PDFs and return generated-file metadata."""
    generated = []
    for employee in employees:
        employee_dir = output_path / "employees" / employee.slug
        employee_dir.mkdir(parents=True, exist_ok=True)
        generated.append(write_contract_pdf(employee_dir, employee, rng))
        generated.append(write_security_pdf(employee_dir, employee, rng))
        generated.append(write_machine_approval_pdf(employee_dir, employee, rng))
        generated.append(write_shift_plan_pdf(employee_dir, employee, rng))
        for qualification in employee.qualifications:
            generated.append(write_certificate_pdf(employee_dir, employee, qualification, rng))
    return generated


def write_contract_pdf(
    employee_dir: Path,
    employee: EmployeeRecord,
    rng: random.Random,
) -> GeneratedFile:
    """Write one employment contract PDF."""
    path = employee_dir / "arbeitsvertrag.pdf"
    sections = [
        (
            "Vertragsparteien",
            [
                f"Arbeitgeber: {COMPANY_NAME}",
                f"Arbeitnehmer: {employee.full_name}, {employee.address}",
                f"Geburtsdatum: {format_date(employee.birth_date, rng)}",
                f"Personalnummer: {employee.personnel_number}",
            ],
        ),
        (
            "Taetigkeit und Verguetung",
            [
                f"Position: {employee.position}",
                f"Abteilung: {employee.department}",
                f"Bruttojahresgehalt: {employee.salary_eur:,.0f} EUR".replace(",", "."),
                f"Beginn: {format_date(employee.start_date, rng)}",
                f"Urlaubstage: {employee.vacation_days}",
                f"Arbeitszeit: {employee.working_hours}",
                f"Probezeit: {employee.probation_months} Monate",
            ],
        ),
        (
            "Unterschriften",
            [
                "Ort/Datum: ______________________________",
                "Arbeitgeber: _____________________________",
                "Arbeitnehmer: ____________________________",
            ],
        ),
    ]
    write_pdf(
        path,
        "Arbeitsvertrag",
        employee.full_name,
        sections,
        tables=[],
        layout=rng.randint(0, 2),
        scanned=False,
        note="HR vertraulich - Zugriff nur fuer berechtigte Rollen",
    )
    return file_metadata(path, "arbeitsvertrag", employee.department, employee)


def write_certificate_pdf(
    employee_dir: Path,
    employee: EmployeeRecord,
    qualification: str,
    rng: random.Random,
) -> GeneratedFile:
    """Write one qualification certificate PDF."""
    filename = f"zertifikat_{slugify(qualification)}.pdf"
    path = employee_dir / filename
    valid_until = date.today() + timedelta(days=rng.randint(90, 1000))
    certificate_number = f"Z-{rng.randint(2000, 9999)}-{rng.randint(10, 99)}"
    sections = [
        (
            "Zertifikat",
            [
                f"Teilnehmer: {employee.full_name}",
                f"Personalnummer: {employee.personnel_number}",
                f"Qualifikation: {qualification}",
                f"Zertifikatsnummer: {certificate_number}",
                "Aussteller: TUEV Nord Akademie / interne Schulungsstelle",
                f"Gueltig bis: {format_date(valid_until, rng)}",
            ],
        ),
        (
            "Schulungsinhalt",
            [
                "Gefaehrdungsbeurteilung am Arbeitsplatz",
                "Praktische Uebung an realen Anlagen",
                "Dokumentationspflichten im Maintenance-System",
                "Abschlusspruefung bestanden, kleine Schreibfehler im Originalprotokoll belassen.",
            ],
        ),
    ]
    write_pdf(
        path,
        qualification,
        f"Zertifikat fuer {employee.full_name}",
        sections,
        tables=[],
        layout=rng.randint(0, 3),
        scanned=rng.random() < 0.25,
        note=rng.choice(("Gueltigkeit vor Einsatz pruefen", "Kopie Personalakte", "")),
    )
    return file_metadata(
        path,
        "qualifikation",
        employee.department,
        employee,
        tags=[qualification, certificate_number],
    )


def write_machine_approval_pdf(
    employee_dir: Path,
    employee: EmployeeRecord,
    rng: random.Random,
) -> GeneratedFile:
    """Write one machine approval PDF."""
    path = employee_dir / "maschinenfreigaben.pdf"
    table = [["Maschine", "Freigabe", "Meister", "Datum"]]
    for machine in employee.machine_approvals:
        table.append(
            [
                machine,
                "bedienen / ruecksetzen",
                employee.manager,
                format_date(date.today(), rng),
            ]
        )
    sections = [
        (
            "Sicherheitsfreigaben",
            [
                "Freigabe nach praktischer Einweisung und Sicherheitscheck.",
                "Bei Stoerungen nur nach Lockout/Tagout und Ruecksprache mit Meister handeln.",
            ],
        )
    ]
    write_pdf(
        path,
        "Maschinenfreigaben",
        employee.full_name,
        sections,
        tables=[table],
        layout=1,
        scanned=rng.random() < 0.15,
        note="Freigegeben",
    )
    return file_metadata(
        path,
        "maschinenfreigabe",
        employee.department,
        employee,
        machine=", ".join(employee.machine_approvals),
    )


def write_security_pdf(
    employee_dir: Path,
    employee: EmployeeRecord,
    rng: random.Random,
) -> GeneratedFile:
    """Write one safety instruction PDF."""
    path = employee_dir / "sicherheitsunterweisung.pdf"
    sections = [
        (
            "Unterweisung",
            [
                f"Teilnehmer: {employee.full_name}",
                "PSA: Sicherheitsschuhe, Schutzbrille, Gehoerschutz nach Bereich.",
                "Lockout/Tagout: Energiequellen trennen, pruefen, kennzeichnen.",
                "Unfallvermeidung: Stolperstellen melden, defekte Werkzeuge sperren.",
                "Verhalten bei Stoerungen: Anlage sichern, Meister informieren, Bericht anlegen.",
            ],
        ),
        (
            "Bestaetigung",
            [
                "Ich bestaetige die Teilnahme an der Sicherheitsunterweisung.",
                "Unterschrift Mitarbeiter: __________________________",
                "Unterschrift Unterweisender: _______________________",
            ],
        ),
    ]
    write_pdf(
        path,
        "Sicherheitsunterweisung",
        employee.department,
        sections,
        tables=[],
        layout=2,
        scanned=rng.random() < 0.3,
        note="PSA / LOTO",
    )
    return file_metadata(path, "sicherheitsunterweisung", employee.department, employee)


def write_shift_plan_pdf(
    employee_dir: Path,
    employee: EmployeeRecord,
    rng: random.Random,
) -> GeneratedFile:
    """Write one weekly shift plan PDF."""
    path = employee_dir / "schichtplan_kw21.pdf"
    table = [["KW", "Mo", "Di", "Mi", "Do", "Fr", "Team"]]
    shifts = ["Frueh", "Spaet", "Nacht", "frei"]
    for week in range(21, 25):
        table.append(
            [
                str(week),
                rng.choice(shifts),
                rng.choice(shifts),
                rng.choice(shifts),
                rng.choice(shifts),
                rng.choice(shifts),
                rng.choice(("Team A", "Team B", "Team C")),
            ]
        )
    sections = [
        (
            "Schichtmodell",
            [
                f"Mitarbeiter: {employee.full_name}",
                f"Modell: {employee.shift_model}",
                "Aenderungen muessen bis Mittwoch 12:00 Uhr durch den Meister bestaetigt werden.",
            ],
        )
    ]
    write_pdf(
        path,
        "Schichtplan KW 21-24",
        employee.department,
        sections,
        tables=[table],
        layout=0,
        scanned=False,
        note="Aushangkopie",
    )
    return file_metadata(path, "schichtplan", employee.department, employee)


def write_maintenance_reports(
    output_path: Path,
    reports: list[MaintenanceReportRecord],
    rng: random.Random,
) -> list[GeneratedFile]:
    """Write all maintenance report PDFs and return generated-file metadata."""
    report_dir = output_path / "maintenance_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    for index, report in enumerate(reports, start=1):
        path = report_dir / f"wartungsbericht_{index:03d}.pdf"
        write_maintenance_report_pdf(path, report, rng)
        generated.append(
            GeneratedFile(
                path=str(path),
                document_type="wartungsbericht",
                department="Instandhaltung",
                owner=report.technician,
                machine=report.machine,
                report_number=report.report_number,
                scanned=report.scanned,
                tags=[report.priority, report.status, report.machine],
            )
        )
    return generated


def write_maintenance_report_pdf(
    path: Path,
    report: MaintenanceReportRecord,
    rng: random.Random,
) -> None:
    """Write one detailed maintenance report PDF."""
    sections = [
        (
            "Berichtsdaten",
            [
                f"Wartungsberichtnummer: {report.report_number}",
                f"Datum: {format_date(report.report_date, rng)}",
                f"Maschine/Anlage: {report.machine}",
                f"Standort/Bereich: {report.area}",
                f"Techniker: {report.technician}",
                f"Prioritaet: {report.priority}",
                f"Status: {report.status}",
            ],
        ),
        ("Durchgefuehrte elektrische Pruefungen", list(report.electrical_checks)),
        ("Durchgefuehrte mechanische Pruefungen", list(report.mechanical_checks)),
        ("Festgestellte Maengel", list(report.defects)),
        ("Empfohlene Massnahmen", list(report.recommendations)),
        (
            "Zusammenfassung",
            [
                report.summary,
                f"Naechste Wartung: {format_date(report.next_maintenance, rng)}",
                "Unterschrift Techniker: __________________________",
                "Freigabe Meister: _______________________________",
            ],
        ),
    ]
    table = [["Messpunkt", "Wert", "Grenzwert"]]
    for key, value in report.measured_values.items():
        table.append([key, value, measurement_limit(key)])
    write_pdf(
        path,
        "Wartungsbericht",
        report.report_number,
        sections,
        tables=[table],
        layout=rng.randint(0, 3),
        scanned=report.scanned,
        note=rng.choice(("geprueft", "Wiedervorlage", "Stempel QS", "")),
    )


def write_pdf(
    path: Path,
    title: str,
    subtitle: str,
    sections: list[tuple[str, list[str]]],
    tables: list[list[list[str]]],
    layout: int,
    scanned: bool,
    note: str = "",
) -> None:
    """Write either a text PDF or a scan-like image PDF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if scanned and Image is not None:
        write_scanned_pdf(path, title, subtitle, sections, tables, note)
        return
    write_text_pdf(path, title, subtitle, sections, tables, layout, note)


def write_text_pdf(
    path: Path,
    title: str,
    subtitle: str,
    sections: list[tuple[str, list[str]]],
    tables: list[list[list[str]]],
    layout: int,
    note: str,
) -> None:
    """Write a searchable reportlab PDF with simple industrial layouts."""
    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    y = draw_header(pdf, width, height, title, subtitle, layout, note)
    for heading, lines in sections:
        y = ensure_page_space(pdf, y, 48, width, height, title, subtitle, layout, note)
        pdf.setFont("Helvetica-Bold", 11 + (layout % 2))
        pdf.drawString(22 * mm, y, heading)
        y -= 7 * mm
        pdf.setFont("Helvetica", 9 + (layout % 2))
        for line in lines:
            for wrapped in wrap_text(line, 95):
                y = ensure_page_space(pdf, y, 18, width, height, title, subtitle, layout, note)
                pdf.drawString(24 * mm, y, f"- {wrapped}")
                y -= 5 * mm
        y -= 4 * mm
    for table in tables:
        y = draw_table(pdf, table, y, width, height, title, subtitle, layout, note)
    draw_footer(pdf, width)
    pdf.save()


def write_scanned_pdf(
    path: Path,
    title: str,
    subtitle: str,
    sections: list[tuple[str, list[str]]],
    tables: list[list[list[str]]],
    note: str,
) -> None:
    """Write a scan-like image PDF for OCR simulation."""
    image = Image.new("RGB", (1240, 1754), "#f7f5ef")
    draw = ImageDraw.Draw(image)
    y = 80
    draw.rectangle((70, 50, 230, 130), outline="#1f2937", width=4)
    draw.text((88, 72), "HW", fill="#1f2937")
    draw.text((250, 60), title, fill="#111827")
    draw.text((250, 95), subtitle, fill="#374151")
    if note:
        draw.rectangle((850, 65, 1110, 130), outline="#991b1b", width=3)
        draw.text((875, 88), note[:28], fill="#991b1b")
    y = 165
    for heading, lines in sections:
        draw.text((80, y), heading, fill="#111827")
        y += 32
        for line in lines[:8]:
            draw.text((105, y), f"- {line[:105]}", fill="#1f2937")
            y += 26
        y += 20
        if y > 1420:
            break
    for table in tables[:1]:
        y = draw_image_table(draw, table, y)
    image = add_scan_effects(image)
    image.save(path, "PDF", resolution=150.0)


def draw_header(
    pdf: canvas.Canvas,
    width: float,
    height: float,
    title: str,
    subtitle: str,
    layout: int,
    note: str,
) -> float:
    """Draw a reusable document header and return the starting y-position."""
    accent = colors.HexColor(["#1f4e79", "#4b5563", "#0f766e", "#7c2d12"][layout % 4])
    pdf.setFillColor(accent)
    pdf.rect(0, height - 24 * mm, width, 24 * mm, fill=True, stroke=False)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(22 * mm, height - 14 * mm, "HW")
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(42 * mm, height - 11 * mm, COMPANY_NAME)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(42 * mm, height - 17 * mm, "synthetischer Testdatensatz")
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(22 * mm, height - 37 * mm, title)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(22 * mm, height - 44 * mm, subtitle)
    if note:
        pdf.setStrokeColor(colors.HexColor("#991b1b"))
        pdf.setFillColor(colors.HexColor("#991b1b"))
        pdf.setFont("Helvetica-Bold", 10)
        pdf.rect(width - 62 * mm, height - 47 * mm, 40 * mm, 14 * mm, fill=False)
        pdf.drawCentredString(width - 42 * mm, height - 41 * mm, note[:22])
        pdf.setFillColor(colors.black)
    return height - 58 * mm


def draw_footer(pdf: canvas.Canvas, width: float) -> None:
    """Draw a privacy-safe synthetic-data footer."""
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.HexColor("#6b7280"))
    pdf.drawString(
        20 * mm,
        12 * mm,
        "Synthetisches Dokument fuer AI-/RAG-/OCR-Tests. Keine echten Personendaten.",
    )
    pdf.drawRightString(width - 20 * mm, 12 * mm, f"Seite {pdf.getPageNumber()}")
    pdf.setFillColor(colors.black)


def ensure_page_space(
    pdf: canvas.Canvas,
    y: float,
    required: float,
    width: float,
    height: float,
    title: str,
    subtitle: str,
    layout: int,
    note: str,
) -> float:
    """Start a new page when the current page has insufficient vertical space."""
    if y > required + 24 * mm:
        return y
    draw_footer(pdf, width)
    pdf.showPage()
    return draw_header(pdf, width, height, title, subtitle, layout, note)


def draw_table(
    pdf: canvas.Canvas,
    rows: list[list[str]],
    y: float,
    width: float,
    height: float,
    title: str,
    subtitle: str,
    layout: int,
    note: str,
) -> float:
    """Draw a compact table and return the updated y-position."""
    if not rows:
        return y
    col_width = (width - 44 * mm) / max(len(rows[0]), 1)
    pdf.setFont("Helvetica-Bold", 8)
    for row_index, row in enumerate(rows):
        y = ensure_page_space(pdf, y, 20, width, height, title, subtitle, layout, note)
        x = 22 * mm
        pdf.setFillColor(colors.HexColor("#e5e7eb") if row_index == 0 else colors.white)
        pdf.rect(x, y - 4 * mm, col_width * len(row), 7 * mm, fill=True, stroke=True)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold" if row_index == 0 else "Helvetica", 8)
        for cell in row:
            pdf.drawString(x + 2 * mm, y - 1 * mm, truncate_text(str(cell), col_width - 4 * mm))
            x += col_width
        y -= 7 * mm
    return y - 6 * mm


def draw_image_table(draw: ImageDraw.ImageDraw, rows: list[list[str]], y: int) -> int:
    """Draw a simple table into a scan-like image."""
    for row in rows[:8]:
        x = 80
        for cell in row[:4]:
            draw.rectangle((x, y, x + 250, y + 34), outline="#6b7280")
            draw.text((x + 8, y + 9), str(cell)[:28], fill="#111827")
            x += 250
        y += 34
    return y + 20


def add_scan_effects(image: Image.Image) -> Image.Image:
    """Apply lightweight scan artefacts to an image."""
    rng = random.Random(image.size[0] + image.size[1])
    image = image.rotate(rng.uniform(-1.2, 1.2), expand=False, fillcolor="#f7f5ef")
    image = image.convert("L").filter(ImageFilter.GaussianBlur(radius=0.25)).convert("RGB")
    pixels = image.load()
    for _ in range(3200):
        x = rng.randrange(0, image.size[0])
        y = rng.randrange(0, image.size[1])
        shade = rng.randrange(150, 230)
        pixels[x, y] = (shade, shade, shade)
    return image


def write_employees_csv(path: Path, employees: list[EmployeeRecord]) -> None:
    """Write a CSV export with employee metadata."""
    rows = []
    for employee in employees:
        payload = asdict(employee)
        payload["full_name"] = employee.full_name
        payload["birth_date"] = employee.birth_date.isoformat()
        payload["start_date"] = employee.start_date.isoformat()
        payload["qualifications"] = "; ".join(employee.qualifications)
        payload["machine_approvals"] = "; ".join(employee.machine_approvals)
        rows.append(payload)
    write_csv(path, rows)


def write_maintenance_reports_csv(path: Path, reports: list[MaintenanceReportRecord]) -> None:
    """Write a CSV export with maintenance-report metadata."""
    rows = []
    for report in reports:
        payload = asdict(report)
        payload["report_date"] = report.report_date.isoformat()
        payload["next_maintenance"] = report.next_maintenance.isoformat()
        payload["electrical_checks"] = "; ".join(report.electrical_checks)
        payload["mechanical_checks"] = "; ".join(report.mechanical_checks)
        payload["defects"] = "; ".join(report.defects)
        payload["recommendations"] = "; ".join(report.recommendations)
        payload["measured_values"] = json.dumps(report.measured_values, ensure_ascii=False)
        rows.append(payload)
    write_csv(path, rows)


def write_csv(path: Path, rows: list[dict]) -> None:
    """Write rows to CSV when at least one row exists."""
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_metadata(
    path: Path,
    employees: list[EmployeeRecord],
    reports: list[MaintenanceReportRecord],
    generated_files: list[GeneratedFile],
    seed: int,
) -> None:
    """Write JSON metadata for RAG ingestion and dataset inspection."""
    payload = {
        "dataset": "industrial_rag_dataset",
        "synthetic": True,
        "company": COMPANY_NAME,
        "seed": seed,
        "employees": len(employees),
        "maintenance_reports": len(reports),
        "documents": [asdict(item) for item in generated_files],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_readme(
    path: Path,
    employees: list[EmployeeRecord],
    reports: list[MaintenanceReportRecord],
    generated_files: list[GeneratedFile],
) -> None:
    """Write dataset usage documentation."""
    scanned_count = sum(1 for item in generated_files if item.scanned)
    text = f"""# Industrial RAG Dataset

Dieser Datensatz ist vollstaendig synthetisch und dient nur fuer AI-, RAG-,
OCR-, Embedding-, Chunking- und Berechtigungstests.

## Inhalt

- Mitarbeiter: {len(employees)}
- Wartungsberichte: {len(reports)}
- PDF-Dateien: {len([item for item in generated_files if item.path.endswith(".pdf")])}
- Scan-/OCR-nahe PDFs: {scanned_count}

## Struktur

- `employees/<name>/`: Arbeitsvertrag, Zertifikate, Maschinenfreigaben,
  Sicherheitsunterweisung und Schichtplan.
- `maintenance_reports/`: technische Wartungsberichte mit Messwerten,
  Maengeln, Empfehlungen und Status.
- `metadata.json`: prompt- und RAG-freundliche Metadaten fuer Ingestion.
- `employees.csv` und `maintenance_reports.csv`: tabellarische Uebersichten.

## Hinweis

Alle Namen, Adressen, Personalnummern und Dokumentinhalte sind kuenstlich
erzeugt. Der Bestand soll realistisch wirken, aber keine echten personenbezogenen
Daten enthalten.
"""
    path.write_text(text, encoding="utf-8")


def create_dataset_zip(output_path: Path, zip_name: str) -> Path:
    """Create a ZIP archive next to the generated dataset directory."""
    zip_path = output_path.with_name(zip_name)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(output_path.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(output_path.parent))
    return zip_path


def file_metadata(
    path: Path,
    document_type: str,
    department: str,
    employee: EmployeeRecord,
    machine: str = "",
    tags: list[str] | None = None,
) -> GeneratedFile:
    """Return generated-file metadata for one employee document."""
    return GeneratedFile(
        path=str(path),
        document_type=document_type,
        department=department,
        owner=employee.full_name,
        personnel_number=employee.personnel_number,
        machine=machine,
        tags=tags or [document_type, department],
    )


def maintenance_measurements(machine: str, rng: random.Random) -> dict[str, str]:
    """Return realistic maintenance measurements for one machine."""
    return {
        "Temperatur Lager A": f"{rng.uniform(38, 86):.1f} C",
        "Vibration RMS": f"{rng.uniform(0.8, 7.5):.2f} mm/s",
        "Stromaufnahme": f"{rng.uniform(2.4, 48.0):.1f} A",
        "Druck / Versorgung": pressure_value(machine, rng),
        "Laufzeitzaehler": f"{rng.randint(800, 18400)} h",
    }


def pressure_value(machine: str, rng: random.Random) -> str:
    """Return a pressure-like value tailored to the machine name."""
    if "Hydraulik" in machine or "Pumpe" in machine:
        return f"{rng.randint(110, 185)} bar"
    if "Kompressor" in machine:
        return f"{rng.uniform(6.2, 8.4):.1f} bar"
    return f"{rng.uniform(22.0, 24.5):.1f} VDC"


def recommendations_for_defects(
    defects: tuple[str, ...],
    rng: random.Random,
) -> tuple[str, ...]:
    """Return maintenance recommendations matching observed defects."""
    recommendations = []
    for defect in defects:
        if "Oelspur" in defect:
            recommendations.append(
                "Dichtungssatz bereitlegen und Leckage nach Schichtende beheben."
            )
        elif "Vibration" in defect:
            recommendations.append("Lagerzustand per Schwingungsanalyse erneut pruefen.")
        elif "Filter" in defect:
            recommendations.append("Filterelement beim naechsten Stillstand tauschen.")
        elif "Temperatur" in defect:
            recommendations.append("Thermografie nach 4 h Betrieb wiederholen.")
        else:
            recommendations.append(rng.choice(CHECKS_MECHANICAL))
    return tuple(dict.fromkeys(recommendations))


def maintenance_summary(machine: str, defects: tuple[str, ...], priority: str) -> str:
    """Return a concise report summary."""
    defect_text = "; ".join(defects)
    return (
        f"{machine}: Wartung durchgefuehrt. Auffaelligkeiten: {defect_text}. "
        f"Prioritaet fuer Folgemassnahmen: {priority}."
    )


def measurement_limit(name: str) -> str:
    """Return a simple limit text for a measurement name."""
    if "Temperatur" in name:
        return "< 80 C"
    if "Vibration" in name:
        return "< 4.5 mm/s"
    if "Strom" in name:
        return "laut Typenschild"
    if "Druck" in name:
        return "Soll +/- 10 %"
    return "Dokumentation"


def format_date(value: date, rng: random.Random) -> str:
    """Return intentionally varied German date formats."""
    return rng.choice(
        (
            value.strftime("%d.%m.%Y"),
            value.strftime("%Y-%m-%d"),
            value.strftime("%d/%m/%Y"),
        )
    )


def wrap_text(text: str, max_chars: int) -> list[str]:
    """Wrap text into fixed-width character lines."""
    words = str(text).split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def truncate_text(value: str, max_width: float) -> str:
    """Return text that fits into a reportlab cell width."""
    text = str(value)
    while stringWidth(text, "Helvetica", 8) > max_width and len(text) > 4:
        text = text[:-4] + "..."
    return text


def slugify(value: str) -> str:
    """Return a filesystem-safe ASCII slug."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    return normalized or "eintrag"


if __name__ == "__main__":
    main()
