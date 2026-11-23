"""Access-token lifecycle: issuing, revocation checks and auth error replies.

Two independent ways to end a token before it expires
-----------------------------------------------------
* Per user ("log out of all devices", password change): every token carries a
  "ver" claim copied from User.token_version. Incrementing the column makes
  every older token fail the check below. One integer per user, no list of
  tokens to maintain.
* Per token ("log out" on one device): the token's unique id (jti) is stored
  in revoked_token until the token's own expiry time.

Both are checked by ONE query per authenticated request (see
_token_is_revoked). A token whose user no longer exists is also rejected, so
a deleted account's token gets a 401 instead of reaching the views.

Tokens issued before this module existed have no "ver" claim; they are
treated as version 0, which is the default for every existing user, so
deploying this does not log anyone out.
"""

from datetime import datetime, timezone

from flask import jsonify
from flask_jwt_extended import create_access_token
from sqlalchemy import delete, exists, select
from sqlalchemy.dialects.postgresql import insert

from .. import db
from ..models import RevokedToken, User


TOKEN_VERSION_CLAIM = "ver"

SESSION_ENDED_MESSAGE = "Your session has ended. Please log in again."
SESSION_EXPIRED_MESSAGE = "Your session has expired. Please log in again."
SESSION_INVALID_MESSAGE = "Your session is invalid. Please log in again."
AUTH_REQUIRED_MESSAGE = "Please log in to continue."


def create_user_token(user):
    return create_access_token(
        identity=str(user.id),
        additional_claims={TOKEN_VERSION_CLAIM: user.token_version},
    )


def _token_is_revoked(jwt_payload):
    try:
        user_id = int(jwt_payload["sub"])
    except (KeyError, TypeError, ValueError):
        return True

    # SELECT user.token_version, EXISTS(SELECT 1 FROM revoked_token WHERE jti=:jti)
    # FROM "user" WHERE id = :id   -- one primary-key lookup per request
    row = db.session.execute(
        select(
            User.token_version,
            exists().where(RevokedToken.jti == jwt_payload.get("jti")),
        ).where(User.id == user_id)
    ).first()

    if row is None:
        return True  # account deleted

    token_version, jti_revoked = row
    return bool(jti_revoked) or jwt_payload.get(TOKEN_VERSION_CLAIM, 0) != token_version


def revoke_token(jwt_payload):
    """Store this token's jti until it expires; prune entries already expired."""
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromtimestamp(jwt_payload["exp"], tz=timezone.utc)

    db.session.execute(delete(RevokedToken).where(RevokedToken.expires_at < now))
    db.session.execute(
        insert(RevokedToken)
        .values(jti=jwt_payload["jti"], expires_at=expires_at)
        .on_conflict_do_nothing(index_elements=["jti"])
    )


def _auth_error(message):
    # Every token problem is a 401 (Flask-JWT-Extended answers a bad signature
    # or malformed token with 422 by default). The frontend logs the user out
    # on 401 only, so a 422 would leave it stuck with a dead token, e.g. after
    # JWT_SECRET_KEY is rotated. "error" is the key the frontend displays.
    return jsonify({"error": message}), 401


def register_jwt_callbacks(jwt):
    @jwt.token_in_blocklist_loader
    def token_in_blocklist(jwt_header, jwt_payload):
        return _token_is_revoked(jwt_payload)

    @jwt.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        return _auth_error(SESSION_ENDED_MESSAGE)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return _auth_error(SESSION_EXPIRED_MESSAGE)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return _auth_error(SESSION_INVALID_MESSAGE)

    @jwt.unauthorized_loader
    def missing_token(reason):
        return _auth_error(AUTH_REQUIRED_MESSAGE)
