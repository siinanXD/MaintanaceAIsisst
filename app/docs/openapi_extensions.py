"""Additional OpenAPI schema and path definitions."""

ADDITIONAL_SCHEMAS = {
    "ChatHistoryEntry": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 12},
            "user_id": {"type": "integer", "example": 3},
            "message": {"type": "string", "example": "Was ist ein User?"},
            "response": {"type": "string", "example": "Ein User ist ein Benutzerkonto."},
            "response_type": {"type": "string", "example": "general_chat"},
            "session_id": {"type": "string", "example": "chat-widget"},
            "source_count": {"type": "integer", "example": 1},
            "confidence_score": {"type": "integer", "example": 72},
            "confidence_level": {"type": "string", "example": "high"},
            "audit_event_id": {"type": "integer", "example": 44},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "AIAuditEvent": {
        "type": "object",
        "properties": {
            "workflow": {"type": "string", "example": "general_chat"},
            "status": {"type": "string", "example": "openai_error"},
            "error_category": {"type": "string", "example": "rate_limit"},
            "confidence_score": {"type": "integer", "example": 72},
            "confidence_level": {"type": "string", "example": "high"},
            "retrieval_explainability": {"type": "object"},
            "total_tokens": {"type": "integer", "example": 842},
            "estimated_cost_usd": {"type": "number", "example": 0.0012},
        },
    },
    "KnowledgeDocument": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 5},
            "source_type": {"type": "string", "example": "upload"},
            "title": {"type": "string", "example": "CNC Manual"},
            "status": {"type": "string", "example": "indexed"},
            "quality_status": {"type": "string", "example": "draft"},
            "last_confirmed_at": {
                "type": "string",
                "format": "date-time",
                "nullable": True,
            },
            "confirmation_count": {"type": "integer", "example": 2},
            "aging_checked_at": {
                "type": "string",
                "format": "date-time",
                "nullable": True,
            },
            "chunk_count": {"type": "integer", "example": 18},
            "department": {"type": "string", "example": "Produktion"},
        },
    },
    "MissingInformation": {
        "type": "object",
        "properties": {
            "entry_type": {"type": "string", "example": "error_entry"},
            "status": {"type": "string", "example": "needs_information"},
            "missing_fields": {
                "type": "array",
                "items": {"type": "string"},
                "example": ["machine", "error_code", "previous_checks"],
            },
            "detected_fields": {
                "type": "array",
                "items": {"type": "string"},
                "example": ["symptoms", "affected_area"],
            },
            "completion_ratio": {"type": "number", "example": 0.5},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string", "example": "machine"},
                        "label": {"type": "string", "example": "Maschine oder Anlage"},
                        "question": {
                            "type": "string",
                            "example": "Welche Maschine, Anlage oder Linie ist betroffen?",
                        },
                        "required": {"type": "boolean", "example": True},
                    },
                },
            },
            "summary": {
                "type": "string",
                "example": "Es fehlen gezielte Angaben zu: Maschine oder Anlage.",
            },
        },
    },
    "KnowledgeGap": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 3},
            "question": {"type": "string", "example": "Wie behebe ich Fehler X999?"},
            "context": {"type": "string", "example": "Quellen: 0"},
            "machine": {"type": "string", "example": "Anlage 4"},
            "department": {"type": "string", "example": "Instandhaltung"},
            "status": {"type": "string", "example": "open"},
            "occurrence_count": {"type": "integer", "example": 2},
            "last_seen_at": {"type": "string", "format": "date-time"},
        },
    },
    "KnowledgeNetwork": {
        "type": "object",
        "properties": {
            "nodes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "example": "machine:1"},
                        "type": {"type": "string", "example": "machine"},
                        "label": {"type": "string", "example": "Anlage 4"},
                        "title": {"type": "string", "example": "Anlage 4"},
                        "url": {"type": "string", "example": "/machines"},
                        "weight": {"type": "number", "example": 12.5},
                        "evidence_count": {"type": "integer", "example": 3},
                        "metadata": {"type": "object"},
                        "explainability": {"type": "object"},
                    },
                },
            },
            "edges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "example": "document-1-machine-1"},
                        "source": {"type": "string", "example": "document:1"},
                        "target": {"type": "string", "example": "machine:1"},
                        "type": {"type": "string", "example": "source_relation"},
                        "label": {"type": "string", "example": "direct source"},
                        "weight": {"type": "number", "example": 9.0},
                        "evidence_count": {"type": "integer", "example": 1},
                        "explainability": {"type": "object"},
                    },
                },
            },
            "stats": {"type": "object"},
            "filters": {"type": "object"},
            "explainability": {"type": "object"},
            "privacy": {
                "type": "object",
                "example": {"mode": "metadata_only", "omitted": ["chunk_text"]},
            },
        },
    },
    "RetrievalDebug": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "chat_message_id": {"type": "integer", "example": 12},
                        "audit_event_id": {"type": "integer", "example": 44},
                        "user_question": {"type": "string", "example": "Warum F-900?"},
                        "query_type": {"type": "string", "example": "error_analysis"},
                        "used_sources": {"type": "array", "items": {"type": "object"}},
                        "confidence": {"type": "object"},
                        "conflicts": {"type": "object"},
                        "safety": {"type": "object"},
                        "retrieval_duration_ms": {"type": "integer", "example": 42},
                    },
                },
            },
            "privacy": {"type": "object"},
        },
    },
    "IncidentTimeline": {
        "type": "object",
        "properties": {
            "items": {"type": "array", "items": {"type": "object"}},
            "sequences": {"type": "array", "items": {"type": "object"}},
            "stats": {"type": "object"},
            "filters": {"type": "object"},
            "explainability": {"type": "object"},
        },
    },
    "ChatTemplate": {
        "type": "object",
        "properties": {
            "label": {"type": "string", "example": "Fehler analysieren"},
            "prompt": {"type": "string", "example": "Welche Ursache hat Fehler F-100?"},
            "category": {"type": "string", "example": "Stoerung"},
            "sort_order": {"type": "integer", "example": 10},
        },
    },
    "Site": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 1},
            "code": {"type": "string", "example": "werk-1"},
            "name": {"type": "string", "example": "Werk 1"},
            "timezone": {"type": "string", "example": "Europe/Berlin"},
            "is_active": {"type": "boolean", "example": True},
        },
    },
    "OperationalEvent": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 42},
            "event_type": {"type": "string", "example": "task.completed"},
            "feature": {"type": "string", "example": "tasks"},
            "entity_type": {"type": "string", "example": "task"},
            "entity_id": {"type": "integer", "example": 12},
            "site_id": {"type": "integer", "example": 1},
            "department_id": {"type": "integer", "example": 3},
            "machine_id": {"type": "integer", "nullable": True},
            "task_id": {"type": "integer", "nullable": True},
            "actor_hash": {"type": "string", "example": "pseudonymous-hmac"},
            "actor_role": {"type": "string", "example": "instandhaltung"},
            "source": {"type": "string", "example": "app"},
            "old_value": {"type": "object", "nullable": True},
            "new_value": {"type": "object", "nullable": True},
            "description": {
                "type": "string",
                "example": "Task wurde abgeschlossen.",
            },
            "metadata": {"type": "object"},
            "occurred_at": {"type": "string", "format": "date-time"},
            "created_at": {"type": "string", "format": "date-time"},
        },
    },
    "OperationsSummary": {
        "type": "object",
        "properties": {
            "filters": {"type": "object"},
            "tasks": {"type": "object"},
            "machines": {"type": "object"},
            "inventory": {"type": "object"},
            "workforce": {"type": "object"},
            "documents": {"type": "object"},
            "ai_quality": {"type": "object"},
            "events": {"type": "object"},
        },
    },
    "AssistantTrainingEntry": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 7},
            "title": {"type": "string", "example": "Hydraulik X900"},
            "question": {"type": "string", "example": "Was tun bei X900?"},
            "answer": {"type": "string", "example": "Druck pruefen und Ventil reinigen."},
            "keywords": {"type": "string", "example": "X900, Hydraulik"},
            "category": {"type": "string", "example": "Stoerung"},
            "department": {"type": "string", "example": "Instandhaltung"},
            "is_active": {"type": "boolean", "example": True},
            "priority": {"type": "integer", "example": 50},
            "missing_information": {
                "$ref": "#/components/schemas/MissingInformation",
            },
        },
    },
}


ADDITIONAL_PATHS = {
    "/api/v1/ai/chat/history": {
        "get": {
            "tags": ["AI"],
            "summary": "Search own AI chat history",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Chat history loaded"}},
        }
    },
    "/api/v1/ai/chat/templates": {
        "get": {
            "tags": ["AI"],
            "summary": "Load permission-aware chat templates",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Chat templates loaded"}},
        }
    },
    "/api/v1/ai/feedback": {
        "post": {
            "tags": ["AI"],
            "summary": "Store feedback for an AI answer",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "example": {
                            "chat_message_id": 42,
                            "rating": "partially_helpful",
                            "comment": "Quelle passt, Antwort war zu knapp.",
                            "sources": [
                                {
                                    "type": "knowledge",
                                    "id": 7,
                                    "chunk_id": 13,
                                    "title": "CNC Manual",
                                }
                            ],
                        }
                    }
                },
            },
            "responses": {
                "201": {"description": "Feedback saved"},
                "400": {"$ref": "#/components/responses/ValidationError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
            },
        }
    },
    "/api/v1/ai/order-plan": {
        "post": {
            "tags": ["AI"],
            "summary": "Plan a production order with machine, material and staffing checks",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "example": {
                            "product": "Deckel",
                            "quantity": 100,
                            "department": "Produktion",
                            "work_date": "2026-05-18",
                        }
                    }
                },
            },
            "responses": {
                "200": {"description": "Order plan generated"},
                "400": {"$ref": "#/components/responses/ValidationError"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        }
    },
    "/api/v1/sites": {
        "get": {
            "tags": ["Sites"],
            "summary": "List active plants/sites for selectors",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Sites loaded"}},
        }
    },
    "/api/v1/operations/summary": {
        "get": {
            "tags": ["Operations"],
            "summary": "Load cross-feature operations KPIs",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "from", "in": "query", "schema": {"type": "string", "format": "date"}},
                {"name": "to", "in": "query", "schema": {"type": "string", "format": "date"}},
                {"name": "site_id", "in": "query", "schema": {"type": "integer"}},
                {"name": "department_id", "in": "query", "schema": {"type": "integer"}},
                {"name": "machine_id", "in": "query", "schema": {"type": "integer"}},
            ],
            "responses": {"200": {"description": "Operations summary loaded"}},
        }
    },
    "/api/v1/operations/events": {
        "get": {
            "tags": ["Operations"],
            "summary": "List pseudonymized operational events",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Operations events loaded"}},
        }
    },
    "/api/v1/operations/tasks": {
        "get": {
            "tags": ["Operations"],
            "summary": "Load task lifecycle KPI drilldown",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Task operations loaded"}},
        }
    },
    "/api/v1/operations/machines": {
        "get": {
            "tags": ["Operations"],
            "summary": "Load machine downtime and fault KPIs",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Machine operations loaded"}},
        }
    },
    "/api/v1/operations/inventory": {
        "get": {
            "tags": ["Operations"],
            "summary": "Load inventory risk KPIs",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Inventory operations loaded"}},
        }
    },
    "/api/v1/operations/workforce": {
        "get": {
            "tags": ["Operations"],
            "summary": "Load shift coverage and conflict KPIs",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Workforce operations loaded"}},
        }
    },
    "/api/v1/operations/ai-quality": {
        "get": {
            "tags": ["Operations"],
            "summary": "Load AI latency, cost and feedback KPIs",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "AI quality operations loaded"}},
        }
    },
    "/api/v1/admin/sites": {
        "get": {
            "tags": ["Sites", "Admin"],
            "summary": "List all sites as master admin",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Sites loaded"}},
        },
        "post": {
            "tags": ["Sites", "Admin"],
            "summary": "Create a site",
            "security": [{"bearerAuth": []}],
            "responses": {
                "201": {"description": "Site created"},
                "400": {"$ref": "#/components/responses/ValidationError"},
                "409": {"$ref": "#/components/responses/ValidationError"},
            },
        },
    },
    "/api/v1/admin/sites/{site_id}": {
        "put": {
            "tags": ["Sites", "Admin"],
            "summary": "Update a site",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {"description": "Site updated"},
                "400": {"$ref": "#/components/responses/ValidationError"},
                "404": {"description": "Site not found"},
            },
        }
    },
    "/api/v1/admin/operations/aggregate": {
        "post": {
            "tags": ["Operations", "Admin"],
            "summary": "Rebuild persisted operations aggregates",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Operations aggregates rebuilt"}},
        }
    },
    "/api/v1/admin/ai/chats": {
        "get": {
            "tags": ["Admin"],
            "summary": "Search all AI chats as master admin",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "AI chats loaded"}},
        }
    },
    "/api/v1/admin/ai/events": {
        "get": {
            "tags": ["Admin"],
            "summary": "Search metadata-only AI audit events",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "AI events loaded"}},
        }
    },
    "/api/v1/admin/ai/training": {
        "get": {
            "tags": ["Admin"],
            "summary": "List manual assistant training entries",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Training entries loaded"}},
        },
        "post": {
            "tags": ["Admin"],
            "summary": "Create a manual assistant training entry",
            "security": [{"bearerAuth": []}],
            "responses": {
                "201": {"description": "Training entry created"},
                "400": {"$ref": "#/components/responses/ValidationError"},
            },
        },
    },
    "/api/v1/admin/ai/training/{entry_id}": {
        "put": {
            "tags": ["Admin"],
            "summary": "Update a manual assistant training entry",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {"description": "Training entry updated"},
                "400": {"$ref": "#/components/responses/ValidationError"},
                "404": {"description": "Training entry not found"},
            },
        },
        "delete": {
            "tags": ["Admin"],
            "summary": "Delete a manual assistant training entry",
            "security": [{"bearerAuth": []}],
            "responses": {
                "200": {"description": "Training entry deleted"},
                "404": {"description": "Training entry not found"},
            },
        },
    },
    "/api/v1/admin/ai/knowledge/upload": {
        "post": {
            "tags": ["Admin"],
            "summary": "Upload, chunk and index a knowledge document",
            "security": [{"bearerAuth": []}],
            "responses": {"201": {"description": "Knowledge document uploaded"}},
        }
    },
    "/api/v1/admin/ai/knowledge": {
        "get": {
            "tags": ["Admin"],
            "summary": "List knowledge documents",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Knowledge documents loaded"}},
        }
    },
    "/api/v1/admin/ai/knowledge/status": {
        "get": {
            "tags": ["Admin"],
            "summary": "Inspect RAG index status and source diagnostics",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Knowledge status loaded"}},
        }
    },
    "/api/v1/admin/ai/knowledge-network": {
        "get": {
            "tags": ["Admin"],
            "summary": "Inspect the read-only maintenance knowledge network",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "q", "in": "query", "schema": {"type": "string"}},
                {
                    "name": "source_type",
                    "in": "query",
                    "schema": {"type": "string"},
                },
                {
                    "name": "quality_status",
                    "in": "query",
                    "schema": {"type": "string"},
                },
                {
                    "name": "days",
                    "in": "query",
                    "schema": {"type": "integer", "default": 30},
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {"type": "integer", "default": 120},
                },
                {"name": "focus", "in": "query", "schema": {"type": "string"}},
            ],
            "responses": {
                "200": {
                    "description": "Knowledge network loaded",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/KnowledgeNetwork"}
                        }
                    },
                }
            },
        }
    },
    "/api/v1/admin/ai/retrieval-telemetry": {
        "get": {
            "tags": ["Admin"],
            "summary": "Inspect retrieval telemetry and quality analytics",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "days",
                    "in": "query",
                    "schema": {"type": "integer", "default": 30},
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {"type": "integer", "default": 10},
                },
            ],
            "responses": {"200": {"description": "Retrieval telemetry loaded"}},
        }
    },
    "/api/v1/admin/ai/retrieval-debug": {
        "get": {
            "tags": ["Admin"],
            "summary": "Inspect prompt-safe retrieval debug records",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {"name": "q", "in": "query", "schema": {"type": "string"}},
                {
                    "name": "query_type",
                    "in": "query",
                    "schema": {"type": "string"},
                },
                {
                    "name": "days",
                    "in": "query",
                    "schema": {"type": "integer", "default": 30},
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {"type": "integer", "default": 30},
                },
            ],
            "responses": {
                "200": {
                    "description": "Retrieval debug loaded",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/RetrievalDebug"}
                        }
                    },
                }
            },
        }
    },
    "/api/v1/admin/ai/observability": {
        "get": {
            "tags": ["Admin"],
            "summary": "Inspect AI monitoring, logs, quality metrics and debug blueprints",
            "security": [{"bearerAuth": []}],
            "parameters": [
                {
                    "name": "days",
                    "in": "query",
                    "schema": {"type": "integer", "default": 30},
                },
                {
                    "name": "limit",
                    "in": "query",
                    "schema": {"type": "integer", "default": 10},
                },
                {
                    "name": "chat_message_id",
                    "in": "query",
                    "schema": {"type": "integer"},
                },
            ],
            "responses": {"200": {"description": "AI observability loaded"}},
        }
    },
    "/api/v1/admin/ai/knowledge-gaps": {
        "get": {
            "tags": ["Admin"],
            "summary": "List AI knowledge gaps from unanswered questions",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Knowledge gaps loaded"}},
        }
    },
    "/api/v1/admin/jobs": {
        "get": {
            "tags": ["Admin"],
            "summary": "List background jobs",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Background jobs loaded"}},
        }
    },
    "/api/v1/health/operations": {
        "get": {
            "tags": ["Health", "Admin"],
            "summary": "Inspect operations metrics for administrators",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Operations metrics loaded"}},
        }
    },
    "/api/v1/admin/ai/knowledge/reindex/jobs": {
        "post": {
            "tags": ["Admin"],
            "summary": "Queue a RAG reindex background job",
            "security": [{"bearerAuth": []}],
            "responses": {"202": {"description": "Background job queued"}},
        }
    },
    "/api/v1/admin/ai/knowledge/aging/jobs": {
        "post": {
            "tags": ["Admin"],
            "summary": "Queue a knowledge aging review background job",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": False,
                "content": {"application/json": {"example": {"dry_run": True, "limit": 100}}},
            },
            "responses": {"202": {"description": "Background job queued"}},
        }
    },
    "/api/v1/admin/ai/knowledge/reindex": {
        "post": {
            "tags": ["Admin"],
            "summary": "Rebuild local knowledge chunks, optionally stale only",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Knowledge reindexed"}},
        }
    },
    "/api/v1/admin/ai/knowledge/{id}/reindex": {
        "post": {
            "tags": ["Admin"],
            "summary": "Reindex one knowledge document",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Knowledge document reindexed"}},
        }
    },
    "/api/v1/admin/ai/knowledge/{id}/quality-status": {
        "put": {
            "tags": ["Admin"],
            "summary": "Update the quality workflow status for one knowledge document",
            "security": [{"bearerAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {"example": {"quality_status": "technician_confirmed"}}
                },
            },
            "responses": {
                "200": {"description": "Knowledge quality status updated"},
                "400": {"$ref": "#/components/responses/ValidationError"},
                "403": {"$ref": "#/components/responses/Forbidden"},
            },
        }
    },
    "/api/v1/admin/ai/knowledge/{id}": {
        "delete": {
            "tags": ["Admin"],
            "summary": "Delete a knowledge document",
            "security": [{"bearerAuth": []}],
            "responses": {"200": {"description": "Knowledge document deleted"}},
        }
    },
}
