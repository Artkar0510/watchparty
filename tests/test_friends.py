"""Auth-service: friend request → accept → list."""
import httpx


async def test_friend_request_accept(http: httpx.AsyncClient, friends: tuple) -> None:
    alice, bob = friends

    r = await http.get("/api/v1/users/friends/list", headers=alice["auth_header"])
    assert r.status_code == 200
    friends_list = r.json()
    assert any(f["id"] == bob["user_id"] for f in friends_list)

    r = await http.get("/api/v1/users/friends/ids", headers=alice["auth_header"])
    assert r.status_code == 200
    assert bob["user_id"] in r.json()


async def test_cannot_friend_self(http: httpx.AsyncClient, alice: dict) -> None:
    r = await http.post(
        "/api/v1/users/friends/request",
        json={"addressee_id": alice["user_id"]},
        headers=alice["auth_header"],
    )
    assert r.status_code == 400
