from datetime import datetime, timedelta
from typing import Any, Dict

from wsi_service.settings import Settings

# Attempt to import a settings client from cloudwrappers. This is a stub
# that allows future integration when the cloudwrappers package is available.
try:  # pragma: no cover - import is optional
    from wsi_service.utils.cloudwrappers import settings_client  # type: ignore
except Exception:  # pragma: no cover - fallback for different installation
    try:
        from utils.cloudwrappers import settings_client  # type: ignore
    except Exception:  # pragma: no cover - cloudwrappers not installed
        settings_client = None  # type: ignore


class CloudSettings:
    """Wrapper around :class:`Settings` that refreshes values from the cloud.

    Values are re-fetched from the cloud every hour. Accessing any attribute
    triggers a staleness check; if the cached values are more than an hour old
    we attempt to update them using ``cloudwrappers``. If the client is not
    available this class simply returns the local ``Settings`` values.
    """

    def __init__(self) -> None:
        self._settings = Settings()
        self._client = getattr(settings_client, "SettingsClient", None)
        if self._client:
            self._client = self._client()  # type: ignore[call-arg]
        # Force an immediate refresh so cloud overrides apply at startup.
        self._last_refresh: datetime = datetime.min
        self._refresh()

    def _is_stale(self) -> bool:
        return datetime.utcnow() - self._last_refresh > timedelta(hours=1)

    def _refresh(self) -> None:
        if not self._client:
            # Nothing to refresh from
            self._last_refresh = datetime.utcnow()
            return
        try:  # pragma: no cover - cloud interaction is stubbed
            data: Dict[str, Any] = self._client.fetch_settings()  # type: ignore[attr-defined]
        except Exception:
            data = {}
        for key, value in data.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self._last_refresh = datetime.utcnow()

    def __getattr__(self, name: str) -> Any:
        if self._is_stale():
            self._refresh()
        return getattr(self._settings, name)


# Expose an instance for easy import
settings = CloudSettings()
