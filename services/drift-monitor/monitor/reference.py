import logging
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

AUTO = "auto"
CHAMPION = "champion"


def _default_client() -> Any:
    from mlflow import MlflowClient

    return MlflowClient()


def resolve_reference_uri(
    configured: str,
    fallback: str,
    model_name: str,
    client_factory: Callable[[], Any] = _default_client,
) -> str:
    """The champion's own training sample is the drift baseline, so a promotion made by the
    agent (which only moves the alias) changes the reference too."""
    if configured != AUTO:
        return configured
    try:
        version = client_factory().get_model_version_by_alias(model_name, CHAMPION)
    except Exception as exc:  # registry down or no champion yet
        log.warning("cannot read @%s of %s (%s), using %s", CHAMPION, model_name, exc, fallback)
        return fallback
    uri = (version.tags or {}).get("reference_uri")
    if not uri:
        log.warning(
            "%s v%s has no reference_uri tag, using %s", model_name, version.version, fallback
        )
        return fallback
    log.info("reference of %s v%s: %s", model_name, version.version, uri)
    return uri
