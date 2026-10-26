import logging
import os
from typing import Any

from botocore.exceptions import ClientError

from data.ingest import DATA_DIR
from data.storage import read_table, s3_endpoint, write_parquet

log = logging.getLogger(__name__)

S3_ROOT = "s3://datasets/reference"
LOCAL_ROOT = DATA_DIR / "reference"


def reference_root() -> str:
    """drift-monitor always reads <root>/reference.parquet, which must belong to the champion."""
    return os.environ.get("REFERENCE_ROOT") or (S3_ROOT if s3_endpoint() else str(LOCAL_ROOT))


def versioned_uri(version: str, root: str | None = None) -> str:
    return f"{(root or reference_root()).rstrip('/')}/v{version}/reference.parquet"


def current_uri(root: str | None = None) -> str:
    return f"{(root or reference_root()).rstrip('/')}/reference.parquet"


def publish(version: str, root: str | None = None, client: Any = None) -> str | None:
    source = versioned_uri(version, root)
    try:
        frame = read_table(source, client)
    except (FileNotFoundError, ClientError) as error:
        log.warning("no reference sample for version %s at %s: %s", version, source, error)
        return None
    return write_parquet(frame, current_uri(root), client)
