from elasticsearch import Elasticsearch, helpers

from core.settings import get_settings

MOVIES_INDEX = "movies"

MOVIES_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "standard"},
            "description": {"type": "text", "analyzer": "standard"},
            "rating": {"type": "float"},
            "type": {"type": "keyword"},
            "genres": {"type": "keyword"},
            "updated_at": {"type": "date"},
        }
    }
}


def get_client() -> Elasticsearch:
    settings = get_settings()
    return Elasticsearch(hosts=[settings.elasticsearch.url], request_timeout=30)


def ensure_index(client: Elasticsearch) -> None:
    if not client.indices.exists(index=MOVIES_INDEX):
        client.indices.create(index=MOVIES_INDEX, body=MOVIES_MAPPING)


def bulk_load(client: Elasticsearch, films: list[dict]) -> tuple[int, int]:
    actions = [
        {
            "_index": MOVIES_INDEX,
            "_id": film["id"],
            "_source": {k: v for k, v in film.items() if k != "id"},
        }
        for film in films
    ]
    success, errors = helpers.bulk(client, actions, raise_on_error=False)
    return success, len(errors)
