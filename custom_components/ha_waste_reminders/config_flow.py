from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_ACTIVE_WASTE_TYPES,
    CONF_CALENDAR_ENTITY,
    CONF_DISCOVERED_WASTE_TYPES,
    CONF_EVENING_ENABLED,
    CONF_EVENING_TIME,
    CONF_MONTH_1,
    CONF_MONTH_2,
    CONF_MORNING_ENABLED,
    CONF_MORNING_TIME,
    CONF_NOTIFY_SERVICES,
    CONF_REMINDERS_ENABLED,
    DEFAULT_EVENING_ENABLED,
    DEFAULT_EVENING_TIME,
    DEFAULT_MONTH_1,
    DEFAULT_MONTH_2,
    DEFAULT_MORNING_ENABLED,
    DEFAULT_MORNING_TIME,
    DEFAULT_REMINDERS_ENABLED,
    DOMAIN,
    NAME,
)
from .coordinator import scan_calendar_entries
from .utils import month_name, month_name_to_number, month_options

LOGGER = logging.getLogger(__name__)


def _format_service_label(service: str) -> str:
    label = service.removeprefix("mobile_app_").replace("_", " ").strip()
    return label.title() or service


def _calendar_options(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    return [
        selector.SelectOptionDict(value=state.entity_id, label=state.name or state.entity_id)
        for state in sorted(hass.states.async_all("calendar"), key=lambda state: state.name or state.entity_id)
    ]


def _notify_options(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    notify_domain = hass.services.async_services().get("notify", {})
    return [
        selector.SelectOptionDict(value=service, label=_format_service_label(service))
        for service in sorted(notify_domain)
        if service.startswith("mobile_app_")
    ]


def _notify_selector(options: list[selector.SelectOptionDict]) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            multiple=True,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _month_selector(default: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=month, label=month) for month in month_options()],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _month_default(value: object, fallback: int) -> str:
    return month_name(month_name_to_number(value, fallback))


class WasteReminderConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._entry_map: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        calendars = _calendar_options(self.hass)

        if not calendars:
            return self.async_abort(reason="no_calendars")

        if user_input is not None:
            calendar_entity = user_input[CONF_CALENDAR_ENTITY]
            try:
                discovered_entries = await scan_calendar_entries(self.hass, calendar_entity)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Failed to scan calendar %s", calendar_entity)
                errors["base"] = "scan_failed"
            else:
                if not discovered_entries:
                    errors["base"] = "no_waste_types"
                else:
                    self._entry_map = {summary: waste_type for summary, waste_type in discovered_entries}
                    self._config = {
                        CONF_CALENDAR_ENTITY: calendar_entity,
                        CONF_DISCOVERED_WASTE_TYPES: sorted(self._entry_map),
                    }
                    return await self.async_step_waste_types()

        schema = vol.Schema(
            {
                vol.Required(CONF_CALENDAR_ENTITY): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=calendars, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_waste_types(self, user_input: dict[str, Any] | None = None):
        discovered_entries = sorted(self._entry_map)
        if user_input is not None:
            selected_entries = user_input.get(CONF_ACTIVE_WASTE_TYPES, [])
            self._config[CONF_ACTIVE_WASTE_TYPES] = sorted(selected_entries)
            return await self.async_step_settings()

        options = [
            selector.SelectOptionDict(value=summary, label=summary)
            for summary in discovered_entries
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_ACTIVE_WASTE_TYPES, default=discovered_entries): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="waste_types", data_schema=schema)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._config.update(user_input)
            return await self.async_step_notify_devices()

        schema = vol.Schema(
            {
                vol.Required(CONF_REMINDERS_ENABLED, default=DEFAULT_REMINDERS_ENABLED): bool,
                vol.Required(CONF_EVENING_ENABLED, default=DEFAULT_EVENING_ENABLED): bool,
                vol.Required(CONF_EVENING_TIME, default=DEFAULT_EVENING_TIME): selector.TimeSelector(),
                vol.Required(CONF_MORNING_ENABLED, default=DEFAULT_MORNING_ENABLED): bool,
                vol.Required(CONF_MORNING_TIME, default=DEFAULT_MORNING_TIME): selector.TimeSelector(),
                vol.Required(CONF_MONTH_1, default=month_name(DEFAULT_MONTH_1)): _month_selector(month_name(DEFAULT_MONTH_1)),
                vol.Required(CONF_MONTH_2, default=month_name(DEFAULT_MONTH_2)): _month_selector(month_name(DEFAULT_MONTH_2)),
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    async def async_step_notify_devices(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._config[CONF_NOTIFY_SERVICES] = sorted(user_input.get(CONF_NOTIFY_SERVICES, []))
            self._config.setdefault(CONF_REMINDERS_ENABLED, DEFAULT_REMINDERS_ENABLED)
            return self.async_create_entry(title=NAME, data={}, options=self._config)

        options = _notify_options(self.hass)
        schema = vol.Schema(
            {
                vol.Optional(CONF_NOTIFY_SERVICES, default=[]): _notify_selector(options)
            }
        )
        return self.async_show_form(step_id="notify_devices", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return WasteReminderOptionsFlow(config_entry)


class WasteReminderOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        super().__init__(config_entry)
        self._options = dict(config_entry.options)
        self._entry_map: dict[str, str] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return await self.async_step_calendar()

    async def async_step_calendar(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        calendars = _calendar_options(self.hass)

        if not calendars:
            return self.async_abort(reason="no_calendars")

        if user_input is not None:
            calendar_entity = user_input[CONF_CALENDAR_ENTITY]
            try:
                discovered_entries = await scan_calendar_entries(self.hass, calendar_entity)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Failed to rescan calendar %s", calendar_entity)
                errors["base"] = "scan_failed"
            else:
                if not discovered_entries:
                    errors["base"] = "no_waste_types"
                else:
                    self._entry_map = {summary: waste_type for summary, waste_type in discovered_entries}
                    self._options[CONF_CALENDAR_ENTITY] = calendar_entity
                    self._options[CONF_DISCOVERED_WASTE_TYPES] = sorted(self._entry_map)
                    active = set(self._options.get(CONF_ACTIVE_WASTE_TYPES, []))
                    self._options[CONF_ACTIVE_WASTE_TYPES] = sorted(
                        summary for summary, waste_type in self._entry_map.items() if summary in active or waste_type in active
                    )
                    return await self.async_step_waste_types()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CALENDAR_ENTITY,
                    default=self._options.get(CONF_CALENDAR_ENTITY),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=calendars, mode=selector.SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="calendar", data_schema=schema, errors=errors)

    async def async_step_waste_types(self, user_input: dict[str, Any] | None = None):
        if not self._entry_map and (calendar_entity := self._options.get(CONF_CALENDAR_ENTITY)):
            discovered_entries = await scan_calendar_entries(self.hass, calendar_entity)
            self._entry_map = {summary: waste_type for summary, waste_type in discovered_entries}

        discovered_entries = sorted(self._entry_map)
        if user_input is not None:
            selected_entries = user_input.get(CONF_ACTIVE_WASTE_TYPES, [])
            self._options[CONF_ACTIVE_WASTE_TYPES] = sorted(selected_entries)
            return await self.async_step_settings()

        active_entries = set(self._options.get(CONF_ACTIVE_WASTE_TYPES, []))
        default_entries = [summary for summary, waste_type in self._entry_map.items() if summary in active_entries or waste_type in active_entries]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ACTIVE_WASTE_TYPES,
                    default=default_entries or discovered_entries,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value=value, label=value) for value in discovered_entries],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="waste_types", data_schema=schema)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_notify_devices()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_REMINDERS_ENABLED,
                    default=self._options.get(CONF_REMINDERS_ENABLED, DEFAULT_REMINDERS_ENABLED),
                ): bool,
                vol.Required(
                    CONF_EVENING_ENABLED,
                    default=self._options.get(CONF_EVENING_ENABLED, DEFAULT_EVENING_ENABLED),
                ): bool,
                vol.Required(
                    CONF_EVENING_TIME,
                    default=self._options.get(CONF_EVENING_TIME, DEFAULT_EVENING_TIME),
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_MORNING_ENABLED,
                    default=self._options.get(CONF_MORNING_ENABLED, DEFAULT_MORNING_ENABLED),
                ): bool,
                vol.Required(
                    CONF_MORNING_TIME,
                    default=self._options.get(CONF_MORNING_TIME, DEFAULT_MORNING_TIME),
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_MONTH_1,
                    default=_month_default(self._options.get(CONF_MONTH_1), DEFAULT_MONTH_1),
                ): _month_selector(_month_default(self._options.get(CONF_MONTH_1), DEFAULT_MONTH_1)),
                vol.Required(
                    CONF_MONTH_2,
                    default=_month_default(self._options.get(CONF_MONTH_2), DEFAULT_MONTH_2),
                ): _month_selector(_month_default(self._options.get(CONF_MONTH_2), DEFAULT_MONTH_2)),
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    async def async_step_notify_devices(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._options[CONF_NOTIFY_SERVICES] = sorted(user_input.get(CONF_NOTIFY_SERVICES, []))
            return self.async_create_entry(data=self._options)

        notify_options = _notify_options(self.hass)
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NOTIFY_SERVICES,
                    default=self._options.get(CONF_NOTIFY_SERVICES, []),
                ): _notify_selector(notify_options)
            }
        )
        return self.async_show_form(step_id="notify_devices", data_schema=schema)
