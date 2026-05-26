"""OpenAPI schema fragment 2."""

SCHEMAS_2 = {
    "PaginatedAuditLog": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "example": True},
            "data": {"type": "array", "items": {"$ref": "#/components/schemas/AuditLogEntry"}},
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
            "filename": {"type": "string", "example": "maintenance_backup_20260512_120000.zip"},
            "size_bytes": {"type": "integer", "example": 20480},
            "created_at": {"type": "string", "format": "date-time"},
            "download_url": {
                "type": "string",
                "example": "/api/v1/admin/backups/maintenance_backup_20260512_120000.zip/download",
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
            "message": {"type": "string", "example": "Notification " "deliveries loaded"},
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
            "title": {"type": "string", "example": "CNC-Fraese Spindellager pruefen"},
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
            "started_at": {"type": "string", "format": "date-time", "nullable": True},
            "completed_at": {"type": "string", "format": "date-time", "nullable": True},
        },
    },
    "TaskCreateRequest": {
        "type": "object",
        "required": ["title"],
        "properties": {
            "title": {"type": "string", "example": "CNC-Fraese Spindellager pruefen"},
            "description": {
                "type": "string",
                "example": "Vibrationen dokumentieren und " "Lager pruefen.",
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
}
