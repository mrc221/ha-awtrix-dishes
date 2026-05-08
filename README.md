# AWTRIX Dishes

[![HACS Custom Repository](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

A HACS custom integration for Home Assistant that shows your **Siemens / BSH dishwasher status** on an **Ulanzi TC001 / AWTRIX 3** pixel display. It reads data from the official [Home Connect integration](https://www.home-assistant.io/integrations/home_connect/) and drives three custom apps on your AWTRIX device.

---

## Features

| When | What the display shows |
|------|------------------------|
| **Running** | 🫧 *Programme step* (e.g. "Hauptwäsche") — icon `17590` |
| **Running** | ⏱ *Remaining time + finish time* (e.g. "Noch 42 min \| 15:30 Uhr") — icon `17592` |
| **Finished** | 🍽 *"Geschirrspüler fertig!"* — icon `47488` stays until acknowledged |
| **Acknowledged** | ✅ Display cleared — opening the dishwasher door is the acknowledgement signal |

* Refresh interval is **fully configurable** (default: every 5 minutes while running).
* Both custom AWTRIX apps (`dishes_step` + `dishes_time`) appear in the normal app rotation — they replace the clock slot.
* The *finished* app loops indefinitely until you open the door; once acknowledged, the display returns to normal.
* All apps are cleaned up on HA restart (and recreated on the next poll if still relevant).

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

4. Configure the **refresh interval** (minutes) and **text colour**.

---

## How acknowledgement works

When the programme finishes, the AWTRIX display shows "Geschirrspüler fertig!" persistently (icon `47488`).  
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
| `Drying` / `…ProgramPhase.Drying` | Trocknen |
| `WaitingToStart` / `…ProgramPhase.WaitingToStart` | Wartet |

---

## Sensor

The integration creates a `sensor.dishwasher_status` entity with these attributes:

| Attribute | Description |
|-----------|-------------|
| `status` | Current operation state (e.g. `run`, `finished`, `inactive`) |
| `phase` | Current programme phase (German label) |
| `remaining_seconds` | Remaining time in seconds |
| `end_time` | Estimated finish time (HH:MM) |
| `finished_notified` | Whether the finished AWTRIX app is currently active |

---

## License

MIT