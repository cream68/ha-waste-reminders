from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import _schedule_reminders
from .const import (
    CONF_EVENING_TIME,
    CONF_MORNING_TIME,
    DEFAULT_EVENING_TIME,
    DEFAULT_MORNING_TIME,
    DOMAIN,
)
from .entity import WasteReminderEntity
from .utils import normalize_time_value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EveningReminderTime(runtime.coordinator, entry, hass),
            MorningReminderTime(runtime.coordinator, entry, hass),
        ]
    )


class BaseReminderTime(WasteReminderEntity, TimeEntity):
    def __init__(self, coordinator, entry, hass: HomeAssistant) -> None:
        super().__init__(coordinator, entry)
        self.hass = hass

    async def _async_update_time(self, key: str, value: time) -> None:
        await self.coordinator.async_update_options({key: value})
        _schedule_reminders(self.hass, self.entry)


class EveningReminderTime(BaseReminderTime):
    _attr_name = "Vorabend"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_suggested_object_id = "muell_erinnerung_vorabend"

    def __init__(self, coordinator, entry, hass: HomeAssistant) -> None:
        super().__init__(coordinator, entry, hass)
        self._attr_unique_id = f"{entry.entry_id}_evening_time"

    @property
    def native_value(self) -> time:
        return normalize_time_value(
            self.coordinator.entry.options.get(CONF_EVENING_TIME), DEFAULT_EVENING_TIME
        )

    async def async_set_value(self, value: time) -> None:
        await self._async_update_time(CONF_EVENING_TIME, value)


class MorningReminderTime(BaseReminderTime):
    _attr_name = "Morgens"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_suggested_object_id = "muell_erinnerung_morgens"

    def __init__(self, coordinator, entry, hass: HomeAssistant) -> None:
        super().__init__(coordinator, entry, hass)
        self._attr_unique_id = f"{entry.entry_id}_morning_time"

    @property
    def native_value(self) -> time:
        return normalize_time_value(
            self.coordinator.entry.options.get(CONF_MORNING_TIME), DEFAULT_MORNING_TIME
        )

    async def async_set_value(self, value: time) -> None:
        await self._async_update_time(CONF_MORNING_TIME, value)
