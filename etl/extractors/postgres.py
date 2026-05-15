from datetime import datetime
from typing import Iterator

import psycopg

from core.settings import get_settings


def extract_films(since: datetime, batch_size: int) -> Iterator[list[dict]]:
    settings = get_settings()
    query = """
        SELECT
            fw.id,
            fw.title,
            fw.description,
            fw.rating,
            fw.type,
            fw.updated_at,
            array_agg(DISTINCT g.name) FILTER (WHERE g.name IS NOT NULL) AS genres
        FROM film_work fw
        LEFT JOIN genre_film_work gfw ON gfw.film_work_id = fw.id
        LEFT JOIN genre g ON g.id = gfw.genre_id
        WHERE fw.updated_at > %s
        GROUP BY fw.id
        ORDER BY fw.updated_at
    """
    with psycopg.connect(settings.postgresql.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (since,))
            while True:
                rows = cur.fetchmany(batch_size)
                if not rows:
                    break
                yield [
                    {
                        "id": str(row[0]),
                        "title": row[1],
                        "description": row[2],
                        "rating": row[3],
                        "type": row[4],
                        "updated_at": row[5].isoformat() if row[5] else None,
                        "genres": list(row[6]) if row[6] else [],
                    }
                    for row in rows
                ]
