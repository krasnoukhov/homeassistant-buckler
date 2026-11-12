# Home Assistant Buckler integration

Brings [Buckler (Баклер)](https://bakler.com.ua) voltage relays into Home Assistant through their cloud, [buckler.pw](https://buckler.pw): the event log, including why the relay cut the power, and the protection settings.

Buckler relays can also publish live readings (voltage, current, power, energy) over MQTT, with their own Home Assistant discovery. This integration doesn't repeat those: use the relay's MQTT for live data and this for what MQTT doesn't carry.

## Highlights

### Know why the power went out

Every new entry in the relay's log fires the **Log** event entity, so you can get a notification or log it the moment the relay trips:

| Event type | Log codes | What happened |
|---|---|---|
| `undervoltage` | 122 | Voltage fell below the minimum |
| `overvoltage` | 120, 121 | Voltage rose above the maximum |
| `overcurrent` | 124, 140, 141, 150–159 | Current above the limit |
| `power_limit`, `frequency`, `overheat`, `residual_current` | 127, 128, 125–126, 123 | Other protections |
| `power_lost`, `power_restored` | 200–202 | The relay itself lost or got back its supply |
| `relay_off`, `relay_on`, `turned_off`, `turned_on`, `button` | 100, 110, 1001–1002, 300–324 | Switching |
| `offline`, `online` | 1021, 1022 | Cloud connection |
| `settings_changed`, `protection_ok`, `schedule` | 129, 130–139, 1011–1012 | Housekeeping |
| `other` | anything else | Firmware and system entries |

Each event carries the log's `code`, `type` (e.g. `DOWN_VRMS`), `message` (Ukrainian, as in the app) and `time`. The log is read every 30 seconds. Entries already there when Home Assistant starts don't fire.

### Change protection settings

Numbers, switches and a select for what the Buckler app's settings page has: turn-on delay, voltage minimum, maximum and hysteresis, current maximum and trip curve, power maximum, frequency minimum and maximum, device temperature maximum, each protection on or off, and auto turn-on. Ranges match the app. A change goes to the relay through the cloud and the entity shows it once the cloud has it. If the relay doesn't confirm within 20 seconds, Home Assistant logs a warning.

### Set it up from the UI

Settings → Devices & services → Add integration → **Buckler**, then log in with your buckler.pw email and password. Every relay on the account becomes a device. Telegram sign-in isn't supported.

## Installation

Add `https://github.com/krasnoukhov/homeassistant-buckler` to HACS as a custom repository (category: Integration), install **Buckler** and restart Home Assistant.

## Example automation

```yaml
alias: Buckler cut the power
triggers:
  - trigger: state
    entity_id: event.iflh_log
    not_from: unavailable
conditions:
  - condition: template
    value_template: >
      {{ trigger.to_state.attributes.event_type in
         ['undervoltage', 'overvoltage', 'overcurrent', 'power_limit', 'frequency', 'overheat'] }}
actions:
  - action: notify.notify
    data:
      title: Buckler
      message: "{{ trigger.to_state.attributes.message }}"
```

## Not covered yet

Turning the relay on and off, schedules, energy statistics and tariffs. The relay switch is on MQTT already.
