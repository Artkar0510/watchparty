"""Auth-service: register / login / refresh / verify."""
import httpx


async def test_register_and_login(http: httpx.AsyncClient, alice: dict) -> None:
    # /me returns the freshly-registered user
    r = await http.get("/api/v1/users/me", headers=alice["auth_header"])
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == alice["username"]
    assert data["email"] == alice["email"]
    assert data["is_active"] is True


async def test_refresh_token(http: httpx.AsyncClient, alice: dict) -> None:
    r = await http.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": alice["refresh_token"]},
    )
    assert r.status_code == 200
    new_tokens = r.json()
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"]
    # New access token should authenticate
    r = await http.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert r.status_code == 200


async def test_login_wrong_password(http: httpx.AsyncClient, alice: dict) -> None:
    r = await http.post(
        "/api/v1/auth/login",
        json={"email": alice["email"], "password": "wrong-password"},
    )
    assert r.status_code == 401


async def test_verify_internal(http: httpx.AsyncClient, alice: dict) -> None:
    r = await http.get("/api/v1/auth/verify", headers=alice["auth_header"])
    assert r.status_code == 200
    assert r.json()["user_id"] == alice["user_id"]
