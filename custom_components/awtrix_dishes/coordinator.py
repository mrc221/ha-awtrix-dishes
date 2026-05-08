"""DataUpdateCoordinator for AWTRIX Dishes.

Design overview
---------------
* A ``DataUpdateCoordinator`` with ``update_interval = N minutes`` handles
  periodic status updates while the dishwasher is running.  On every tick it
  reads the current phase and remaining time from HA and refreshes two custom
  apps on the AWTRIX display:

    - ``dishes_step``  (icon 17590) – current programme phase
    - ``dishes_time``  (icon 17592) – remaining time + calculated finish time

* Immediate state-change listeners handle two critical events:

    1. Operation state → ``Finished``: instantly shows the persistent
       ``dishes_done`` app (icon 47488) and clears the running apps.
    2. Door state → ``Open`` **while** finished is active: deletes
       ``dishes_done``, treating the opened door as the user's acknowledgement
       that they noticed the programme is done.

* All three custom apps are cleaned up when the appliance becomes inactive,
  when the integration is unloaded, or on HA restart (the coordinator
  recreates them on the next update cycle if still needed).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .awtrix import AwtrixClient
from .const import (
    APP_NAME_DONE,
    APP_NAME_STEP,
    APP_NAME_TIME,
    CONF_AWTRIX_HOST,
    CONF_DOOR_ENTITY,
    CONF_OPERATION_STATE_ENTITY,
    CONF_PROGRAM_PHASE_ENTITY,
    CONF_REMAINING_TIME_ENTITY,
    CONF_TEXT_COLOR,
    CONF_UPDATE_INTERVAL,
    DEFAULT_FINISHED_COLOR,
    DEFAULT_TEXT_COLOR,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    FINISHED_TEXT,
    ICON_FINISHED,
    ICON_PROGRAM_STEP,
    ICON_REMAINING_TIME,
    OP_STATE_FINISHED,
    OP_STATE_RUN,
    PHASE_LABELS_DE,
)

_LOGGER = logging.getLogger(__name__)


# ── Helper functions ───────────────────────────────────────────────────────────


def _tail(state: str | None) -> str:
    """Return the last dot-separated component of a BSH enum value, lower-cased.

    Examples::

        "BSH.Common.EnumType.OperationState.Run" → "run"
        "Run" → "run"
        "on"  → "on"
    """
    if not state:
        return ""
    return state.split(".")[-1].lower()


def _is_running(state: str | None) -> bool:
    return _tail(state) == OP_STATE_RUN


def _is_finished(state: str | None) -> bool:
    return _tail(state) == OP_STATE_FINISHED


def _is_door_open(state: str | None) -> bool:
    """Return True for both binary_sensor (on) and sensor (Open / …DoorState.Open)."""
    t = _tail(state)
    return t in ("open", "on")


def _format_phase(state: str | None) -> str:
    """Convert a Home Connect programme phase state to a German label."""
    key = _tail(state)
    return PHASE_LABELS_DE.get(key, key.capitalize() if key else "")


def _format_remaining(seconds: int) -> str:
    """Format remaining seconds as 'X min' or 'Xh YYmin'."""
    if seconds <= 0:
        return "--"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins:02d}min"


def _end_time(seconds: int) -> str:
    """Return the wall-clock finish time as HH:MM."""
    if seconds <= 0:
        return "--"
    return (datetime.now() + timedelta(seconds=seconds)).strftime("%H:%M")


# ── Data class ────────────────────────────────────────────────────────────────


@dataclass
class DishwasherData:
    """Data published to HA sensors by the coordinator."""

    status: str = "unknown"
    phase: str = ""
    remaining_seconds: int = 0
    end_time: str = ""
    finished_notified: bool = False


# ── Coordinator ───────────────────────────────────────────────────────────────


class AwtrixDishesCoordinator(DataUpdateCoordinator[DishwasherData]):
    """Reads dishwasher state from HA and drives the AWTRIX display."""

    def __init__(self, hass: HomeAssistant, cfg: dict[str, Any]) -> None:
        self._cfg = cfg

        update_interval = timedelta(
            minutes=cfg.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        )
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

        session = async_get_clientsession(hass)
        self._awtrix = AwtrixClient(session, cfg[CONF_AWTRIX_HOST])

        # Internal state flags
        self._finished_notified: bool = False
        self._running_apps_active: bool = False

        # Listener unsubscribe handles
        self._unsub_listeners: list = []

    # ── Config properties ──────────────────────────────────────────────────────

    @property
    def _op_entity(self) -> str:
        return self._cfg[CONF_OPERATION_STATE_ENTITY]

    @property
    def _rem_entity(self) -> str | None:
        v = self._cfg.get(CONF_REMAINING_TIME_ENTITY, "")
        return v or None

    @property
    def _phase_entity(self) -> str | None:
        v = self._cfg.get(CONF_PROGRAM_PHASE_ENTITY, "")
        return v or None

    @property
    def _door_entity(self) -> str | None:
        v = self._cfg.get(CONF_DOOR_ENTITY, "")
        return v or None

    @property
    def _color(self) -> str:
        return self._cfg.get(CONF_TEXT_COLOR, DEFAULT_TEXT_COLOR)

    # ── Listener management ────────────────────────────────────────────────────

    @callback
    def async_setup_listeners(self) -> None:
        """Register HA state-change listeners for immediate reaction."""
        entities: list[str] = [self._op_entity]
        if self._door_entity:
            entities.append(self._door_entity)

        unsub = async_track_state_change_event(
            self.hass, entities, self._on_state_change
        )
        self._unsub_listeners.append(unsub)
        _LOGGER.debug("State-change listeners registered for %s", entities)

    def async_remove_listeners(self) -> None:
        """Unregister all state-change listeners (called on unload)."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    # ── State-change handler ───────────────────────────────────────────────────

    @callback
    def _on_state_change(self, event: Event) -> None:
        """Dispatch incoming state-change events to the right handler."""
        entity_id: str = event.data.get("entity_id", "")
        new_state = event.data.get("new_state")
        if not new_state:
            return

        if entity_id == self._op_entity:
            self._on_operation_change(new_state.state)
        elif entity_id == self._door_entity:
            self._on_door_change(new_state.state)

    def _on_operation_change(self, state_val: str) -> None:
        if _is_finished(state_val) and not self._finished_notified:
            _LOGGER.info("Dishwasher finished — triggering AWTRIX notification")
            self.hass.async_create_task(self._send_finished_notification())
        elif not _is_running(state_val) and not _is_finished(state_val):
            # Inactive / error / ready — clean up any running apps
            if self._running_apps_active:
                _LOGGER.debug("Dishwasher no longer running — removing status apps")
                self.hass.async_create_task(self._cleanup_running_apps())

    def _on_door_change(self, state_val: str) -> None:
        if _is_door_open(state_val) and self._finished_notified:
            _LOGGER.info("Door opened — user acknowledged finished notification")
            self.hass.async_create_task(self._dismiss_finished_notification())

    # ── AWTRIX display actions ─────────────────────────────────────────────────

    async def _send_running_apps(self, phase: str, remaining_sec: int) -> None:
        """Push fresh running-status custom apps to the AWTRIX display."""
        phase_text = phase or "Läuft…"

        if remaining_sec > 0:
            time_text = (
                f"Noch {_format_remaining(remaining_sec)}"
                f" | {_end_time(remaining_sec)} Uhr"
            )
        else:
            time_text = "Läuft…"

        await self._awtrix.set_custom_app(
            APP_NAME_STEP,
            {
                "text": phase_text,
                "icon": ICON_PROGRAM_STEP,
                "color": self._color,
                "scrollSpeed": 50,
            },
        )
        await self._awtrix.set_custom_app(
            APP_NAME_TIME,
            {
                "text": time_text,
                "icon": ICON_REMAINING_TIME,
                "color": self._color,
                "scrollSpeed": 50,
            },
        )
        self._running_apps_active = True

    async def _send_finished_notification(self) -> None:
        """Replace running apps with the persistent 'finished' custom app."""
        await self._cleanup_running_apps()

        success = await self._awtrix.set_custom_app(
            APP_NAME_DONE,
            {
                "text": FINISHED_TEXT,
                "icon": ICON_FINISHED,
                "color": DEFAULT_FINISHED_COLOR,
                "scrollSpeed": 50,
                "repeat": -1,  # loop indefinitely
            },
        )
        if success:
            self._finished_notified = True
            self.async_update_listeners()
        else:
            _LOGGER.warning(
                "Could not send finished notification to AWTRIX — will retry on next poll"
            )

    async def _dismiss_finished_notification(self) -> None:
        """Delete the finished custom app after the door-open acknowledgement."""
        await self._awtrix.delete_custom_app(APP_NAME_DONE)
        self._finished_notified = False
        self.async_update_listeners()
        _LOGGER.info("Finished notification dismissed (door opened)")

    async def _cleanup_running_apps(self) -> None:
        """Remove the running-status custom apps from the AWTRIX display."""
        if self._running_apps_active:
            await self._awtrix.delete_custom_app(APP_NAME_STEP)
            await self._awtrix.delete_custom_app(APP_NAME_TIME)
            self._running_apps_active = False

    # ── Main update cycle ──────────────────────────────────────────────────────

    async def _async_update_data(self) -> DishwasherData:
        """Called by HA every N minutes; refreshes the display while running."""

        # ── Read operation state ────────────────────────────────────────────────
        op_state = self.hass.states.get(self._op_entity)
        if op_state is None or op_state.state in ("unknown", "unavailable"):
            raise UpdateFailed(
                f"Entity '{self._op_entity}' is unavailable. "
                "Is the Home Connect integration running?"
            )
        state_val = op_state.state

        # ── Read optional entities ──────────────────────────────────────────────
        remaining_sec = 0
        if self._rem_entity:
            rem = self.hass.states.get(self._rem_entity)
            if rem and rem.state not in ("unknown", "unavailable", "None"):
                try:
                    remaining_sec = int(float(rem.state))
                except (ValueError, TypeError):
                    pass

        phase = ""
        if self._phase_entity:
            ph = self.hass.states.get(self._phase_entity)
            if ph and ph.state not in ("unknown", "unavailable", "None"):
                phase = _format_phase(ph.state)

        # ── Update AWTRIX display ───────────────────────────────────────────────
        if _is_running(state_val):
            await self._send_running_apps(phase, remaining_sec)
            # If we somehow come back to "running" after finished, reset flag
            if self._finished_notified:
                self._finished_notified = False

        elif _is_finished(state_val):
            # State listener fires immediately; this is a safety net for
            # HA restarts where the listener fires after the first poll.
            if not self._finished_notified:
                await self._send_finished_notification()

        else:
            # Inactive / Ready / Error / Paused / DelayedStart
            await self._cleanup_running_apps()
            # If we missed the door event (e.g. HA was restarted while
            # finished was showing), honour the current door state.
            if self._finished_notified and self._door_entity:
                door = self.hass.states.get(self._door_entity)
                if door and _is_door_open(door.state):
                    await self._dismiss_finished_notification()

        return DishwasherData(
            status=_tail(state_val),
            phase=phase,
            remaining_seconds=remaining_sec,
            end_time=_end_time(remaining_sec) if remaining_sec > 0 else "",
            finished_notified=self._finished_notified,
        )
