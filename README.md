# 🎧 Dual-Audio — Dichotic Audio Mixer & Player

[![Platform Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue.svg?logo=windows)](https://github.com/je-tu-il/Dual-Audio/releases)
[![Release](https://img.shields.io/github/v/release/je-tu-il/Dual-Audio?color=success&include_prereleases)](https://github.com/je-tu-il/Dual-Audio/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg?logo=python)](requirements.txt)
[![UI: CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-blueviolet.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Une application moderne et intuitive permettant de **jouer deux pistes audio simultanément en écoute dichotique** : une piste dans l'oreille gauche et une autre dans l'oreille droite, avec réglages indépendants de volume et export du mix stéréo.

---

## ⚡ Téléchargement 1-Clic (Sans Python)

Pour les utilisateurs Windows :

👉 **[Télécharger Dual-Audio.exe (Dernière Version)](https://github.com/je-tu-il/Dual-Audio/releases/latest)**

1. Téléchargez `Dual-Audio.exe` ou l'archive portable `.zip`.
2. Double-cliquez pour ouvrir.
3. Branchez votre casque ou vos écouteurs.
4. Chargez votre piste gauche (bleue) et votre piste droite (rouge).
5. Ajustez les volumes puis appuyez sur **▶ LECTURE** ou exportez en fichier unique !

---

## ✨ Fonctionnalités

- 🎧 **Écoute Dichotique Précise** : Séparation spatiale stricte 100% canal gauche / 100% canal droit.
- 🎚️ **Mixage Dynamique en Direct** : Sliders de volume indépendants pour chaque oreille réactifs en temps réel.
- 💾 **Export Stéréo (MP3 / WAV)** : Fusionnez vos deux musiques en un seul fichier stéréo avec application automatique des gains de volume choisis.
- 🎨 **Interface Dark Mode Moderne** : Conçue avec CustomTkinter, animation fluide de chargement et gestion ergonomique des erreurs.
- ⌨️ **Raccourci Espace** : Lancez ou coupez la lecture avec la barre d'espace.

---

## 🛠️ Lancement pour Développeurs (Code Source)

### Prérequis
- Python 3.9 ou supérieur
- FFmpeg (recommandé pour l'export MP3 avec pydub)

### Installation
```bash
git clone https://github.com/je-tu-il/Dual-Audio.git
cd Dual-Audio
pip install -r requirements.txt
```

### Lancement
```bash
python main.py
```

---

## 📄 Licence

Ce projet est sous licence MIT. Libre d'utilisation et de modification.
