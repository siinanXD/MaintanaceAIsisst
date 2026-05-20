"""Tests for the synthetic industrial document dataset generator."""

import csv
import json
import zipfile

from pypdf import PdfReader

from scripts.industrial_document_dataset_generator import (
    generate_industrial_document_dataset,
)


def test_industrial_document_dataset_generator_creates_expected_files(tmp_path):
    """Verify the generator writes PDFs, CSVs, metadata, README and ZIP output."""
    output = tmp_path / "industrial_rag_dataset"

    result = generate_industrial_document_dataset(
        output=output,
        employee_count=2,
        maintenance_report_count=3,
        seed=123,
        clean=True,
        zip_name="industrial_rag_dataset_test.zip",
    )

    employee_dirs = sorted((output / "employees").iterdir())
    report_files = sorted((output / "maintenance_reports").glob("*.pdf"))
    assert result["employees"] == 2
    assert result["maintenance_reports"] == 3
    assert len(employee_dirs) == 2
    assert len(report_files) == 3
    assert (output / "metadata.json").exists()
    assert (output / "employees.csv").exists()
    assert (output / "maintenance_reports.csv").exists()
    assert (output / "README.md").exists()
    assert (tmp_path / "industrial_rag_dataset_test.zip").exists()

    first_employee_pdfs = sorted(employee_dirs[0].glob("*.pdf"))
    assert {path.name for path in first_employee_pdfs} >= {
        "arbeitsvertrag.pdf",
        "maschinenfreigaben.pdf",
        "schichtplan_kw21.pdf",
        "sicherheitsunterweisung.pdf",
    }
    assert first_employee_pdfs[0].read_bytes().startswith(b"%PDF")
    assert report_files[0].read_bytes().startswith(b"%PDF")


def test_industrial_document_dataset_metadata_and_csv_are_consistent(tmp_path):
    """Verify prompt-safe metadata and CSV exports describe generated documents."""
    output = tmp_path / "dataset"
    generate_industrial_document_dataset(
        output=output,
        employee_count=3,
        maintenance_report_count=4,
        seed=456,
        clean=True,
        zip_name="dataset.zip",
    )

    metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    employees = list(csv.DictReader((output / "employees.csv").open(encoding="utf-8")))
    reports = list(csv.DictReader((output / "maintenance_reports.csv").open(encoding="utf-8")))
    documents = metadata["documents"]

    assert metadata["synthetic"] is True
    assert metadata["employees"] == 3
    assert metadata["maintenance_reports"] == 4
    assert len(employees) == 3
    assert len(reports) == 4
    assert any(item["document_type"] == "arbeitsvertrag" for item in documents)
    assert any(item["document_type"] == "wartungsbericht" for item in documents)
    assert all("personnel_number" in item for item in documents)


def test_industrial_document_dataset_zip_contains_relative_dataset_paths(tmp_path):
    """Verify the generated archive contains dataset-relative files."""
    output = tmp_path / "dataset"
    generate_industrial_document_dataset(
        output=output,
        employee_count=1,
        maintenance_report_count=1,
        seed=789,
        clean=True,
        zip_name="dataset.zip",
    )

    with zipfile.ZipFile(tmp_path / "dataset.zip") as archive:
        names = set(archive.namelist())

    assert "dataset/README.md" in names
    assert "dataset/metadata.json" in names
    assert any(name.startswith("dataset/employees/") and name.endswith(".pdf") for name in names)
    assert "dataset/maintenance_reports/wartungsbericht_001.pdf" in names


def test_industrial_document_dataset_text_pdf_is_extractable(tmp_path):
    """Verify at least one generated text PDF remains searchable for RAG ingestion."""
    output = tmp_path / "dataset"
    generate_industrial_document_dataset(
        output=output,
        employee_count=1,
        maintenance_report_count=1,
        seed=321,
        clean=True,
        zip_name="dataset.zip",
    )
    contract = next((output / "employees").glob("*/arbeitsvertrag.pdf"))
    reader = PdfReader(str(contract))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Arbeitsvertrag" in text
    assert "Personalnummer" in text
    assert "Synthetisches Dokument" in text
