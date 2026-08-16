# B2B Serv

Application desktop Windows pour sessions B2B DJ a distance en mode `host auto + tunnel automatique`.

## Usage utilisateur

1. Le host lance l'app
2. Il clique sur `Creer une session`
3. L'app demarre automatiquement un relais local
4. L'app ouvre automatiquement un tunnel public via `cloudflared`
5. Le host partage le lien genere
6. Le guest lance l'app et clique sur `Rejoindre une session`
7. Le guest colle le lien complet
8. Le host accepte la demande

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

## Contenu de l'export

- `B2B Serv.exe`
- `cloudflared.exe` embarque automatiquement
- toutes les ressources Python necessaires

## Architecture

- [main.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\main.py) : point d'entree
- [b2b_serv/app.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\b2b_serv\app.py) : interface desktop
- [relay_server.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\relay_server.py) : relais local du host
- [b2b_serv/network.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\b2b_serv\network.py) : client HTTP de session
- [b2b_serv/tunnel.py](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\b2b_serv\tunnel.py) : tunnel `cloudflared`
- [build.ps1](C:\Users\FLOWUP\Desktop\bot_sf1x\B2B%20Serv\build.ps1) : script d'export Windows

## Etat actuel

Cette version est prete pour export desktop et demo utilisateur.

Limites restantes :

- transport HTTP avec polling, pas encore optimise latence extreme
- simulation des commandes, pas encore injection MIDI/HID reelle dans les logiciels DJ
- pas encore d'installateur `.msi` ou `.exe setup`

## Etape suivante recommande

1. passer du polling HTTP a WebSocket ou QUIC
2. brancher la vraie capture MIDI/HID
3. injecter dans un port MIDI virtuel Windows
4. creer un vrai installateur
