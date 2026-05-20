"""Quality helpers for AI knowledge source chunks."""

from dataclasses import dataclass

from app.services.text_normalization_service import normalize_text, tokenize_text

MIN_CHUNK_CHARACTERS = 24
MIN_CHUNK_TOKENS = 3
BOILERPLATE_TOKENS = {
    "copyright",
    "seite",
    "page",
    "confidential",
    "vertraulich",
    "all",
    "rights",
    "reserved",
}

_LAST_CHUNK_QUALITY_REPORTS = {}


@dataclass
class ChunkQualityReport:
    """Track prompt-safe quality decisions made during chunk rebuilding."""

    skipped_duplicate_chunks: int = 0
    skipped_low_quality_chunks: int = 0
    affected_documents: int = 0

    def to_dict(self):
        """Return a JSON-serializable quality report."""
        return {
            "skipped_duplicate_chunks": self.skipped_duplicate_chunks,
            "skipped_low_quality_chunks": self.skipped_low_quality_chunks,
            "affected_documents": self.affected_documents,
        }


def chunk_payload_text(chunk_payload):
    """Return text from a chunk payload or raw chunk value."""
    if isinstance(chunk_payload, dict):
        return str(chunk_payload.get("text") or "")
    return str(chunk_payload or "")


def normalize_chunk_text(value):
    """Return normalized text used for source-quality checks."""
    return normalize_text(value, lowercase=True, fold_german=True)


def chunk_fingerprint(value):
    """Return a stable fingerprint for duplicate detection within one source."""
    normalized = normalize_chunk_text(value)
    return " ".join(sorted(tokenize_text(normalized, min_length=2, expand_synonyms=False)))


def is_low_quality_chunk(value):
    """Return whether a chunk is too weak to persist as retrieval evidence."""
    normalized = normalize_chunk_text(value)
    if not normalized:
        return True
    tokens = tokenize_text(normalized, min_length=2, expand_synonyms=False)
    if _has_technical_signal(normalized):
        return False
    if len(normalized) < MIN_CHUNK_CHARACTERS:
        return True
    if len(tokens) < MIN_CHUNK_TOKENS:
        return True
    if tokens and tokens.issubset(BOILERPLATE_TOKENS):
        return True
    return False


def filter_quality_chunks(chunk_payloads):
    """Return chunks that pass quality checks plus a prompt-safe report."""
    accepted_chunks = []
    seen_fingerprints = set()
    report = ChunkQualityReport()
    for chunk_payload in chunk_payloads:
        chunk_text = chunk_payload_text(chunk_payload)
        if is_low_quality_chunk(chunk_text):
            report.skipped_low_quality_chunks += 1
            continue
        fingerprint = chunk_fingerprint(chunk_text)
        if fingerprint and fingerprint in seen_fingerprints:
            report.skipped_duplicate_chunks += 1
            continue
        if fingerprint:
            seen_fingerprints.add(fingerprint)
        accepted_chunks.append(chunk_payload)
    if report.skipped_duplicate_chunks or report.skipped_low_quality_chunks:
        report.affected_documents = 1
    return accepted_chunks, report


def reset_chunk_quality_reports():
    """Clear in-process chunk-quality reports before a new reindex run."""
    _LAST_CHUNK_QUALITY_REPORTS.clear()


def remember_chunk_quality_report(document_id, report):
    """Store the latest chunk-quality report for one document."""
    if document_id is None or report is None:
        return
    _LAST_CHUNK_QUALITY_REPORTS[int(document_id)] = report


def chunk_quality_report_for_document(document_id):
    """Return the latest quality report for one document id."""
    return _LAST_CHUNK_QUALITY_REPORTS.get(int(document_id), ChunkQualityReport())


def latest_chunk_quality_summary():
    """Return the latest aggregate chunk-quality summary."""
    return aggregate_chunk_quality_reports(_LAST_CHUNK_QUALITY_REPORTS.values())


def aggregate_chunk_quality_reports(reports):
    """Return a combined prompt-safe quality report for several documents."""
    summary = ChunkQualityReport()
    affected_documents = 0
    for report in reports:
        if not report:
            continue
        summary.skipped_duplicate_chunks += int(report.skipped_duplicate_chunks or 0)
        summary.skipped_low_quality_chunks += int(report.skipped_low_quality_chunks or 0)
        if report.skipped_duplicate_chunks or report.skipped_low_quality_chunks:
            affected_documents += 1
    summary.affected_documents = affected_documents
    return summary.to_dict()


def _has_technical_signal(value):
    """Return whether short text still contains useful technical evidence."""
    tokens = tokenize_text(value, min_length=2, expand_synonyms=False)
    if any(any(char.isdigit() for char in token) for token in tokens):
        return True
    technical_terms = {
        "fehler",
        "fehlercode",
        "task",
        "maschine",
        "wartung",
        "loesung",
        "ursache",
        "sensor",
        "ventil",
        "presse",
    }
    return bool(tokens.intersection(technical_terms))
