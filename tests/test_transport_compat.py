"""Transport regressions runnable without installing a Home Assistant server."""

import ast
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from uuid import uuid4


SOURCE = Path(__file__).resolve().parents[1] / "custom_components" / "companion_link"


def load_definitions(filename, namespace, names):
    tree = ast.parse((SOURCE / filename).read_text(encoding="utf-8-sig"))
    definitions = [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)) and node.name in names]
    exec(compile(ast.Module(body=definitions, type_ignores=[]), filename, "exec"), namespace)


def core():
    namespace = dict(
        __package__="transport_regression", asyncio=asyncio, uuid4=uuid4,
        ConfigEntry=object, HomeAssistant=object, callback=lambda function: function,
        timedelta=timedelta, dt_util=SimpleNamespace(utcnow=lambda: datetime.now(timezone.utc)),
        ClientError=OSError, ClientTimeout=lambda **kwargs: kwargs,
        CONF_HOST="host", CONF_ACCESS_TOKEN="access_token", CONF_DEVICE_ID="device_id",
        DOMAIN="companion_link", EVENT_UPDATE="update", EVENT_COMMAND_RESULT="result",
        EVENT_COMMAND="command", POLL_INTERVAL=timedelta(seconds=10), PLATFORMS=["select"],
        _register_services=lambda hass: None,
        async_track_time_interval=lambda *args: lambda: None,
        _LOGGER=SimpleNamespace(debug=lambda *args: None, warning=lambda *args: None, error=lambda *args: None),
    )
    load_definitions("__init__.py", namespace, {"DeviceData", "async_setup_entry", "async_migrate_entry", "async_unload_entry"})
    load_definitions("legacy.py", namespace, {"LegacyDeviceData"})
    return namespace


class Response:
    def __init__(self, data): self.data = data
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    def raise_for_status(self): pass
    async def json(self): return self.data


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ns = core()
        self.events = []
        self.hass = SimpleNamespace(
            data={}, bus=SimpleNamespace(async_fire=lambda name, data: self.events.append((name, data)),
                                         async_listen=lambda *args: lambda: None),
            config_entries=SimpleNamespace(async_update_entry=lambda entry, **kwargs: entry.__dict__.update(kwargs)),
        )
        self.entry = SimpleNamespace(data={"device_id": "sony"}, entry_id="one", version=1)

    async def test_migration_preserves_existing_pairing_and_rejects_future_version(self):
        data = self.entry.data
        self.assertTrue(await self.ns["async_migrate_entry"](self.hass, self.entry))
        self.assertIs(self.entry.data, data)
        self.assertEqual(self.entry.version, 2)
        self.entry.version = 3
        self.assertFalse(await self.ns["async_migrate_entry"](self.hass, self.entry))

    async def test_setup_and_unload_choose_transport_from_existing_pairing(self):
        package = ModuleType("transport_regression")
        package.__path__ = []
        legacy_module = ModuleType("transport_regression.legacy")
        legacy_module.LegacyDeviceData = self.ns["LegacyDeviceData"]
        sys.modules[package.__name__] = package
        sys.modules[legacy_module.__name__] = legacy_module
        try:
            for http in (False, True):
                with self.subTest(http=http):
                    cancelled = []
                    forwarded = []
                    if http:
                        self.entry.data.update(host="10.0.0.20", access_token="test-token")

                    async def forward(entry, platforms): forwarded.extend(platforms)
                    async def unload(entry, platforms): return True

                    self.hass.config_entries.async_forward_entry_setups = forward
                    self.hass.config_entries.async_unload_platforms = unload
                    self.hass.services = SimpleNamespace(async_remove=lambda *args: None)
                    self.hass.bus.async_listen = lambda name, handler: lambda: cancelled.append(name)
                    self.ns["async_track_time_interval"] = lambda *args: lambda: cancelled.append("timer")
                    self.ns["async_get_clientsession"] = lambda hass: SimpleNamespace(get=lambda *args, **kwargs: Response({"device_id": "sony"}))
                    self.assertTrue(await self.ns["async_setup_entry"](self.hass, self.entry))
                    device = self.hass.data["companion_link"]["one"]
                    self.assertEqual(isinstance(device, self.ns["LegacyDeviceData"]), not http)
                    self.assertEqual(forwarded, ["select"])
                    self.assertTrue(await self.ns["async_unload_entry"](self.hass, self.entry))
                    self.assertNotIn("one", self.hass.data["companion_link"])
                    self.assertEqual(len(cancelled), 1 if http else 3)
        finally:
            sys.modules.pop(legacy_module.__name__, None)
            sys.modules.pop(package.__name__, None)

    async def test_legacy_filters_devices_and_matches_concurrent_results(self):
        device = self.ns["LegacyDeviceData"](self.hass, self.entry)
        now = datetime.now(timezone.utc)
        device.async_update(SimpleNamespace(data={"device_id": "other"}, time_fired=now))
        self.assertFalse(device.available)
        device.async_update(SimpleNamespace(data={"device_id": "sony", "input_source": "Android"}, time_fired=now))
        self.assertTrue(device.available)
        first = asyncio.create_task(device._async_send_command("sleep", {}))
        second = asyncio.create_task(device._async_send_command("wake", {}))
        await asyncio.sleep(0)
        first_id, second_id = [event[1]["request_id"] for event in self.events]
        for request_id, success in ((second_id, True), (first_id, False)):
            device.async_command_result(SimpleNamespace(data={"device_id": "sony", "request_id": request_id, "success": success}, time_fired=now))
        self.assertFalse((await first)["success"])
        self.assertTrue((await second)["success"])
        self.assertFalse(device._pending)

    async def test_legacy_unload_cancels_pending_requests(self):
        device = self.ns["LegacyDeviceData"](self.hass, self.entry)
        task = asyncio.create_task(device._async_send_command("sleep", {}))
        await asyncio.sleep(0)
        device.cancel_pending()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertFalse(device._pending)

    async def test_http_poll_and_command_use_paired_credentials(self):
        self.entry.data.update(host="10.0.0.20", access_token="test-token")
        device = self.ns["DeviceData"](self.hass, self.entry)
        calls = []

        def get(url, **kwargs):
            calls.append((url, kwargs))
            return Response({"device_id": "sony", "input_source": "Android", "alarms": [], "rss_sources": []})

        def post(url, **kwargs):
            calls.append((url, kwargs))
            return Response({"command": "input_source", "success": True})

        self.ns["async_get_clientsession"] = lambda hass: SimpleNamespace(get=get, post=post)
        await device.async_poll()
        self.assertTrue(device.available)
        result = await device._async_send_command("input_source", {"source": "HDMI"})
        self.assertTrue(result["success"])
        command_call = next(call for call in calls if call[0].endswith("/api/command"))
        self.assertEqual(command_call[1]["json"], {"command": "input_source", "source": "HDMI"})
        self.assertEqual(command_call[1]["headers"]["Authorization"], "Bearer test-token")

    async def test_http_command_returns_its_own_result_when_shared_state_changes(self):
        self.entry.data.update(host="10.0.0.20", access_token="test-token")
        device = self.ns["DeviceData"](self.hass, self.entry)
        self.ns["async_get_clientsession"] = lambda hass: SimpleNamespace(post=lambda *args, **kwargs: Response({"success": True}))

        async def concurrent_poll(): device.command_result = {"success": False}

        device.async_poll = concurrent_poll
        self.assertTrue((await device._async_send_command("wake", {}))["success"])
        self.assertFalse(device.command_result["success"])


if __name__ == "__main__":
    unittest.main()
