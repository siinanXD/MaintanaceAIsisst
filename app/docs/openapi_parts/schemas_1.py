"""OpenAPI schema fragment 1."""

SCHEMAS_1 = {
    "ErrorResponse": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "example": False},
            "message": {"type": "string", "example": "Invalid credentials"},
            "error": {"type": "string", "example": "invalid_credentials"},
            "missing_information": {"$ref": "#/components/schemas/MissingInformation"},
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
            "employee_access_levels": {"type": "array", "items": {"type": "object"}},
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
}
