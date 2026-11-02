"""
DualAudio - Configuration Manager
Gère la persistance des règles d'assignation audio par oreille (gauche/droite)
dans un fichier local JSON.
"""

import json
import os
import threading

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dualaudio_config.json")

DEFAULT_CONFIG = {
    "rules": {
        "ms-teams.exe": {
            "name": "Microsoft Teams",
            "balance": 1.0,        # 1.0 = Oreille Droite uniquement
            "volume": 1.0,
            "auto_apply": True
        },
        "vlc.exe": {
            "name": "VLC media player",
            "balance": -1.0,       # -1.0 = Oreille Gauche uniquement
            "volume": 1.0,
            "auto_apply": True
        }
    },
    "settings": {
        "auto_enforce": True,
        "polling_interval_ms": 500,
        "show_system_sounds": True,
        "group_by_app": True
    }
}


class ConfigManager:
    def __init__(self, config_path=DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self._lock = threading.Lock()
        self.config = self._load()

    def _load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # S'assurer que les clés minimales existent
                    if "rules" not in data:
                        data["rules"] = {}
                    if "settings" not in data:
                        data["settings"] = DEFAULT_CONFIG["settings"]
                    return data
            except Exception as e:
                print(f"[ConfigManager] Erreur chargement config: {e}")
        return json.loads(json.dumps(DEFAULT_CONFIG))

    def save(self):
        with self._lock:
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[ConfigManager] Erreur sauvegarde config: {e}")

    def get_rule(self, process_name):
        with self._lock:
            return self.config["rules"].get(process_name.lower())

    def set_rule(self, process_name, balance=None, volume=None, auto_apply=True, name=None):
        with self._lock:
            key = process_name.lower()
            if key not in self.config["rules"]:
                self.config["rules"][key] = {
                    "name": name or process_name,
                    "balance": 0.0,
                    "volume": 1.0,
                    "auto_apply": auto_apply
                }
            if balance is not None:
                self.config["rules"][key]["balance"] = round(float(balance), 3)
            if volume is not None:
                self.config["rules"][key]["volume"] = round(float(volume), 3)
            if auto_apply is not None:
                self.config["rules"][key]["auto_apply"] = bool(auto_apply)
            if name:
                self.config["rules"][key]["name"] = name
        self.save()

    def remove_rule(self, process_name):
        with self._lock:
            key = process_name.lower()
            if key in self.config["rules"]:
                del self.config["rules"][key]
        self.save()

    def get_all_rules(self):
        with self._lock:
            return dict(self.config["rules"])

    def get_settings(self):
        with self._lock:
            return dict(self.config["settings"])

    def update_settings(self, **kwargs):
        with self._lock:
            self.config["settings"].update(kwargs)
        self.save()
