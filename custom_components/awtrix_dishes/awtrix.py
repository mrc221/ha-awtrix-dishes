"""AWTRIX 3 HTTP API client for AWTRIX Dishes."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

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
        return await self._post(
            f"/api/custom?name={quote(name)}", json_payload=payload
        )

    async def delete_custom_app(self, name: str) -> bool:
        """Remove a named custom app from the display rotation.

        Per the AWTRIX 3 docs, sending an empty body (NOT a `{}` JSON object)
        tells the firmware to delete the app. Some firmware revisions treat
        ``{}`` as "create an app with no fields", leaving a stale empty app
        on the rotation. We send no body at all to be safe.
        """
        return await self._post(
            f"/api/custom?name={quote(name)}", json_payload=None, send_body=False
        )

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

    async def _post(
        self,
        path: str,
        *,
        json_payload: dict[str, Any] | None,
        send_body: bool = True,
    ) -> bool:
        url = f"{self._base}{path}"
        try:
            kwargs: dict[str, Any] = {
                "timeout": aiohttp.ClientTimeout(total=5),
            }
            if send_body:
                kwargs["json"] = json_payload if json_payload is not None else {}
            else:
                # Force a true empty body so AWTRIX deletes the custom app.
                kwargs["data"] = b""
                kwargs["headers"] = {"Content-Type": "application/json"}

            _LOGGER.debug(
                "AWTRIX POST %s body=%s",
                url,
                kwargs.get("json") if send_body else "<empty>",
            )

            async with self._session.post(url, **kwargs) as resp:
                body = ""
                try:
                    body = (await resp.text())[:200]
                except Exception:  # noqa: BLE001
                    pass
                if resp.status not in (200, 204):
                    _LOGGER.warning(
                        "AWTRIX %s returned HTTP %s body=%r",
                        url,
                        resp.status,
                        body,
                    )
                    return False
                _LOGGER.debug("AWTRIX %s -> %s %r", url, resp.status, body)
                return True
        except aiohttp.ClientConnectorError as exc:
            _LOGGER.error("Cannot reach AWTRIX device at %s: %s", self._base, exc)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.error("AWTRIX request error (%s): %s", url, exc)
        return False
