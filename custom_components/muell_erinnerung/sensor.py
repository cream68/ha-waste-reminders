from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import WasteReminderEntity
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextPickupSensor(runtime.coordinator, entry),
            UpcomingPickupsSensor(runtime.coordinator, entry),
        ]
    )


class NextPickupSensor(WasteReminderEntity, SensorEntity):
    _attr_name = "Nächste"
    _attr_unique_id = None
    _attr_suggested_object_id = "muell_naechste_abholung"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_pickup"

    @property
    def native_value(self) -> str:
        if (event := self.coordinator.next_relevant_event()) is None:
            return "Keine relevante Abholung"

        today = dt_util.now().date()
        if event.date == today:
            prefix = "Heute"
        elif event.date == today + timedelta(days=1):
            prefix = "Morgen"
        else:
            prefix = event.date.isoformat()
        return f"{prefix}: {event.waste_type}"

    @property
    def extra_state_attributes(self) -> dict:
        if (event := self.coordinator.next_relevant_event()) is None:
            return {}

        today = dt_util.now().date()
        return {
            "date": event.date.isoformat(),
            "waste_type": event.waste_type,
            "summary": event.summary,
            "days_until": (event.date - today).days,
            "calendar_event_uid": event.uid,
        }


class UpcomingPickupsSensor(WasteReminderEntity, SensorEntity):
    _attr_name = "Termine"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_object_id = "muell_naechste_termine"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_upcoming_pickups"

    @property
    def native_value(self) -> str:
        count = len(self.coordinator.upcoming_relevant_events())
        return f"{count} Termine"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "events": [
                {
                    "date": event.date.isoformat(),
                    "type": event.waste_type,
                    "summary": event.summary,
                    "uid": event.uid,
                }
                for event in self.coordinator.upcoming_relevant_events()
            ]
        }
