from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACTIVE_WASTE_TYPES,
    CONF_DISCOVERED_WASTE_TYPES,
    CONF_REMINDERS_ENABLED,
    DEFAULT_REMINDERS_ENABLED,
    DOMAIN,
)
from .entity import WasteReminderEntity
from .utils import slugify


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime.coordinator

    entities: list[SwitchEntity] = [MasterReminderSwitch(coordinator, entry)]
    entities.extend(WasteTypeSwitch(coordinator, entry, waste_type) for waste_type in coordinator.data.discovered_waste_types)
    async_add_entities(entities)

    known_types = set(coordinator.data.discovered_waste_types)

    @callback
    def _add_new_switches() -> None:
        nonlocal known_types
        current_types = set(coordinator.data.discovered_waste_types)
        new_types = sorted(current_types - known_types)
        if not new_types:
            return
        known_types = current_types
        async_add_entities([WasteTypeSwitch(coordinator, entry, waste_type) for waste_type in new_types])

    entry.async_on_unload(coordinator.async_add_listener(_add_new_switches))


class MasterReminderSwitch(WasteReminderEntity, SwitchEntity):
    _attr_name = "Aktiv"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_suggested_object_id = "muell_erinnerungen_aktiv"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_reminders_enabled"

    @property
    def is_on(self) -> bool:
        return self.coordinator.entry.options.get(CONF_REMINDERS_ENABLED, DEFAULT_REMINDERS_ENABLED)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_update_options({CONF_REMINDERS_ENABLED: True})

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_update_options({CONF_REMINDERS_ENABLED: False})


class WasteTypeSwitch(WasteReminderEntity, SwitchEntity):
    def __init__(self, coordinator, entry, waste_type: str) -> None:
        super().__init__(coordinator, entry)
        self.waste_type = waste_type
        slug = slugify(waste_type)
        self._attr_name = waste_type
        self._attr_unique_id = f"{entry.entry_id}_waste_{slug}"
        self._attr_suggested_object_id = f"muell_{slug}"

    @property
    def available(self) -> bool:
        return self.waste_type in self.coordinator.entry.options.get(CONF_DISCOVERED_WASTE_TYPES, [])

    @property
    def is_on(self) -> bool:
        return self.waste_type in self.coordinator.entry.options.get(CONF_ACTIVE_WASTE_TYPES, [])

    async def async_turn_on(self, **kwargs) -> None:
        active = set(self.coordinator.entry.options.get(CONF_ACTIVE_WASTE_TYPES, []))
        active.add(self.waste_type)
        await self.coordinator.async_update_options({CONF_ACTIVE_WASTE_TYPES: sorted(active)})

    async def async_turn_off(self, **kwargs) -> None:
        active = set(self.coordinator.entry.options.get(CONF_ACTIVE_WASTE_TYPES, []))
        active.discard(self.waste_type)
        await self.coordinator.async_update_options({CONF_ACTIVE_WASTE_TYPES: sorted(active)})
