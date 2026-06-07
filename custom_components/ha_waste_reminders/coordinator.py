from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import logging

from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACTIVE_WASTE_TYPES,
    CONF_CALENDAR_ENTITY,
    CONF_DISCOVERED_WASTE_TYPES,
    CONF_MONTH_1,
    CONF_MONTH_2,
    CONF_REMINDERS_ENABLED,
    CONF_NOTIFY_SERVICES,
    COORDINATOR_UPDATE_HOURS,
    DEFAULT_MONTH_1,
    DEFAULT_MONTH_2,
    DEFAULT_REMINDERS_ENABLED,
    DOMAIN,
    NAME,
    NEXT_EVENTS_LIMIT,
    NOTIFICATION_TITLE,
    REMINDER_EVENING,
    REMINDER_MORNING,
    SCAN_DAYS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .utils import (
    detect_waste_type,
    format_short_german_date,
    normalize_event_date,
    month_name_to_number,
)

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class WasteEvent:
    date: date
    waste_type: str
    summary: str
    uid: str | None = None


@dataclass(slots=True)
class WasteCoordinatorData:
    events: list[WasteEvent]
    discovered_waste_types: list[str]


class WasteReminderCoordinator(DataUpdateCoordinator[WasteCoordinatorData]):
    """Coordinate calendar state, discovery and notifications."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=NAME,
            update_interval=timedelta(hours=COORDINATOR_UPDATE_HOURS),
        )
        self.entry = entry
        self.store = Store[dict](hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry.entry_id}")
        self.sent_notifications: dict[str, str] = {}

    async def async_initialize(self) -> None:
        """Load persisted coordinator state."""
        stored = await self.store.async_load() or {}
        self.sent_notifications = dict(stored.get("sent_notifications", {}))
        self._prune_sent_notifications()

    async def _async_update_data(self) -> WasteCoordinatorData:
        calendar_entity = self.entry.options[CONF_CALENDAR_ENTITY]
        try:
            raw_events = await async_fetch_calendar_events(self.hass, calendar_entity, SCAN_DAYS)
        except HomeAssistantError as err:
            raise UpdateFailed(str(err)) from err

        events: list[WasteEvent] = []
        discovered: set[str] = set()

        for raw_event in raw_events:
            summary = (raw_event.get("summary") or "").strip()
            if not summary:
                continue

            event_date = normalize_event_date(raw_event.get("start"))
            if event_date is None:
                continue

            discovered.add(summary)
            events.append(
                WasteEvent(
                    date=event_date,
                    waste_type=detect_waste_type(summary) or summary,
                    summary=summary,
                    uid=raw_event.get("uid"),
                )
            )

        events.sort(key=lambda event: (event.date, event.summary, event.waste_type))
        discovered_waste_types = sorted(discovered)

        await self._async_sync_discovered_types(discovered_waste_types)
        return WasteCoordinatorData(events=events, discovered_waste_types=discovered_waste_types)

    async def _async_sync_discovered_types(self, discovered_waste_types: list[str]) -> None:
        current = list(self.entry.options.get(CONF_DISCOVERED_WASTE_TYPES, []))
        if current == discovered_waste_types:
            return

        active = set(self.entry.options.get(CONF_ACTIVE_WASTE_TYPES, []))
        discovered_set = set(discovered_waste_types)
        merged_active = sorted(
            entry for entry in discovered_waste_types if entry in active or detect_waste_type(entry) in active
        )
        await self.async_update_options(
            {
                CONF_DISCOVERED_WASTE_TYPES: discovered_waste_types,
                CONF_ACTIVE_WASTE_TYPES: merged_active,
            }
        )

    async def async_update_options(self, updates: dict) -> None:
        """Persist updated config entry options without a reload."""
        new_options = {**self.entry.options, **updates}
        self.hass.config_entries.async_update_entry(self.entry, options=new_options)
        self.entry = self.hass.config_entries.async_get_entry(self.entry.entry_id) or self.entry
        self.async_update_listeners()

    def next_relevant_event(self) -> WasteEvent | None:
        """Return the next active waste event."""
        today = dt_util.now().date()
        active = self._active_entries
        for event in self.data.events:
            if event.date >= today and event.summary in active:
                return event
        return None

    def upcoming_relevant_events(self) -> list[WasteEvent]:
        """Return upcoming active events."""
        today = dt_util.now().date()
        active = self._active_entries
        return [
            event
            for event in self.data.events
            if event.date >= today and event.summary in active
        ][:NEXT_EVENTS_LIMIT]

    async def async_send_test_notification(self) -> None:
        """Send a test notification to every configured target."""
        await self._async_send_notification(f"{format_short_german_date(dt_util.now().date())} Test")

    async def async_send_manual_check_notification(self) -> None:
        """Send a notification for relevant pickups today or tomorrow."""
        await self.async_request_refresh()

        messages: list[str] = []
        for target_date in (dt_util.now().date(), dt_util.now().date() + timedelta(days=1)):
            waste_types = self._waste_types_for_date(target_date)
            if not waste_types:
                continue

            formatted_date = format_short_german_date(target_date)
            messages.extend(f"{formatted_date} {summary}" for summary in waste_types)

        if not messages:
            LOGGER.debug("Manual calendar check found no relevant events for today or tomorrow")
            return

        await self._async_send_notification("\n".join(messages))

    async def async_send_reminder(self, reminder_type: str) -> None:
        """Send the daily reminder if relevant events exist."""
        if not self.entry.options.get(CONF_REMINDERS_ENABLED, DEFAULT_REMINDERS_ENABLED):
            return

        await self.async_request_refresh()

        base_date = dt_util.now().date()
        if not self._is_service_month(base_date.month):
            LOGGER.debug("Skipping %s reminder outside configured service months", reminder_type)
            return

        target_date = base_date + timedelta(days=1) if reminder_type == REMINDER_EVENING else base_date
        matching_events = [
            event for event in self.data.events if event.date == target_date and event.summary in self._active_entries
        ]
        if not matching_events:
            return

        unsent_events = [
            event
            for event in matching_events
            if not self._already_sent(event.date, event.summary, reminder_type)
        ]
        if not unsent_events:
            return

        summaries = list(dict.fromkeys(event.summary for event in unsent_events))
        message = self._build_reminder_message(reminder_type, summaries)
        await self._async_send_notification(message)

        for event in unsent_events:
            self.sent_notifications[self._sent_key(event.date, event.summary, reminder_type)] = datetime.now(UTC).isoformat()

        self._prune_sent_notifications()
        await self.store.async_save({"sent_notifications": self.sent_notifications})

    async def async_rescan(self) -> None:
        """Refresh calendar data now."""
        await self.async_request_refresh()

    async def _async_send_notification(self, message: str) -> None:
        notify_services = self.entry.options.get(CONF_NOTIFY_SERVICES, [])
        if not notify_services:
            LOGGER.warning("No mobile_app notify services configured; skipping notification")
            return

        for service in notify_services:
            try:
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {"message": message, "title": NOTIFICATION_TITLE},
                    blocking=True,
                )
            except HomeAssistantError:
                LOGGER.exception("Failed to call notify.%s", service)

    def _build_reminder_message(self, reminder_type: str, summaries: list[str]) -> str:
        target_date = dt_util.now().date() + timedelta(days=1) if reminder_type == REMINDER_EVENING else dt_util.now().date()
        formatted_date = format_short_german_date(target_date)
        return "\n".join(f"{formatted_date} {summary}" for summary in summaries)

    @property
    def _active_entries(self) -> set[str]:
        return set(self.entry.options.get(CONF_ACTIVE_WASTE_TYPES, []))

    def _waste_types_for_date(self, target_date: date) -> list[str]:
        return list(
            dict.fromkeys(
                event.summary
                for event in self.data.events
                if event.date == target_date and event.summary in self._active_entries
            )
        )

    def _is_service_month(self, month: int) -> bool:
        configured_months = {
            month_name_to_number(self.entry.options.get(CONF_MONTH_1), DEFAULT_MONTH_1),
            month_name_to_number(self.entry.options.get(CONF_MONTH_2), DEFAULT_MONTH_2),
        }
        return month in configured_months

    def _already_sent(self, target_date: date, summary: str, reminder_type: str) -> bool:
        return self._sent_key(target_date, summary, reminder_type) in self.sent_notifications

    @staticmethod
    def _sent_key(target_date: date, summary: str, reminder_type: str) -> str:
        return f"{target_date.isoformat()}|{summary}|{reminder_type}"

    def _prune_sent_notifications(self) -> None:
        cutoff = dt_util.now().date() - timedelta(days=30)
        self.sent_notifications = {
            key: stored_at
            for key, stored_at in self.sent_notifications.items()
            if self._parse_key_date(key) >= cutoff
        }

    @staticmethod
    def _parse_key_date(key: str) -> date:
        return date.fromisoformat(key.split("|", maxsplit=1)[0])


async def scan_calendar_waste_types(hass: HomeAssistant, calendar_entity: str) -> list[str]:
    """Read calendar events and return discovered waste types."""
    events = await async_fetch_calendar_events(hass, calendar_entity, SCAN_DAYS)
    discovered = {
        waste_type
        for event in events
        if (waste_type := detect_waste_type(event.get("summary") or ""))
    }
    return sorted(discovered)


async def scan_calendar_entries(hass: HomeAssistant, calendar_entity: str) -> list[tuple[str, str]]:
    """Read calendar events and return unique summaries."""
    events = await async_fetch_calendar_events(hass, calendar_entity, SCAN_DAYS)
    discovered: dict[str, str] = {}
    for event in events:
        summary = (event.get("summary") or "").strip()
        if not summary:
            continue
        if summary in discovered:
            continue
        discovered[summary] = detect_waste_type(summary) or summary

    return sorted(discovered.items(), key=lambda item: item[0].casefold())


async def async_fetch_calendar_events(hass: HomeAssistant, calendar_entity: str, days: int) -> list[dict]:
    """Fetch raw events from a calendar entity."""
    start = dt_util.now()
    end = start + timedelta(days=days)
    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        "get_events",
        {
            "entity_id": calendar_entity,
            "start_date_time": start,
            "end_date_time": end,
        },
        blocking=True,
        return_response=True,
    )

    if not isinstance(response, dict):
        raise HomeAssistantError("calendar.get_events returned no usable response")

    entity_data = response.get(calendar_entity, {})
    events = entity_data.get("events", [])
    if not isinstance(events, list):
        raise HomeAssistantError("calendar.get_events returned an invalid event list")

    return events
