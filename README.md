# B2B Serv

Application desktop Windows pour sessions B2B DJ a distance en mode `host auto + tunnel automatique`.

Repo GitHub : `https://github.com/nutelex/B2B-Server`

## Pour l'utilisateur final

1. Installer l'application
2. Le host clique sur `Creer une session`
3. Il partage le lien genere
4. Le guest clique sur `Rejoindre une session`
5. Il colle le lien
6. Le host accepte la demande

## Mises a jour

- l'application verifie au demarrage si une nouvelle release GitHub existe
- si une nouvelle version est disponible, elle propose d'ouvrir la page de telechargement
- les builds Windows sont prepares automatiquement par GitHub Actions

## Lancer en developpement

```bash
python main.py
```

## Export Windows

```bash
export.bat
```

ou

```powershell
.\build.ps1
```

Le build PyInstaller genere un dossier exportable dans `dist\B2B Serv`.

## Release GitHub

Le workflow [release.yml](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\.github\workflows\release.yml) :

- build l'application Windows
- embarque `cloudflared.exe`
- cree une archive `.zip`
- publie automatiquement la release quand tu pousses un tag `v*`

Exemple :

```bash
git tag v0.1.0
git push origin v0.1.0
```

## Architecture

- [main.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\main.py) : point d'entree
- [b2b_serv/app.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\b2b_serv\app.py) : interface desktop
- [relay_server.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\relay_server.py) : relais local du host
- [b2b_serv/network.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\b2b_serv\network.py) : client HTTP de session
- [b2b_serv/tunnel.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\b2b_serv\tunnel.py) : tunnel `cloudflared`
- [b2b_serv/updater.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\b2b_serv\updater.py) : verification des nouvelles releases
- [b2b_serv/version.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\b2b_serv\version.py) : version de l'application

## Etat actuel

Cette version est prete pour :

- repo GitHub separe
- push du code
- build Windows local
- release GitHub automatisee
- verification de mise a jour au lancement

Limites restantes :

- transport HTTP avec polling
- pas encore de vrai passthrough MIDI/HID vers Serato, rekordbox, Traktor ou VirtualDJ
- pas encore d'installateur Windows complet type Inno Setup ou MSI
