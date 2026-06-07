from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MONTH_1, CONF_MONTH_2, DEFAULT_MONTH_1, DEFAULT_MONTH_2, DOMAIN
from .entity import WasteReminderEntity
from .utils import month_name, month_name_to_number, month_options


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ServiceMonthSelect(runtime.coordinator, entry, CONF_MONTH_1, DEFAULT_MONTH_1, "Dienstmonat 1", "muell_monat_1"),
            ServiceMonthSelect(runtime.coordinator, entry, CONF_MONTH_2, DEFAULT_MONTH_2, "Dienstmonat 2", "muell_monat_2"),
        ]
    )


class ServiceMonthSelect(WasteReminderEntity, SelectEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = month_options()

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        option_key: str,
        default_value: int,
        name: str,
        object_id: str,
    ) -> None:
        super().__init__(coordinator, entry)
        self.option_key = option_key
        self.default_value = default_value
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{option_key}"
        self._attr_suggested_object_id = object_id

    @property
    def current_option(self) -> str:
        stored = self.coordinator.entry.options.get(self.option_key)
        if isinstance(stored, str) and stored in self.options:
            return stored
        return month_name(month_name_to_number(stored, self.default_value))

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_update_options({self.option_key: option})
