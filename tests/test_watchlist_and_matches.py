"""Content-service: watchlist + match-engine over friends' watchlists."""
import httpx


async def test_watchlist_add_remove(http: httpx.AsyncClient, alice: dict, film: dict) -> None:
    r = await http.post(
        "/api/v1/watchlist",
        json={"film_work_id": film["id"]},
        headers=alice["auth_header"],
    )
    assert r.status_code == 201

    r = await http.get("/api/v1/watchlist", headers=alice["auth_header"])
    assert r.status_code == 200
    assert any(f["id"] == film["id"] for f in r.json())

    r = await http.delete(
        f"/api/v1/watchlist/{film['id']}",
        headers=alice["auth_header"],
    )
    assert r.status_code == 204


async def test_matches_with_friend(http: httpx.AsyncClient, friends: tuple, film: dict) -> None:
    alice, bob = friends

    for user in (alice, bob):
        r = await http.post(
            "/api/v1/watchlist",
            json={"film_work_id": film["id"]},
            headers=user["auth_header"],
        )
        assert r.status_code == 201

    r = await http.get("/api/v1/matches", headers=alice["auth_header"])
    assert r.status_code == 200
    matches = r.json()

    matched = next((m for m in matches if m["film"]["id"] == film["id"]), None)
    assert matched is not None
    assert bob["user_id"] in matched["matched_friend_ids"]
