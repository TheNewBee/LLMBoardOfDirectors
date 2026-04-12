from __future__ import annotations

from boardroom.api.services.config_service import ConfigService
from boardroom.api.services.meeting_service import MeetingService
from boardroom.models import AppConfig

_CONFIG_SERVICE = ConfigService()
_MEETING_SERVICE = MeetingService(max_workers=3)


def get_config_service() -> ConfigService:
    return _CONFIG_SERVICE


def get_meeting_service() -> MeetingService:
    return _MEETING_SERVICE


def get_app_config() -> AppConfig:
    return _CONFIG_SERVICE.load()
