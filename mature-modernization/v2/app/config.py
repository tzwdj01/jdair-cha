from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
RELEASE_ROOT = Path(__file__).resolve().parents[1]


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUE_VALUES


def env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or default


def env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("CHA_V2_LEGACY_BASE_URL must be an HTTP(S) URL")
    return normalized


def env_url(name: str, default: str = "") -> str:
    raw = os.getenv(name, default).strip()
    if not raw:
        return ""
    parsed = urlparse(raw.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an HTTP(S) URL")
    return raw.rstrip("/")


def release_marker(name: str, default: str) -> str:
    try:
        value = (RELEASE_ROOT / name).read_text(encoding="utf-8").strip()
    except OSError:
        return default
    return value or default


@dataclass(frozen=True)
class Settings:
    service_name: str
    environment: str
    version: str
    build: str
    allowed_hosts: tuple[str, ...]
    legacy_base_url: str
    legacy_timeout_seconds: float
    dashboard_device_ttl_seconds: int
    dashboard_video_ttl_seconds: int
    dashboard_flight_ttl_seconds: int
    dashboard_routine_ttl_seconds: int
    dashboard_trend_ttl_seconds: int
    dashboard_stale_seconds: int
    dashboard_initial_wait_seconds: float
    dashboard_state_dir: str
    realtime_session_ttl_seconds: int
    realtime_cleanup_interval_seconds: int
    realtime_closed_retention_seconds: int
    realtime_command_timeout_seconds: float
    realtime_max_streams_per_session: int
    realtime_max_sessions_per_owner: int
    realtime_session_create_limit: int
    realtime_session_create_window_seconds: int
    realtime_max_retained_sessions: int
    realtime_allowed_origins: tuple[str, ...]
    realtime_allow_missing_ws_origin: bool
    realtime_canary_users: tuple[str, ...]
    aee_api_base_url: str
    aee_origin: str
    aee_gateway_host: str
    aee_gateway_port: int
    aee_gateway_ssl: bool
    aee_gateway_http_proxy: str
    aee_username: str
    aee_password: str
    aee_login_timeout_seconds: float
    aee_connect_timeout_seconds: float
    feature_dashboard_v2: bool
    feature_realtime_readonly: bool
    feature_realtime_audio: bool
    feature_realtime_control: bool
    feature_account_pool_v2: bool
    feature_records_v2: bool

    def realtime_aee_is_configured(self) -> bool:
        return bool(
            self.aee_api_base_url
            and self.aee_origin
            and self.aee_gateway_host
            and self.aee_gateway_port > 0
            and self.aee_username
            and self.aee_password
        )

    def realtime_canary_is_configured(self) -> bool:
        return bool(self.realtime_canary_users)

    def realtime_canary_user_allowed(self, username: str) -> bool:
        normalized = username.strip().casefold()
        if not normalized:
            return False
        return normalized in {
            item.strip().casefold()
            for item in self.realtime_canary_users
            if item.strip()
        }

    def realtime_is_configured(self) -> bool:
        return (
            self.realtime_aee_is_configured()
            and self.realtime_canary_is_configured()
        )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            service_name=os.getenv("CHA_V2_SERVICE_NAME", "jdair-cha-v2"),
            environment=os.getenv("CHA_V2_ENVIRONMENT", "production"),
            version=os.getenv(
                "CHA_V2_VERSION",
                release_marker("VERSION", "0.2.0"),
            ),
            build=os.getenv(
                "CHA_V2_BUILD",
                release_marker("BUILD", "m1-legacy-adapter"),
            ),
            allowed_hosts=env_csv(
                "CHA_V2_ALLOWED_HOSTS",
                ("cha.jdair.top", "127.0.0.1", "localhost"),
            ),
            legacy_base_url=normalize_base_url(
                os.getenv(
                    "CHA_V2_LEGACY_BASE_URL",
                    "http://127.0.0.1:8790",
                )
            ),
            legacy_timeout_seconds=env_float(
                "CHA_V2_LEGACY_TIMEOUT_SECONDS",
                20.0,
            ),
            dashboard_device_ttl_seconds=env_int(
                "CHA_V2_DASHBOARD_DEVICE_TTL_SECONDS",
                15,
            ),
            dashboard_video_ttl_seconds=env_int(
                "CHA_V2_DASHBOARD_VIDEO_TTL_SECONDS",
                180,
            ),
            dashboard_flight_ttl_seconds=env_int(
                "CHA_V2_DASHBOARD_FLIGHT_TTL_SECONDS",
                60,
            ),
            dashboard_routine_ttl_seconds=env_int(
                "CHA_V2_DASHBOARD_ROUTINE_TTL_SECONDS",
                300,
            ),
            dashboard_trend_ttl_seconds=env_int(
                "CHA_V2_DASHBOARD_TREND_TTL_SECONDS",
                300,
            ),
            dashboard_stale_seconds=env_int(
                "CHA_V2_DASHBOARD_STALE_SECONDS",
                3600,
            ),
            dashboard_initial_wait_seconds=env_float(
                "CHA_V2_DASHBOARD_INITIAL_WAIT_SECONDS",
                1.5,
            ),
            dashboard_state_dir=os.getenv(
                "CHA_V2_DASHBOARD_STATE_DIR",
                "/opt/jdair-cha/v2/data",
            ).strip()
            or "/opt/jdair-cha/v2/data",
            realtime_session_ttl_seconds=env_int(
                "CHA_V2_REALTIME_SESSION_TTL_SECONDS",
                60,
            ),
            realtime_cleanup_interval_seconds=env_int(
                "CHA_V2_REALTIME_CLEANUP_INTERVAL_SECONDS",
                10,
            ),
            realtime_closed_retention_seconds=env_int(
                "CHA_V2_REALTIME_CLOSED_RETENTION_SECONDS",
                300,
            ),
            realtime_command_timeout_seconds=env_float(
                "CHA_V2_REALTIME_COMMAND_TIMEOUT_SECONDS",
                5.0,
            ),
            realtime_max_streams_per_session=min(
                env_int(
                    "CHA_V2_REALTIME_MAX_STREAMS_PER_SESSION",
                    6,
                ),
                6,
            ),
            realtime_max_sessions_per_owner=max(
                1,
                min(
                    env_int("CHA_V2_REALTIME_MAX_SESSIONS_PER_OWNER", 3),
                    10,
                ),
            ),
            realtime_session_create_limit=max(
                1,
                min(
                    env_int("CHA_V2_REALTIME_SESSION_CREATE_LIMIT", 10),
                    1000,
                ),
            ),
            realtime_session_create_window_seconds=max(
                1,
                env_int(
                    "CHA_V2_REALTIME_SESSION_CREATE_WINDOW_SECONDS",
                    60,
                ),
            ),
            realtime_max_retained_sessions=max(
                8,
                min(
                    env_int(
                        "CHA_V2_REALTIME_MAX_RETAINED_SESSIONS",
                        128,
                    ),
                    1024,
                ),
            ),
            realtime_allowed_origins=env_csv(
                "CHA_V2_REALTIME_ALLOWED_ORIGINS",
                (),
            ),
            realtime_allow_missing_ws_origin=env_bool(
                "CHA_V2_REALTIME_ALLOW_MISSING_WS_ORIGIN",
                False,
            ),
            realtime_canary_users=env_csv(
                "CHA_V2_REALTIME_CANARY_USERS",
                (),
            ),
            aee_api_base_url=env_url("CHA_V2_AEE_API_BASE_URL"),
            aee_origin=env_url(
                "CHA_V2_AEE_ORIGIN",
            ),
            aee_gateway_host=os.getenv(
                "CHA_V2_AEE_GATEWAY_HOST",
                "",
            ).strip(),
            aee_gateway_port=env_int("CHA_V2_AEE_GATEWAY_PORT", 7711),
            aee_gateway_ssl=env_bool("CHA_V2_AEE_GATEWAY_SSL"),
            aee_gateway_http_proxy=os.getenv(
                "CHA_V2_AEE_GATEWAY_HTTP_PROXY",
                "",
            ).strip(),
            aee_username=os.getenv("CHA_V2_AEE_USERNAME", "").strip(),
            aee_password=os.getenv("CHA_V2_AEE_PASSWORD", ""),
            aee_login_timeout_seconds=env_float(
                "CHA_V2_AEE_LOGIN_TIMEOUT_SECONDS",
                15.0,
            ),
            aee_connect_timeout_seconds=env_float(
                "CHA_V2_AEE_CONNECT_TIMEOUT_SECONDS",
                15.0,
            ),
            feature_dashboard_v2=env_bool("CHA_V2_FEATURE_DASHBOARD_V2"),
            feature_realtime_readonly=env_bool(
                "CHA_V2_FEATURE_REALTIME_READONLY"
            ),
            feature_realtime_audio=env_bool("CHA_V2_FEATURE_REALTIME_AUDIO"),
            feature_realtime_control=env_bool(
                "CHA_V2_FEATURE_REALTIME_CONTROL"
            ),
            feature_account_pool_v2=env_bool(
                "CHA_V2_FEATURE_ACCOUNT_POOL_V2"
            ),
            feature_records_v2=env_bool("CHA_V2_FEATURE_RECORDS_V2"),
        )

    def public_features(self) -> dict[str, bool]:
        return {
            "dashboard_v2": self.feature_dashboard_v2,
            "realtime_readonly": self.feature_realtime_readonly,
            "realtime_audio": self.feature_realtime_audio,
            "realtime_control": self.feature_realtime_control,
            "account_pool_v2": self.feature_account_pool_v2,
            "records_v2": self.feature_records_v2,
        }

    def legacy_is_required(self) -> bool:
        return self.feature_dashboard_v2 or self.feature_records_v2
