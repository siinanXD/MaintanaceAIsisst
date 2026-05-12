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
            "AI assistance, inventory forecasting and administration. "
            "The stable public API lives under /api/v1; breaking changes use "
            "a new major prefix such as /api/v2."
        ),
    },
    "servers": [
        {
            "url": "http://127.0.0.1:5050/api/v1",
            "description": "Local development server (v1)",
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
        {"name": "Admin", "description": "Users, permissions, audit log and backups"},
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
                    "error": {"type": "string", "example": "invalid_credentials"},
                },
            },
            "Pagination": {
                "type": "object",
                "description": "Pagination metadata returned by list endpoints.",
                "properties": {
                    "page": {"type": "integer", "example": 1},
                    "limit": {"type": "integer", "example": 20},
                    "total": {"type": "integer", "example": 100},
                    "pages": {"type": "integer", "example": 5},
                },
            },
            "PaginatedTasks": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {"type": "array", "items": {"$ref": "#/components/schemas/Task"}},
                    "pagination": {"$ref": "#/components/schemas/Pagination"},
                    "message": {"type": "string", "example": "OK"},
                },
            },
            "PaginatedErrors": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {"type": "array", "items": {"$ref": "#/components/schemas/ErrorEntry"}},
                    "pagination": {"$ref": "#/components/schemas/Pagination"},
                    "message": {"type": "string", "example": "OK"},
                },
            },
            "PaginatedEmployees": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {"type": "array", "items": {"$ref": "#/components/schemas/Employee"}},
                    "pagination": {"$ref": "#/components/schemas/Pagination"},
                    "message": {"type": "string", "example": "OK"},
                },
            },
            "SuccessResponse": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "message": {"type": "string", "example": "OK"},
                    "data": {"type": "object"},
                },
            },
            "PermissionValue": {
                "type": "object",
                "properties": {
                    "can_view": {"type": "boolean", "example": True},
                    "can_write": {"type": "boolean", "example": False},
                    "employee_access_level": {
                        "type": "string",
                        "enum": ["none", "basic", "shift", "confidential"],
                        "example": "basic",
                    },
                },
            },
            "PermissionSchema": {
                "type": "object",
                "properties": {
                    "dashboards": {
                        "type": "array",
                        "items": {"type": "object"},
                        "example": [{"key": "tasks", "label": "Tasks"}],
                    },
                    "groups": {
                        "type": "array",
                        "items": {"type": "object"},
                        "example": [{"key": "work", "label": "Arbeit", "dashboards": ["tasks"]}],
                    },
                    "employee_access_levels": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "role_defaults": {"type": "object"},
                },
            },
            "AuditLogEntry": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 17},
                    "actor": {"$ref": "#/components/schemas/User"},
                    "action": {"type": "string", "example": "permissions.update"},
                    "resource_type": {"type": "string", "example": "user"},
                    "resource_id": {"type": "string", "example": "12"},
                    "before": {"type": "object"},
                    "after": {"type": "object"},
                    "ip_address": {"type": "string", "example": "127.0.0.1"},
                    "user_agent": {"type": "string", "example": "Mozilla/5.0"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "PaginatedAuditLog": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/AuditLogEntry"},
                    },
                    "pagination": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "example": 50},
                            "offset": {"type": "integer", "example": 0},
                            "total": {"type": "integer", "example": 1},
                        },
                    },
                    "message": {"type": "string", "example": "Audit log loaded"},
                },
            },
            "BackupMetadata": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "example": "maintenance_backup_20260512_120000.zip"},
                    "filename": {
                        "type": "string",
                        "example": "maintenance_backup_20260512_120000.zip",
                    },
                    "size_bytes": {"type": "integer", "example": 20480},
                    "created_at": {"type": "string", "format": "date-time"},
                    "download_url": {
                        "type": "string",
                        "example": (
                            "/api/v1/admin/backups/"
                            "maintenance_backup_20260512_120000.zip/download"
                        ),
                    },
                },
            },
            "MailStatus": {
                "type": "object",
                "properties": {
                    "enabled": {"type": "boolean", "example": False},
                    "dry_run": {"type": "boolean", "example": True},
                    "host_configured": {"type": "boolean", "example": False},
                    "port": {"type": "integer", "example": 587},
                    "username_configured": {"type": "boolean", "example": False},
                    "from_configured": {"type": "boolean", "example": True},
                    "use_tls": {"type": "boolean", "example": True},
                },
            },
            "NotificationDelivery": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 1},
                    "notification_type": {"type": "string", "example": "task_urgent"},
                    "recipient_user_id": {"type": "integer", "nullable": True, "example": 2},
                    "recipient_email": {"type": "string", "example": "ops@example.test"},
                    "channel": {"type": "string", "example": "email"},
                    "subject": {"type": "string", "example": "Dringender Task: CNC steht"},
                    "status": {"type": "string", "example": "dry_run"},
                    "error": {"type": "string", "example": ""},
                    "dedupe_key": {"type": "string", "example": "task_urgent:2026-05-12:7:2"},
                    "payload": {"type": "object"},
                    "sent_at": {"type": "string", "format": "date-time", "nullable": True},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
            "PaginatedNotificationDeliveries": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean", "example": True},
                    "data": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/NotificationDelivery"},
                    },
                    "pagination": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "example": 50},
                            "offset": {"type": "integer", "example": 0},
                            "total": {"type": "integer", "example": 1},
                        },
                    },
                    "mail": {"$ref": "#/components/schemas/MailStatus"},
                    "message": {
                        "type": "string",
                        "example": "Notification deliveries loaded",
                    },
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
                        "example": (
                            "Anlage stoppen, Kuehlkreislauf pruefen, " "Probelauf dokumentieren."
                        ),
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
                    "status": {
                        "type": "string",
                        "enum": ["draft", "in_review", "approved", "rejected"],
                        "example": "draft",
                    },
                    "current_version_id": {
                        "type": "integer",
                        "nullable": True,
                        "example": 3,
                    },
                    "summary": {
                        "type": "string",
                        "example": "Kurzfassung der wichtigsten Wartungspunkte.",
                    },
                    "summary_status": {
                        "type": "string",
                        "example": "completed",
                    },
                    "approved_at": {
                        "type": "string",
                        "format": "date-time",
                        "nullable": True,
                    },
                    "approval_comment": {"type": "string", "example": ""},
                    "download_url": {
                        "type": "string",
                        "example": "/api/v1/documents/8/download",
                    },
                    "pdf_url": {
                        "type": "string",
                        "example": "/api/v1/documents/8/download.pdf",
                    },
                },
            },
            "DocumentVersion": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "example": 12},
                    "document_id": {"type": "integer", "example": 8},
                    "version_number": {"type": "integer", "example": 1},
                    "original_filename": {
                        "type": "string",
                        "example": "maintenance_report.html",
                    },
                    "content_type": {"type": "string", "example": "text/html"},
                    "file_size": {"type": "integer", "example": 8192},
                    "created_by": {"type": "integer", "example": 1},
                    "created_at": {"type": "string", "format": "date-time"},
                    "download_url": {
                        "type": "string",
                        "example": "/api/v1/documents/8/download",
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
                        "example": ["Ursache oder wahrscheinliche Fehlerquelle dokumentieren."],
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
                    "original_filename": {
                        "type": "string",
                        "example": "cnc-manual.pdf",
                    },
                    "content_type": {"type": "string", "example": "application/pdf"},
                    "file_size": {"type": "integer", "example": 245760},
                    "analysis_status": {"type": "string", "example": "completed"},
                    "summary_status": {"type": "string", "example": "completed"},
                    "current_version_id": {
                        "type": "integer",
                        "nullable": True,
                        "example": 7,
                    },
                    "created_by": {"type": "integer", "example": 1},
                    "created_at": {"type": "string", "format": "date-time"},
                    "updated_at": {"type": "string", "format": "date-time"},
                    "download_url": {
                        "type": "string",
                        "example": "/api/v1/documents/manuals/4/download",
                    },
                },
            },
        },
        "responses": {
            "Unauthorized": {
                "description": "Missing or invalid JWT token",
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}
                },
            },
            "Forbidden": {
                "description": "User lacks the required role or dashboard permission",
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}
                },
            },
            "ValidationError": {
                "description": "Invalid or incomplete request payload",
                "content": {
                    "application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}
                },
            },
        },
    },
    "paths": {
        "/api/v1/auth/register": {
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
                            "application/json": {"schema": {"$ref": "#/components/schemas/User"}}
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "409": {"$ref": "#/components/responses/ValidationError"},
                },
            }
        },
        "/api/v1/auth/login": {
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
        "/api/v1/admin/permissions/schema": {
            "get": {
                "tags": ["Admin"],
                "summary": "Read permission editor schema",
                "description": (
                    "Returns dashboard groups, labels, employee access labels " "and role defaults."
                ),
                "security": [{"bearerAuth": []}],
                "responses": {
                    "200": {
                        "description": "Permission schema",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PermissionSchema"},
                                "example": {
                                    "dashboards": [{"key": "tasks", "label": "Tasks"}],
                                    "groups": [
                                        {
                                            "key": "work",
                                            "label": "Arbeit",
                                            "dashboards": ["tasks"],
                                        }
                                    ],
                                    "employee_access_levels": [
                                        {"key": "basic", "label": "Basisdaten"}
                                    ],
                                    "role_defaults": {
                                        "produktion": {
                                            "tasks": {
                                                "can_view": True,
                                                "can_write": True,
                                                "employee_access_level": "none",
                                            }
                                        }
                                    },
                                },
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            }
        },
        "/api/v1/admin/users/{user_id}/permissions": {
            "get": {
                "tags": ["Admin"],
                "summary": "Read user permissions",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "user_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Permissions by dashboard",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "additionalProperties": {
                                        "$ref": "#/components/schemas/PermissionValue"
                                    },
                                },
                                "example": {
                                    "tasks": {
                                        "can_view": True,
                                        "can_write": True,
                                        "employee_access_level": "none",
                                    }
                                },
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                },
            },
            "put": {
                "tags": ["Admin"],
                "summary": "Replace user permissions",
                "description": "Keeps admin user management locked to master admins.",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "user_id",
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
                                "type": "object",
                                "properties": {
                                    "permissions": {
                                        "type": "object",
                                        "additionalProperties": {
                                            "$ref": "#/components/schemas/PermissionValue"
                                        },
                                    }
                                },
                            },
                            "example": {
                                "permissions": {
                                    "tasks": {
                                        "can_view": True,
                                        "can_write": True,
                                        "employee_access_level": "none",
                                    }
                                }
                            },
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Updated user",
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/User"}}
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                },
            },
        },
        "/api/v1/admin/audit-log": {
            "get": {
                "tags": ["Admin"],
                "summary": "Search security audit log",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {"name": "q", "in": "query", "schema": {"type": "string"}},
                    {"name": "actor_id", "in": "query", "schema": {"type": "integer"}},
                    {"name": "action", "in": "query", "schema": {"type": "string"}},
                    {"name": "resource_type", "in": "query", "schema": {"type": "string"}},
                    {
                        "name": "date_from",
                        "in": "query",
                        "schema": {"type": "string", "format": "date-time"},
                    },
                    {
                        "name": "date_to",
                        "in": "query",
                        "schema": {"type": "string", "format": "date-time"},
                    },
                    {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 50}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer", "default": 0}},
                ],
                "responses": {
                    "200": {
                        "description": "Paginated audit events",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PaginatedAuditLog"},
                                "example": {
                                    "success": True,
                                    "data": [
                                        {
                                            "id": 1,
                                            "action": "permissions.update",
                                            "resource_type": "user",
                                            "resource_id": "2",
                                            "actor": {"id": 1, "username": "master.admin"},
                                            "before": {},
                                            "after": {},
                                            "created_at": "2026-05-12T12:00:00+00:00",
                                        }
                                    ],
                                    "pagination": {"limit": 50, "offset": 0, "total": 1},
                                    "message": "Audit log loaded",
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
        "/api/v1/admin/backups": {
            "get": {
                "tags": ["Admin"],
                "summary": "List backup archives",
                "security": [{"bearerAuth": []}],
                "responses": {
                    "200": {
                        "description": "Available backups",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "$ref": "#/components/schemas/BackupMetadata"
                                            },
                                        },
                                        "message": {"type": "string"},
                                    },
                                },
                                "example": {
                                    "success": True,
                                    "data": [],
                                    "message": "Backups loaded",
                                },
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            },
            "post": {
                "tags": ["Admin"],
                "summary": "Create backup archive",
                "security": [{"bearerAuth": []}],
                "responses": {
                    "201": {
                        "description": "Backup created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                                "example": {
                                    "success": True,
                                    "data": {
                                        "id": "maintenance_backup_20260512_120000.zip",
                                        "filename": "maintenance_backup_20260512_120000.zip",
                                    },
                                    "message": "Backup created",
                                },
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            },
        },
        "/api/v1/admin/backups/{backup_id}/download": {
            "get": {
                "tags": ["Admin"],
                "summary": "Download one backup archive",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "backup_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {"description": "ZIP archive"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                },
            }
        },
        "/api/v1/admin/backups/{backup_id}/restore": {
            "post": {
                "tags": ["Admin"],
                "summary": "Restore one backup archive",
                "description": (
                    "Requires confirm=true and creates a safety backup before " "replacing files."
                ),
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "backup_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["confirm"],
                                "properties": {"confirm": {"type": "boolean", "example": True}},
                            },
                            "example": {"confirm": True},
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Backup restored",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                                "example": {
                                    "success": True,
                                    "data": {
                                        "restored_backup": "maintenance_backup_20260512_120000.zip"
                                    },
                                    "message": "Backup restored",
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
        "/api/v1/admin/notifications/deliveries": {
            "get": {
                "tags": ["Admin"],
                "summary": "List notification deliveries",
                "description": (
                    "Returns email delivery records and redacted mail " "configuration status."
                ),
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {"name": "type", "in": "query", "schema": {"type": "string"}},
                    {"name": "status", "in": "query", "schema": {"type": "string"}},
                    {"name": "q", "in": "query", "schema": {"type": "string"}},
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                    {"name": "offset", "in": "query", "schema": {"type": "integer"}},
                ],
                "responses": {
                    "200": {
                        "description": "Notification deliveries",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/PaginatedNotificationDeliveries"
                                },
                                "example": {
                                    "success": True,
                                    "data": [
                                        {
                                            "id": 1,
                                            "notification_type": "task_urgent",
                                            "recipient_email": "ops@example.test",
                                            "status": "dry_run",
                                            "subject": "Dringender Task: CNC steht",
                                            "created_at": "2026-05-12T12:00:00+00:00",
                                        }
                                    ],
                                    "pagination": {"limit": 50, "offset": 0, "total": 1},
                                    "mail": {"enabled": False, "dry_run": True},
                                    "message": "Notification deliveries loaded",
                                },
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            }
        },
        "/api/v1/admin/notifications/test-email": {
            "post": {
                "tags": ["Admin"],
                "summary": "Send test email",
                "description": (
                    "Creates a delivery record and sends via SMTP unless " "dry-run is enabled."
                ),
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "recipient_email": {
                                        "type": "string",
                                        "example": "ops@example.test",
                                    }
                                },
                            },
                            "example": {"recipient_email": "ops@example.test"},
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Test email delivery recorded",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                                "example": {
                                    "success": True,
                                    "data": {
                                        "notification_type": "test_email",
                                        "recipient_email": "ops@example.test",
                                        "status": "dry_run",
                                    },
                                    "mail": {"enabled": False, "dry_run": True},
                                    "message": "Test email recorded",
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
        "/api/v1/tasks": {
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
                            "application/json": {"schema": {"$ref": "#/components/schemas/Task"}}
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "500": {"$ref": "#/components/responses/ValidationError"},
                },
            },
        },
        "/api/v1/tasks/{task_id}/start": {
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
        "/api/v1/tasks/{task_id}/complete": {
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
                        "description": (
                            "Task completed, optionally with generated document metadata"
                        ),
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
                                        "download_url": "/api/v1/documents/8/download",
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
        "/api/v1/tasks/prioritize": {
            "post": {
                "tags": ["AI", "Tasks"],
                "summary": "Prioritize visible tasks",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": False,
                    "content": {"application/json": {"example": {"status": "open", "limit": 10}}},
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
        "/api/v1/errors": {
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
        "/api/v1/errors/search": {
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
                                        "solution": (
                                            "Kuehlkreislauf pruefen und Probelauf " "dokumentieren."
                                        ),
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
        "/api/v1/errors/similar": {
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
        "/api/v1/errors/analyze": {
            "post": {
                "tags": ["AI", "Errors"],
                "summary": "Analyze an error description",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "example": {
                                "description": (
                                    "CNC-Fraese stoppt mit Temperaturwarnung an der Spindel"
                                )
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
        "/api/v1/ai/daily-briefing": {
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
        "/api/v1/machines/{machine_id}/assistant": {
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
                            "example": {"question": "Welche Wartung ist vor Schichtbeginn wichtig?"}
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
                        "content": {"application/json": {"example": {"status": "ok"}}},
                    }
                },
            }
        },
        "/api/v1/employees": {
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
                            "schema": {"$ref": "#/components/schemas/EmployeeCreateRequest"},
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
        "/api/v1/shiftplans/generate": {
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
        "/api/v1/documents": {
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
                                    "items": {"$ref": "#/components/schemas/GeneratedDocument"},
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
        "/api/v1/documents/{document_id}/download": {
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
                            "text/html": {"schema": {"type": "string", "format": "binary"}}
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                },
            }
        },
        "/api/v1/documents/{document_id}/download.pdf": {
            "get": {
                "tags": ["Documents"],
                "summary": "Download a generated document as server-rendered PDF",
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
                        "description": "PDF maintenance report as file download",
                        "content": {
                            "application/pdf": {"schema": {"type": "string", "format": "binary"}}
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                },
            }
        },
        "/api/v1/documents/{document_id}/versions": {
            "get": {
                "tags": ["Documents"],
                "summary": "List immutable versions for a generated document",
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
                        "description": "Document versions",
                        "content": {
                            "application/json": {
                                "example": {
                                    "success": True,
                                    "message": "Document versions loaded",
                                    "data": [
                                        {
                                            "id": 12,
                                            "document_id": 8,
                                            "version_number": 1,
                                            "original_filename": ("maintenance_report.html"),
                                        }
                                    ],
                                },
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {"type": "boolean"},
                                        "message": {"type": "string"},
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "$ref": ("#/components/schemas/" "DocumentVersion")
                                            },
                                        },
                                    },
                                },
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                },
            }
        },
        "/api/v1/documents/{document_id}/summarize": {
            "post": {
                "tags": ["Documents", "AI"],
                "summary": "Create or update a stored document summary",
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
                        "description": "Stored summary with diagnostics",
                        "content": {
                            "application/json": {
                                "example": {
                                    "success": True,
                                    "message": "Document summarized",
                                    "data": {
                                        "summary": "Wartung abgeschlossen.",
                                        "summary_status": "completed",
                                        "diagnostics": {"status": "local_answer"},
                                    },
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
        "/api/v1/documents/{document_id}/submit-review": {
            "post": {
                "tags": ["Documents"],
                "summary": "Submit a generated document for approval",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "document_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {"example": {"comment": "Bitte fachlich pruefen."}}
                    },
                },
                "responses": {
                    "200": {
                        "description": "Document status changed to in_review",
                        "content": {
                            "application/json": {
                                "example": {
                                    "success": True,
                                    "message": "Document submitted for review",
                                    "data": {"status": "in_review"},
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
        "/api/v1/documents/{document_id}/approve": {
            "post": {
                "tags": ["Documents"],
                "summary": "Approve a generated document",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "document_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {"example": {"comment": "Freigegeben fuer Ablage."}}
                    },
                },
                "responses": {
                    "200": {
                        "description": "Document status changed to approved",
                        "content": {
                            "application/json": {
                                "example": {
                                    "success": True,
                                    "message": "Document approved",
                                    "data": {"status": "approved"},
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
        "/api/v1/documents/{document_id}/reject": {
            "post": {
                "tags": ["Documents"],
                "summary": "Reject a generated document",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "document_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "requestBody": {
                    "required": False,
                    "content": {"application/json": {"example": {"comment": "Ursache fehlt."}}},
                },
                "responses": {
                    "200": {
                        "description": "Document status changed to rejected",
                        "content": {
                            "application/json": {
                                "example": {
                                    "success": True,
                                    "message": "Document rejected",
                                    "data": {"status": "rejected"},
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
        "/api/v1/documents/{document_id}/review": {
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
                        "description": ("Quality review with score, findings, and recommendations"),
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/DocumentReview"},
                                "example": {
                                    "quality_score": 80,
                                    "status": "needs_review",
                                    "findings": [
                                        {
                                            "field": "Ursache",
                                            "severity": "warning",
                                            "message": ("Ursache ist sehr knapp dokumentiert."),
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
        "/api/v1/documents/manuals": {
            "get": {
                "tags": ["Documents"],
                "summary": "List machine manuals",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "machine_id",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": "q",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "example": "Fehlercode",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Visible machine manuals",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/MachineManual"},
                                }
                            }
                        },
                    },
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            },
            "post": {
                "tags": ["Documents"],
                "summary": "Upload a machine manual",
                "security": [{"bearerAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "file": {
                                        "type": "string",
                                        "format": "binary",
                                    },
                                    "machine_id": {"type": "integer"},
                                    "department": {"type": "string"},
                                },
                                "required": ["file"],
                            }
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Manual stored with extracted text metadata",
                        "content": {
                            "application/json": {
                                "example": {
                                    "success": True,
                                    "message": "Manual uploaded",
                                    "data": {
                                        "id": 4,
                                        "title": "CNC-Fraese Handbuch",
                                        "analysis_status": "not_started",
                                    },
                                }
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/ValidationError"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                },
            },
        },
        "/api/v1/documents/manuals/{manual_id}/download": {
            "get": {
                "tags": ["Documents"],
                "summary": "Download a stored machine manual",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "manual_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Manual file download",
                        "content": {
                            "application/octet-stream": {
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
        "/api/v1/documents/manuals/{manual_id}/analyze": {
            "post": {
                "tags": ["Documents", "AI"],
                "summary": "Analyze a machine manual and store structured notes",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "manual_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Manual analysis result",
                        "content": {
                            "application/json": {
                                "example": {
                                    "success": True,
                                    "message": "Manual analyzed",
                                    "data": {
                                        "analysis_status": "completed",
                                        "analysis": {
                                            "wartungsintervalle": ["Lager monatlich pruefen"]
                                        },
                                    },
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
        "/api/v1/documents/manuals/{manual_id}/summarize": {
            "post": {
                "tags": ["Documents", "AI"],
                "summary": "Summarize a machine manual and store the summary",
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "manual_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Stored manual summary",
                        "content": {
                            "application/json": {
                                "example": {
                                    "success": True,
                                    "message": "Manual summarized",
                                    "data": {
                                        "summary_status": "completed",
                                        "summary": "Handbuch mit Wartung und Sicherheit.",
                                    },
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
        "/api/v1/documents/manuals/{manual_id}": {
            "delete": {
                "tags": ["Documents"],
                "summary": "Delete a machine manual",
                "description": (
                    "Allowed for master admins or the manual creator with "
                    "documents write permission."
                ),
                "security": [{"bearerAuth": []}],
                "parameters": [
                    {
                        "name": "manual_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "204": {"description": "Manual deleted"},
                    "401": {"$ref": "#/components/responses/Unauthorized"},
                    "403": {"$ref": "#/components/responses/Forbidden"},
                    "404": {"$ref": "#/components/responses/ValidationError"},
                },
            }
        },
        "/api/v1/inventory/forecast": {
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

    @app.get("/api/v1/swagger.json")
    @app.get("/api/swagger.json")  # backward compat redirect
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
