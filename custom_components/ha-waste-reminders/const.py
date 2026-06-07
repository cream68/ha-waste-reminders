from __future__ import annotations

from datetime import time

DOMAIN = "ha-waste-reminders"
NAME = "ha waste reminders"
NOTIFICATION_TITLE = "Taubenweg 15"

PLATFORMS = ["sensor", "switch", "time", "button", "select"]

CONF_ACTIVE_WASTE_TYPES = "active_waste_types"
CONF_CALENDAR_ENTITY = "calendar_entity"
CONF_DISCOVERED_WASTE_TYPES = "discovered_waste_types"
CONF_EVENING_ENABLED = "evening_enabled"
CONF_EVENING_TIME = "evening_time"
CONF_MONTH_1 = "month_1"
CONF_MONTH_2 = "month_2"
CONF_MORNING_ENABLED = "morning_enabled"
CONF_MORNING_TIME = "morning_time"
CONF_NOTIFY_SERVICES = "notify_services"
CONF_REMINDERS_ENABLED = "reminders_enabled"

DEFAULT_EVENING_ENABLED = True
DEFAULT_EVENING_TIME = time(hour=18, minute=0)
DEFAULT_MONTH_1 = 1
DEFAULT_MONTH_2 = 7
DEFAULT_MORNING_ENABLED = True
DEFAULT_MORNING_TIME = time(hour=7, minute=0)
DEFAULT_REMINDERS_ENABLED = True

SCAN_DAYS = 180
NEXT_EVENTS_LIMIT = 10
COORDINATOR_UPDATE_HOURS = 6
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_state"

REMINDER_EVENING = "evening"
REMINDER_MORNING = "morning"
