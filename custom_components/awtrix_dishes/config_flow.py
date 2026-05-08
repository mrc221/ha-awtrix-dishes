"""Config flow for AWTRIX Dishes.

Two-step initial setup:
  1. user     – AWTRIX device IP (tested against /api/stats)
  2. entities – Home Connect entity pickers + tuning options

Options flow allows changing everything except the AWTRIX host.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_AWTRIX_HOST,
    CONF_DOOR_ENTITY,
    CONF_DRYING_TIMER,
    CONF_OPERATION_STATE_ENTITY,
    CONF_PROGRAM_PHASE_ENTITY,
    CONF_REMAINING_TIME_ENTITY,
    CONF_TEXT_COLOR,
    CONF_UPDATE_INTERVAL,
    DEFAULT_DRYING_TIMER,
    DEFAULT_TEXT_COLOR,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


# ── Schema helpers ─────────────────────────────────────────────────────────────


def _entity_selector() -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig())


def _int_selector(minimum: int, maximum: int) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=1,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _entities_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Schema for the 'entities' step and options init step."""
    return vol.Schema(
        {
            vol.Required(
                CONF_OPERATION_STATE_ENTITY,
                default=defaults.get(CONF_OPERATION_STATE_ENTITY, ""),
            ): _entity_selector(),
            vol.Optional(
                CONF_REMAINING_TIME_ENTITY,
                default=defaults.get(CONF_REMAINING_TIME_ENTITY, ""),
            ): _entity_selector(),
            vol.Optional(
                CONF_PROGRAM_PHASE_ENTITY,
                default=defaults.get(CONF_PROGRAM_PHASE_ENTITY, ""),
            ): _entity_selector(),
            vol.Optional(
                CONF_DOOR_ENTITY,
                default=defaults.get(CONF_DOOR_ENTITY, ""),
            ): _entity_selector(),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): _int_selector(1, 60),
            vol.Required(
                CONF_DRYING_TIMER,
                default=defaults.get(CONF_DRYING_TIMER, DEFAULT_DRYING_TIMER),
            ): _int_selector(0, 120),
            vol.Required(
                CONF_TEXT_COLOR,
                default=defaults.get(CONF_TEXT_COLOR, DEFAULT_TEXT_COLOR),
            ): selector.TextSelector(),
        },
        extra=vol.ALLOW_EXTRA,
    )


# ── Validation ─────────────────────────────────────────────────────────────────


def _normalize_host(raw: Any) -> str:
    if not isinstance(raw, str):
        return ""
    host = raw.strip()
    host = host.removeprefix("http://").removeprefix("https://")
    return host.rstrip("/")


def _normalize_options(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_OPERATION_STATE_ENTITY: user_input.get(CONF_OPERATION_STATE_ENTITY, ""),
        CONF_REMAINING_TIME_ENTITY: user_input.get(CONF_REMAINING_TIME_ENTITY, ""),
        CONF_PROGRAM_PHASE_ENTITY: user_input.get(CONF_PROGRAM_PHASE_ENTITY, ""),
        CONF_DOOR_ENTITY: user_input.get(CONF_DOOR_ENTITY, ""),
        CONF_UPDATE_INTERVAL: max(
            1, min(60, int(user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)))
        ),
        CONF_DRYING_TIMER: max(
            0, min(120, int(user_input.get(CONF_DRYING_TIMER, DEFAULT_DRYING_TIMER)))
        ),
        CONF_TEXT_COLOR: user_input.get(CONF_TEXT_COLOR, DEFAULT_TEXT_COLOR) or DEFAULT_TEXT_COLOR,
    }


async def _validate_awtrix(hass, host: str) -> str | None:
    """Test connectivity to the AWTRIX device. Returns error key or None."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"http://{host}/api/stats",
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status != 200:
                _LOGGER.debug("AWTRIX %s returned HTTP %s", host, resp.status)
                return "cannot_connect"
    except asyncio.TimeoutError:
        return "timeout"
    except Exception:  # noqa: BLE001
        return "cannot_connect"
    return None


# ── Config flow ────────────────────────────────────────────────────────────────


class AwtrixDishesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Two-step config flow for AWTRIX Dishes."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection: dict[str, Any] = {}

    # Step 1 — AWTRIX device ───────────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask for the AWTRIX device IP and validate connectivity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = _normalize_host(user_input.get(CONF_AWTRIX_HOST, ""))
            if not host:
                errors["base"] = "invalid_host"
            else:
                try:
                    await self.async_set_unique_id(host.lower())
                    self._abort_if_unique_id_configured()
                    error = await _validate_awtrix(self.hass, host)
                    if error:
                        errors["base"] = error
                    else:
                        self._connection[CONF_AWTRIX_HOST] = host
                        return await self.async_step_entities()
                except AbortFlow:
                    raise
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error validating AWTRIX host")
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AWTRIX_HOST, default="192.168.1.100"
                    ): selector.TextSelector(),
                },
                extra=vol.ALLOW_EXTRA,
            ),
            errors=errors,
        )

    # Step 2 — Home Connect entities & settings ───────────────────────────────

    async def async_step_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select Home Connect entities and configure display options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            op_entity = user_input.get(CONF_OPERATION_STATE_ENTITY, "")
            if not op_entity:
                errors[CONF_OPERATION_STATE_ENTITY] = "missing_entity"
            else:
                options = _normalize_options(user_input)
                return self.async_create_entry(
                    title=f"AWTRIX Dishes ({self._connection[CONF_AWTRIX_HOST]})",
                    data=dict(self._connection),
                    options=options,
                )

        return self.async_show_form(
            step_id="entities",
            data_schema=_entities_schema({}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return AwtrixDishesOptionsFlow()


# ── Options flow ───────────────────────────────────────────────────────────────


class AwtrixDishesOptionsFlow(config_entries.OptionsFlow):
    """Allow changing entity assignments and display settings after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            op_entity = user_input.get(CONF_OPERATION_STATE_ENTITY, "")
            if not op_entity:
                errors[CONF_OPERATION_STATE_ENTITY] = "missing_entity"
            else:
                options = _normalize_options(user_input)
                return self.async_create_entry(title="", data=options)

        # Build defaults from current config.
        try:
            entry = self.config_entry
            current: dict[str, Any] = {**(entry.data or {}), **(entry.options or {})}
        except Exception:  # noqa: BLE001
            current = {}

        return self.async_show_form(
            step_id="init",
            data_schema=_entities_schema(current),
            errors=errors,
        )
