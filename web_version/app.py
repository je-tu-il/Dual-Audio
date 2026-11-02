"""
DualAudio - Point d'entrée principal
Lance le contrôleur audio Windows, le serveur local et l'interface graphique.
"""

import sys
import os
import time
import socket
import threading
import argparse
import webbrowser
from wsgiref.simple_server import make_server, WSGIRequestHandler
from bottle import ServerAdapter

from config_manager import ConfigManager
from audio_controller import AudioController
from server import create_app

try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        # Masquer les requêtes de logs pour garder la console propre
        pass


class QuietWSGIRefServer(ServerAdapter):
    def run(self, handler):
        self.server = make_server(self.host, self.port, handler, handler_class=QuietHandler)
        self.server.serve_forever()

    def shutdown(self):
        if hasattr(self, "server"):
            self.server.shutdown()


def find_free_port(preferred_port=58432):
    """Trouve un port disponible, en commençant par le port préféré."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred_port))
            return preferred_port
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description="DualAudio - Routage audio par oreille pour casque")
    parser.add_argument("--browser", action="store_true", help="Ouvrir dans le navigateur par défaut plutôt qu'en fenêtre native")
    parser.add_argument("--no-gui", action="store_true", help="Lancer en mode serveur sans ouvrir de fenêtre")
    parser.add_argument("--port", type=int, default=None, help="Port d'écoute local personnalisé")
    args = parser.parse_args()

    print("=" * 60)
    print("🎧 DualAudio - Contrôle Audio Indépendant par Oreille")
    print("=" * 60)

    # 1. Initialisation des composants
    config_mgr = ConfigManager()
    audio_ctl = AudioController(config_mgr)

    # 2. Démarrage de la surveillance d'arrière-plan (application auto des règles)
    print("-> Démarrage du moniteur audio en arrière-plan...")
    audio_ctl.start_background_enforcer(interval_sec=0.75)

    # 3. Démarrage du serveur web local
    port = args.port or find_free_port(58432)
    app = create_app(audio_ctl, config_mgr)
    server_adapter = QuietWSGIRefServer(host="127.0.0.1", port=port)

    server_thread = threading.Thread(
        target=lambda: app.run(server=server_adapter, quiet=True),
        daemon=True,
        name="DualAudio-WebServer"
    )
    server_thread.start()

    url = f"http://127.0.0.1:{port}"
    print(f"-> Serveur local actif sur : {url}")
    print(f"-> Périphérique détecté : {audio_ctl.get_active_device_name()}")

    # 4. Lancement de l'interface graphique
    use_browser = args.browser or not HAS_WEBVIEW

    if args.no_gui:
        print("-> Mode serveur actif (Ctrl+C pour quitter).")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    elif use_browser:
        print("-> Ouverture dans votre navigateur Web...")
        webbrowser.open(url)
        print("-> Interface ouverte. Appuyez sur Ctrl+C dans cette fenêtre pour quitter.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    else:
        print("-> Ouverture de la fenêtre native pywebview...")
        try:
            window = webview.create_window(
                title="DualAudio • Routage Audio par Oreille",
                url=url,
                width=1020,
                height=840,
                min_size=(780, 600),
                text_select=False
            )
            webview.start()
        except Exception as e:
            print(f"[!] Erreur pywebview: {e}. Basculement sur le navigateur par défaut...")
            webbrowser.open(url)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

    # 5. Nettoyage à la fermeture
    print("\n-> Arrêt de DualAudio...")
    audio_ctl.stop_background_enforcer()
    server_adapter.shutdown()
    print("-> Au revoir !")


if __name__ == "__main__":
    main()
