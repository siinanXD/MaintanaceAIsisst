"""Server-rendered web page routes."""

from flask import Blueprint, render_template

web_bp = Blueprint("web", __name__)

AI_ADMIN_VIEWS = {
    "overview": "/admin/ai",
    "models": "/admin/ai/models",
    "retrieval": "/admin/ai/retrieval",
    "knowledge": "/admin/ai/knowledge",
    "training": "/admin/ai/training",
    "diagnostics": "/admin/ai/diagnostics",
    "feedback": "/admin/ai/feedback",
    "indexing": "/admin/ai/indexing",
}


def render_ai_admin_page(view_name):
    """Render a specific AI admin subpage inside the shared shell."""
    return render_template(
        "admin_ai.html",
        admin_ai_view=view_name,
        ai_admin_views=AI_ADMIN_VIEWS,
    )


@web_bp.get("/")
def dashboard():
    """Render the dashboard page."""
    return render_template("dashboard.html")


@web_bp.get("/login")
def login_page():
    """Render the login page."""
    return render_template("login.html")


@web_bp.get("/api-docs")
def api_docs_page():
    """Render the API documentation page."""
    return render_template("api_docs.html")


@web_bp.get("/tasks")
def tasks_page():
    """Render the task management page."""
    return render_template("tasks.html")


@web_bp.get("/errors")
def errors_page():
    """Render the error catalog page."""
    return render_template("errors.html")


@web_bp.get("/admin/users")
def admin_users_page():
    """Render the admin user management page."""
    return render_template("admin_users.html")


@web_bp.get("/admin/ai")
def admin_ai_page():
    """Render the AI administration overview page."""
    return render_ai_admin_page("overview")


@web_bp.get("/admin/ai/models")
def admin_ai_models_page():
    """Render the AI model administration page."""
    return render_ai_admin_page("models")


@web_bp.get("/admin/ai/retrieval")
def admin_ai_retrieval_page():
    """Render the AI retrieval administration page."""
    return render_ai_admin_page("retrieval")


@web_bp.get("/admin/ai/knowledge")
def admin_ai_knowledge_page():
    """Render the AI knowledge source administration page."""
    return render_ai_admin_page("knowledge")


@web_bp.get("/admin/ai/training")
def admin_ai_training_page():
    """Render the AI training data administration page."""
    return render_ai_admin_page("training")


@web_bp.get("/admin/ai/diagnostics")
def admin_ai_diagnostics_page():
    """Render the AI diagnostics administration page."""
    return render_ai_admin_page("diagnostics")


@web_bp.get("/admin/ai/feedback")
def admin_ai_feedback_page():
    """Render the AI feedback administration page."""
    return render_ai_admin_page("feedback")


@web_bp.get("/admin/ai/indexing")
def admin_ai_indexing_page():
    """Render the AI indexing administration page."""
    return render_ai_admin_page("indexing")


@web_bp.get("/employees")
def employees_page():
    """Render the employee page."""
    return render_template("employees.html")


@web_bp.get("/shiftplans")
def shiftplans_page():
    """Render the shift planning page."""
    return render_template("shiftplans.html")


@web_bp.get("/machines")
def machines_page():
    """Render the machine page."""
    return render_template("machines.html")


@web_bp.get("/machines/<int:machine_id>")
def machine_detail_page(machine_id):
    """Render the machine-centered detail page."""
    return render_template("machine_detail.html", machine_id=machine_id)


@web_bp.get("/inventory")
def inventory_page():
    """Render the inventory page."""
    return render_template("inventory.html")


@web_bp.get("/documents")
def documents_page():
    """Render the generated documents overview."""
    return render_template("documents.html")


@web_bp.get("/handover")
def handover_page():
    """Render the shift handover page."""
    return render_template("handover.html")


@web_bp.get("/vacations")
def vacations_page():
    """Render the vacation planning page."""
    return render_template("vacations.html")
