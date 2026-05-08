"""AWTRIX 3 HTTP API client for AWTRIX Dishes."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class AwtrixClient:
    """Send notifications and manage custom apps on an AWTRIX 3 / Ulanzi TC001 device."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self._base = f"http://{host}"

    # ── Public API ─────────────────────────────────────────────────────────────

    async def set_custom_app(self, name: str, payload: dict[str, Any]) -> bool:
        """Create or update a named custom app in the display rotation.

        The app persists until explicitly deleted or the device reboots.
        """
        return await self._post(f"/api/custom?name={name}", payload)

    async def delete_custom_app(self, name: str) -> bool:
        """Remove a named custom app from the display rotation.

        Sending an empty JSON object tells AWTRIX 3 to discard the app.
        """
        return await self._post(f"/api/custom?name={name}", {})

    async def is_reachable(self) -> bool:
        """Return True if the AWTRIX device responds on /api/stats."""
        try:
            async with self._session.get(
                f"{self._base}/api/stats",
                timeout=aiohttp.ClientTimeout(total=4),
            ) as resp:
                return resp.status == 200
        except Exception:  # noqa: BLE001
            return False

    # ── Internal ───────────────────────────────────────────────────────────────

    async def _post(self, path: str, payload: dict[str, Any]) -> bool:
        try:
            async with self._session.post(
                f"{self._base}{path}",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status not in (200, 204):
                    _LOGGER.warning(
                        "AWTRIX %s%s returned HTTP %s", self._base, path, resp.status
                    )
                    return False
                return True
        except aiohttp.ClientConnectorError:
            _LOGGER.error("Cannot reach AWTRIX device at %s", self._base)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("AWTRIX request error (%s): %s", path, exc)
        return False
