"""
ETL: PostgreSQL → Elasticsearch

Runs continuously, checking for updated films every `poll_interval` seconds.
State (last sync timestamp) is persisted to a JSON file so restarts don't
re-index everything from scratch.
"""
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from core.settings import get_settings
from extractors.postgres import extract_films
from loaders.elasticsearch import bulk_load, ensure_index, get_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ETL] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def load_state(path: str) -> datetime:
    p = Path(path)
    if p.exists():
        data = json.loads(p.read_text())
        return datetime.fromisoformat(data["last_sync"])
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def save_state(path: str, last_sync: datetime) -> None:
    Path(path).write_text(json.dumps({"last_sync": last_sync.isoformat()}))


def run_once(settings) -> datetime:
    last_sync = load_state(settings.etl.state_file)
    new_last_sync = last_sync

    client = get_client()
    ensure_index(client)

    total_indexed = 0
    for batch in extract_films(since=last_sync, batch_size=settings.etl.batch_size):
        if not batch:
            continue
        success, errors = bulk_load(client, batch)
        total_indexed += success
        if errors:
            logger.warning("Bulk errors: %d", errors)

        batch_max_updated = max(
            datetime.fromisoformat(f["updated_at"]) for f in batch if f.get("updated_at")
        )
        if batch_max_updated > new_last_sync:
            new_last_sync = batch_max_updated

    client.close()

    if total_indexed:
        logger.info("Indexed %d films since %s", total_indexed, last_sync)

    if new_last_sync != last_sync:
        save_state(settings.etl.state_file, new_last_sync)

    return new_last_sync


def main() -> None:
    settings = get_settings()
    logger.info("ETL service started. Poll interval: %ds", settings.etl.poll_interval)

    while True:
        try:
            run_once(settings)
        except Exception as exc:
            logger.error("ETL cycle failed: %s", exc, exc_info=True)

        time.sleep(settings.etl.poll_interval)


if __name__ == "__main__":
    main()
