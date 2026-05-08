# AWTRIX Dishes

[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

A HACS custom integration for Home Assistant that shows your **Siemens / BSH dishwasher status** on an **Ulanzi TC001 / AWTRIX 3** pixel display. It reads data from the official [Home Connect integration](https://www.home-assistant.io/integrations/home_connect/) and drives custom apps on your AWTRIX device.

---

## Features

| When | What the display shows |
|------|------------------------|
| **Running** | 🫧 *Programme step* (e.g. "Hauptwäsche") — icon `17590` |
| **Running** | ⏱ *Remaining time + finish time* (e.g. "Noch 42 min \| 15:30 Uhr") — icon `17592` |
| **Drying** | 💨 *Drying countdown* (e.g. "Trocknen 38 min") — icon `61038` (optional, see below) |
| **Finished** | 🍽 *"Geschirrspüler fertig!"* — icon `47488` stays until acknowledged |
| **Acknowledged** | ✅ Display cleared — opening the dishwasher door is the acknowledgement signal |

* Refresh interval is **fully configurable** (default: every 5 minutes while running).
* Custom AWTRIX apps (`dishes_step`, `dishes_time`, `dishes_drying`, `dishes_done`) appear in the normal app rotation — they replace the clock slot.
* Optional **drying timer**: after the programme finishes a configurable countdown (default: disabled) is shown before the "finished" notification appears. Useful for dishwashers that need extra drying time.
* The *finished* app loops indefinitely until you open the door; once acknowledged, the display returns to normal.
* All apps are cleaned up on HA restart (and recreated on the next poll if still relevant).
* The **remaining time entity** can be either a numeric sensor (seconds remaining) or a `device_class: timestamp` sensor (end datetime) — both are handled automatically.

---

## Requirements

* Home Assistant 2024.1 or newer
* [Home Connect integration](https://www.home-assistant.io/integrations/home_connect/) installed and your dishwasher connected
* AWTRIX 3 firmware on your Ulanzi TC001 (or any compatible AWTRIX 3 device)

---

## Installation via HACS

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/mrc221/ha-awtrix-dishes` as an **Integration**.
3. Search for *AWTRIX Dishes* and install it.
4. Restart Home Assistant.

---

## Setup

1. Go to **Settings → Devices & Services → Add Integration → AWTRIX Dishes**.
2. **Step 1 – AWTRIX Device**: Enter the IP address of your Ulanzi TC001 (e.g. `192.168.1.42`). The integration will test the connection.
3. **Step 2 – Home Connect Entities**: Select the entities created by the Home Connect integration:

| Field | Example entity | Required |
|-------|---------------|----------|
| Operation State | `sensor.dishwasher_operation_state` | ✅ |
| Remaining Time | `sensor.dishwasher_remaining_program_time` | ○ |
| Programme Phase | `sensor.dishwasher_program_phase` | ○ |
| Door | `binary_sensor.dishwasher_door` | ○ (needed for auto-acknowledgement) |

> **Tip**: Open *Developer Tools → States* in HA and search for your appliance name to find the exact entity IDs.

4. Configure the **refresh interval** (minutes), **drying timer** (minutes, 0 = disabled) and **text colour**.

---

## Drying Timer

Some dishwashers keep the door closed after the programme ends to allow passive drying. Set the **drying timer** (in minutes) to show a countdown on the display before the "finished" notification appears. During the countdown the display shows "Trocknen X min" (icon `61038`). Set to `0` (default) to disable and show the "finished" notification immediately.

---

## How acknowledgement works

When the programme finishes (and the optional drying timer has elapsed), the AWTRIX display shows "Geschirrspüler fertig!" persistently (icon `47488`).  
As soon as you **open the dishwasher door**, the integration detects the door state change and automatically clears the notification — no button press needed.

If you did not configure a door entity, the finished notification stays until the next time the dishwasher becomes inactive (e.g. power-cycled) or until you reload the integration.

---

## Home Connect state values

The integration handles both short (`Run`, `Finished`) and full BSH enum values (`BSH.Common.EnumType.OperationState.Run`).  
Programme phases are translated to German:

| HA state | Display |
|----------|---------|
| `Prewash` / `…ProgramPhase.Prewash` | Vorspülen |
| `MainWash` / `…ProgramPhase.MainWash` | Hauptwäsche |
| `Rinse` / `…ProgramPhase.Rinse` | Spülen |
| `FinalRinse` / `…ProgramPhase.FinalRinse` | Klarspülen |
| `IntermediateRinse` / `…ProgramPhase.IntermediateRinse` | Zwischenspülen |
| `Drying` / `…ProgramPhase.Drying` | Trocknen |
| `WaitingToStart` / `…ProgramPhase.WaitingToStart` | Wartet |

---

## Sensor

The integration creates a `sensor.awtrix_dishes_dishwasher_status` entity with these attributes:

| Attribute | Description |
|-----------|-------------|
| `status` | Current operation state (e.g. `run`, `finished`, `inactive`) |
| `phase` | Current programme phase (German label) |
| `remaining_seconds` | Remaining time in seconds |
| `end_time` | Estimated finish time (HH:MM) |
| `finished_notified` | Whether the finished AWTRIX app is currently active |

---

## Troubleshooting

If nothing appears on your AWTRIX display:

1. **Enable debug logging** in `configuration.yaml` and reload the integration:
   ```yaml
   logger:
     logs:
       custom_components.awtrix_dishes: debug
   ```
   Each AWTRIX HTTP request and its response are logged. Look for `AWTRIX POST` lines.
2. **Verify the AWTRIX HTTP API is reachable** from Home Assistant — open `http://<awtrix-ip>/api/stats` in a browser.
3. **Make sure the icon IDs are present on the device.** Open the AWTRIX web UI → *Icons* and download the IDs `17590`, `17592`, `47488` (and `61038` if you use the drying timer).
4. **Confirm the operation-state entity** reports `run`, `finished`, etc. — not `unknown` or `unavailable`. Some Home Connect dishwashers don't expose a *program phase* sensor; the integration falls back to "Laeuft" in that case, which is normal.

---

## Changelog

### 1.0.3
* **Fix**: Push the running-status apps to AWTRIX **immediately** when the dishwasher starts, instead of waiting for the next poll interval (could be up to 5 minutes).
* **Fix**: `delete_custom_app` now sends a truly empty body. Some AWTRIX 3 firmware revisions interpreted the previous `{}` payload as "create empty app", leaving stale entries on the rotation.
* **Fix**: Replaced the unicode ellipsis `…` with ASCII `...`/plain text — the AWTRIX 3 default font does not render U+2026 reliably.
* **Improvement**: Custom apps now include `duration`, `scrollSpeed` and a generous `lifetime` so they survive at least one poll cycle and self-clean if Home Assistant goes away.
* **Improvement**: Verbose debug logging for every AWTRIX HTTP request — URL, payload and response are now logged at `DEBUG` level.

### 1.0.2
* **Fix**: The remaining time entity now supports both numeric sensors (seconds) and `device_class: timestamp` sensors (ISO 8601 end datetime). Previously, timestamp-type sensors silently yielded `remaining_seconds = 0`.

### 1.0.1
* Initial public release.
* Drying timer: optional post-program countdown before the "finished" notification.
* Auto-acknowledgement via door entity.
* German program phase labels.

---

## License

MIT