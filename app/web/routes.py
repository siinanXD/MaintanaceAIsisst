from flask import Blueprint, render_template


web_bp = Blueprint("web", __name__)


@web_bp.get("/")
def dashboard():
    return render_template("dashboard.html")


@web_bp.get("/login")
def login_page():
    return render_template("login.html")


@web_bp.get("/api-docs")
def api_docs_page():
    return render_template("api_docs.html")


@web_bp.get("/tasks")
def tasks_page():
    return render_template("tasks.html")


@web_bp.get("/errors")
def errors_page():
    return render_template("errors.html")


@web_bp.get("/admin/users")
def admin_users_page():
    return render_template("admin_users.html")


@web_bp.get("/employees")
def employees_page():
    return render_template("employees.html")


@web_bp.get("/shiftplans")
def shiftplans_page():
    return render_template("shiftplans.html")


@web_bp.get("/machines")
def machines_page():
    return render_template("machines.html")


@web_bp.get("/inventory")
def inventory_page():
    return render_template("inventory.html")


@web_bp.get("/documents")
def documents_page():
    """Render the generated documents overview."""
    return render_template("documents.html")
