import os
import subprocess
import sys

# --- PATCH ANTI-CMD (Bloque les fenêtres noires) ---
if os.name == 'nt':
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    _original_Popen = subprocess.Popen
    class Popen(_original_Popen):
        def __init__(self, *args, **kwargs):
            kwargs['startupinfo'] = startupinfo
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)
    subprocess.Popen = Popen
# ---------------------------------------------------

import customtkinter as ctk
from tkinter import filedialog
import pygame
import threading
import time
from pydub import AudioSegment

# Config Design
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Init Audio
pygame.mixer.pre_init(44100, -16, 2, 2048)
pygame.init()
pygame.mixer.set_num_channels(8)

class AudioDeck(ctk.CTkFrame):
    def __init__(self, master, side_name, side_index, color):
        super().__init__(master)
        self.side_name = side_name
        self.side_index = side_index
        self.accent_color = color
        
        self.filepath = None
        self.filename_short = "Inconnu"
        self.sound = None
        self.channel = None
        self.pydub_audio = None 
        
        # Variables pour la barre de chargement
        self.loading_progress_val = 0.0
        self.is_loading_active = False # L'interrupteur de sécurité

        # Design Cadre
        self.configure(fg_color="#2b2b2b", corner_radius=15, border_width=2, border_color=color)
        self.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Titre
        self.lbl_title = ctk.CTkLabel(self, text=f"OREILLE {side_name}", font=("Roboto", 20, "bold"), text_color=color)
        self.lbl_title.pack(pady=(15, 5))

        # Nom Fichier
        self.lbl_file = ctk.CTkLabel(self, text="Aucun fichier", text_color="gray", wraplength=180)
        self.lbl_file.pack(pady=5)

        # Barre de chargement
        self.progress = ctk.CTkProgressBar(self, width=180, height=12, progress_color=color)
        self.progress.set(0)
        
        # Bouton Charger
        self.btn_load = ctk.CTkButton(self, text="Charger Musique", command=self.select_file, fg_color=color, hover_color="#333333")
        self.btn_load.pack(pady=10)

        # Slider Volume
        self.lbl_vol = ctk.CTkLabel(self, text="Volume: 80%")
        self.lbl_vol.pack(pady=(5,0))
        self.slider = ctk.CTkSlider(self, from_=0, to=1, command=self.update_volume, progress_color=color)
        self.slider.set(0.8)
        self.slider.pack(pady=5, padx=20, fill="x")

    def select_file(self):
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.ogg *.m4a *.flac")])
        if path:
            self.filepath = path
            threading.Thread(target=self.heavy_import, args=(path,), daemon=True).start()
            self.start_animation()

    def start_animation(self):
        self.is_loading_active = True # On active l'animation
        self.btn_load.configure(state="disabled", text="Chargement...")
        self.progress.pack(pady=5)
        self.loading_progress_val = 0.0
        self.progress.set(0)
        self.fake_progress_loop()

    def fake_progress_loop(self):
        # Si le chargement est fini (flag False), on arrête TOUT DE SUITE la boucle
        if not self.is_loading_active:
            return

        # Sinon on avance doucement
        if self.loading_progress_val < 0.85: # On s'arrête à 85% en attendant la fin réelle
            self.loading_progress_val += 0.015 # Vitesse de progression
            self.progress.set(self.loading_progress_val)
            # On se rappelle plus souvent pour plus de fluidité (30ms)
            self.after(30, self.fake_progress_loop)

    def heavy_import(self, path):
        try:
            pg_sound = pygame.mixer.Sound(path)
            pd_audio = AudioSegment.from_file(path)
            name = os.path.splitext(os.path.basename(path))[0]
            self.after(0, lambda: self.finish_loading(pg_sound, pd_audio, name))
        except Exception as e:
            # En cas d'erreur on arrête proprement
            self.after(0, self.stop_animation_error)

    def finish_loading(self, pg_sound, pd_audio, name):
        # 1. On coupe l'animation fictive IMMÉDIATEMENT
        self.is_loading_active = False
        
        # 2. On met les données
        self.sound = pg_sound
        self.pydub_audio = pd_audio
        self.filename_short = name
        
        # 3. On force la barre à 100% visuellement
        self.progress.set(1.0) 
        
        # 4. Affichage du nom
        disp_name = name if len(name) < 25 else name[:12] + "..." + name[-8:]
        self.lbl_file.configure(text=disp_name, text_color="white")
        
        # 5. On attend un peu que l'utilisateur voie le 100% avant de cacher
        self.after(500, self.reset_loading_ui)

    def stop_animation_error(self):
        self.is_loading_active = False
        self.reset_loading_ui()
        self.lbl_file.configure(text="Erreur fichier", text_color="#e74c3c")

    def reset_loading_ui(self):
        self.progress.pack_forget()
        self.btn_load.configure(state="normal", text="Changer Musique")

    def update_volume(self, value):
        val_float = float(value)
        self.lbl_vol.configure(text=f"Volume: {int(val_float*100)}%")
        if self.channel:
            if self.side_index == 0:
                self.channel.set_volume(val_float, 0.0)
            else:
                self.channel.set_volume(0.0, val_float)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Dual Brain Audio Mixer")
        self.geometry("750x500")
        self.is_playing = False

        self.lbl_main = ctk.CTkLabel(self, text="MIXEUR DICHOTIQUE", font=("Roboto", 24, "bold"))
        self.lbl_main.pack(pady=15)

        # Decks
        self.deck_area = ctk.CTkFrame(self, fg_color="transparent")
        self.deck_area.pack(fill="both", expand=True, padx=20)
        self.deck_left = AudioDeck(self.deck_area, "GAUCHE", 0, "#3498db")
        self.deck_right = AudioDeck(self.deck_area, "DROITE", 1, "#e74c3c")

        # Contrôles
        self.ctrl_area = ctk.CTkFrame(self, height=80, fg_color="#1a1a1a", corner_radius=20)
        self.ctrl_area.pack(fill="x", padx=20, pady=20)
        
        self.ctrl_area.grid_columnconfigure(0, weight=0)
        self.ctrl_area.grid_columnconfigure(1, weight=1)
        self.ctrl_area.grid_columnconfigure(2, weight=0)
        self.ctrl_area.grid_columnconfigure(3, weight=0)

        self.btn_play = ctk.CTkButton(self.ctrl_area, text="▶ LECTURE", font=("Arial", 16, "bold"), 
                                      command=self.toggle_play, height=45, width=150,
                                      fg_color="#2ecc71", hover_color="#27ae60")
        self.btn_play.grid(row=0, column=0, padx=20, pady=15)

        self.btn_export = ctk.CTkButton(self.ctrl_area, text="💾 EXPORTER MP3", font=("Arial", 14, "bold"), 
                                        command=self.export_mix, height=45,
                                        fg_color="#9b59b6", hover_color="#8e44ad")
        self.btn_export.grid(row=0, column=2, padx=(20, 5), pady=15)

        self.lbl_status = ctk.CTkLabel(self.ctrl_area, text="", font=("Arial", 24, "bold"))
        self.lbl_status.grid(row=0, column=3, padx=(0, 20), pady=15)

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
                self.after(500, lambda: self.btn_play.configure(fg_color="#2ecc71"))
                return

            pygame.mixer.stop()
            
            self.deck_left.channel = pygame.mixer.find_channel()
            self.deck_left.channel.play(self.deck_left.sound, loops=-1)
            self.deck_left.update_volume(self.deck_left.slider.get())

            self.deck_right.channel = pygame.mixer.find_channel()
            self.deck_right.channel.play(self.deck_right.sound, loops=-1)
            self.deck_right.update_volume(self.deck_right.slider.get())

            self.is_playing = True
            self.btn_play.configure(text="⏹ STOP", fg_color="#c0392b", hover_color="#7b241c")
            self.deck_left.btn_load.configure(state="disabled")
            self.deck_right.btn_load.configure(state="disabled")

    def export_mix(self):
        if not self.deck_left.pydub_audio or not self.deck_right.pydub_audio:
            self.show_status("✘", "#e74c3c")
            return

        default_name = f"{self.deck_left.filename_short}_VS_{self.deck_right.filename_short}.mp3"
        save_path = filedialog.asksaveasfilename(defaultextension=".mp3", initialfile=default_name, filetypes=[("MP3", "*.mp3")])
        if not save_path: return

        self.btn_export.configure(text="Traitement...", state="disabled")
        self.lbl_status.configure(text="")
        threading.Thread(target=self.process_export, args=(save_path,), daemon=True).start()

    def process_export(self, save_path):
        try:
            sound_L = self.deck_left.pydub_audio
            sound_R = self.deck_right.pydub_audio
            
            import math
            def get_gain(slider_val): return 20 * math.log10(slider_val) if slider_val > 0 else -100
            
            sound_L = sound_L + get_gain(self.deck_left.slider.get())
            sound_R = sound_R + get_gain(self.deck_right.slider.get())

            mixed = sound_L.pan(-1.0).overlay(sound_R.pan(1.0))
            mixed.export(save_path, format="mp3")
            
            self.after(0, lambda: self.show_status("✔", "#2ecc71"))
        except Exception as e:
            self.after(0, lambda: self.show_status("✘", "#e74c3c"))
        finally:
            self.after(0, lambda: self.btn_export.configure(text="💾 EXPORTER MP3", state="normal"))

    def show_status(self, symbol, color):
        self.lbl_status.configure(text=symbol, text_color=color)
        self.after(3000, lambda: self.lbl_status.configure(text=""))

if __name__ == "__main__":
    app = App()
    app.mainloop()
