"""OpenAPI schema fragment 3."""

SCHEMAS_3 = {
    "ErrorEntry": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 9},
            "machine": {"type": "string", "example": "CNC-Fraese 01"},
            "error_code": {"type": "string", "example": "CNC-E-104"},
            "title": {"type": "string", "example": "Temperatur ausserhalb Toleranz"},
            "description": {
                "type": "string",
                "example": "Spindeltemperatur steigt nach 20 " "Minuten.",
            },
            "possible_causes": {
                "type": "string",
                "example": "Kuehlung, Sensor oder Lager " "pruefen.",
            },
            "solution": {
                "type": "string",
                "example": "Anlage stoppen, Kuehlkreislauf pruefen, " "Probelauf dokumentieren.",
            },
            "department": {"$ref": "#/components/schemas/Department"},
            "missing_information": {"$ref": "#/components/schemas/MissingInformation"},
        },
    },
    "ErrorCreateRequest": {
        "type": "object",
        "required": ["machine", "error_code", "title"],
        "properties": {
            "machine": {"type": "string", "example": "CNC-Fraese 01"},
            "error_code": {"type": "string", "example": "CNC-E-104"},
            "title": {"type": "string", "example": "Temperatur ausserhalb Toleranz"},
            "description": {
                "type": "string",
                "example": "Spindeltemperatur steigt nach " "20 Minuten.",
            },
            "possible_causes": {
                "type": "string",
                "example": "Kuehlung, Sensor oder Lager " "pruefen.",
            },
            "solution": {
                "type": "string",
                "example": "Kuehlkreislauf pruefen und " "Probelauf dokumentieren.",
            },
            "department": {"type": "string", "example": "Instandhaltung"},
        },
    },
    "DailyBriefing": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "format": "date", "example": "2026-05-01"},
            "sections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "example": "Kritische " "Tasks"},
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                            "example": ["2 " "dringende " "Aufgaben " "heute " "faellig"],
                        },
                    },
                },
            },
            "diagnostics": {"type": "object", "example": {"status": "fallback_used"}},
        },
    },
    "InventoryForecast": {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {"type": "object"}},
            "unmatched_tasks": {"type": "array", "items": {"type": "object"}},
            "summary": {
                "type": "object",
                "example": {"critical": 1, "high": 2, "medium": 0, "total": 3},
            },
        },
    },
    "Machine": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 1},
            "name": {"type": "string", "example": "CNC-Fraese 01"},
            "produced_item": {"type": "string", "example": "Aluminiumgehaeuse"},
            "required_employees": {"type": "integer", "example": 2},
        },
    },
    "Employee": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 12},
            "personnel_number": {"type": "string", "example": "MA-0042"},
            "name": {"type": "string", "example": "Hans Mueller"},
            "department": {"type": "string", "example": "Instandhaltung"},
            "team": {"type": "integer", "nullable": True, "example": 2},
            "shift_model": {"type": "string", "example": "3-Schicht"},
            "current_shift": {"type": "string", "example": "Fruehschicht"},
            "qualifications": {"type": "string", "example": "Elektriker, SPS-Programmierung"},
            "favorite_machine": {"type": "string", "example": "CNC-Fraese 01"},
            "favorite_machine_id": {"type": "integer", "nullable": True, "example": 1},
        },
    },
    "EmployeeCreateRequest": {
        "type": "object",
        "required": ["personnel_number", "name"],
        "properties": {
            "personnel_number": {"type": "string", "example": "MA-0042"},
            "name": {"type": "string", "example": "Hans Mueller"},
            "department": {"type": "string", "example": "Instandhaltung"},
            "shift_model": {"type": "string", "example": "3-Schicht"},
            "current_shift": {"type": "string", "example": "Fruehschicht"},
            "qualifications": {"type": "string", "example": "Elektriker"},
            "favorite_machine": {"type": "string", "example": "CNC-Fraese 01"},
            "favorite_machine_id": {"type": "integer", "nullable": True},
        },
    },
    "EmployeeMachineQualification": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 9},
            "employee_id": {"type": "integer", "example": 12},
            "machine_id": {"type": "integer", "example": 1},
            "level": {
                "type": "string",
                "enum": ["basic", "trained", "expert", "trainer"],
                "example": "trained",
            },
            "valid_until": {
                "type": "string",
                "format": "date",
                "nullable": True,
                "example": "2026-12-31",
            },
            "notes": {"type": "string", "example": "Freigabe durch " "Teamleitung"},
        },
    },
    "ShiftPlanConflict": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "duplicate_assignment",
                    "vacation_conflict",
                    "missing_qualification",
                    "coverage",
                    "rest_time",
                    "weekly_hours",
                    "consecutive_days",
                ],
                "example": "missing_qualification",
            },
            "severity": {"type": "string", "example": "critical"},
            "message": {"type": "string", "example": "Mitarbeiter hat keine " "Maschinenfreigabe."},
            "employee_id": {"type": "integer", "nullable": True, "example": 12},
            "machine_id": {"type": "integer", "nullable": True, "example": 1},
            "work_date": {
                "type": "string",
                "format": "date",
                "nullable": True,
                "example": "2026-05-05",
            },
        },
    },
}
