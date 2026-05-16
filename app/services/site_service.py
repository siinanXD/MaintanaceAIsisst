"""Site service helpers for multi-plant operations."""

from app.extensions import db
from app.models import Site

DEFAULT_SITE_CODE = "werk-1"
DEFAULT_SITE_NAME = "Werk 1"
DEFAULT_SITE_TIMEZONE = "Europe/Berlin"


def ensure_default_site():
    """Create and return the default site used for existing installations."""
    site = Site.query.filter_by(code=DEFAULT_SITE_CODE).first()
    if site:
        return site
    site = Site(
        code=DEFAULT_SITE_CODE,
        name=DEFAULT_SITE_NAME,
        timezone=DEFAULT_SITE_TIMEZONE,
        is_active=True,
    )
    db.session.add(site)
    db.session.flush()
    return site


def list_sites(include_inactive=False):
    """Return sites ordered for API and UI selectors."""
    query = Site.query.order_by(Site.is_active.desc(), Site.name.asc(), Site.id.asc())
    if not include_inactive:
        query = query.filter(Site.is_active.is_(True))
    return query.all()


def create_site(data):
    """Create a site from API payload data."""
    try:
        code = str(data.get("code") or "").strip().lower()
        name = str(data.get("name") or "").strip()
        if not code:
            return None, {"error": "code is required"}, 400
        if not name:
            return None, {"error": "name is required"}, 400
        if Site.query.filter_by(code=code).first():
            return None, {"error": "site code already exists"}, 409
        site = Site(
            code=code,
            name=name,
            timezone=str(data.get("timezone") or DEFAULT_SITE_TIMEZONE).strip(),
            is_active=parse_bool(data.get("is_active"), default=True),
        )
    except ValueError as exc:
        return None, {"error": str(exc)}, 400
    db.session.add(site)
    db.session.commit()
    return site, None, 201


def update_site(site, data):
    """Apply a partial update to a site."""
    try:
        if "code" in data:
            code = str(data.get("code") or "").strip().lower()
            if not code:
                return None, {"error": "code must not be empty"}, 400
            existing = Site.query.filter(Site.code == code, Site.id != site.id).first()
            if existing:
                return None, {"error": "site code already exists"}, 409
            site.code = code
        if "name" in data:
            name = str(data.get("name") or "").strip()
            if not name:
                return None, {"error": "name must not be empty"}, 400
            site.name = name
        if "timezone" in data:
            site.timezone = str(data.get("timezone") or DEFAULT_SITE_TIMEZONE).strip()
        if "is_active" in data:
            site.is_active = parse_bool(data.get("is_active"), default=site.is_active)
    except ValueError as exc:
        return None, {"error": str(exc)}, 400
    db.session.commit()
    return site, None, 200


def parse_bool(value, default=True):
    """Parse a site boolean payload value."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError("is_active must be a boolean")
