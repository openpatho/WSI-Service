from datetime import datetime, timedelta, timezone
from typing import Any
import os, json
from botocore.exceptions import NoCredentialsError

from wsi_service.settings import Settings

# Attempt to import AWS secrets loader from cloudwrappers. Only the AWS portion
# is used here; dotenv support from that module is intentionally ignored.
try:  # pragma: no cover - import is optional
    from wsi_service.utils.cloudwrappers.aws_secrets import (  # type: ignore
        _list_and_get_secrets, _parse_nested_secret_value
    )
except Exception:  # pragma: no cover - fallback for different installation
    try:
        from utils.cloudwrappers.aws_secrets import _list_and_get_secrets, _parse_nested_secret_value  # type: ignore
    except Exception:  # pragma: no cover - aws secrets module not installed
        _list_and_get_secrets = None  # type: ignore
        _parse_nested_secret_value = None


class CloudSettings:
    """Wrapper around :class:`Settings` that refreshes AWS secrets.

    Secrets are re-fetched every hour. Accessing any attribute triggers a
    staleness check; if the cached values are more than an hour old we attempt
    to refresh them from AWS. If the loader is unavailable this class simply
    returns the local ``Settings`` values.
    """
    def _load_aws_credentials(self):
        if os.path.exists("/run/secrets/aws_credentials"):
            credentials_path = "/run/secrets/aws_credentials"
        else:
            credentials_path = "aws_credentials.json"
        print(f"looking for credentials at: {credentials_path}")
        if os.path.exists(credentials_path):
            with open(credentials_path, "r") as file:
                print("loading json credentials")
                credentials = json.load(file)
                os.environ["AWS_ACCESS_KEY_ID"] = credentials["aws_access_key_id"]
                os.environ["AWS_SECRET_ACCESS_KEY"] = credentials["aws_secret_access_key"]
                os.environ["AWS_DEFAULT_REGION"] = credentials["aws_default_region"]
        else:
            raise NoCredentialsError()

    def __init__(self) -> None:
        self._last_refresh: datetime = datetime.min
        self._load_aws_credentials() # Load AWS credentials from local file or secret on first run
        self._settings = Settings()
        # Force an immediate refresh so secrets apply at startup.
        self._refresh()

    def _is_stale(self) -> bool:
        return datetime.now(timezone.utc) - self._last_refresh > timedelta(hours=1)

    def _load_secrets(self) -> None:
        if _list_and_get_secrets is None:
            return
        try:  # pragma: no cover - network interaction is stubbed
            secrets = _list_and_get_secrets()
        except Exception:
            return
        
        if not secrets:
            print("blank/no/falsy secrets")
            return
        # un-nest the secrets:
        unnested={}
        for key, value in secrets.items():
                parsed = _parse_nested_secret_value(value)
                if isinstance(parsed, dict):
                    
                    for nested_key, nested_value in parsed.items():
                        lower_key = nested_key.lower() # settings seems to use all lowercase - should try to be consistent
                        unnested[lower_key] = nested_value
                else:
                    lower_key  = key.lower()  # settings seems to use all lowercase - should try to be consistent
                    unnested[lower_key] = parsed

        secrets = unnested # put them back here for rest of code.
        
        # TODO: Map values from ``secrets`` into ``self._settings`` if needed.
        


        # Dry run: Print what we would do with the secrets
        if secrets:
            print(f"[CloudSettings] Found {len(secrets)} secrets from AWS:")
            for key in secrets.keys():
                print(f"  - {key}")
            
            # Check which settings would be overridden
            existing_settings = [attr for attr in dir(self._settings) if not attr.startswith('_')]
            would_override = [key for key in secrets.keys() if key in existing_settings]
            would_add = [key for key in secrets.keys() if key not in existing_settings]
            
            if would_override:
                print(f"[CloudSettings] Would override {len(would_override)} existing settings:")
                for key in would_override:
                    print(f"  - {key}")
            else:
                print("No existing settings would be over-ridden")
            
            if would_add:
                print(f"[CloudSettings] Would add {len(would_add)} new settings:")
                for key in would_add:
                    print(f"  - {key}")
        else:
            print("[CloudSettings] No secrets found from AWS")

    def _refresh(self) -> None:
        self._load_secrets()
        self._last_refresh = datetime.now(timezone.utc)

    def __getattr__(self, name: str) -> Any:
        if self._is_stale():
            # if the cloud settings are stale, refresh them
            self._refresh()
        return getattr(self._settings, name)


# Expose an instance for easy import
settings = CloudSettings()
