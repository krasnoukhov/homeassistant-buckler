# homeassistant-buckler

A Home Assistant custom integration (domain `buckler`) for Buckler voltage relays through their cloud, buckler.pw. User docs: [README.md](README.md). This file is for working on the code.

## The cloud

Nothing here is documented by Buckler. It was read from the web app's bundle (`https://buckler.pw/main.<hash>.js`, an Angular app) and checked against a КМР-121-40 in November 2026.

- REST, base `https://buckler.pw`:
  - `POST /api/users/login` `{email, password}` → the account (`_id`, `email`, `relays[{name, serialNumber, _id}]`) plus `token` and `expireAt` (ms, ~30 days). A wrong password is 401 `{"message": "Incorrect email or password"}`.
  - Authenticated calls send `Authorization: <token>`, without `Bearer`. A bad token is 401 `{"message": "Not valid token"}`.
  - `GET /api/relay/<serial>` → `{relay, user}`; `relay.settings` has the protection sections. `relay._id` is what the socket calls `relayId`.
  - `GET /api/relay/<serial>/logs?page=1&limit=N` → `{data, length}`, newest first. Entries: `_id`, `code`, `type`, `message`, `timestamp`, `cp_time`, `info`.
- Socket.IO 2 (Engine.IO 3) at `wss://buckler.pw/socket.io/?EIO=3&transport=websocket`. `api._SocketIo` speaks just enough of it for one short exchange, because python-socketio 5 can't talk to a 2.x server.
  - `join room` `{relayId, token}` first.
  - `user:settings:changed` `{relayId, settings: {<section>: <whole section>}, token}` acks `{success}` when the cloud takes it; `server:settings:changed` `{ok, settings}` follows when the relay confirms.
  - The web app uses many more events (schedules, `user:need:action` for on/off, monitoring); list them with a regex over `socket.(on|emit|fromEvent)("…")` in the bundle.
- Settings units: `current.max` is mA and `power.max` W; the entities show A and kW. `current.category` 2/3/5/7 is curve A/B/C/D. Ranges in `number.py` are the web app's.
- Log codes: the web app's code → message table is the `bg` object in the bundle; `const.EVENT_TYPES_BY_CODE` groups them. `type` strings come from the server and aren't in the bundle.

## Layout

- `custom_components/buckler/api.py`: REST and Socket.IO client, token refresh.
- `coordinator.py`: one poll every 30 s per account (relay, then its log, for each relay); works out new log entries; `async_save` merges a change into the section and sends it.
- `event.py`, `number.py`, `switch.py`, `select.py`, `binary_sensor.py`: entities. Settings entities exist only for fields the relay has.
- `tests/`: pytest with `pytest-homeassistant-custom-component`; the cloud is stubbed in `conftest.py` (entities) or with `aioclient_mock` and a fake websocket (`test_api.py`).

## Commands

```bash
uv venv --python 3.14 && uv pip install -r requirements_test.txt black
.venv/bin/black . --fast && .venv/bin/pytest
docker run --rm --platform linux/amd64 -v "$PWD/custom_components:/github/workspace/custom_components" ghcr.io/home-assistant/hassfest
```

## Releasing

Bump `version` in `manifest.json` and merge to `main`; `release.yml` tags `v<version>` and creates the release. If that run fails, rerun it from the latest `main` with `gh workflow run release.yml`. It skips a version that's already tagged.

`main` needs a pull request with one approval; admins can push directly.
