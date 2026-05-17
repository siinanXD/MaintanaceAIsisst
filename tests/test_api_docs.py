"""Tests for OpenAPI documentation and demo setup entry points."""


def test_openapi_json_documents_core_endpoints(client):
    """Verify the OpenAPI JSON exposes the documented production endpoints."""
    response = client.get("/api/swagger.json")

    assert response.status_code == 200
    spec = response.get_json()
    paths = spec["paths"]

    assert spec["openapi"].startswith("3.")
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/register" in paths
    assert "/api/v1/tasks" in paths
    assert "/api/v1/tasks/{task_id}/start" in paths
    assert "/api/v1/tasks/{task_id}/complete" in paths
    assert "/api/v1/errors/search" in paths
    assert "/api/v1/errors/similar" in paths
    assert "/api/v1/ai/daily-briefing" in paths
    assert "/api/v1/ai/order-plan" in paths
    assert "/api/v1/ai/feedback" in paths
    assert "/api/v1/ai/chat/history" in paths
    assert "/api/v1/sites" in paths
    assert "/api/v1/operations/summary" in paths
    assert "/api/v1/operations/events" in paths
    assert "/api/v1/operations/tasks" in paths
    assert "/api/v1/operations/machines" in paths
    assert "/api/v1/operations/inventory" in paths
    assert "/api/v1/operations/workforce" in paths
    assert "/api/v1/operations/ai-quality" in paths
    assert "/api/v1/admin/sites" in paths
    assert "/api/v1/admin/sites/{site_id}" in paths
    assert "/api/v1/admin/operations/aggregate" in paths
    assert "/api/v1/admin/ai/chats" in paths
    assert "/api/v1/admin/ai/events" in paths
    assert "/api/v1/admin/jobs" in paths
    assert "/api/v1/admin/ai/knowledge/upload" in paths
    assert "/api/v1/admin/ai/knowledge" in paths
    assert "/api/v1/admin/ai/knowledge/status" in paths
    assert "/api/v1/admin/ai/retrieval-telemetry" in paths
    assert "/api/v1/admin/ai/knowledge-gaps" in paths
    assert "/api/v1/admin/ai/knowledge/reindex/jobs" in paths
    assert "/api/v1/admin/ai/knowledge/reindex" in paths
    assert "/api/v1/admin/ai/knowledge/{id}/reindex" in paths
    assert "/api/v1/admin/ai/knowledge/{id}/quality-status" in paths
    assert "/api/v1/admin/ai/knowledge/{id}" in paths
    assert "/api/v1/machines/{machine_id}/assistant" in paths
    assert "/api/v1/inventory/forecast" in paths
    assert "/api/v1/admin/permissions/schema" in paths
    assert "/api/v1/admin/users/{user_id}/permissions" in paths
    assert "/api/v1/admin/audit-log" in paths
    assert "/api/v1/admin/backups" in paths
    assert "/api/v1/admin/backups/{backup_id}/download" in paths
    assert "/api/v1/admin/backups/{backup_id}/restore" in paths
    assert "/api/v1/admin/notifications/deliveries" in paths
    assert "/api/v1/admin/notifications/test-email" in paths
    assert "/api/v1/employees/qualifications" in paths
    assert "/api/v1/employees/{employee_id}/qualifications" in paths
    assert "/api/v1/shiftplans/{plan_id}/conflicts" in paths
    assert "/api/v1/shiftplans/validate" in paths
    assert "/api/v1/shiftplans/{plan_id}/export.xlsx" in paths
    assert "/api/v1/notifications" in paths
    assert "/api/v1/notifications/{id}/read" in paths
    assert "/api/v1/notifications/read-all" in paths
    assert "/api/v1/documents/{document_id}/download.pdf" in paths
    assert "/api/v1/documents/{document_id}/summarize" in paths
    assert "/api/v1/documents/{document_id}/submit-review" in paths
    assert "/api/v1/documents/{document_id}/approve" in paths
    assert "/api/v1/documents/{document_id}/reject" in paths
    assert "/api/v1/documents/{document_id}/versions" in paths
    assert "/api/v1/documents/manuals" in paths
    assert "/api/v1/documents/manuals/{manual_id}/download" in paths
    assert "/api/v1/documents/manuals/{manual_id}/analyze" in paths
    assert "/api/v1/documents/manuals/{manual_id}/summarize" in paths
    assert "/api/v1/documents/manuals/{manual_id}" in paths


def test_openapi_examples_are_present(client):
    """Verify important endpoints include concise example payloads."""
    spec = client.get("/api/swagger.json").get_json()

    task_example = spec["paths"]["/api/v1/tasks"]["post"]["requestBody"]["content"][
        "application/json"
    ]["example"]
    briefing_example = spec["paths"]["/api/v1/ai/daily-briefing"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["example"]

    assert task_example["title"]
    assert task_example["priority"] == "urgent"
    assert briefing_example["sections"]
    assert spec["components"]["schemas"]["ErrorResponse"]["properties"]["message"]["example"]
    assert spec["components"]["schemas"]["PaginatedAuditLog"]["properties"]["pagination"]
    assert spec["components"]["schemas"]["BackupMetadata"]["properties"]["download_url"]["example"]
    assert spec["components"]["schemas"]["NotificationDelivery"]["properties"]["status"]["example"]
    assert spec["components"]["schemas"]["MailStatus"]["properties"]["dry_run"]["example"] is True
    assert spec["components"]["schemas"]["GeneratedDocument"]["properties"]["pdf_url"]["example"]
    assert spec["components"]["schemas"]["EmployeeMachineQualification"]["properties"]["level"][
        "example"
    ]
    assert spec["components"]["schemas"]["ShiftPlanConflict"]["properties"]["type"]["example"]
    assert spec["components"]["schemas"]["Notification"]["properties"]["title"]["example"]
    assert spec["components"]["schemas"]["DocumentVersion"]["properties"]["version_number"][
        "example"
    ]
    assert spec["components"]["schemas"]["MachineManual"]["properties"]["download_url"]["example"]
    assert spec["components"]["schemas"]["ChatHistoryEntry"]["properties"]["response_type"][
        "example"
    ]
    assert spec["components"]["schemas"]["ChatHistoryEntry"]["properties"]["session_id"][
        "example"
    ]
    assert spec["components"]["schemas"]["AIAuditEvent"]["properties"]["error_category"]["example"]
    assert spec["components"]["schemas"]["KnowledgeDocument"]["properties"]["status"]["example"]
    assert spec["components"]["schemas"]["KnowledgeDocument"]["properties"]["quality_status"][
        "example"
    ]
    assert spec["components"]["schemas"]["KnowledgeGap"]["properties"]["status"]["example"]
    assert spec["components"]["schemas"]["MissingInformation"]["properties"]["questions"]
    assert spec["components"]["schemas"]["Site"]["properties"]["code"]["example"]
    assert spec["components"]["schemas"]["OperationalEvent"]["properties"]["actor_hash"]["example"]
    assert spec["components"]["schemas"]["OperationsSummary"]["properties"]["tasks"]


def test_swagger_ui_route_loads(client):
    """Verify the Swagger UI or local fallback page is reachable."""
    response = client.get("/swagger/", follow_redirects=True)

    assert response.status_code == 200
    assert b"Swagger" in response.data


def test_api_docs_page_links_to_swagger(client):
    """Verify the developer docs page points to Swagger and OpenAPI JSON."""
    response = client.get("/api-docs")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "/swagger/" in body
    assert "/api/swagger.json" in body
