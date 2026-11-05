"""Optics control capability, validation and command failure regressions."""
import ast
from types import SimpleNamespace
import unittest
from test_transport_compat import SOURCE, load_definitions

class Base:
    def __init__(self, coordinator, *args): self.coordinator = coordinator
    @property
    def available(self): return self.coordinator.available

class OpticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.calls = []
        self.success = True
        async def send(command, values):
            self.calls.append((command, values))
            return {"success": self.success, "message": "device rejected"}
        self.data = SimpleNamespace(available=True, values={"projector_control_available": True,
            "projector_keystone": 15}, _async_send_command=send)
        self.ns = dict(CompanionLinkEntity=Base, NumberEntity=type("NumberEntity", (), {}),
            NumberMode=SimpleNamespace(BOX="box"), ButtonEntity=type("ButtonEntity", (), {}),
            HomeAssistantError=ValueError)
        load_definitions("number.py", self.ns, {"CompanionLinkKeystone"})
        load_definitions("button.py", self.ns, {"CompanionLinkProjectorButton", "CompanionLinkAutoFocusButton"})

    async def test_signed_zero_values_and_rejection_without_truncation(self):
        entity = self.ns["CompanionLinkKeystone"](self.data)
        self.assertEqual(entity.native_value, 15)
        for value in [-15, 0, 15]: await entity.async_set_native_value(value)
        self.assertEqual(self.calls, [("keystone", {"value": n}) for n in [-15, 0, 15]])
        for value in [-16, 16, 1.5, float("nan")]:
            with self.assertRaises(ValueError): await entity.async_set_native_value(value)
        self.assertEqual(len(self.calls), 3)
        self.data.values["projector_control_available"] = False
        self.assertFalse(entity.available)
        self.data.values["projector_keystone"] = None
        self.assertIsNone(entity.native_value)

    async def test_autofocus_and_keystone_surface_device_failures(self):
        button = self.ns["CompanionLinkAutoFocusButton"](self.data)
        await button.async_press()
        self.assertEqual(self.calls, [("auto_focus", {})])
        self.success = False
        with self.assertRaisesRegex(ValueError, "device rejected"): await button.async_press()
        with self.assertRaisesRegex(ValueError, "device rejected"):
            await self.ns["CompanionLinkKeystone"](self.data).async_set_native_value(10)

    async def test_discover_once_after_capability_and_cleanup_listener(self):
        tree = ast.parse((SOURCE / "entity.py").read_text(encoding="utf-8-sig"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "add_optics_entities")
        ns = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "entity.py", "exec"), ns)
        listeners, unloads, entities = [], [], []
        self.data.add_listener = lambda fn: (listeners.append(fn) or (lambda: None))
        entry = SimpleNamespace(async_on_unload=unloads.append)
        ns["add_optics_entities"](entry, self.data, entities.extend, lambda _: ["keystone", "autofocus"])
        self.assertEqual(entities, [])
        self.data.values["projector_optics_supported"] = True
        listeners[0](); listeners[0]()
        self.assertEqual(entities, ["keystone", "autofocus"])
        self.assertEqual(len(unloads), 1)

if __name__ == "__main__": unittest.main()
