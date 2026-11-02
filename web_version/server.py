"""
DualAudio - Backend Web & API Server (Bottle)
Expose une API REST locale pour l'interface graphique (pywebview ou navigateur).
"""

import os
import json
import bottle
from bottle import Bottle, request, response, static_file

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def create_app(audio_controller, config_manager):
    app = Bottle()

    # CORS & JSON headers helper
    def json_resp(data, status=200):
        response.status = status
        response.content_type = "application/json; charset=utf-8"
        return json.dumps(data, ensure_ascii=False)

    @app.hook("after_request")
    def enable_cors():
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"

    @app.route("/", method=["GET"])
    def index():
        return static_file("index.html", root=WEB_DIR)

    @app.route("/static/<filepath:path>", method=["GET"])
    def serve_static(filepath):
        return static_file(filepath, root=WEB_DIR)

    @app.route("/api/state", method=["GET"])
    def get_state():
        settings = config_manager.get_settings()
        group_by_app = settings.get("group_by_app", True)
        sessions = audio_controller.get_audio_sessions(group_by_app=group_by_app)
        device_name = audio_controller.get_active_device_name()
        diagnostics = audio_controller.get_device_diagnostics()
        rules = config_manager.get_all_rules()

        return json_resp({
            "device": device_name,
            "diagnostics": diagnostics,
            "apps": sessions,
            "rules": rules,
            "settings": settings
        })

    @app.route("/api/open_settings", method=["POST", "OPTIONS"])
    def open_settings():
        if request.method == "OPTIONS":
            return ""
        data = request.json or {}
        target = data.get("target", "sound")
        if target == "bluetooth":
            os.system("start ms-settings:bluetooth")
        elif target == "mixer":
            os.system("start ms-settings:apps-volume")
        elif target == "cpl":
            os.system("start mmsys.cpl")
        else:
            os.system("start ms-settings:sound")
        return json_resp({"success": True})

    @app.route("/api/balance", method=["POST", "OPTIONS"])
    def set_balance():
        if request.method == "OPTIONS":
            return ""
        data = request.json or {}
        process_name = data.get("process_name")
        balance = data.get("balance")
        if process_name is None or balance is None:
            return json_resp({"error": "process_name et balance requis"}, 400)
        res = audio_controller.set_app_balance(process_name, float(balance))
        return json_resp(res)

    @app.route("/api/volume", method=["POST", "OPTIONS"])
    def set_volume():
        if request.method == "OPTIONS":
            return ""
        data = request.json or {}
        process_name = data.get("process_name")
        volume = data.get("volume")
        if process_name is None or volume is None:
            return json_resp({"error": "process_name et volume requis"}, 400)
        res = audio_controller.set_app_volume(process_name, float(volume))
        return json_resp(res)

    @app.route("/api/mute", method=["POST", "OPTIONS"])
    def set_mute():
        if request.method == "OPTIONS":
            return ""
        data = request.json or {}
        process_name = data.get("process_name")
        muted = data.get("muted")
        if process_name is None or muted is None:
            return json_resp({"error": "process_name et muted requis"}, 400)
        res = audio_controller.set_app_mute(process_name, bool(muted))
        return json_resp(res)

    @app.route("/api/preset", method=["POST", "OPTIONS"])
    def set_preset():
        if request.method == "OPTIONS":
            return ""
        data = request.json or {}
        process_name = data.get("process_name")
        preset = data.get("preset")  # 'left', 'center', 'right'
        if not process_name or not preset:
            return json_resp({"error": "process_name et preset requis"}, 400)
        res = audio_controller.set_quick_preset(process_name, preset)
        return json_resp(res)

    @app.route("/api/scenario", method=["POST", "OPTIONS"])
    def apply_scenario():
        if request.method == "OPTIONS":
            return ""
        data = request.json or {}
        scenario = data.get("scenario")
        if not scenario:
            return json_resp({"error": "scenario requis"}, 400)
        res = audio_controller.apply_scenario(scenario)
        return json_resp(res)

    @app.route("/api/auto_apply", method=["POST", "OPTIONS"])
    def toggle_auto_apply():
        if request.method == "OPTIONS":
            return ""
        data = request.json or {}
        process_name = data.get("process_name")
        auto_apply = data.get("auto_apply", True)
        if not process_name:
            return json_resp({"error": "process_name requis"}, 400)
        config_manager.set_rule(process_name, auto_apply=bool(auto_apply))
        return json_resp({"success": True})

    @app.route("/api/settings", method=["POST", "OPTIONS"])
    def update_settings():
        if request.method == "OPTIONS":
            return ""
        data = request.json or {}
        config_manager.update_settings(**data)
        return json_resp({"success": True, "settings": config_manager.get_settings()})

    return app
