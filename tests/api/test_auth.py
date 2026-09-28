import pytest

pytestmark = pytest.mark.asyncio


async def test_register_creates_user_and_owner_membership(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "founder@example.com",
            "password": "SuperSecret123",
            "full_name": "Founder Person",
            "tenant_name": "Founder Co",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "founder@example.com"
    assert body["is_email_verified"] is False
    assert "hashed_password" not in body
    assert "password" not in body


async def test_register_duplicate_email_rejected(client):
    payload = {
        "email": "dupe@example.com",
        "password": "SuperSecret123",
        "full_name": "Dupe",
        "tenant_name": "Dupe Co",
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "RESOURCE_CONFLICT"


async def test_register_weak_password_rejected(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short", "full_name": "Weak", "tenant_name": "Weak Co"},
    )
    assert resp.status_code == 422


async def test_login_success_returns_tokens(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "SuperSecret123", "full_name": "L", "tenant_name": "L Co"},
    )
    resp = await client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "SuperSecret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_login_invalid_credentials(client):
    resp = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_FAILED"


async def test_login_wrong_password_for_existing_user(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@example.com", "password": "SuperSecret123", "full_name": "W", "tenant_name": "W Co"},
    )
    resp = await client.post("/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "totallyWrong123"})
    assert resp.status_code == 401


async def test_me_requires_bearer_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_user_and_memberships(client, register_and_login):
    token, tenant_id, email = await register_and_login()
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == email
    assert body["memberships"][0]["tenant_id"] == tenant_id
    assert body["memberships"][0]["role"] == "owner"


async def test_refresh_token_rotation(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "rotate@example.com", "password": "SuperSecret123", "full_name": "R", "tenant_name": "R Co"},
    )
    login = await client.post("/api/v1/auth/login", json={"email": "rotate@example.com", "password": "SuperSecret123"})
    old_refresh = login.json()["refresh_token"]

    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_resp.status_code == 200
    new_tokens = refresh_resp.json()
    assert new_tokens["refresh_token"] != old_refresh


async def test_refresh_token_reuse_is_detected_and_revokes_session(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "reuse@example.com", "password": "SuperSecret123", "full_name": "R", "tenant_name": "R Co"},
    )
    login = await client.post("/api/v1/auth/login", json={"email": "reuse@example.com", "password": "SuperSecret123"})
    old_refresh = login.json()["refresh_token"]

    first_use = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert first_use.status_code == 200
    new_refresh = first_use.json()["refresh_token"]

    # Reusing the ALREADY-ROTATED (now revoked) token must fail...
    reuse_attempt = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse_attempt.status_code == 401

    # ...and must have revoked the entire session family, including the new token.
    followup = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert followup.status_code == 401


async def test_refresh_with_invalid_token(client):
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401


async def test_logout_revokes_refresh_token(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "logout@example.com", "password": "SuperSecret123", "full_name": "L", "tenant_name": "L Co"},
    )
    login = await client.post("/api/v1/auth/login", json={"email": "logout@example.com", "password": "SuperSecret123"})
    refresh_token = login.json()["refresh_token"]

    logout_resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 204

    refresh_after_logout = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_after_logout.status_code == 401


async def test_forgot_password_does_not_leak_account_existence(client):
    resp_existing = await client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@example.com"})
    assert resp_existing.status_code == 202
    # Response shape must be identical whether or not the account exists.
    assert "reset link has been sent" in resp_existing.json()["message"]


async def test_full_password_reset_flow(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "resetme@example.com", "password": "OldPassword123", "full_name": "R", "tenant_name": "R Co"},
    )
    await client.post("/api/v1/auth/forgot-password", json={"email": "resetme@example.com"})
    sent = client.sent_emails
    reset_email = next(m for m in sent if "reset" in m.subject.lower())
    token = reset_email.body.split("token=")[1].strip()

    reset_resp = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "BrandNewPassword123"}
    )
    assert reset_resp.status_code == 204

    old_login = await client.post("/api/v1/auth/login", json={"email": "resetme@example.com", "password": "OldPassword123"})
    assert old_login.status_code == 401

    new_login = await client.post("/api/v1/auth/login", json={"email": "resetme@example.com", "password": "BrandNewPassword123"})
    assert new_login.status_code == 200


async def test_reset_password_invalid_token(client):
    resp = await client.post("/api/v1/auth/reset-password", json={"token": "bogus", "new_password": "BrandNewPassword123"})
    assert resp.status_code == 422


async def test_email_verification_flow(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "verify@example.com", "password": "SuperSecret123", "full_name": "V", "tenant_name": "V Co"},
    )
    sent = client.sent_emails
    verify_email = next(m for m in sent if "verify" in m.subject.lower())
    token = verify_email.body.split("token=")[1].strip()

    verify_resp = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_resp.status_code == 204

    # Using it a second time must fail (single-use).
    verify_again = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify_again.status_code == 422


async def test_resend_verification_does_not_leak_account_existence(client):
    resp = await client.post("/api/v1/auth/resend-verification", json={"email": "nobody-here@example.com"})
    assert resp.status_code == 202
