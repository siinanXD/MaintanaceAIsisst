"""OpenAPI and Swagger UI configuration for the public API surface."""

import logging

from flask import jsonify, render_template


logger = logging.getLogger(__name__)


OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Maintenance Assistant API",
        "version": "1.0.0",
        "description": (
            "Backend API for authentication, task workflows, error catalog, "
            "AI assistance and inventory forecasting."
        ),
    },
    "servers": [
        {
            "url": "http://127.0.0.1:5050",
            "description": "Local development server",
        }
    ],
    "tags": [
        {"name": "Auth", "description": "Login and user registration"},
        {"name": "Tasks", "description": "Task lifecycle and prioritization"},
        {"name": "Errors", "description": "Error catalog and AI suggestions"},
        {"name": "AI", "description": "Daily briefing and AI assistant endpoints"},
        {"name": "Machines", "description": "Machine records and assistant"},
        {"name": "Inventory", "description": "Inventory and spare-part forecasts"},
        {"name": "Employees", "description": "Employee records and document management"},
        {"name": "ShiftPlans", "description": "AI-generated shift plans and calendar"},
        {"name": "Documents", "description": "Generated maintenance reports and quality reviews"},
        {"name": "Health", "description": "Service health probes"},
    ],
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        },
        "schemas": {
            "ErrorResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": False},
                    "message": {"type": "string", "example": "Invalid credentials"},
                    "error": {"type": "string", "example": "Invalid credentials"},
                },
            },
            "Department": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "name": {"type": "string", "example": "Instandhaltung"},
                },
            },
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "username": {"type": "string", "example": "master.admin"},
                    "email": {"type": "string", "example": "master.admin@demo.local"},
                    "role": {"type": "string", "example": "master_admin"},
                    "department": {"$ref": "#/components/schemas/Department"},
                    "employee_id": {"type": "integer", "nullable": True, "example": 12},
                    "is_active": {"type": "boolean", "example": True},
                },
            },
            "Task": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 42},
                    "title": {
                        "type": "string",
                        "example": "CNC-Fraese Spindellager pruefen",
                    },
                    "description": {
                        "type": "string",
                        "example": "Vibrationen dokumentieren und Lager pruefen.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["urgent", "soon", "normal"],
                        "example": "urgent",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "done", "cancelled"],
                        "example": "open",
                    },
                    "due_date": {"type": "string", "format": "date", "example": "2026-05-04"},
                    "department": {"$ref": "#/components/schemas/Department"},
                    "current_worker_id": {"type": "integer", "nullable": True, "example": 3},
                    "started_at": {
                        "type": "string",
                        "format": "date-time",
                        "nullable": True,
                    },
                    "completed_at": {
                        "type": "string",
                        "format": "date-time",
                        "nullable": True,
                    },
                },
            },
            "TaskCreateRequest": {
                "type": "object",
                "required": ["title"],
                "properties": {
                    "title": {
                        "type": "string",
                        "example": "CNC-Fraese Spindellager pruefen",
                    },
                    "description": {
                        "type": "string",
                        "example": "Vibrationen dokumentieren und Lager pruefen.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["urgent", "soon", "normal"],
                        "example": "urgent",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "done"],
                        "example": "open",
                    },
                    "due_date": {"type": "string", "format": "date", "example": "2026-05-04"},
                    "department": {"type": "string", "example": "Instandhaltung"},
                },
            },
            "ErrorEntry": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 9},
                    "machine": {"type": "string", "example": "CNC-Fraese 01"},
                    "error_code": {"type": "string", "example": "CNC-E-104"},
                    "title": {"type": "string", "example": "Temperatur ausserhalb Toleranz"},
                    "description": {
                        "type": "string",
                        "example": "Spindeltemperatur steigt nach 20 Minuten.",
                    },
                    "possible_causes": {
                        "type": "string",
                        "example": "Kuehlung, Sensor oder Lager pruefen.",
                    },
                    "solution": {
                        "type": "string",
                        "example": "Anlage stoppen, Kuehlkreislauf pruefen, Probelauf dokumentieren.",
                    },
                    "department": {"$ref": "#/components/schemas/Department"},
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
                        "example": "Spindeltemperatur steigt nach 20 Minuten.",
                    },
                    "possible_causes": {
                        "type": "string",
                        "example": "Kuehlung, Sensor oder Lager pruefen.",
                    },
                    "solution": {
                        "type": "string",
                        "example": "Kuehlkreislauf pruefen und Probelauf dokumentieren.",
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
                                "title": {"type": "string", "example": "Kritische Tasks"},
                                "items": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "example": ["2 dringende Aufgaben heute faellig"],
                                },
                            },
                        },
                    },
                    "diagnostics": {
                        "type": "object",
                        "example": {"status": "fallback_used"},
                    },
                },
            },
            "InventoryForecast": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "unmatched_tasks": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
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
                    "qualifications": {
                        "type": "string",
                        "example": "Elektriker, SPS-Programmierung",
                    },
                    "favorite_machine": {"type": "string", "example": "CNC-Fraese 01"},
                    "favorite_machine_id": {
                        "type": "integer",
                        "nullable": True,
                        "example": 1,
                    },
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
            "ShiftPlanEntry": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 101},
                    "employee": {"$ref": "#/components/schemas/Employee"},
                    "machine": {"$ref": "#/components/schemas/Machine"},
                    "work_date": {
                        "type": "string",
                        "format": "date",
                        "example": "2026-05-05",
                    },
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
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "example": "2026-05-05",
                    },
                    "days": {"type": "integer", "example": 7},
                    "rhythm": {"type": "string", "example": "3-Schicht"},
                    "preferences": {
                        "type": "string",
                        "example": "Urlaub: Hans Mueller 06.-08.05.",
                    },
                    "notes": {"type": "string", "example": ""},
                    "entries": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/ShiftPlanEntry"},
                    },
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "GeneratedDocument": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 8},
                    "task_id": {"type": "integer", "example": 42},
                    "document_type": {
                        "type": "string",
                        "example": "maintenance_report",
                    },
                    "title": {
                        "type": "string",
                        "example": "Wartungsbericht Task 42",
                    },
                    "department": {"type": "string", "example": "Instandhaltung"},
                    "machine": {"type": "string", "example": "CNC-Fraese 01"},
                    "machine_id": {"type": "integer", "nullable": True, "example": 1},
                    "created_at": {"type": "string", "format": "date-time"},
                    "download_url": {
                        "type": "string",
                        "example": "/api/documents/8/download",
                    },
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
                                    "example": "Ursache ist sehr knapp dokumentiert.",
                                },
                            },
                        },
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "example": [
                            "Ursache oder wahrscheinliche Fehlerquelle dokumentieren."
                        ],
                    },
                    "diagnostics": {
                        "type": "object",
                        "example": {"status": "local_answer", "provider": "local"},
                    },
                },
            },
        },
        "responses": {
            "Unauthorized": {
                "description": "Missing or invalid JWT token",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                },
            },
            "Forbidden": {
                "description": "User lacks the required role or dashboard permission",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                },
            },
            "ValidationError": {
                "description": "Invalid or incomplete request payload",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                    }
                },
            },
        },
    },
    "paths": {
        "/api/auth/register": {
            "post": {
                "tags": ["Auth"],
                "summary": "Register a user",
                "description": "Creates a user and assigns default dashboard permissions.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["username", "email", "password"],
                                "properties": {
                                    "username": {"type": "string"},
                                    "email": {"type": "string", "format": "email"},
                                    "password": {"type": "string", "format": "password"},
                                    "role": {"type": "string", "example": "produktion"},
                                    "department": {"type": "string", "example": "Produktion"},
                                },
                            },
                            "example": {
                                "username": "produktion.demo",
                                "email": "produktion.demo@example.test",
                                "password": "Demo1234!",
                                "role": "produktion",
                                "department": "Produktion",
                            },
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "User created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "409": {"$ref": "#/components/responses/ValidationError"},
                },
            }
        },
        "/api/auth/login": {
            "post": {
                "tags": ["Auth"],
                "summary": "Login",
                "description": "Authenticates by username, email or login field and returns a JWT.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["login", "password"],
                                "properties": {
                                    "login": {"type": "string"},
                                    "password": {"type": "string", "format": "password"},
                                },
                            },
                            "example": {
                                "login": "master.admin",
                                "password": "Demo1234!",
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "JWT token and current user",
                        "content": {
                            "application/json": {
                                "example": {
                                    "access_token": "eyJhbGciOiJIUzI1NiIs...",
                                    "user": {
                                        "id": 1,
                                        "username": "master.admin",
                                        "role": "master_admin",
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
        "/api/tasks": {
            "get": {
                "tags": ["Tasks"],
                "summary": "List visible tasks",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "status",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["open", "in_progress", "done", "cancelled"],
                        },
                    },
                    {
                        "name": "priority",
                        "in": "query",
                        "schema": {
                            "type": "string",
                            "enum": ["urgent", "soon", "normal"],
                        },
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Visible tasks",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Task"},
                                }
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            },
            "post": {
                "tags": ["Tasks"],
                "summary": "Create a task",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TaskCreateRequest"},
                            "example": {
                                "title": "CNC-Fraese Spindellager pruefen",
                                "description": "Vibrationen dokumentieren und Lager pruefen.",
                                "priority": "urgent",
                                "status": "open",
                                "due_date": "2026-05-04",
                                "department": "Instandhaltung",
                            },
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Task created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Task"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "500": {"$ref": "#/components/responses/ValidationError"},
                },
            },
        },
        "/api/tasks/{task_id}/start": {
            "post": {
                "tags": ["Tasks"],
                "summary": "Start a task",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "requestBody": {
                    "required": False,
                    "content": {"application/json": {"example": {}}},
                },
                "responses": {
                    "200": {
                        "description": "Task moved to in_progress",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Task"},
                                "example": {
                                    "id": 42,
                                    "title": "CNC-Fraese Spindellager pruefen",
                                    "status": "in_progress",
                                    "current_worker_id": 3,
                                },
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                    "409": {"$ref": "#/components/responses/ValidationError"},
                },
            }
        },
        "/api/tasks/{task_id}/complete": {
            "post": {
                "tags": ["Tasks"],
                "summary": "Complete a task",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "example": {
                                "generate_report": True,
                                "notes": "Lager geprueft, Probelauf ohne Auffaelligkeiten.",
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Task completed, optionally with generated document metadata",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Task"},
                                "example": {
                                    "id": 42,
                                    "title": "CNC-Fraese Spindellager pruefen",
                                    "status": "done",
                                    "completed_by": 3,
                                    "generated_document": {
                                        "id": 8,
                                        "download_url": "/api/documents/8/download",
                                    },
                                },
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                    "409": {"$ref": "#/components/responses/ValidationError"},
                },
            }
        },
        "/api/tasks/prioritize": {
            "post": {
                "tags": ["AI", "Tasks"],
                "summary": "Prioritize visible tasks",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "example": {"status": "open", "limit": 10}
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Non-persisted AI or fallback priorities",
                        "content": {
                            "application/json": {
                                "example": [
                                    {
                                        "task": {"id": 42, "title": "CNC-Fraese pruefen"},
                                        "score": 88,
                                        "risk_level": "high",
                                        "reason": "Faelligkeit und Anlagenbezug kritisch.",
                                        "recommended_action": "Heute starten.",
                                    }
                                ]
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            }
        },
        "/api/errors": {
            "post": {
                "tags": ["Errors"],
                "summary": "Create an error catalog entry",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorCreateRequest"},
                            "example": {
                                "machine": "CNC-Fraese 01",
                                "error_code": "CNC-E-104",
                                "title": "Temperatur ausserhalb Toleranz",
                                "description": "Spindeltemperatur steigt nach 20 Minuten.",
                                "possible_causes": "Kuehlung, Sensor oder Lager pruefen.",
                                "solution": "Kuehlkreislauf pruefen und Probelauf dokumentieren.",
                                "department": "Instandhaltung",
                            },
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Error entry created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorEntry"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            }
        },
        "/api/errors/search": {
            "get": {
                "tags": ["Errors"],
                "summary": "Search the visible error catalog",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "query",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "example": "Temperatur CNC",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Matching error entries",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/ErrorEntry"},
                                },
                                "example": [
                                    {
                                        "id": 9,
                                        "machine": "CNC-Fraese 01",
                                        "error_code": "CNC-E-104",
                                        "title": "Temperatur ausserhalb Toleranz",
                                        "possible_causes": "Kuehlung, Sensor oder Lager pruefen.",
                                        "solution": "Kuehlkreislauf pruefen und Probelauf dokumentieren.",
                                    }
                                ],
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            }
        },
        "/api/errors/similar": {
            "post": {
                "tags": ["AI", "Errors"],
                "summary": "Suggest similar error catalog entries",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "example": {
                                "description": "CNC-Fraese meldet hohe Temperatur an der Spindel",
                                "machine": "CNC-Fraese 01",
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Similar error suggestions",
                        "content": {
                            "application/json": {
                                "example": {
                                    "items": [
                                        {
                                            "entry": {
                                                "error_code": "CNC-E-104",
                                                "title": "Temperatur ausserhalb Toleranz",
                                            },
                                            "score": 91,
                                            "reason": "Maschine und Temperaturbegriff passen.",
                                        }
                                    ]
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
        "/api/errors/analyze": {
            "post": {
                "tags": ["AI", "Errors"],
                "summary": "Analyze an error description",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "example": {
                                "description": "CNC-Fraese stoppt mit Temperaturwarnung an der Spindel"
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Non-persisted error analysis",
                        "content": {
                            "application/json": {
                                "example": {
                                    "machine": "CNC-Fraese 01",
                                    "error_code": "AI-001",
                                    "title": "Temperaturwarnung Spindel",
                                    "possible_causes": "Kuehlung, Sensor oder Lager.",
                                    "solution": "Kuehlung pruefen und Probelauf dokumentieren.",
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
        "/api/ai/daily-briefing": {
            "get": {
                "tags": ["AI"],
                "summary": "Get the daily briefing",
                "security": [{"bearerAuth": []}],
                "responses": {
                    "200": {
                        "description": "Daily maintenance briefing",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/DailyBriefing"},
                                "example": {
                                    "date": "2026-05-01",
                                    "sections": [
                                        {
                                            "title": "Heute",
                                            "items": ["3 offene Tasks, 1 kritisch"],
                                        }
                                    ],
                                    "diagnostics": {"status": "fallback_used"},
                                },
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                },
            }
        },
        "/api/machines/{machine_id}/assistant": {
            "post": {
                "tags": ["AI", "Machines"],
                "summary": "Ask the machine assistant",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "machine_id",
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
                                "question": "Welche Wartung ist vor Schichtbeginn wichtig?"
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Machine-specific assistant answer",
                        "content": {
                            "application/json": {
                                "example": {
                                    "answer": "Pruefe offene Tasks und knappe Ersatzteile.",
                                    "diagnostics": {"status": "local_answer"},
                                }
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
        "/health": {
            "get": {
                "tags": ["Health"],
                "summary": "Health probe",
                "description": (
                    "Returns 200 OK for load balancer and container probes. "
                    "No authentication required."
                ),
                "responses": {
                    "200": {
                        "description": "Service is running",
                        "content": {
                            "application/json": {
                                "example": {"status": "ok"}
                            }
                        },
                    }
                },
            }
        },
        "/api/employees": {
            "get": {
                "tags": ["Employees"],
                "summary": "List employees",
                "description": (
                    "Returns employees filtered by the caller's employee access level. "
                    "Non-admin users see only their department."
                ),
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
                            "schema": {
                                "$ref": "#/components/schemas/EmployeeCreateRequest"
                            },
                            "example": {
                                "personnel_number": "MA-0042",
                                "name": "Hans Mueller",
                                "department": "Instandhaltung",
                                "shift_model": "3-Schicht",
                                "qualifications": "Elektriker, SPS-Programmierung",
                                "favorite_machine": "CNC-Fraese 01",
                            },
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Employee created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Employee"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            },
        },
        "/api/employees/{employee_id}": {
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
                            "schema": {
                                "$ref": "#/components/schemas/EmployeeCreateRequest"
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Employee updated",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Employee"}
                            }
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
                    "204": {"description": "Employee deleted"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                },
            },
        },
        "/api/shiftplans": {
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
                                    "items": {
                                        "$ref": "#/components/schemas/ShiftPlan"
                                    },
                                }
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            }
        },
        "/api/shiftplans/generate": {
            "post": {
                "tags": ["ShiftPlans", "AI"],
                "summary": "Generate an AI shift plan",
                "description": (
                    "Generates a shift plan using AI or a local fallback. "
                    "Returns warnings and coverage info alongside the persisted plan."
                ),
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "example": {
                                "title": "Schichtplan KW 19",
                                "start_date": "2026-05-05",
                                "days": 7,
                                "rhythm": "3-Schicht",
                                "preferences": "Urlaub: Hans Mueller 06.-08.05.",
                            }
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "AI-generated shift plan",
                        "content": {
                            "application/json": {
                                "example": {
                                    "plan": {"id": 5, "title": "Schichtplan KW 19"},
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
        "/api/shiftplans/calendar": {
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
                        "description": (
                            "Filter by employee ID; defaults to the current user's "
                            "linked employee."
                        ),
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Shift calendar entries for the requested employee",
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
        "/api/documents": {
            "get": {
                "tags": ["Documents"],
                "summary": "List generated documents",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "example": 42,
                    },
                    {
                        "name": "department",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "example": "Instandhaltung",
                    },
                    {
                        "name": "machine",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "example": "CNC-Fraese 01",
                    },
                    {
                        "name": "date_from",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "format": "date"},
                        "example": "2026-05-01",
                    },
                    {
                        "name": "date_to",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string", "format": "date"},
                        "example": "2026-05-31",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Visible generated documents, newest first",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/components/schemas/GeneratedDocument"
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
        "/api/documents/{document_id}/download": {
            "get": {
                "tags": ["Documents"],
                "summary": "Download a generated document",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "document_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "HTML maintenance report as file download",
                        "content": {
                            "text/html": {
                                "schema": {"type": "string", "format": "binary"}
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
        "/api/documents/{document_id}/review": {
            "post": {
                "tags": ["Documents", "AI"],
                "summary": "Review document quality",
                "description": (
                    "Returns a non-persisted AI or local quality review for a "
                    "generated maintenance report."
                ),
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "document_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": (
                            "Quality review with score, findings, and recommendations"
                        ),
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/DocumentReview"
                                },
                                "example": {
                                    "quality_score": 80,
                                    "status": "needs_review",
                                    "findings": [
                                        {
                                            "field": "Ursache",
                                            "severity": "warning",
                                            "message": (
                                                "Ursache ist sehr knapp dokumentiert."
                                            ),
                                        }
                                    ],
                                    "recommendations": [
                                        "Ursache oder wahrscheinliche Fehlerquelle "
                                        "dokumentieren."
                                    ],
                                    "diagnostics": {"status": "local_answer"},
                                },
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
        "/api/inventory/forecast": {
            "post": {
                "tags": ["Inventory", "AI"],
                "summary": "Forecast spare-part risks",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "example": {
                                "status": "open",
                                "limit": 20,
                                "low_stock_threshold": 5,
                            }
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Inventory risk forecast",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/InventoryForecast"},
                                "example": {
                                    "items": [
                                        {
                                            "machine": {"id": 1, "name": "CNC-Fraese 01"},
                                            "material": {
                                                "id": 5,
                                                "name": "Hartmetall-Fraeser 8 mm",
                                            },
                                            "quantity": 2,
                                            "risk_level": "high",
                                            "match_reason": "Treffer ueber Teilnamen: cnc, fraese",
                                        }
                                    ],
                                    "unmatched_tasks": [],
                                    "summary": {
                                        "critical": 0,
                                        "high": 1,
                                        "medium": 0,
                                        "total": 1,
                                    },
                                },
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            }
        },
    },
}


def hide_route_from_generated_spec(_rule):
    """Keep flasgger from mixing route docstrings into the curated spec."""
    return False


def include_schema_model(_tag):
    """Allow flasgger to expose schema models from the curated template."""
    return True


def configure_api_documentation(app):
    """Register OpenAPI JSON and Swagger UI routes on the Flask app."""

    @app.get("/api/swagger.json")
    def swagger_json():
        """Return the OpenAPI specification as JSON."""
        return jsonify(OPENAPI_SPEC)

    try:
        from flasgger import Swagger
    except ImportError:
        logger.warning("flasgger_missing swagger_ui=fallback")

        @app.get("/swagger/")
        def swagger_fallback():
            """Render a lightweight Swagger UI fallback using the OpenAPI JSON."""
            return render_template("swagger.html")

        return

    Swagger(
        app,
        template=OPENAPI_SPEC,
        config={
            "headers": [],
            "specs": [
                {
                    "endpoint": "apispec",
                    "route": "/apispec_1.json",
                    "rule_filter": hide_route_from_generated_spec,
                    "model_filter": include_schema_model,
                }
            ],
            "static_url_path": "/flasgger_static",
            "swagger_ui": True,
            "specs_route": "/swagger/",
        },
    )
