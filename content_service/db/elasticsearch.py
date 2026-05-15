from elasticsearch import AsyncElasticsearch

from core.settings import get_settings

_client: AsyncElasticsearch | None = None

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


async def init_elasticsearch() -> None:
    global _client
    settings = get_settings()
    _client = AsyncElasticsearch(
        hosts=[settings.elasticsearch.url],
        request_timeout=settings.elasticsearch.request_timeout,
    )
    if not await _client.indices.exists(index=MOVIES_INDEX):
        await _client.indices.create(index=MOVIES_INDEX, body=MOVIES_MAPPING)


async def close_elasticsearch() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None


def get_es() -> AsyncElasticsearch:
    if _client is None:
        raise RuntimeError("Elasticsearch client is not initialized")
    return _client
