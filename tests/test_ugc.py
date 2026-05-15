"""UGC-service: likes, bookmarks, reviews."""
import httpx


async def test_likes_flow(http: httpx.AsyncClient, alice: dict, film: dict) -> None:
    r = await http.post(f"/api/v1/likes/{film['id']}", headers=alice["auth_header"])
    assert r.status_code == 201

    # Duplicate like is rejected
    r = await http.post(f"/api/v1/likes/{film['id']}", headers=alice["auth_header"])
    assert r.status_code == 400

    # Aggregate count
    r = await http.get(f"/api/v1/likes/film/{film['id']}")
    assert r.status_code == 200
    assert r.json()["likes_count"] >= 1

    # My likes
    r = await http.get("/api/v1/likes/me", headers=alice["auth_header"])
    assert r.status_code == 200
    assert any(like["film_id"] == film["id"] for like in r.json())

    # Unlike
    r = await http.delete(f"/api/v1/likes/{film['id']}", headers=alice["auth_header"])
    assert r.status_code == 204


async def test_bookmarks(http: httpx.AsyncClient, alice: dict, film: dict) -> None:
    r = await http.post(
        "/api/v1/bookmarks",
        json={"film_id": film["id"]},
        headers=alice["auth_header"],
    )
    assert r.status_code == 201

    r = await http.get("/api/v1/bookmarks", headers=alice["auth_header"])
    assert r.status_code == 200
    assert any(b["film_id"] == film["id"] for b in r.json())


async def test_reviews(http: httpx.AsyncClient, alice: dict, film: dict) -> None:
    r = await http.post(
        f"/api/v1/reviews/{film['id']}",
        json={"text": "Отличный фильм", "rating": 9},
        headers=alice["auth_header"],
    )
    assert r.status_code == 201

    r = await http.get(f"/api/v1/reviews/film/{film['id']}")
    assert r.status_code == 200
    reviews = r.json()
    assert any(rv["text"] == "Отличный фильм" and rv["rating"] == 9 for rv in reviews)
