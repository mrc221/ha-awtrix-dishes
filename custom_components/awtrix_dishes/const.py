"""Constants for AWTRIX Dishes."""
from __future__ import annotations

DOMAIN = "awtrix_dishes"
INTEGRATION_VERSION = "1.0.2"

# ── Config entry keys ──────────────────────────────────────────────────────────
CONF_AWTRIX_HOST = "awtrix_host"
CONF_OPERATION_STATE_ENTITY = "operation_state_entity"
CONF_REMAINING_TIME_ENTITY = "remaining_time_entity"
CONF_PROGRAM_PHASE_ENTITY = "program_phase_entity"
CONF_DOOR_ENTITY = "door_entity"
CONF_UPDATE_INTERVAL = "update_interval"   # minutes, while running
CONF_TEXT_COLOR = "text_color"
CONF_DRYING_TIMER = "drying_timer"         # minutes, 0 = disabled

# ── Defaults ───────────────────────────────────────────────────────────────────
DEFAULT_UPDATE_INTERVAL = 5   # minutes
DEFAULT_TEXT_COLOR = "#00BFFF"
DEFAULT_FINISHED_COLOR = "#00FF00"
DEFAULT_DRYING_TIMER = 0      # disabled by default

# ── AWTRIX icon IDs (from requirements) ───────────────────────────────────────
ICON_PROGRAM_STEP = "17590"
ICON_REMAINING_TIME = "17592"
ICON_FINISHED = "47488"
ICON_DRYING = "61038"

# ── AWTRIX custom app names ───────────────────────────────────────────────────
APP_NAME_STEP = "dishes_step"
APP_NAME_TIME = "dishes_time"
APP_NAME_DONE = "dishes_done"
APP_NAME_DRYING = "dishes_drying"

# ── Keys that live in entry.options (user-editable after setup) ───────────────
OPTION_KEYS = (
    CONF_OPERATION_STATE_ENTITY,
    CONF_REMAINING_TIME_ENTITY,
    CONF_PROGRAM_PHASE_ENTITY,
    CONF_DOOR_ENTITY,
    CONF_UPDATE_INTERVAL,
    CONF_TEXT_COLOR,
    CONF_DRYING_TIMER,
)

# ── Home Connect operation state values (short form as seen in HA) ─────────────
OP_STATE_RUN = "run"
OP_STATE_FINISHED = "finished"
OP_STATE_INACTIVE = "inactive"
OP_STATE_PAUSE = "pause"
OP_STATE_DELAYED = "delayedstart"

# ── German display labels for program phases ──────────────────────────────────
# Matched against the normalised last component of the HA state string.
PHASE_LABELS_DE: dict[str, str] = {
    "prewash": "Vorspülen",
    "mainwash": "Hauptwäsche",
    "wash": "Waschen",
    "rinse": "Spülen",
    "finalrinse": "Klarspülen",
    "intermediaterinse": "Zwischenspülen",
    "drying": "Trocknen",
    "dry": "Trocknen",
    "waitingtostart": "Wartet",
    "finished": "Fertig",
    "none": "",
}

# ── Text shown on the finished AWTRIX app ─────────────────────────────────────
FINISHED_TEXT = "Geschirrspüler fertig!"
DRYING_TEXT = "Trocknen"
