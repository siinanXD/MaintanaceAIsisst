from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
jwt = JWTManager()
migrate = Migrate()


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    """Return True if the token's JTI is in the blocklist (i.e. logged out)."""
    from app.models import TokenBlocklist

    jti = jwt_payload.get("jti")
    return bool(jti and db.session.query(TokenBlocklist.id).filter_by(jti=jti).first())
