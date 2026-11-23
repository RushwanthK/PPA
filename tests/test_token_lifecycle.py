"""Security regression tests for the access-token lifecycle.

Covers revocation (single-device logout, log out of all devices, password
change, deleted account), the "ver" claim, and the uniform 401 replies the
frontend relies on to log the user out.
"""

from datetime import datetime, timedelta, timezone

import pytest
from flask_jwt_extended import create_access_token, decode_token

from app.models import RevokedToken, User
from app.utils.auth_tokens import (
    AUTH_REQUIRED_MESSAGE,
    SESSION_ENDED_MESSAGE,
    SESSION_EXPIRED_MESSAGE,
    SESSION_INVALID_MESSAGE,
)


PASSWORD = "TestPassword123!"
NEW_PASSWORD = "BrandNewPassword456!"


@pytest.fixture(autouse=True)
def clean_revoked_tokens(db_session):
    yield
    db_session.rollback()
    db_session.query(RevokedToken).delete(synchronize_session=False)
    db_session.commit()


def _login(client, password=PASSWORD, name="testuser"):
    response = client.post("/login", json={"name": name, "password": password})
    return response


def _token(client, password=PASSWORD):
    response = _login(client, password)
    assert response.status_code == 200
    return response.get_json()["token"]


def _me(client, token):
    return client.get("/me", headers={"Authorization": f"Bearer {token}"})


def _profile_update(test_user, **extra):
    return {"name": "testuser", "dob": "1996-01-01", "place": "Bengaluru", **extra}


def _put_profile(client, test_user, token, **extra):
    return client.put(
        f"/users/{test_user.id}",
        json=_profile_update(test_user, **extra),
        headers={"Authorization": f"Bearer {token}"},
    )


# ============================================================
# Token contents
# ============================================================


def test_login_token_carries_the_users_token_version(app, client, test_user):
    token = _token(client)

    with app.app_context():
        claims = decode_token(token)

    assert claims["ver"] == 0
    assert claims["sub"] == str(test_user.id)


def test_tokens_issued_before_versioning_still_work(app, client, test_user):
    # Tokens already in browsers when this ships have no "ver" claim. They are
    # treated as version 0, so deploying does not log anyone out.
    with app.app_context():
        legacy_token = create_access_token(identity=str(test_user.id))

    assert _me(client, legacy_token).status_code == 200


# ============================================================
# Single-device logout
# ============================================================


def test_logout_revokes_only_the_current_token(client, test_user):
    laptop = _token(client)
    phone = _token(client)

    response = client.post("/logout", headers={"Authorization": f"Bearer {laptop}"})
    assert response.status_code == 200

    revoked = _me(client, laptop)
    assert revoked.status_code == 401
    assert revoked.get_json() == {"error": SESSION_ENDED_MESSAGE}

    assert _me(client, phone).status_code == 200


def test_logout_requires_a_token(client):
    response = client.post("/logout")

    assert response.status_code == 401
    assert response.get_json() == {"error": AUTH_REQUIRED_MESSAGE}


def test_logout_prunes_revocations_that_already_expired(client, test_user, db_session):
    db_session.add(
        RevokedToken(
            jti="expired-entry",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    token = _token(client)
    client.post("/logout", headers={"Authorization": f"Bearer {token}"})

    db_session.expire_all()
    remaining = {row.jti for row in db_session.query(RevokedToken).all()}

    assert "expired-entry" not in remaining
    assert len(remaining) == 1  # only the token just logged out


# ============================================================
# Log out of all devices
# ============================================================


def test_logout_all_revokes_every_existing_token(client, test_user):
    laptop = _token(client)
    phone = _token(client)

    response = client.post("/logout-all", headers={"Authorization": f"Bearer {laptop}"})
    assert response.status_code == 200

    assert _me(client, laptop).status_code == 401
    assert _me(client, phone).status_code == 401

    # Logging in again issues a token with the new version.
    assert _me(client, _token(client)).status_code == 200


def test_logout_all_affects_only_that_user(client, test_user, other_user):
    other = _login(client, "OtherPassword123!", name="otheruser").get_json()["token"]
    mine = _token(client)

    client.post("/logout-all", headers={"Authorization": f"Bearer {mine}"})

    assert _me(client, other).status_code == 200


# ============================================================
# Password change
# ============================================================


def test_password_change_requires_the_current_password(client, test_user):
    token = _token(client)

    response = _put_profile(client, test_user, token, password=NEW_PASSWORD)

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Current password is required to set a new password."
    )
    assert _login(client, PASSWORD).status_code == 200


def test_wrong_current_password_changes_nothing(client, test_user, db_session):
    token = _token(client)

    response = _put_profile(
        client,
        test_user,
        token,
        name="renamed",
        password=NEW_PASSWORD,
        current_password="not-my-password",
    )

    # 403 rather than 401: the session is valid, so the frontend must not
    # log the user out.
    assert response.status_code == 403
    assert response.get_json()["error"] == "Current password is incorrect."

    db_session.expire_all()
    user = db_session.get(User, test_user.id)
    assert user.name == "testuser"  # the rename was rolled back too
    assert user.token_version == 0
    assert _me(client, token).status_code == 200
    assert _login(client, PASSWORD).status_code == 200


def test_password_change_ends_other_sessions_and_keeps_this_one(client, test_user):
    this_device = _token(client)
    other_device = _token(client)

    response = _put_profile(
        client,
        test_user,
        this_device,
        password=NEW_PASSWORD,
        current_password=PASSWORD,
    )

    assert response.status_code == 200
    new_token = response.get_json()["token"]

    assert _me(client, this_device).status_code == 401
    assert _me(client, other_device).status_code == 401
    assert _me(client, new_token).status_code == 200

    assert _login(client, PASSWORD).status_code == 401
    assert _login(client, NEW_PASSWORD).status_code == 200


def test_profile_update_without_password_keeps_sessions(client, test_user):
    token = _token(client)

    response = _put_profile(client, test_user, token, place="Mysuru")

    assert response.status_code == 200
    assert "token" not in response.get_json()
    assert _me(client, token).status_code == 200


def test_wrong_current_passwords_are_rate_limited(client, test_user, rate_limited):
    token = _token(client)

    for _ in range(5):
        response = _put_profile(
            client,
            test_user,
            token,
            password=NEW_PASSWORD,
            current_password="guess",
        )
        assert response.status_code == 403

    # Even the right current password is refused once the account is limited.
    response = _put_profile(
        client,
        test_user,
        token,
        password=NEW_PASSWORD,
        current_password=PASSWORD,
    )

    assert response.status_code == 429
    assert response.get_json()["error"].startswith(
        "Too many incorrect current-password attempts."
    )


def test_profile_updates_do_not_use_up_the_password_allowance(
    client, test_user, rate_limited
):
    token = _token(client)

    for _ in range(6):
        assert _put_profile(client, test_user, token, place="Mysuru").status_code == 200


# ============================================================
# Deleted accounts and bad tokens
# ============================================================


def test_token_of_a_deleted_account_is_rejected(app, client):
    with app.app_context():
        token = create_access_token(identity="999999999", additional_claims={"ver": 0})

    response = _me(client, token)

    assert response.status_code == 401
    assert response.get_json() == {"error": SESSION_ENDED_MESSAGE}


def test_expired_token_gets_401(app, client, test_user):
    with app.app_context():
        token = create_access_token(
            identity=str(test_user.id),
            additional_claims={"ver": 0},
            expires_delta=timedelta(seconds=-10),
        )

    response = _me(client, token)

    assert response.status_code == 401
    assert response.get_json() == {"error": SESSION_EXPIRED_MESSAGE}


@pytest.mark.parametrize("corrupt", ["bad_signature", "garbage"])
def test_invalid_tokens_get_401_not_422(client, test_user, corrupt):
    # Flask-JWT-Extended answers these with 422 by default. The frontend only
    # logs out on 401, so it would be stuck with a dead token (for example
    # after JWT_SECRET_KEY is rotated).
    if corrupt == "bad_signature":
        token = _token(client)[:-4] + "AAAA"
    else:
        token = "not.a.jwt"

    response = _me(client, token)

    assert response.status_code == 401
    assert response.get_json() == {"error": SESSION_INVALID_MESSAGE}


def test_token_signed_with_another_secret_gets_401(app, client, test_user):
    import jwt as pyjwt

    forged = pyjwt.encode(
        {
            "sub": str(test_user.id),
            "type": "access",
            "jti": "forged",
            "fresh": False,
            "ver": 0,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "not-the-server-secret-but-long-enough-for-hs256",
        algorithm="HS256",
    )

    assert _me(client, forged).status_code == 401
