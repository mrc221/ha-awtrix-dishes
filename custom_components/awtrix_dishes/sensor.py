"""Sensor platform for AWTRIX Dishes."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, INTEGRATION_VERSION
from .coordinator import AwtrixDishesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AwtrixDishesCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            DishwasherStatusSensor(coordinator, entry),
        ]
    )


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="AWTRIX Dishes",
        manufacturer="Siemens / BSH",
        model="Dishwasher Monitor",
        sw_version=INTEGRATION_VERSION,
    )


class DishwasherStatusSensor(CoordinatorEntity[AwtrixDishesCoordinator], SensorEntity):
    """Sensor exposing the current dishwasher / AWTRIX display state."""

    _attr_name = "Dishwasher Status"
    _attr_icon = "mdi:dishwasher"

    def __init__(
        self, coordinator: AwtrixDishesCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str:
        if self.coordinator.data is None:
            return "unknown"
        return self.coordinator.data.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            "phase": data.phase,
            "remaining_seconds": data.remaining_seconds,
            "end_time": data.end_time,
            "finished_notified": data.finished_notified,
        }
