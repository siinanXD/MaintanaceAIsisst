"""OpenAPI schema fragment 4."""

SCHEMAS_4 = {
    "Notification": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 3},
            "notification_type": {"type": "string", "example": "shiftplan_publish"},
            "title": {"type": "string", "example": "Schichtplan veroeffentlicht"},
            "body": {"type": "string", "example": "Plan KW 19 wurde veroeffentlicht."},
            "link_url": {"type": "string", "example": "/shiftplans"},
            "is_read": {"type": "boolean", "example": False},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "ShiftPlanEntry": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 101},
            "employee": {"$ref": "#/components/schemas/Employee"},
            "machine": {"$ref": "#/components/schemas/Machine"},
            "work_date": {"type": "string", "format": "date", "example": "2026-05-05"},
            "shift": {"type": "string", "example": "Fruehschicht"},
            "start_time": {"type": "string", "example": "06:00"},
            "end_time": {"type": "string", "example": "14:00"},
            "notes": {"type": "string", "example": ""},
        },
    },
    "ShiftPlan": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 5},
            "title": {"type": "string", "example": "Schichtplan KW 19"},
            "start_date": {"type": "string", "format": "date", "example": "2026-05-05"},
            "days": {"type": "integer", "example": 7},
            "rhythm": {"type": "string", "example": "3-Schicht"},
            "preferences": {"type": "string", "example": "Urlaub: Hans Mueller 06.-08.05."},
            "notes": {"type": "string", "example": ""},
            "entries": {"type": "array", "items": {"$ref": "#/components/schemas/ShiftPlanEntry"}},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "GeneratedDocument": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 8},
            "task_id": {"type": "integer", "example": 42},
            "document_type": {"type": "string", "example": "maintenance_report"},
            "title": {"type": "string", "example": "Wartungsbericht Task 42"},
            "department": {"type": "string", "example": "Instandhaltung"},
            "machine": {"type": "string", "example": "CNC-Fraese 01"},
            "machine_id": {"type": "integer", "nullable": True, "example": 1},
            "created_at": {"type": "string", "format": "date-time"},
            "status": {
                "type": "string",
                "enum": ["draft", "in_review", "approved", "rejected"],
                "example": "draft",
            },
            "current_version_id": {"type": "integer", "nullable": True, "example": 3},
            "summary": {
                "type": "string",
                "example": "Kurzfassung der wichtigsten " "Wartungspunkte.",
            },
            "summary_status": {"type": "string", "example": "completed"},
            "approved_at": {"type": "string", "format": "date-time", "nullable": True},
            "approval_comment": {"type": "string", "example": ""},
            "download_url": {"type": "string", "example": "/api/v1/documents/8/download"},
            "pdf_url": {"type": "string", "example": "/api/v1/documents/8/download.pdf"},
        },
    },
    "DocumentVersion": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 12},
            "document_id": {"type": "integer", "example": 8},
            "version_number": {"type": "integer", "example": 1},
            "original_filename": {"type": "string", "example": "maintenance_report.html"},
            "content_type": {"type": "string", "example": "text/html"},
            "file_size": {"type": "integer", "example": 8192},
            "created_by": {"type": "integer", "example": 1},
            "created_at": {"type": "string", "format": "date-time"},
            "download_url": {"type": "string", "example": "/api/v1/documents/8/download"},
        },
    },
    "DocumentReview": {
        "type": "object",
        "properties": {
            "quality_score": {"type": "integer", "example": 80},
            "status": {
                "type": "string",
                "enum": ["good", "needs_review", "incomplete"],
                "example": "needs_review",
            },
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "example": "Ursache"},
                        "severity": {
                            "type": "string",
                            "enum": ["info", "warning", "critical"],
                            "example": "warning",
                        },
                        "message": {
                            "type": "string",
                            "example": "Ursache " "ist " "sehr " "knapp " "dokumentiert.",
                        },
                    },
                },
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "example": ["Ursache oder wahrscheinliche " "Fehlerquelle dokumentieren."],
            },
            "diagnostics": {
                "type": "object",
                "example": {"status": "local_answer", "provider": "local"},
            },
        },
    },
    "MachineManual": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 4},
            "machine_id": {"type": "integer", "nullable": True, "example": 1},
            "department": {"type": "string", "example": "Instandhaltung"},
            "title": {"type": "string", "example": "CNC-Fraese Handbuch"},
            "original_filename": {"type": "string", "example": "cnc-manual.pdf"},
            "content_type": {"type": "string", "example": "application/pdf"},
            "file_size": {"type": "integer", "example": 245760},
            "analysis_status": {"type": "string", "example": "completed"},
            "summary_status": {"type": "string", "example": "completed"},
            "current_version_id": {"type": "integer", "nullable": True, "example": 7},
            "created_by": {"type": "integer", "example": 1},
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {"type": "string", "format": "date-time"},
            "download_url": {"type": "string", "example": "/api/v1/documents/manuals/4/download"},
        },
    },
}
