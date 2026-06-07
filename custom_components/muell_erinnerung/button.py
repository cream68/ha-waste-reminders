from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import WasteReminderEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TestNotificationButton(runtime.coordinator, entry),
            CalendarCheckButton(runtime.coordinator, entry),
            RescanCalendarButton(runtime.coordinator, entry),
        ]
    )


class TestNotificationButton(WasteReminderEntity, ButtonEntity):
    _attr_name = "Testnachricht senden"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_object_id = "muell_testbenachrichtigung"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_test_notification"

    async def async_press(self) -> None:
        await self.coordinator.async_send_test_notification()


class CalendarCheckButton(WasteReminderEntity, ButtonEntity):
    _attr_name = "Kalender prüfen"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_object_id = "muell_kalender_pruefen"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_calendar_check"

    async def async_press(self) -> None:
        await self.coordinator.async_send_manual_check_notification()


class RescanCalendarButton(WasteReminderEntity, ButtonEntity):
    _attr_name = "Neu scannen"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_object_id = "muell_kalender_neu_scannen"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_rescan_calendar"

    async def async_press(self) -> None:
        await self.coordinator.async_rescan()
