#!/usr/bin/env python3
"""
Dual-Audio — Dichotic Audio Mixer & Player
Jouez deux fichiers audio différents simultanément (un dans chaque oreille) avec contrôle de volume indépendant et export stéréo mixé.
"""

import os
import subprocess
import sys
import threading
import time
import math
import tkinter as tk
from tkinter import filedialog, messagebox

# --- Patch Anti-Console Windows sous Windows ---
if os.name == "nt":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    _original_Popen = subprocess.Popen

    class Popen(_original_Popen):
        def __init__(self, *args, **kwargs):
            kwargs["startupinfo"] = startupinfo
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    subprocess.Popen = Popen

import customtkinter as ctk
import pygame
from pydub import AudioSegment

# Config UI
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Init Audio Pygame
try:
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.init()
    pygame.mixer.set_num_channels(8)
except Exception as e:
    print(f"Avertissement initialisation audio : {e}")


class AudioDeck(ctk.CTkFrame):
    def __init__(self, master, side_name, side_index, color):
        super().__init__(master)
        self.side_name = side_name
        self.side_index = side_index  # 0: Gauche, 1: Droite
        self.accent_color = color

        self.filepath = None
        self.filename_short = "Inconnu"
        self.sound = None
        self.channel = None
        self.pydub_audio = None

        self.loading_progress_val = 0.0
        self.is_loading_active = False

        self.configure(fg_color="#2b2b2b", corner_radius=15, border_width=2, border_color=color)
        self.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.lbl_title = ctk.CTkLabel(
            self, text=f"OREILLE {side_name}", font=("Roboto", 20, "bold"), text_color=color
        )
        self.lbl_title.pack(pady=(15, 5))

        self.lbl_file = ctk.CTkLabel(self, text="Aucun fichier chargé", text_color="gray", wraplength=200)
        self.lbl_file.pack(pady=5)

        self.progress = ctk.CTkProgressBar(self, width=180, height=12, progress_color=color)
        self.progress.set(0)

        self.btn_load = ctk.CTkButton(
            self, text="Choisir un fichier", command=self.select_file, fg_color=color, hover_color="#333333"
        )
        self.btn_load.pack(pady=10)

        self.lbl_vol = ctk.CTkLabel(self, text="Volume: 80%")
        self.lbl_vol.pack(pady=(5, 0))
        self.slider = ctk.CTkSlider(self, from_=0, to=1, command=self.update_volume, progress_color=color)
        self.slider.set(0.8)
        self.slider.pack(pady=5, padx=20, fill="x")

    def select_file(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Fichiers Audio", "*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.wma"),
                ("Tous les fichiers", "*.*"),
            ]
        )
        if path:
            self.filepath = path
            threading.Thread(target=self.heavy_import, args=(path,), daemon=True).start()
            self.start_animation()

    def start_animation(self):
        self.is_loading_active = True
        self.btn_load.configure(state="disabled", text="Chargement...")
        self.progress.pack(pady=5)
        self.loading_progress_val = 0.0
        self.progress.set(0)
        self.fake_progress_loop()

    def fake_progress_loop(self):
        if not self.is_loading_active:
            return

        if self.loading_progress_val < 0.85:
            self.loading_progress_val += 0.02
            self.progress.set(self.loading_progress_val)
            self.after(30, self.fake_progress_loop)

    def heavy_import(self, path):
        try:
            pg_sound = pygame.mixer.Sound(path)
            pd_audio = AudioSegment.from_file(path)
            name = os.path.splitext(os.path.basename(path))[0]
            self.after(0, lambda: self.finish_loading(pg_sound, pd_audio, name))
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self.stop_animation_error(err_msg))

    def finish_loading(self, pg_sound, pd_audio, name):
        self.is_loading_active = False
        self.sound = pg_sound
        self.pydub_audio = pd_audio
        self.filename_short = name

        self.progress.set(1.0)
        disp_name = name if len(name) < 25 else name[:12] + "..." + name[-8:]
        self.lbl_file.configure(text=disp_name, text_color="white")
        self.after(400, self.reset_loading_ui)

    def stop_animation_error(self, err_msg="Erreur"):
        self.is_loading_active = False
        self.reset_loading_ui()
        self.lbl_file.configure(text="Erreur lecture fichier", text_color="#e74c3c")
        messagebox.showerror("Erreur Audio", f"Impossible de charger le fichier audio :\n{err_msg}")

    def reset_loading_ui(self):
        self.progress.pack_forget()
        self.btn_load.configure(state="normal", text="Changer de Musique")

    def update_volume(self, value):
        val_float = float(value)
        self.lbl_vol.configure(text=f"Volume: {int(val_float * 100)}%")
        if self.channel:
            if self.side_index == 0:
                self.channel.set_volume(val_float, 0.0)
            else:
                self.channel.set_volume(0.0, val_float)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Dual-Audio — Dichotic Audio Mixer")
        self.geometry("780x520")
        self.minsize(680, 480)
        self.is_playing = False

        self.lbl_main = ctk.CTkLabel(self, text="MIXEUR DICHOTIQUE (DUAL AUDIO)", font=("Roboto", 22, "bold"))
        self.lbl_main.pack(pady=15)

        self.lbl_sub = ctk.CTkLabel(
            self,
            text="Écouteurs ou casque requis : un flux audio distinct dans chaque oreille.",
            font=("Roboto", 12),
            text_color="#9ca3af"
        )
        self.lbl_sub.pack(pady=(0, 10))

        # Decks gauche / droite
        self.deck_area = ctk.CTkFrame(self, fg_color="transparent")
        self.deck_area.pack(fill="both", expand=True, padx=20)
        self.deck_left = AudioDeck(self.deck_area, "GAUCHE", 0, "#3498db")
        self.deck_right = AudioDeck(self.deck_area, "DROITE", 1, "#e74c3c")

        # Zone de commandes
        self.ctrl_area = ctk.CTkFrame(self, height=80, fg_color="#1a1a1a", corner_radius=20)
        self.ctrl_area.pack(fill="x", padx=20, pady=20)

        self.ctrl_area.grid_columnconfigure(0, weight=0)
        self.ctrl_area.grid_columnconfigure(1, weight=1)
        self.ctrl_area.grid_columnconfigure(2, weight=0)
        self.ctrl_area.grid_columnconfigure(3, weight=0)

        self.btn_play = ctk.CTkButton(
            self.ctrl_area,
            text="▶ LECTURE",
            font=("Arial", 16, "bold"),
            command=self.toggle_play,
            height=45,
            width=160,
            fg_color="#2ecc71",
            hover_color="#27ae60",
        )
        self.btn_play.grid(row=0, column=0, padx=20, pady=15)

        self.btn_export = ctk.CTkButton(
            self.ctrl_area,
            text="💾 EXPORTER LE MIX",
            font=("Arial", 14, "bold"),
            command=self.export_mix,
            height=45,
            width=180,
            fg_color="#9b59b6",
            hover_color="#8e44ad",
        )
        self.btn_export.grid(row=0, column=2, padx=(10, 10), pady=15)

        self.lbl_status = ctk.CTkLabel(self.ctrl_area, text="", font=("Arial", 18, "bold"))
        self.lbl_status.grid(row=0, column=3, padx=(0, 20), pady=15)

        self.bind("<space>", lambda e: self.toggle_play())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def toggle_play(self):
        if self.is_playing:
            pygame.mixer.stop()
            self.is_playing = False
            self.btn_play.configure(text="▶ LECTURE", fg_color="#2ecc71", hover_color="#27ae60")
            self.deck_left.btn_load.configure(state="normal")
            self.deck_right.btn_load.configure(state="normal")
        else:
            if not self.deck_left.sound or not self.deck_right.sound:
                self.btn_play.configure(fg_color="#e74c3c")
                self.show_status("Veuillez charger 2 pistes", "#e74c3c")
                self.after(800, lambda: self.btn_play.configure(fg_color="#2ecc71"))
                return

            pygame.mixer.stop()

            self.deck_left.channel = pygame.mixer.find_channel()
            if self.deck_left.channel:
                self.deck_left.channel.play(self.deck_left.sound, loops=-1)
                self.deck_left.update_volume(self.deck_left.slider.get())

            self.deck_right.channel = pygame.mixer.find_channel()
            if self.deck_right.channel:
                self.deck_right.channel.play(self.deck_right.sound, loops=-1)
                self.deck_right.update_volume(self.deck_right.slider.get())

            self.is_playing = True
            self.btn_play.configure(text="⏹ STOP", fg_color="#c0392b", hover_color="#7b241c")
            self.deck_left.btn_load.configure(state="disabled")
            self.deck_right.btn_load.configure(state="disabled")

    def export_mix(self):
        if not self.deck_left.pydub_audio or not self.deck_right.pydub_audio:
            self.show_status("Chargez 2 fichiers d'abord", "#e74c3c")
            return

        default_name = f"{self.deck_left.filename_short}_VS_{self.deck_right.filename_short}.mp3"
        save_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            initialfile=default_name,
            filetypes=[("Fichier MP3", "*.mp3"), ("Fichier WAV", "*.wav")],
        )
        if not save_path:
            return

        self.btn_export.configure(text="Exportation en cours...", state="disabled")
        self.lbl_status.configure(text="")
        threading.Thread(target=self.process_export, args=(save_path,), daemon=True).start()

    def process_export(self, save_path):
        try:
            sound_L = self.deck_left.pydub_audio
            sound_R = self.deck_right.pydub_audio

            def get_gain(slider_val):
                return 20 * math.log10(slider_val) if slider_val > 0 else -100

            sound_L = sound_L + get_gain(self.deck_left.slider.get())
            sound_R = sound_R + get_gain(self.deck_right.slider.get())

            mixed = sound_L.pan(-1.0).overlay(sound_R.pan(1.0))

            ext = os.path.splitext(save_path)[1].lower().replace(".", "")
            if not ext:
                ext = "mp3"

            mixed.export(save_path, format=ext)
            self.after(0, lambda: self.show_status("✔ Export Réussi", "#2ecc71"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self.show_status("✘ Erreur Export", "#e74c3c"))
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Erreur d'exportation",
                    f"Impossible d'exporter le fichier audio :\n{err}\n\n"
                    "Note : L'export MP3 nécessite FFmpeg sur votre système. "
                    "Vous pouvez aussi choisir d'exporter au format .WAV !",
                ),
            )
        finally:
            self.after(0, lambda: self.btn_export.configure(text="💾 EXPORTER LE MIX", state="normal"))

    def show_status(self, text, color):
        self.lbl_status.configure(text=text, text_color=color)
        self.after(4000, lambda: self.lbl_status.configure(text=""))

    def on_close(self):
        try:
            pygame.mixer.stop()
            pygame.quit()
        except Exception:
            pass
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
