from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change

from .const import (
    CONF_EVENING_ENABLED,
    CONF_EVENING_TIME,
    CONF_MORNING_ENABLED,
    CONF_MORNING_TIME,
    DEFAULT_EVENING_ENABLED,
    DEFAULT_EVENING_TIME,
    DEFAULT_MORNING_ENABLED,
    DEFAULT_MORNING_TIME,
    DOMAIN,
    PLATFORMS,
    REMINDER_EVENING,
    REMINDER_MORNING,
)
from .coordinator import WasteReminderCoordinator
from .utils import normalize_time_value


def _schedule_job(hass: HomeAssistant, coroutine) -> None:
    """Schedule a coroutine safely from time callbacks."""
    hass.add_job(coroutine)


@dataclass
class RuntimeData:
    coordinator: WasteReminderCoordinator
    unsubscribers: list[Callable[[], None]]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = WasteReminderCoordinator(hass, entry)
    await coordinator.async_initialize()
    await coordinator.async_config_entry_first_refresh()

    runtime = RuntimeData(coordinator=coordinator, unsubscribers=[])
    hass.data[DOMAIN][entry.entry_id] = runtime
    entry.async_on_unload(entry.add_update_listener(async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _schedule_reminders(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if runtime := hass.data[DOMAIN].get(entry.entry_id):
        for unsubscribe in runtime.unsubscribers:
            unsubscribe()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    runtime: RuntimeData = hass.data[DOMAIN][entry.entry_id]
    runtime.coordinator.entry = entry
    _schedule_reminders(hass, entry)
    await runtime.coordinator.async_request_refresh()


@callback
def _schedule_reminders(hass: HomeAssistant, entry: ConfigEntry) -> None:
    runtime: RuntimeData = hass.data[DOMAIN][entry.entry_id]
    for unsubscribe in runtime.unsubscribers:
        unsubscribe()
    runtime.unsubscribers = []

    coordinator = runtime.coordinator

    if entry.options.get(CONF_EVENING_ENABLED, DEFAULT_EVENING_ENABLED):
        evening_time = normalize_time_value(
            entry.options.get(CONF_EVENING_TIME), DEFAULT_EVENING_TIME
        )
        runtime.unsubscribers.append(
            async_track_time_change(
                hass,
                lambda now: _schedule_job(hass, coordinator.async_send_reminder(REMINDER_EVENING)),
                hour=evening_time.hour,
                minute=evening_time.minute,
                second=0,
            )
        )

    if entry.options.get(CONF_MORNING_ENABLED, DEFAULT_MORNING_ENABLED):
        morning_time = normalize_time_value(
            entry.options.get(CONF_MORNING_TIME), DEFAULT_MORNING_TIME
        )
        runtime.unsubscribers.append(
            async_track_time_change(
                hass,
                lambda now: _schedule_job(hass, coordinator.async_send_reminder(REMINDER_MORNING)),
                hour=morning_time.hour,
                minute=morning_time.minute,
                second=0,
            )
        )

    runtime.unsubscribers.append(
        async_track_time_change(
            hass,
            lambda now: _schedule_job(hass, coordinator.async_rescan()),
            hour=0,
            minute=5,
            second=0,
        )
    )
