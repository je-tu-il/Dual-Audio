#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dual-Audio — Dichotic Audio Mixer & Player
Jouez deux fichiers audio différents simultanément (un dans chaque oreille) avec contrôle de volume indépendant et export stéréo mixé.
"""

import os
import sys
import threading
import time
import math
import tkinter as tk
from tkinter import filedialog, messagebox

# --- Patch Anti-Console Windows sous Windows ---
if os.name == "nt":
    import subprocess
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

# Configuration UI
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Initialisation Audio ultra-rapide
try:
    pygame.mixer.pre_init(44100, -16, 2, 1024)
    pygame.init()
    pygame.mixer.set_num_channels(8)
except Exception as e:
    pass


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

        self.configure(fg_color="#232630", corner_radius=15, border_width=2, border_color=color, cursor="hand2")
        self.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # En-tête du Deck
        self.lbl_title = ctk.CTkLabel(
            self, text=f"OREILLE {side_name}", font=("Roboto", 20, "bold"), text_color=color
        )
        self.lbl_title.pack(pady=(15, 5))

        # Zone d'interaction clic direct pour charger
        self.drop_card = ctk.CTkFrame(self, fg_color="#181a20", corner_radius=10, border_width=1, border_color="#333a4d")
        self.drop_card.pack(fill="x", padx=15, pady=8)

        self.lbl_file = ctk.CTkLabel(
            self.drop_card,
            text="📁 Cliquez pour choisir un fichier",
            font=("Roboto", 12),
            text_color="#94a3b8",
            wraplength=220,
            justify="center"
        )
        self.lbl_file.pack(pady=15, padx=10)

        # Rendre toute la carte cliquable
        for w in (self, self.drop_card, self.lbl_file, self.lbl_title):
            w.bind("<Button-1>", lambda e: self.select_file())

        self.lbl_vol = ctk.CTkLabel(self, text="Volume: 80%", font=("Roboto", 12, "bold"))
        self.lbl_vol.pack(pady=(10, 0))
        self.slider = ctk.CTkSlider(self, from_=0, to=1, command=self.update_volume, progress_color=color)
        self.slider.set(0.8)
        self.slider.pack(pady=5, padx=20, fill="x")

    def select_file(self):
        path = filedialog.askopenfilename(
            title=f"Choisir la musique pour l'oreille {self.side_name}",
            filetypes=[
                ("Fichiers Audio", "*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.wma"),
                ("Tous les fichiers", "*.*"),
            ]
        )
        if path:
            self.filepath = path
            self.load_audio_fast(path)

    def load_audio_fast(self, path):
        """Chargement instantané de pygame sans bloquer avec pydub"""
        name = os.path.splitext(os.path.basename(path))[0]
        self.lbl_file.configure(text=f"Chargement de {name[:20]}...", text_color="#60a5fa")
        
        def _bg_load():
            try:
                pg_sound = pygame.mixer.Sound(path)
                self.after(0, lambda: self.on_audio_loaded(pg_sound, name, path))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self.on_audio_error(err))

        threading.Thread(target=_bg_load, daemon=True).start()

    def on_audio_loaded(self, pg_sound, name, path):
        self.sound = pg_sound
        self.filename_short = name
        self.filepath = path
        disp_name = name if len(name) < 26 else name[:14] + "..." + name[-8:]
        self.lbl_file.configure(
            text=f"🎵 {disp_name}\n✓ Prêt à jouer (Cliquez pour changer)",
            text_color="#34d399"
        )

    def on_audio_error(self, err_msg):
        self.lbl_file.configure(text="❌ Erreur de lecture", text_color="#f87171")
        messagebox.showerror("Erreur Audio", f"Impossible de charger le fichier audio :\n{err_msg}")

    def update_volume(self, value):
        val_float = float(value)
        self.lbl_vol.configure(text=f"Volume: {int(val_float * 100)}%")
        if self.channel:
            if self.side_index == 0:
                self.channel.set_volume(val_float, 0.0)
            else:
                self.channel.set_volume(0.0, val_float)

    def get_pydub_segment(self):
        """Chargé à la demande uniquement pour l'export"""
        if self.filepath:
            from pydub import AudioSegment
            return AudioSegment.from_file(self.filepath)
        return None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Dual-Audio — Dichotic Audio Mixer")
        self.geometry("780x500")
        self.minsize(680, 460)
        self.is_playing = False

        self.lbl_main = ctk.CTkLabel(self, text="MIXEUR DICHOTIQUE (DUAL AUDIO)", font=("Roboto", 22, "bold"))
        self.lbl_main.pack(pady=(15, 2))

        self.lbl_sub = ctk.CTkLabel(
            self,
            text="Écouteurs ou casque requis : un flux audio distinct dans chaque oreille.",
            font=("Roboto", 12),
            text_color="#94a3b8"
        )
        self.lbl_sub.pack(pady=(0, 10))

        # Decks gauche / droite
        self.deck_area = ctk.CTkFrame(self, fg_color="transparent")
        self.deck_area.pack(fill="both", expand=True, padx=20)
        self.deck_left = AudioDeck(self.deck_area, "GAUCHE", 0, "#38bdf8")
        self.deck_right = AudioDeck(self.deck_area, "DROITE", 1, "#f43f5e")

        # Zone de commandes
        self.ctrl_area = ctk.CTkFrame(self, height=75, fg_color="#181a20", corner_radius=16)
        self.ctrl_area.pack(fill="x", padx=20, pady=15)

        self.ctrl_area.grid_columnconfigure(0, weight=0)
        self.ctrl_area.grid_columnconfigure(1, weight=1)
        self.ctrl_area.grid_columnconfigure(2, weight=0)
        self.ctrl_area.grid_columnconfigure(3, weight=0)

        self.btn_play = ctk.CTkButton(
            self.ctrl_area,
            text="▶ LECTURE",
            font=("Arial", 15, "bold"),
            command=self.toggle_play,
            height=42,
            width=150,
            fg_color="#10b981",
            hover_color="#059669",
        )
        self.btn_play.grid(row=0, column=0, padx=20, pady=15)

        self.btn_export = ctk.CTkButton(
            self.ctrl_area,
            text="💾 EXPORTER LE MIX",
            font=("Arial", 14, "bold"),
            command=self.export_mix,
            height=42,
            width=170,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
        )
        self.btn_export.grid(row=0, column=2, padx=(10, 10), pady=15)

        self.lbl_status = ctk.CTkLabel(self.ctrl_area, text="", font=("Arial", 14, "bold"))
        self.lbl_status.grid(row=0, column=3, padx=(0, 20), pady=15)

        self.bind("<space>", lambda e: self.toggle_play())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def toggle_play(self):
        if self.is_playing:
            pygame.mixer.stop()
            self.is_playing = False
            self.btn_play.configure(text="▶ LECTURE", fg_color="#10b981", hover_color="#059669")
        else:
            if not self.deck_left.sound or not self.deck_right.sound:
                self.btn_play.configure(fg_color="#f43f5e")
                self.show_status("Veuillez charger 2 pistes", "#f43f5e")
                self.after(800, lambda: self.btn_play.configure(fg_color="#10b981"))
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
            self.btn_play.configure(text="⏹ STOP", fg_color="#ef4444", hover_color="#dc2626")

    def export_mix(self):
        if not self.deck_left.sound or not self.deck_right.sound:
            self.show_status("Chargez 2 fichiers d'abord", "#f43f5e")
            return

        default_name = f"{self.deck_left.filename_short}_VS_{self.deck_right.filename_short}.mp3"
        save_path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            initialfile=default_name,
            filetypes=[("Fichier MP3", "*.mp3"), ("Fichier WAV", "*.wav")],
        )
        if not save_path:
            return

        self.btn_export.configure(text="Export en cours...", state="disabled")
        self.lbl_status.configure(text="")
        threading.Thread(target=self.process_export, args=(save_path,), daemon=True).start()

    def process_export(self, save_path):
        try:
            sound_L = self.deck_left.get_pydub_segment()
            sound_R = self.deck_right.get_pydub_segment()

            if sound_L is None or sound_R is None:
                raise Exception("Impossible de lire les flux audio pour l'export.")

            def get_gain(slider_val):
                return 20 * math.log10(slider_val) if slider_val > 0 else -100

            sound_L = sound_L + get_gain(self.deck_left.slider.get())
            sound_R = sound_R + get_gain(self.deck_right.slider.get())

            mixed = sound_L.pan(-1.0).overlay(sound_R.pan(1.0))

            ext = os.path.splitext(save_path)[1].lower().replace(".", "")
            if not ext:
                ext = "mp3"

            mixed.export(save_path, format=ext)
            self.after(0, lambda: self.show_status("✔ Export Réussi", "#10b981"))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self.show_status("✘ Erreur Export", "#f43f5e"))
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
