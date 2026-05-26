"""OpenAPI path fragment for documents inventory."""

PATHS_DOCUMENTS_INVENTORY = {
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
                    "description": "Visible generated documents, " "newest first",
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
                    "description": "HTML " "maintenance " "report " "as " "file " "download",
                    "content": {"text/html": {"schema": {"type": "string", "format": "binary"}}},
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
            "summary": "Download a generated " "document as server-rendered " "PDF",
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
                    "description": "PDF " "maintenance " "report " "as " "file " "download",
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
            "summary": "List immutable versions for a " "generated document",
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
                    "description": "Document " "versions",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "message": "Document " "versions " "loaded",
                                "data": [
                                    {
                                        "id": 12,
                                        "document_id": 8,
                                        "version_number": 1,
                                        "original_filename": "maintenance_report.html",
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
                                        "items": {"$ref": "#/components/schemas/DocumentVersion"},
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
            "summary": "Create or update a stored " "document summary",
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
                    "description": "Stored " "summary " "with " "diagnostics",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "message": "Document " "summarized",
                                "data": {
                                    "summary": "Wartung " "abgeschlossen.",
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
            "summary": "Submit a generated " "document for approval",
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
                    "application/json": {"example": {"comment": "Bitte " "fachlich " "pruefen."}}
                },
            },
            "responses": {
                "200": {
                    "description": "Document " "status " "changed " "to " "in_review",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "message": "Document " "submitted " "for " "review",
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
                    "application/json": {"example": {"comment": "Freigegeben " "fuer " "Ablage."}}
                },
            },
            "responses": {
                "200": {
                    "description": "Document " "status " "changed " "to " "approved",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "message": "Document " "approved",
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
                "content": {"application/json": {"example": {"comment": "Ursache " "fehlt."}}},
            },
            "responses": {
                "200": {
                    "description": "Document " "status " "changed " "to " "rejected",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "message": "Document " "rejected",
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
            "description": "Returns a non-persisted AI or "
            "local quality review for a "
            "generated maintenance report.",
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
                    "description": "Quality "
                    "review "
                    "with "
                    "score, "
                    "findings, "
                    "and "
                    "recommendations",
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
                                        "message": "Ursache "
                                        "ist "
                                        "sehr "
                                        "knapp "
                                        "dokumentiert.",
                                    }
                                ],
                                "recommendations": [
                                    "Ursache "
                                    "oder "
                                    "wahrscheinliche "
                                    "Fehlerquelle "
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
                    "description": "Visible machine " "manuals",
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
            "summary": "Upload and auto-index a machine manual",
            "description": "Stores the file, extracts text when "
            "possible, creates a summary and indexes "
            "searchable RAG chunks.",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string", "format": "binary"},
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
                    "description": "Manual stored with " "extracted text " "metadata",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "message": "Manual " "uploaded",
                                "data": {
                                    "id": 4,
                                    "title": "CNC-Fraese " "Handbuch",
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
            "summary": "Download a stored machine " "manual",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "manual_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {
                    "description": "Manual " "file " "download",
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
            "summary": "Analyze a machine manual " "and store structured notes",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "manual_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {
                    "description": "Manual " "analysis " "result",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "message": "Manual " "analyzed",
                                "data": {
                                    "analysis_status": "completed",
                                    "analysis": {
                                        "wartungsintervalle": ["Lager " "monatlich " "pruefen"]
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
            "summary": "Summarize a machine " "manual and store the " "summary",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "manual_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {
                    "description": "Stored " "manual " "summary",
                    "content": {
                        "application/json": {
                            "example": {
                                "success": True,
                                "message": "Manual " "summarized",
                                "data": {
                                    "summary_status": "completed",
                                    "summary": "Handbuch " "mit " "Wartung " "und " "Sicherheit.",
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
            "description": "Allowed for master admins or "
            "the manual creator with "
            "documents write permission.",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "manual_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "204": {"description": "Manual " "deleted"},
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
                        "example": {"status": "open", "limit": 20, "low_stock_threshold": 5}
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Inventory risk " "forecast",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/InventoryForecast"},
                            "example": {
                                "items": [
                                    {
                                        "machine": {"id": 1, "name": "CNC-Fraese " "01"},
                                        "material": {
                                            "id": 5,
                                            "name": "Hartmetall-Fraeser " "8 " "mm",
                                        },
                                        "quantity": 2,
                                        "risk_level": "high",
                                        "match_reason": "Treffer "
                                        "ueber "
                                        "Teilnamen: "
                                        "cnc, "
                                        "fraese",
                                    }
                                ],
                                "unmatched_tasks": [],
                                "summary": {"critical": 0, "high": 1, "medium": 0, "total": 1},
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
}
