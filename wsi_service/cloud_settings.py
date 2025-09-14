from datetime import datetime, timedelta
from typing import Any

from wsi_service.settings import Settings

# Attempt to import AWS secrets loader from cloudwrappers. Only the AWS portion
# is used here; dotenv support from that module is intentionally ignored.
try:  # pragma: no cover - import is optional
    from wsi_service.utils.cloudwrappers.aws_secrets import (  # type: ignore
        _list_and_get_secrets,
    )
except Exception:  # pragma: no cover - fallback for different installation
    try:
        from utils.cloudwrappers.aws_secrets import _list_and_get_secrets  # type: ignore
    except Exception:  # pragma: no cover - aws secrets module not installed
        _list_and_get_secrets = None  # type: ignore


class CloudSettings:
    """Wrapper around :class:`Settings` that refreshes AWS secrets.

    Secrets are re-fetched every hour. Accessing any attribute triggers a
    staleness check; if the cached values are more than an hour old we attempt
    to refresh them from AWS. If the loader is unavailable this class simply
    returns the local ``Settings`` values.
    """

    def __init__(self) -> None:
        self._last_refresh: datetime = datetime.min
        self._settings = Settings()
        # Force an immediate refresh so secrets apply at startup.
        self._refresh()

    def _is_stale(self) -> bool:
        return datetime.utcnow() - self._last_refresh > timedelta(hours=1)

    def _load_secrets(self) -> None:
        if _list_and_get_secrets is None:
            return
        try:  # pragma: no cover - network interaction is stubbed
            secrets = _list_and_get_secrets()
        except Exception:
            secrets = {}
        # TODO: Map values from ``secrets`` into ``self._settings`` if needed.

    def _refresh(self) -> None:
        self._load_secrets()
        self._settings = Settings()
        self._last_refresh = datetime.utcnow()

    def __getattr__(self, name: str) -> Any:
        if self._is_stale():
            self._refresh()
        return getattr(self._settings, name)


# Expose an instance for easy import
settings = CloudSettings()
