# -*- coding: utf-8 -*-
"""
Suite de tests unitaires et d'intégration pour Dual-Audio.
"""

import ast
import ctypes
import hashlib
import importlib
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web_version.config_manager import ConfigManager, DEFAULT_CONFIG  # noqa: E402


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg_path = Path(self.tmp.name) / "test_dualaudio_config.json"

    def test_defaults_when_file_missing(self):
        mgr = ConfigManager(config_path=str(self.cfg_path))
        rules = mgr.get_all_rules()
        settings = mgr.get_settings()
        self.assertIn("ms-teams.exe", rules)
        self.assertIn("vlc.exe", rules)
        self.assertEqual(settings["polling_interval_ms"], DEFAULT_CONFIG["settings"]["polling_interval_ms"])

    def test_set_remove_rule_and_settings_persistence(self):
        mgr = ConfigManager(config_path=str(self.cfg_path))
        mgr.set_rule("Spotify.EXE", balance=-0.3456, volume=0.7891, auto_apply=False, name="Spotify")
        mgr.update_settings(auto_enforce=False, polling_interval_ms=250)

        reloaded = ConfigManager(config_path=str(self.cfg_path))
        rule = reloaded.get_rule("spotify.exe")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["name"], "Spotify")
        self.assertEqual(rule["balance"], -0.346)
        self.assertEqual(rule["volume"], 0.789)
        self.assertFalse(rule["auto_apply"])

        settings = reloaded.get_settings()
        self.assertFalse(settings["auto_enforce"])
        self.assertEqual(settings["polling_interval_ms"], 250)

        reloaded.remove_rule("SPOTIFY.EXE")
        reloaded_again = ConfigManager(config_path=str(self.cfg_path))
        self.assertIsNone(reloaded_again.get_rule("spotify.exe"))

    def test_recovers_missing_top_level_keys(self):
        self.cfg_path.write_text(json.dumps({"unexpected": 1}), encoding="utf-8")
        mgr = ConfigManager(config_path=str(self.cfg_path))
        self.assertEqual(mgr.get_all_rules(), {})
        self.assertEqual(mgr.get_settings()["polling_interval_ms"], DEFAULT_CONFIG["settings"]["polling_interval_ms"])

    def test_recovers_non_dict_null_and_partial_settings_without_mutating_defaults(self):
        orig_defaults = json.loads(json.dumps(DEFAULT_CONFIG))

        # 1. Valid JSON list instead of dict
        self.cfg_path.write_text(json.dumps(["rules", "settings"]), encoding="utf-8")
        mgr_list = ConfigManager(config_path=str(self.cfg_path))
        self.assertIn("ms-teams.exe", mgr_list.get_all_rules())
        self.assertEqual(mgr_list.get_settings()["polling_interval_ms"], DEFAULT_CONFIG["settings"]["polling_interval_ms"])

        # 2. Null rules & null settings
        self.cfg_path.write_text(json.dumps({"rules": None, "settings": None}), encoding="utf-8")
        mgr_null = ConfigManager(config_path=str(self.cfg_path))
        self.assertEqual(mgr_null.get_all_rules(), {})
        self.assertEqual(mgr_null.get_settings(), DEFAULT_CONFIG["settings"])

        # 3. Partial settings preserve remaining default keys
        self.cfg_path.write_text(json.dumps({"rules": {}, "settings": {"auto_enforce": False}}), encoding="utf-8")
        mgr_partial = ConfigManager(config_path=str(self.cfg_path))
        partial_settings = mgr_partial.get_settings()
        self.assertFalse(partial_settings["auto_enforce"])
        self.assertEqual(partial_settings["polling_interval_ms"], DEFAULT_CONFIG["settings"]["polling_interval_ms"])

        # 4. Missing settings does not alias global DEFAULT_CONFIG["settings"]
        self.cfg_path.write_text(json.dumps({"rules": {}}), encoding="utf-8")
        mgr_missing = ConfigManager(config_path=str(self.cfg_path))
        mgr_missing.update_settings(polling_interval_ms=999, custom_flag=True)
        self.assertEqual(DEFAULT_CONFIG, orig_defaults)

    def test_set_rule_clamps_ranges_and_rejects_non_finite_values(self):
        mgr = ConfigManager(config_path=str(self.cfg_path))
        mgr.set_rule("clamp.exe", balance=999.0, volume=-5.0)
        rule = mgr.get_rule("clamp.exe")
        self.assertEqual(rule["balance"], 1.0)
        self.assertEqual(rule["volume"], 0.0)

        mgr.set_rule("clamp2.exe", balance=-42.0, volume=12.5)
        rule2 = mgr.get_rule("clamp2.exe")
        self.assertEqual(rule2["balance"], -1.0)
        self.assertEqual(rule2["volume"], 1.0)

        for bad_bal, bad_vol in (
            (float("nan"), 0.5),
            (0.0, float("inf")),
            (float("-inf"), None),
        ):
            with self.subTest(bad_bal=bad_bal, bad_vol=bad_vol):
                with self.assertRaises(ValueError):
                    mgr.set_rule("bad.exe", balance=bad_bal, volume=bad_vol)
                self.assertIsNone(mgr.get_rule("bad.exe"))

        raw_text = self.cfg_path.read_text(encoding="utf-8")
        parsed = json.loads(raw_text)
        self.assertIn("clamp.exe", parsed["rules"])
        self.assertNotIn("bad.exe", parsed["rules"])


class TestAudioControllerPureLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._saved_modules = {}
        cls._injected_names = []
        cls._had_ac = "web_version.audio_controller" in sys.modules

        missing_mods = {}
        for name in ("comtypes", "pycaw", "pycaw.pycaw", "psutil"):
            if name in sys.modules:
                continue
            try:
                importlib.import_module(name)
            except ImportError:
                missing_mods[name] = True

        if missing_mods:
            if "comtypes" in missing_mods:
                class _StubGUID(ctypes.Structure):
                    def __init__(self, val=None):
                        super().__init__()
                        self.val = val

                comtypes_mod = types.ModuleType("comtypes")
                comtypes_mod.GUID = _StubGUID
                comtypes_mod.IUnknown = object
                comtypes_mod.COMMETHOD = lambda *args, **kwargs: None
                comtypes_mod.HRESULT = int
                cls._saved_modules["comtypes"] = sys.modules.get("comtypes")
                sys.modules["comtypes"] = comtypes_mod
                cls._injected_names.append("comtypes")

            if "pycaw" in missing_mods or "pycaw.pycaw" in missing_mods:
                pycaw_pkg = types.ModuleType("pycaw")
                pycaw_sub = types.ModuleType("pycaw.pycaw")
                pycaw_sub.AudioUtilities = mock.MagicMock()
                pycaw_sub.ISimpleAudioVolume = mock.MagicMock()
                pycaw_sub.IAudioMeterInformation = mock.MagicMock()
                pycaw_sub.IAudioSessionControl2 = mock.MagicMock()
                pycaw_pkg.pycaw = pycaw_sub
                for mod_name, mod_obj in (("pycaw", pycaw_pkg), ("pycaw.pycaw", pycaw_sub)):
                    if mod_name not in sys.modules:
                        cls._saved_modules[mod_name] = None
                        sys.modules[mod_name] = mod_obj
                        cls._injected_names.append(mod_name)

            if "psutil" in missing_mods:
                cls._saved_modules["psutil"] = sys.modules.get("psutil")
                sys.modules["psutil"] = mock.MagicMock()
                cls._injected_names.append("psutil")

        cls.ac_mod = importlib.import_module("web_version.audio_controller")

    @classmethod
    def tearDownClass(cls):
        if cls._injected_names and not cls._had_ac:
            sys.modules.pop("web_version.audio_controller", None)
        for name in cls._injected_names:
            old = cls._saved_modules.get(name)
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old

    def test_balance_to_channel_volumes_and_clamping(self):
        fn = self.ac_mod.balance_to_channel_volumes
        self.assertEqual(fn(-1.0), (1.0, 0.0))
        self.assertEqual(fn(0.0), (1.0, 1.0))
        self.assertEqual(fn(1.0), (0.0, 1.0))
        self.assertEqual(fn(-0.5), (1.0, 0.5))
        self.assertEqual(fn(0.25), (0.75, 1.0))
        # Clamping outside [-1, 1]
        self.assertEqual(fn(-2.5), (1.0, 0.0))
        self.assertEqual(fn(3.0), (0.0, 1.0))

    def test_channel_volumes_to_balance_roundtrips_and_edge_cases(self):
        to_bal = self.ac_mod.channel_volumes_to_balance
        to_vol = self.ac_mod.balance_to_channel_volumes

        self.assertEqual(to_bal(0.0, 0.0), 0.0)
        self.assertEqual(to_bal(0.805, 0.800), 0.0)
        self.assertEqual(to_bal(1.0, 0.0), -1.0)
        self.assertEqual(to_bal(0.0, 1.0), 1.0)

        for bal in (-1.0, -0.75, -0.3, 0.0, 0.4, 0.85, 1.0):
            left, right = to_vol(bal)
            self.assertAlmostEqual(to_bal(left, right), bal, places=3)

        # Negative and non-finite inputs
        self.assertEqual(to_bal(-0.5, 1.0), 1.0)
        self.assertEqual(to_bal(1.0, -0.5), -1.0)
        self.assertEqual(to_bal(float("nan"), 1.0), 0.0)
        self.assertEqual(to_bal(1.0, float("nan")), 0.0)
        self.assertEqual(to_bal(float("inf"), float("inf")), 0.0)
        self.assertTrue(math.isfinite(to_bal(float("-inf"), 0.5)))
        self.assertEqual(to_bal(float("-inf"), 0.5), 0.0)

    def test_known_apps_and_friendly_app_info(self):
        self.assertIn("vlc.exe", self.ac_mod.KNOWN_APPS_INFO)
        self.assertIn("ms-teams.exe", self.ac_mod.KNOWN_APPS_INFO)

        ctrl = self.ac_mod.AudioController(config_manager=None)
        vlc_info = ctrl.get_friendly_app_info("VLC.EXE")
        self.assertEqual(vlc_info["name"], "VLC media player")

        disp_info = ctrl.get_friendly_app_info("custom_app.exe", display_name="My Custom App")
        self.assertEqual(disp_info["name"], "My Custom App")

        fallback_info = ctrl.get_friendly_app_info("my_synth-player.exe")
        self.assertEqual(fallback_info["name"], "My Synth Player")


class TestBuildAndExecutable(unittest.TestCase):
    def test_root_exe_is_valid_pe_and_up_to_date(self):
        exe_path = PROJECT_ROOT / "Dual-Audio.exe"
        main_path = PROJECT_ROOT / "main.py"
        dist_exe = PROJECT_ROOT / "dist" / "Dual-Audio.exe"

        self.assertTrue(exe_path.is_file(), "Dual-Audio.exe must exist at project root")
        data = exe_path.read_bytes()
        self.assertGreater(len(data), 1024)
        self.assertEqual(data[:2], b"MZ")
        pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
        self.assertEqual(data[pe_offset:pe_offset + 4], b"PE\x00\x00")

        self.assertGreaterEqual(exe_path.stat().st_mtime, main_path.stat().st_mtime)

        if dist_exe.is_file():
            root_hash = hashlib.sha256(data).hexdigest()
            dist_hash = hashlib.sha256(dist_exe.read_bytes()).hexdigest()
            self.assertEqual(root_hash, dist_hash)

    def test_spec_and_build_script_alignment(self):
        spec_text = (PROJECT_ROOT / "Dual-Audio.spec").read_text(encoding="utf-8")
        self.assertIn("main.py", spec_text)
        self.assertIn("customtkinter", spec_text)
        self.assertIn("pygame", spec_text)
        self.assertIn("audioop_lts", spec_text)
        self.assertIn("name='Dual-Audio'", spec_text)

        bat_text = (PROJECT_ROOT / "build_exe.bat").read_text(encoding="utf-8")
        self.assertIn('--name="Dual-Audio"', bat_text)
        self.assertIn("main.py", bat_text)
        self.assertIn("Dual-Audio.exe", bat_text)


class TestMainAndEntrypoint(unittest.TestCase):
    def test_main_module_exports_and_entrypoint_ast(self):
        orig_popen = subprocess.Popen
        try:
            main_mod = importlib.import_module("main")
            self.assertTrue(hasattr(main_mod, "App"))
            self.assertTrue(hasattr(main_mod, "AudioDeck"))
            self.assertTrue(callable(getattr(main_mod, "main", None)))
        finally:
            subprocess.Popen = orig_popen

        pyw_path = PROJECT_ROOT / "Double musique.pyw"
        src = pyw_path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(pyw_path))
        self.assertTrue(any(isinstance(n, ast.ImportFrom) and n.module == "main" for n in tree.body))


if __name__ == "__main__":
    unittest.main()
