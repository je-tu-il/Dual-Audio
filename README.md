# Dual Audio Web

Un mixeur pour écouter deux pistes simultanément au casque, une par oreille, avec des volumes indépendants et un export WAV stéréo. Les fichiers sont traités dans le navigateur.

## Ouvrir

Sous Windows, double-cliquer sur [Lancer_Projet.bat](Lancer_Projet.bat). Sur les autres systèmes, ouvrir directement [pages/index.html](pages/index.html). Charger ses propres pistes ou utiliser les sons d’essai.

## Tester

Lancer [run_tests.bat](run_tests.bat) sous Windows ou exécuter `node --test tests/web-audio.test.cjs` depuis la racine du dépôt.

## Publier

Choisir **GitHub Actions** dans les réglages Pages, puis lancer le workflow **Dual Audio Web** depuis la branche principale. Voir les [tâches de publication](.github/WEB_TASKS.md).

Le catalogue du portfolio héberge une copie de `pages/` dans `projects/dual-audio/`. Pour la synchroniser depuis la racine du dépôt, utiliser la commande PowerShell suivante.

```powershell
Copy-Item pages/* ../../07_PORTFOLIO_ET_DOCS/je-tu-il.github.io/projects/dual-audio -Recurse -Force
```

[Licence MIT](LICENSE)
