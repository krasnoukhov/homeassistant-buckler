"""Tests for the Buckler cloud client."""

import asyncio
from contextlib import asynccontextmanager
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import aiohttp
import pytest

from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.buckler.api import (
    BASE_URL,
    BucklerApi,
    BucklerError,
    InvalidAuth,
    parse_packet,
)

from . import RELAY_ID, SERIAL, USER, relay

LOGIN_URL = f"{BASE_URL}/api/users/login"
RELAY_URL = f"{BASE_URL}/api/relay/{SERIAL}"


def _login_ok(aioclient_mock, token: str = "tok-1", days: float = 30) -> None:
    aioclient_mock.post(
        LOGIN_URL,
        json={**USER, "token": token, "expireAt": (time.time() + days * 86400) * 1000},
    )


def _api(hass: HomeAssistant) -> BucklerApi:
    return BucklerApi(async_get_clientsession(hass), USER["email"], "secret")


async def test_login_keeps_account_without_token(
    hass: HomeAssistant, aioclient_mock
) -> None:
    _login_ok(aioclient_mock)
    api = _api(hass)
    user = await api.login()

    assert "token" not in user
    assert api.relays == USER["relays"]
    assert aioclient_mock.mock_calls[0][2] == {
        "email": USER["email"],
        "password": "secret",
    }


async def test_bad_password(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.post(
        LOGIN_URL, status=401, json={"message": "Incorrect email or password"}
    )
    with pytest.raises(InvalidAuth, match="Incorrect email or password"):
        await _api(hass).login()


async def test_get_sends_token_and_retries_after_401(
    hass: HomeAssistant, aioclient_mock
) -> None:
    _login_ok(aioclient_mock)
    api = _api(hass)
    await api.login()

    calls = []

    async def relay_response(method, url, data):
        calls.append(aioclient_mock.mock_calls[-1][3]["Authorization"])
        if len(calls) == 1:
            return AiohttpClientMockResponse(
                method, url, status=401, json={"message": "Not valid token"}
            )
        return AiohttpClientMockResponse(method, url, json={"relay": relay()})

    aioclient_mock.get(RELAY_URL, side_effect=relay_response)
    result = await api.relay(SERIAL)

    assert result["_id"] == RELAY_ID
    assert calls == ["tok-1", "tok-1"]
    # Logged in again between the two
    assert sum(1 for c in aioclient_mock.mock_calls if str(c[1]) == LOGIN_URL) == 2


async def test_token_near_expiry_logs_in_again(
    hass: HomeAssistant, aioclient_mock
) -> None:
    _login_ok(aioclient_mock, days=0.5)
    aioclient_mock.get(
        f"{RELAY_URL}/logs?page=1&limit=20", json={"data": [], "length": 0}
    )
    api = _api(hass)
    await api.login()
    assert await api.logs(SERIAL, 20) == []
    assert sum(1 for c in aioclient_mock.mock_calls if str(c[1]) == LOGIN_URL) == 2


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ('0{"sid":"x"}', None),
        ("3", None),
        ("40", ("0", None, None)),
        (
            '42["server:settings:changed",{"ok":true}]',
            ("2", None, ["server:settings:changed", {"ok": True}]),
        ),
        ('4312[{"success":true}]', ("3", 12, [{"success": True}])),
    ],
)
def test_parse_packet(data, expected) -> None:
    assert parse_packet(data) == expected


class FakeWs:
    """Answers with scripted frames, then hangs."""

    def __init__(self, frames: list[str]) -> None:
        self.frames = list(frames)
        self.sent: list[str] = []

    async def send_str(self, data: str) -> None:
        self.sent.append(data)

    async def receive(self):
        if not self.frames:
            await asyncio.sleep(3600)
        return SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=self.frames.pop(0))


async def _save(hass, aioclient_mock, frames):
    _login_ok(aioclient_mock)
    api = _api(hass)
    ws = FakeWs(frames)

    @asynccontextmanager
    async def connect(*args, **kwargs):
        yield ws

    with (
        patch.object(api._session, "ws_connect", connect),
        patch("custom_components.buckler.api.CONFIRM_TIMEOUT", 0.05),
    ):
        result = await api.save_settings(RELAY_ID, "voltage", {"min": 180})
    return result, ws


OPEN = ['0{"sid":"x","pingInterval":25000}', "40"]


async def test_save_waits_for_confirmation(hass: HomeAssistant, aioclient_mock) -> None:
    result, ws = await _save(
        hass,
        aioclient_mock,
        [*OPEN, '431[{"success":true}]', '42["server:settings:changed",{"ok":true}]'],
    )
    assert result is True
    assert [json.loads(s[2:].lstrip("0123456789")) for s in ws.sent] == [
        ["join room", {"relayId": RELAY_ID, "token": "tok-1"}],
        [
            "user:settings:changed",
            {
                "relayId": RELAY_ID,
                "settings": {"voltage": {"min": 180}},
                "token": "tok-1",
            },
        ],
    ]
    assert ws.sent[1].startswith("421[")


async def test_save_without_confirmation(hass: HomeAssistant, aioclient_mock) -> None:
    result, _ = await _save(hass, aioclient_mock, [*OPEN, '431[{"success":true}]'])
    assert result is False


async def test_save_refused(hass: HomeAssistant, aioclient_mock) -> None:
    with pytest.raises(BucklerError, match="refused"):
        await _save(hass, aioclient_mock, [*OPEN, '431[{"success":false}]'])
