"""OpenAPI path fragment for workforce shiftplans."""

PATHS_WORKFORCE_SHIFTPLANS = {
    "/api/v1/employees": {
        "get": {
            "tags": ["Employees"],
            "summary": "List employees",
            "description": "Returns employees filtered by the caller's employee "
            "access level. Non-admin users see only their "
            "department.",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "department",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "example": "Instandhaltung",
                }
            ],
            "responses": {
                "200": {
                    "description": "Visible employee list",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Employee"},
                            }
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        },
        "post": {
            "tags": ["Employees"],
            "summary": "Create an employee",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/EmployeeCreateRequest"},
                        "example": {
                            "personnel_number": "MA-0042",
                            "name": "Hans " "Mueller",
                            "department": "Instandhaltung",
                            "shift_model": "3-Schicht",
                            "qualifications": "Elektriker, " "SPS-Programmierung",
                            "favorite_machine": "CNC-Fraese " "01",
                        },
                    }
                },
            },
            "responses": {
                "201": {
                    "description": "Employee created",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Employee"}}
                    },
                },
                "400": {"$ref": "#/components/responses/ValidationError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        },
    },
    "/api/v1/employees/{employee_id}": {
        "put": {
            "tags": ["Employees"],
            "summary": "Update an employee",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "employee_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                }
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/EmployeeCreateRequest"}
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Employee " "updated",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Employee"}}
                    },
                },
                "400": {"$ref": "#/components/responses/ValidationError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
                "404": {"$ref": "#/components/responses/ValidationError"},
            },
        },
        "delete": {
            "tags": ["Employees"],
            "summary": "Delete an employee",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "employee_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                }
            ],
            "responses": {
                "204": {"description": "Employee " "deleted"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
                "404": {"$ref": "#/components/responses/ValidationError"},
            },
        },
    },
    "/api/v1/employees/qualifications": {
        "get": {
            "tags": ["Employees"],
            "summary": "List the structured employee-machine " "qualification matrix",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Employees, " "machines, " "qualification " "rows and " "levels",
                    "content": {
                        "application/json": {
                            "example": {
                                "employees": [{"id": 12, "name": "Hans " "Mueller"}],
                                "machines": [{"id": 1, "name": "CNC-Fraese " "01"}],
                                "qualifications": [
                                    {"employee_id": 12, "machine_id": 1, "level": "trained"}
                                ],
                                "levels": ["basic", "expert", "trained", "trainer"],
                            }
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        }
    },
    "/api/v1/employees/{employee_id}/qualifications": {
        "put": {
            "tags": ["Employees"],
            "summary": "Replace structured machine " "qualifications for one " "employee",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "employee_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                }
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "example": {
                            "qualifications": [
                                {
                                    "machine_id": 1,
                                    "level": "expert",
                                    "valid_until": "2026-12-31",
                                    "notes": "Freigabe " "erneuert",
                                }
                            ]
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Updated " "employee " "qualification " "rows",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/EmployeeMachineQualification"}
                        }
                    },
                },
                "400": {"$ref": "#/components/responses/ValidationError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
                "404": {"$ref": "#/components/responses/ValidationError"},
            },
        }
    },
    "/api/v1/shiftplans": {
        "get": {
            "tags": ["ShiftPlans"],
            "summary": "List shift plans",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "All shift plans with entries",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/ShiftPlan"},
                            }
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        }
    },
    "/api/v1/shiftplans/models": {
        "get": {
            "tags": ["ShiftPlans"],
            "summary": "List supported shift model templates",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Available shift model " "templates",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "data": [
                                    {
                                        "key": "three_shift",
                                        "name": "3-Schicht " "Frueh/Spaet/Nacht",
                                        "display_name": "3-Schicht " "Frueh/Spaet/Nacht",
                                        "description": "Frueh-, " "Spaet- " "und " "Nachtschicht.",
                                        "shifts": [
                                            {
                                                "key": "Frueh",
                                                "name": "Fruehschicht",
                                                "start_time": "06:00",
                                                "end_time": "14:00",
                                            }
                                        ],
                                        "shift_times": {
                                            "Frueh": {"start_time": "06:00", "end_time": "14:00"}
                                        },
                                        "team_count": 3,
                                        "weekend_operation": False,
                                        "rotation_direction": "forward",
                                        "weekly_hours_target": 40.0,
                                        "max_consecutive_nights": 3,
                                        "recommended_rest_hours": 11.0,
                                    }
                                ],
                            }
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        }
    },
    "/api/v1/shiftplans/generate": {
        "post": {
            "tags": ["ShiftPlans"],
            "summary": "Generate a rule-based shift plan",
            "description": "Generates a deterministic rule-based "
            "shift plan. Returns warnings and "
            "coverage info alongside the persisted "
            "plan.",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "example": {
                            "title": "Schichtplan " "KW " "19",
                            "start_date": "2026-05-05",
                            "days": 7,
                            "shift_model_key": "three_shift",
                            "rhythm": "3-Schicht",
                            "preferences": {"text": "Urlaub: " "Hans " "Mueller " "06.-08.05."},
                        }
                    }
                },
            },
            "responses": {
                "201": {
                    "description": "Generated shift " "plan",
                    "content": {
                        "application/json": {
                            "example": {
                                "plan": {"id": 5, "title": "Schichtplan " "KW " "19"},
                                "warnings": [],
                                "coverage": {"covered": 7, "total": 7},
                                "diagnostics": {"status": "openai_used"},
                            }
                        }
                    },
                },
                "400": {"$ref": "#/components/responses/ValidationError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        }
    },
    "/api/v1/shiftplans/{plan_id}/conflicts": {
        "get": {
            "tags": ["ShiftPlans"],
            "summary": "List shift plan conflicts",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "plan_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {
                    "description": "Conflict " "list " "with " "summary " "and " "coverage",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "data": {
                                    "plan_id": 5,
                                    "conflicts": [
                                        {
                                            "type": "missing_qualification",
                                            "severity": "critical",
                                            "message": "Freigabe " "fehlt.",
                                        }
                                    ],
                                    "summary": {"total": 1, "critical": 1},
                                },
                            }
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
                "404": {"$ref": "#/components/responses/ValidationError"},
            },
        }
    },
    "/api/v1/shiftplans/validate": {
        "post": {
            "tags": ["ShiftPlans"],
            "summary": "Validate an ad-hoc or existing shift plan",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "example": {
                            "entries": [
                                {
                                    "employee_id": 12,
                                    "machine_id": 1,
                                    "work_date": "2026-05-05",
                                    "shift": "Frueh",
                                    "start_time": "06:00",
                                    "end_time": "14:00",
                                }
                            ]
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Validation result",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "conflicts": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/ShiftPlanConflict"},
                                    }
                                },
                            }
                        }
                    },
                },
                "400": {"$ref": "#/components/responses/ValidationError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        }
    },
    "/api/v1/shiftplans/{plan_id}/export.xlsx": {
        "get": {
            "tags": ["ShiftPlans"],
            "summary": "Export a shift plan as XLSX",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "plan_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {
                    "description": "XLSX " "workbook",
                    "content": {
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                            "schema": {"type": "string", "format": "binary"}
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
                "404": {"$ref": "#/components/responses/ValidationError"},
            },
        }
    },
    "/api/v1/shiftplans/calendar": {
        "get": {
            "tags": ["ShiftPlans"],
            "summary": "Get shift calendar for a user or employee",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "employee_id",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer"},
                    "description": "Filter by employee ID; "
                    "defaults to the current "
                    "user's linked employee.",
                }
            ],
            "responses": {
                "200": {
                    "description": "Shift calendar " "entries for the " "requested employee",
                    "content": {
                        "application/json": {
                            "example": {
                                "employee_id": 12,
                                "entries": [
                                    {
                                        "work_date": "2026-05-05",
                                        "shift": "Fruehschicht",
                                        "start_time": "06:00",
                                        "end_time": "14:00",
                                    }
                                ],
                            }
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        }
    },
}
