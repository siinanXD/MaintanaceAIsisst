"""OpenAPI path fragment for auth admin."""

PATHS_AUTH_ADMIN = {
    "/api/v1/auth/register": {
        "post": {
            "tags": ["Auth"],
            "summary": "Register a user",
            "description": "Creates a user and assigns default dashboard " "permissions.",
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
            "description": "Authenticates by username, email or login field " "and returns a JWT.",
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
                        "example": {"login": "master.admin", "password": "Demo1234!"},
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "JWT token and current user",
                    "content": {
                        "application/json": {
                            "example": {
                                "access_token": "<jwt-access-token>",
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
            "description": "Returns dashboard groups, labels, "
            "employee access labels and role "
            "defaults.",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Permission " "schema",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/PermissionSchema"},
                            "example": {
                                "dashboards": [{"key": "tasks", "label": "Tasks"}],
                                "groups": [
                                    {"key": "work", "label": "Arbeit", "dashboards": ["tasks"]}
                                ],
                                "employee_access_levels": [{"key": "basic", "label": "Basisdaten"}],
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
                {"name": "user_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {
                    "description": "Permissions " "by " "dashboard",
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
            "description": "Keeps admin user management " "locked to master admins.",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "user_id", "in": "path", "required": True, "schema": {"type": "integer"}}
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
                    "description": "Updated " "user",
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
                                "message": "Audit " "log " "loaded",
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
                                        "items": {"$ref": "#/components/schemas/BackupMetadata"},
                                    },
                                    "message": {"type": "string"},
                                },
                            },
                            "example": {
                                "success": True,
                                "data": [],
                                "message": "Backups " "loaded",
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
                                "message": "Backup " "created",
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
                {"name": "backup_id", "in": "path", "required": True, "schema": {"type": "string"}}
            ],
            "responses": {
                "200": {"description": "ZIP " "archive"},
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
            "description": "Requires confirm=true and "
            "creates a safety backup "
            "before replacing files.",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "backup_id", "in": "path", "required": True, "schema": {"type": "string"}}
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
                    "description": "Backup " "restored",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SuccessResponse"},
                            "example": {
                                "success": True,
                                "data": {
                                    "restored_backup": "maintenance_backup_20260512_120000.zip"
                                },
                                "message": "Backup " "restored",
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
            "description": "Returns email delivery records "
            "and redacted mail "
            "configuration status.",
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
                    "description": "Notification " "deliveries",
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
                                        "subject": "Dringender " "Task: " "CNC " "steht",
                                        "created_at": "2026-05-12T12:00:00+00:00",
                                    }
                                ],
                                "pagination": {"limit": 50, "offset": 0, "total": 1},
                                "mail": {"enabled": False, "dry_run": True},
                                "message": "Notification " "deliveries " "loaded",
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
            "description": "Creates a delivery record and "
            "sends via SMTP unless dry-run "
            "is enabled.",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": False,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "recipient_email": {"type": "string", "example": "ops@example.test"}
                            },
                        },
                        "example": {"recipient_email": "ops@example.test"},
                    }
                },
            },
            "responses": {
                "201": {
                    "description": "Test " "email " "delivery " "recorded",
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
                                "message": "Test " "email " "recorded",
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
    "/api/v1/notifications": {
        "get": {
            "tags": ["Notifications"],
            "summary": "List current user's in-app notifications",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "limit",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 50},
                }
            ],
            "responses": {
                "200": {
                    "description": "Recent notifications and " "unread count",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "data": {
                                    "unread_count": 2,
                                    "items": [
                                        {
                                            "id": 3,
                                            "title": "Schichtplan " "veroeffentlicht",
                                            "is_read": False,
                                        }
                                    ],
                                },
                            }
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        }
    },
    "/api/v1/notifications/{id}/read": {
        "patch": {
            "tags": ["Notifications"],
            "summary": "Mark one notification as read",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {"description": "Notification " "marked read"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/ValidationError"},
            },
        }
    },
    "/api/v1/notifications/read-all": {
        "patch": {
            "tags": ["Notifications"],
            "summary": "Mark all current user's notifications as " "read",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {
                    "description": "Unread " "notifications " "marked read",
                    "content": {
                        "application/json": {"example": {"success": True, "data": {"updated": 2}}}
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        }
    },
    "/health": {
        "get": {
            "tags": ["Health"],
            "summary": "Health probe",
            "description": "Returns 200 OK for load balancer and container probes. No "
            "authentication required.",
            "responses": {
                "200": {
                    "description": "Service is running",
                    "content": {"application/json": {"example": {"status": "ok"}}},
                }
            },
        }
    },
}
