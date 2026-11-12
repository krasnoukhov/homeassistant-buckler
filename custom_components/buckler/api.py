"""Client for the Buckler cloud at buckler.pw."""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import math
import time
from typing import Any
from urllib.parse import quote

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://buckler.pw"
# The server runs Socket.IO 2 (Engine.IO 3)
SOCKET_URL = "wss://buckler.pw/socket.io/?EIO=3&transport=websocket"
TIMEOUT = aiohttp.ClientTimeout(total=20)
# Log in again this long before the token runs out (tokens last ~30 days)
TOKEN_MARGIN = 24 * 3600
CONFIRM_TIMEOUT = 20


class BucklerError(Exception):
    """The cloud failed or answered something unexpected."""


class InvalidAuth(BucklerError):
    """Wrong email or password."""


class BucklerApi:
    """Logs in with email and password and reads or changes relays."""

    def __init__(
        self, session: aiohttp.ClientSession, email: str, password: str
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()
        # The login response: _id, username, email, relays, ...
        self.user: dict[str, Any] = {}

    async def login(self) -> dict[str, Any]:
        """Log in and return the account."""
        try:
            async with self._session.post(
                f"{BASE_URL}/api/users/login",
                json={"email": self._email, "password": self._password},
                timeout=TIMEOUT,
            ) as resp:
                if resp.status in (400, 401, 403, 404):
                    raise InvalidAuth(await _message(resp))
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BucklerError(f"Login failed: {err}") from err

        if not isinstance(data, dict) or not data.get("token"):
            raise BucklerError("Login returned no token")
        self._token = data["token"]
        expire_at = data.get("expireAt")
        # Without an expiry, rely on a 401 to log in again
        self._expires_at = float(expire_at) / 1000 if expire_at else math.inf
        self.user = {k: v for k, v in data.items() if k not in ("token", "expireAt")}
        return self.user

    @property
    def relays(self) -> list[dict[str, Any]]:
        """The account's relays: name, serialNumber, _id."""
        return self.user.get("relays") or []

    async def relay(self, serial: str) -> dict[str, Any]:
        """A relay with its settings."""
        data = await self._get(f"/api/relay/{quote(serial)}")
        if not isinstance(data, dict) or not isinstance(data.get("relay"), dict):
            raise BucklerError(f"No relay {serial} in the answer")
        return data["relay"]

    async def logs(self, serial: str, limit: int) -> list[dict[str, Any]]:
        """The relay's event log, newest first."""
        data = await self._get(f"/api/relay/{quote(serial)}/logs?page=1&limit={limit}")
        return (data or {}).get("data") or []

    async def save_settings(
        self, relay_id: str, section: str, values: dict[str, Any]
    ) -> bool:
        """Send one settings section. True once the relay confirms it.

        The web app does this over Socket.IO, not REST.
        """
        token = await self._valid_token()
        try:
            async with self._session.ws_connect(SOCKET_URL, timeout=TIMEOUT) as ws:
                sio = _SocketIo(ws)
                await sio.connected()
                await sio.emit("join room", {"relayId": relay_id, "token": token})
                ack = await sio.call(
                    "user:settings:changed",
                    {
                        "relayId": relay_id,
                        "settings": {section: values},
                        "token": token,
                    },
                )
                if not isinstance(ack, dict) or not ack.get("success"):
                    raise BucklerError(f"Cloud refused the settings: {ack}")
                try:
                    async with asyncio.timeout(CONFIRM_TIMEOUT):
                        data = await sio.wait_event("server:settings:changed")
                except TimeoutError:
                    return False
                return bool(isinstance(data, dict) and data.get("ok"))
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BucklerError(f"Saving settings failed: {err}") from err

    async def _valid_token(self) -> str:
        async with self._lock:
            if not self._token or time.time() > self._expires_at - TOKEN_MARGIN:
                await self.login()
            assert self._token
            return self._token

    async def _get(self, path: str) -> Any:
        for attempt in range(2):
            token = await self._valid_token()
            try:
                async with self._session.get(
                    f"{BASE_URL}{path}",
                    headers={"Authorization": token},
                    timeout=TIMEOUT,
                ) as resp:
                    if resp.status == 401:
                        if attempt == 0:
                            self._token = None
                            continue
                        raise BucklerError(f"{path}: {await _message(resp)}")
                    resp.raise_for_status()
                    return await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError) as err:
                raise BucklerError(f"{path}: {err}") from err
        return None


async def _message(resp: aiohttp.ClientResponse) -> str:
    try:
        return (await resp.json(content_type=None))["message"]
    except (ValueError, KeyError, TypeError, aiohttp.ClientError):
        return f"HTTP {resp.status}"


def parse_packet(data: str) -> tuple[str, int | None, Any] | None:
    """Socket.IO packet inside an Engine.IO message: (type, ack id, payload)."""
    # "4" is an Engine.IO message; the rest (open, ping, pong) carries nothing for us
    if len(data) < 2 or data[0] != "4":
        return None
    rest = data[2:]
    digits = 0
    while digits < len(rest) and rest[digits].isdigit():
        digits += 1
    ack_id = int(rest[:digits]) if digits else None
    body = rest[digits:]
    return data[1], ack_id, json.loads(body) if body else None


class _SocketIo:
    """Just enough Socket.IO 2 for a short session: no pings, no reconnects."""

    def __init__(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        self._ws = ws
        self._ids = itertools.count(1)
        self._events: list[tuple[str, Any]] = []

    async def connected(self) -> None:
        while (await self._next())[0] != "0":
            pass

    async def emit(self, event: str, data: Any) -> None:
        await self._ws.send_str("42" + json.dumps([event, data]))

    async def call(self, event: str, data: Any) -> Any:
        ack_id = next(self._ids)
        await self._ws.send_str(f"42{ack_id}" + json.dumps([event, data]))
        while True:
            kind, got_id, payload = await self._next()
            if kind == "3" and got_id == ack_id:
                return payload[0] if payload else None

    async def wait_event(self, event: str) -> Any:
        while True:
            for i, (name, data) in enumerate(self._events):
                if name == event:
                    del self._events[i]
                    return data
            await self._next()

    async def _next(self) -> tuple[str, int | None, Any]:
        while True:
            msg = await self._ws.receive()
            if msg.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.ERROR,
            ):
                raise BucklerError("Socket closed")
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            packet = parse_packet(msg.data)
            if packet is None:
                continue
            kind, _, payload = packet
            if kind == "4":
                raise BucklerError(f"Socket error: {payload}")
            if kind == "2" and isinstance(payload, list) and payload:
                self._events.append(
                    (payload[0], payload[1] if len(payload) > 1 else None)
                )
            return packet
