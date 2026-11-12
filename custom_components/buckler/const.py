"""Constants for the Buckler integration."""

DOMAIN = "buckler"
UPDATE_INTERVAL = 30
# Log entries read per poll; more than this between polls are missed
LOG_PAGE = 20

# Log codes (from the web app) grouped into event types
EVENT_TYPES_BY_CODE: dict[int, str] = {
    100: "relay_off",
    110: "relay_on",
    120: "overvoltage",
    121: "overvoltage",
    122: "undervoltage",
    123: "residual_current",
    124: "overcurrent",
    125: "overheat",
    126: "overheat",
    127: "power_limit",
    128: "frequency",
    129: "settings_changed",
    **{code: "protection_ok" for code in range(130, 140)},
    140: "overcurrent",
    141: "overcurrent",
    # 151 OVER_CURRENT_OIA seen on a КМР-121-40; 150s look like per-line instant current
    **{code: "overcurrent" for code in range(150, 160)},
    200: "power_lost",
    201: "power_restored",
    202: "power_lost",
    300: "button",
    310: "button",
    **{code: "button" for code in range(320, 325)},
    1001: "turned_on",
    1002: "turned_off",
    1011: "schedule",
    1012: "schedule",
    1021: "offline",
    1022: "online",
}
EVENT_TYPE_OTHER = "other"
EVENT_TYPES = sorted({*EVENT_TYPES_BY_CODE.values(), EVENT_TYPE_OTHER})

# Current trip curve: cloud category -> option
CURVES = {2: "a", 3: "b", 5: "c", 7: "d"}
