"""
DualAudio - Audio Controller (Windows Core Audio / WASAPI)
Permet de contrôler le volume et le routage des canaux (Gauche / Droite)
par application sous Windows.
"""

import math
import time
import os
import threading
import ctypes
from ctypes import wintypes, POINTER, c_uint32, c_float

import comtypes
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
import psutil

from pycaw.pycaw import (
    AudioUtilities,
    ISimpleAudioVolume,
    IAudioMeterInformation,
    IAudioSessionControl2
)


# Definition COM de IChannelAudioVolume (absent par defaut de pycaw)
class IChannelAudioVolume(IUnknown):
    _iid_ = GUID('{1C158861-B533-4B30-B1CF-E853E51C59B8}')
    _methods_ = [
        COMMETHOD([], HRESULT, 'GetChannelCount',
                  (['out'], POINTER(c_uint32), 'pnChannelCount')),
        COMMETHOD([], HRESULT, 'SetChannelVolume',
                  (['in'], c_uint32, 'dwIndex'),
                  (['in'], c_float, 'fLevel'),
                  (['in'], POINTER(GUID), 'EventContext')),
        COMMETHOD([], HRESULT, 'GetChannelVolume',
                  (['in'], c_uint32, 'dwIndex'),
                  (['out'], POINTER(c_float), 'pfLevel')),
        COMMETHOD([], HRESULT, 'SetAllVolumes',
                  (['in'], c_uint32, 'dwCount'),
                  (['in'], POINTER(c_float), 'pfVolumes'),
                  (['in'], POINTER(GUID), 'EventContext')),
        COMMETHOD([], HRESULT, 'GetAllVolumes',
                  (['in'], c_uint32, 'dwCount'),
                  (['out'], POINTER(c_float), 'pfVolumes')),
    ]


KNOWN_APPS_INFO = {
    "ms-teams.exe": {"name": "Microsoft Teams", "category": "Appel & Réunion", "icon": "teams", "color": "#6264A7"},
    "teams.exe": {"name": "Microsoft Teams", "category": "Appel & Réunion", "icon": "teams", "color": "#6264A7"},
    "vlc.exe": {"name": "VLC media player", "category": "Lecteur Média", "icon": "vlc", "color": "#FF8800"},
    "chrome.exe": {"name": "Google Chrome", "category": "Navigateur Web", "icon": "chrome", "color": "#4285F4"},
    "msedge.exe": {"name": "Microsoft Edge", "category": "Navigateur Web", "icon": "edge", "color": "#0078D7"},
    "firefox.exe": {"name": "Mozilla Firefox", "category": "Navigateur Web", "icon": "firefox", "color": "#FF7139"},
    "spotify.exe": {"name": "Spotify", "category": "Musique & Podcast", "icon": "spotify", "color": "#1DB954"},
    "discord.exe": {"name": "Discord", "category": "Discussion & Voix", "icon": "discord", "color": "#5865F2"},
    "slack.exe": {"name": "Slack", "category": "Communication", "icon": "slack", "color": "#4A154B"},
    "zoom.exe": {"name": "Zoom Meetings", "category": "Visioconférence", "icon": "zoom", "color": "#0B5CFF"},
    "obs64.exe": {"name": "OBS Studio", "category": "Streaming / Capture", "icon": "obs", "color": "#302E31"},
    "steam.exe": {"name": "Steam", "category": "Jeux", "icon": "steam", "color": "#171A21"},
    "system": {"name": "Sons Système Windows", "category": "Système", "icon": "system", "color": "#00A4EF"}
}


def get_file_description(filepath):
    """Extrait la description du fichier binaire PE Windows (ex: 'Microsoft Teams')."""
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(filepath, None)
        if not size:
            return None
        res = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(filepath, 0, size, res):
            return None
        sub_block = '\\VarFileInfo\\Translation'
        ptr = ctypes.c_void_p()
        u_len = ctypes.c_uint()
        if not ctypes.windll.version.VerQueryValueW(res, sub_block, ctypes.byref(ptr), ctypes.byref(u_len)):
            return None
        trans = ctypes.cast(ptr, ctypes.POINTER(wintypes.WORD))
        lang, codepage = trans[0], trans[1]
        str_query = f'\\StringFileInfo\\{lang:04x}{codepage:04x}\\FileDescription'
        if ctypes.windll.version.VerQueryValueW(res, str_query, ctypes.byref(ptr), ctypes.byref(u_len)):
            desc = ctypes.wstring_at(ptr)
            if desc and desc.strip():
                return desc.strip()
    except Exception:
        pass
    return None


def balance_to_channel_volumes(balance: float):
    """
    Convertit une valeur de balance (-1.0 = Gauche, 0.0 = Centre, 1.0 = Droite)
    en volumes normalisés de canaux [Left, Right].
    """
    b = max(-1.0, min(1.0, float(balance)))
    if b <= 0:
        # Pente vers la gauche
        left = 1.0
        right = 1.0 + b  # à b = -1.0, right = 0.0
    else:
        # Pente vers la droite
        left = 1.0 - b   # à b = 1.0, left = 0.0
        right = 1.0
    return round(left, 3), round(right, 3)


def channel_volumes_to_balance(left: float, right: float) -> float:
    """Convertit les volumes de canaux [Left, Right] en balance dans [-1.0, 1.0]."""
    try:
        l_val = float(left)
        r_val = float(right)
    except (TypeError, ValueError):
        return 0.0
    if not (math.isfinite(l_val) and math.isfinite(r_val)):
        return 0.0
    l_val = max(0.0, l_val)
    r_val = max(0.0, r_val)
    max_v = max(l_val, r_val)
    if max_v < 0.001:
        return 0.0
    if abs(l_val - r_val) < 0.02:
        return 0.0
    if l_val > r_val:
        bal = (r_val / l_val) - 1.0
    else:
        bal = 1.0 - (l_val / r_val)
    return round(max(-1.0, min(1.0, bal)), 3)


class AudioController:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread = None
        self._cached_descriptions = {}

    def get_friendly_app_info(self, process_name, exe_path=None, display_name=None):
        """Détermine un nom agréable et des métadonnées pour l'application."""
        key = process_name.lower() if process_name else "system"
        if key in KNOWN_APPS_INFO:
            info = dict(KNOWN_APPS_INFO[key])
            return info

        # Regarder dans le cache de description d'exécutable
        if key in self._cached_descriptions:
            name = self._cached_descriptions[key]
        else:
            name = None
            if exe_path and os.path.exists(exe_path):
                name = get_file_description(exe_path)
            if not name and display_name and not display_name.startswith("@"):
                name = display_name
            if not name:
                # Nettoyage du nom de fichier .exe
                name = process_name[:-4] if process_name.lower().endswith(".exe") else process_name
                name = name.replace("-", " ").replace("_", " ").title()
            self._cached_descriptions[key] = name

        return {
            "name": name,
            "category": "Application",
            "icon": "default",
            "color": "#6366F1"
        }

    def get_active_device_name(self):
        """Récupère le nom du périphérique de sortie audio par défaut (ex: Casque Bose)."""
        comtypes.CoInitialize()
        try:
            device = AudioUtilities.GetSpeakers()
            if device and hasattr(device, "FriendlyName"):
                return device.FriendlyName
            return "Périphérique audio par défaut"
        except Exception:
            return "Casque / Écouteurs"
        finally:
            comtypes.CoUninitialize()

    def get_device_diagnostics(self):
        """Diagnostique si des casques connus sont dans l'état déconnecté (Unplugged)."""
        comtypes.CoInitialize()
        try:
            active_name = self.get_active_device_name()
            devices = AudioUtilities.GetAllDevices()
            unplugged_headsets = []
            for d in devices:
                n = d.FriendlyName.lower()
                if any(k in n for k in ["casque", "bose", "earbuds", "headphone", "headset"]):
                    if d.state.name == "Unplugged":
                        unplugged_headsets.append(d.FriendlyName)
            return {
                "active_device": active_name,
                "is_pc_speakers": any(k in active_name.lower() for k in ["haut-parleur", "speaker", "realtek"]),
                "unplugged_headsets": sorted(list(set(unplugged_headsets)))
            }
        except Exception:
            return {
                "active_device": self.get_active_device_name(),
                "is_pc_speakers": False,
                "unplugged_headsets": []
            }
        finally:
            comtypes.CoUninitialize()

    def get_audio_sessions(self, group_by_app=True):
        """
        Énumère toutes les sessions audio actuelles.
        Retourne la liste des applications avec leur état (balance, volume, peak, etc.).
        """
        comtypes.CoInitialize()
        apps_map = {}
        try:
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                try:
                    proc = s.Process
                    pid = s.ProcessId
                    pname = proc.name() if proc else "System"
                    exe_path = None
                    if proc:
                        try:
                            exe_path = proc.exe()
                        except Exception:
                            pass

                    # Volume & Muet
                    sav = s._ctl.QueryInterface(ISimpleAudioVolume)
                    master_vol = float(sav.GetMasterVolume())
                    is_muted = bool(sav.GetMute())

                    # Canaux & Balance
                    chan = s._ctl.QueryInterface(IChannelAudioVolume)
                    chan_count = chan.GetChannelCount()
                    if chan_count >= 2:
                        vol_l = float(chan.GetChannelVolume(0))
                        vol_r = float(chan.GetChannelVolume(1))
                    elif chan_count == 1:
                        vol_l = vol_r = float(chan.GetChannelVolume(0))
                    else:
                        vol_l = vol_r = 1.0

                    balance = channel_volumes_to_balance(vol_l, vol_r)

                    # Peak audio meter
                    peak = 0.0
                    try:
                        meter = s._ctl.QueryInterface(IAudioMeterInformation)
                        peak = float(meter.GetPeakValue())
                    except Exception:
                        pass

                    key = pname.lower()
                    app_info = self.get_friendly_app_info(pname, exe_path, s.DisplayName)

                    # Règle enregistrée dans la config ?
                    rule = self.config_manager.get_rule(pname)
                    has_rule = rule is not None
                    auto_apply = rule.get("auto_apply", True) if rule else True

                    session_item = {
                        "id": f"{key}_{pid}",
                        "process_name": pname,
                        "pid": pid,
                        "display_name": app_info["name"],
                        "category": app_info["category"],
                        "icon": app_info["icon"],
                        "color": app_info["color"],
                        "master_volume": round(master_vol, 3),
                        "is_muted": is_muted,
                        "left_volume": round(vol_l, 3),
                        "right_volume": round(vol_r, 3),
                        "balance": balance,
                        "peak": round(peak, 3),
                        "channel_count": chan_count,
                        "has_rule": has_rule,
                        "auto_apply": auto_apply,
                        "sessions_count": 1
                    }

                    if group_by_app:
                        if key not in apps_map:
                            apps_map[key] = session_item
                        else:
                            # Cumuler le peak et garder le volume représentatif
                            apps_map[key]["peak"] = max(apps_map[key]["peak"], session_item["peak"])
                            apps_map[key]["sessions_count"] += 1
                    else:
                        apps_map[f"{key}_{pid}"] = session_item

                except Exception as ex:
                    # Session expirée ou inaccessible
                    continue

        finally:
            comtypes.CoUninitialize()

        # Convertir en liste triée (d'abord les applications connues ou avec du son)
        result = list(apps_map.values())
        result.sort(key=lambda x: (x["process_name"] == "System", -x["peak"], x["display_name"].lower()))
        return result

    def set_app_balance(self, target_process: str, balance: float):
        """
        Définit la balance (orientation oreille gauche / droite) pour toutes
        les sessions audio d'une application donnée.
        balance : -1.0 (Oreille Gauche pure) -> 0.0 (Les deux) -> 1.0 (Oreille Droite pure).
        """
        left_vol, right_vol = balance_to_channel_volumes(balance)
        target_key = target_process.lower()

        comtypes.CoInitialize()
        updated_count = 0
        try:
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                proc = s.Process
                pname = proc.name() if proc else "System"
                if pname.lower() == target_key:
                    try:
                        chan = s._ctl.QueryInterface(IChannelAudioVolume)
                        count = chan.GetChannelCount()
                        if count >= 2:
                            chan.SetChannelVolume(0, left_vol, None)
                            chan.SetChannelVolume(1, right_vol, None)
                            updated_count += 1
                        elif count == 1:
                            # Monocanal
                            chan.SetChannelVolume(0, max(left_vol, right_vol), None)
                            updated_count += 1
                    except Exception as ex:
                        print(f"[AudioController] Erreur set_balance sur {pname}: {ex}")
        finally:
            comtypes.CoUninitialize()

        # Enregistrer la règle dans la configuration persistante
        self.config_manager.set_rule(target_process, balance=balance)
        return {"success": True, "updated_sessions": updated_count, "left": left_vol, "right": right_vol}

    def set_app_volume(self, target_process: str, volume: float):
        """Définit le volume principal (0.0 à 1.0) pour une application."""
        vol = max(0.0, min(1.0, float(volume)))
        target_key = target_process.lower()

        comtypes.CoInitialize()
        try:
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                proc = s.Process
                pname = proc.name() if proc else "System"
                if pname.lower() == target_key:
                    try:
                        sav = s._ctl.QueryInterface(ISimpleAudioVolume)
                        sav.SetMasterVolume(vol, None)
                    except Exception as ex:
                        print(f"[AudioController] Erreur set_volume sur {pname}: {ex}")
        finally:
            comtypes.CoUninitialize()

        self.config_manager.set_rule(target_process, volume=vol)
        return {"success": True, "volume": vol}

    def set_app_mute(self, target_process: str, muted: bool):
        """Active ou désactive le mode muet pour une application."""
        target_key = target_process.lower()
        comtypes.CoInitialize()
        try:
            sessions = AudioUtilities.GetAllSessions()
            for s in sessions:
                proc = s.Process
                pname = proc.name() if proc else "System"
                if pname.lower() == target_key:
                    try:
                        sav = s._ctl.QueryInterface(ISimpleAudioVolume)
                        sav.SetMute(bool(muted), None)
                    except Exception as ex:
                        print(f"[AudioController] Erreur set_mute sur {pname}: {ex}")
        finally:
            comtypes.CoUninitialize()
        return {"success": True, "muted": muted}

    def set_quick_preset(self, target_process: str, preset: str):
        """
        Applique un préréglage instantané :
        - 'left'   : Oreille Gauche uniquement (-1.0)
        - 'center' : Les deux oreilles / Stéréo (0.0)
        - 'right'  : Oreille Droite uniquement (1.0)
        """
        preset_map = {
            "left": -1.0,
            "center": 0.0,
            "right": 1.0
        }
        balance = preset_map.get(preset.lower(), 0.0)
        return self.set_app_balance(target_process, balance)

    def apply_scenario(self, scenario_id: str):
        """
        Applique un scénario complet :
        - 'teams_right_vlc_left' : Le cas d'usage demandé (Teams à Droite, VLC à Gauche)
        - 'swap'                : Inverse les oreilles pour toutes les applications actives
        - 'reset_all'           : Remet toutes les applications au centre (les deux oreilles)
        """
        if scenario_id == "teams_right_vlc_left":
            # 1. Teams -> Oreille Droite (1.0)
            self.set_app_balance("ms-teams.exe", 1.0)
            self.set_app_balance("teams.exe", 1.0)
            # 2. VLC -> Oreille Gauche (-1.0)
            self.set_app_balance("vlc.exe", -1.0)
            return {
                "success": True,
                "message": "Scénario appliqué : Teams dans l'oreille droite, VLC dans l'oreille gauche !"
            }

        elif scenario_id == "swap":
            comtypes.CoInitialize()
            try:
                sessions = AudioUtilities.GetAllSessions()
                processed = set()
                for s in sessions:
                    proc = s.Process
                    pname = proc.name() if proc else "System"
                    key = pname.lower()
                    if key in processed:
                        continue
                    processed.add(key)
                    try:
                        chan = s._ctl.QueryInterface(IChannelAudioVolume)
                        if chan.GetChannelCount() >= 2:
                            vl = chan.GetChannelVolume(0)
                            vr = chan.GetChannelVolume(1)
                            # Inverser L et R
                            chan.SetChannelVolume(0, vr, None)
                            chan.SetChannelVolume(1, vl, None)
                            new_b = channel_volumes_to_balance(vr, vl)
                            self.config_manager.set_rule(pname, balance=new_b)
                    except Exception:
                        pass
            finally:
                comtypes.CoUninitialize()
            return {"success": True, "message": "Oreilles inversées (Gauche ⇄ Droite)"}

        elif scenario_id == "reset_all":
            comtypes.CoInitialize()
            try:
                sessions = AudioUtilities.GetAllSessions()
                for s in sessions:
                    try:
                        chan = s._ctl.QueryInterface(IChannelAudioVolume)
                        if chan.GetChannelCount() >= 2:
                            chan.SetChannelVolume(0, 1.0, None)
                            chan.SetChannelVolume(1, 1.0, None)
                    except Exception:
                        pass
                for k in self.config_manager.get_all_rules().keys():
                    self.config_manager.set_rule(k, balance=0.0)
            finally:
                comtypes.CoUninitialize()
            return {"success": True, "message": "Toutes les applications sont réinitialisées (centrées)."}

        return {"success": False, "message": f"Scénario inconnu : {scenario_id}"}

    def start_background_enforcer(self, interval_sec=0.75):
        """
        Démarre un thread d'arrière-plan qui vérifie les sessions actives.
        Si une nouvelle session audio démarre pour une application disposant
        d'une règle enregistrée, la balance est automatiquement appliquée !
        """
        if self._running:
            return
        self._running = True

        def loop():
            while self._running:
                try:
                    settings = self.config_manager.get_settings()
                    if settings.get("auto_enforce", True):
                        rules = self.config_manager.get_all_rules()
                        if rules:
                            comtypes.CoInitialize()
                            try:
                                sessions = AudioUtilities.GetAllSessions()
                                for s in sessions:
                                    proc = s.Process
                                    pname = proc.name() if proc else "System"
                                    rule = rules.get(pname.lower())
                                    if rule and rule.get("auto_apply", True):
                                        target_b = rule.get("balance", 0.0)
                                        exp_l, exp_r = balance_to_channel_volumes(target_b)
                                        try:
                                            chan = s._ctl.QueryInterface(IChannelAudioVolume)
                                            if chan.GetChannelCount() >= 2:
                                                cur_l = chan.GetChannelVolume(0)
                                                cur_r = chan.GetChannelVolume(1)
                                                # Si les volumes ne correspondent pas, forcer l'application
                                                if abs(cur_l - exp_l) > 0.05 or abs(cur_r - exp_r) > 0.05:
                                                    chan.SetChannelVolume(0, exp_l, None)
                                                    chan.SetChannelVolume(1, exp_r, None)
                                        except Exception:
                                            pass
                            finally:
                                comtypes.CoUninitialize()
                except Exception as e:
                    # Ne pas faire planter la boucle
                    pass
                time.sleep(interval_sec)

        self._monitor_thread = threading.Thread(target=loop, daemon=True, name="DualAudio-Enforcer")
        self._monitor_thread.start()

    def stop_background_enforcer(self):
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
