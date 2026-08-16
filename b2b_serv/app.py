from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from urllib.parse import parse_qs, urlparse
import webbrowser

from relay_server import LocalRelayServer

from .models import SessionState
from .network import SessionEngine
from .tunnel import CloudflaredTunnel
from .updater import check_for_update
from .version import __version__

LOCAL_RELAY_HOST = "127.0.0.1"
LOCAL_RELAY_PORT = 47000


class B2BServApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("B2B Serv")
        self.root.geometry("1100x760")
        self.root.minsize(920, 680)

        self.state = SessionState()
        self.engine = SessionEngine(self._handle_event)
        self.local_relay: LocalRelayServer | None = None
        self.tunnel = CloudflaredTunnel(self._log_tunnel)
        self.is_busy = False

        self.username_var = tk.StringVar(value="Mon blaze DJ")
        self.code_var = tk.StringVar(value="------")
        self.link_var = tk.StringVar(value="Le lien apparaitra ici")
        self.status_var = tk.StringVar(value="Choisis une action pour commencer.")
        self.hero_var = tk.StringVar(value=f"Session inactive - v{__version__}")
        self.network_var = tk.StringVar(value="Le host cree automatiquement son serveur et son tunnel.")

        self.play_vars: dict[str, tk.StringVar] = {}
        self.volume_vars: dict[str, tk.DoubleVar] = {}
        self.remote_status_vars: dict[str, tk.StringVar] = {}
        self.log_text: tk.Text
        self.create_button: ttk.Button
        self.join_button: ttk.Button

        self._build_ui()
        self.root.after(1200, self._check_updates_async)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.root.configure(bg="#0d1016")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#0d1016")
        style.configure("Panel.TFrame", background="#171c26")
        style.configure("Glass.TFrame", background="#10151d")
        style.configure("TLabel", background="#0d1016", foreground="#f5f7fb")
        style.configure("Panel.TLabel", background="#171c26", foreground="#f5f7fb")
        style.configure("Muted.TLabel", background="#171c26", foreground="#aab3c5")
        style.configure("Big.TButton", padding=16, font=("Segoe UI", 12, "bold"))
        style.configure("Accent.TButton", padding=16, font=("Segoe UI", 12, "bold"))
        style.map("Accent.TButton", background=[("!disabled", "#ff6a3d")], foreground=[("!disabled", "white")])

        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)

        hero = ttk.Frame(outer, style="Panel.TFrame", padding=24)
        hero.pack(fill="x")
        ttk.Label(hero, text="B2B Serv", style="Panel.TLabel", font=("Bahnschrift", 28, "bold")).pack(anchor="w")
        ttk.Label(
            hero,
            text="Version desktop prete a etre exportee pour des sessions B2B simples.",
            style="Muted.TLabel",
            font=("Segoe UI", 12),
        ).pack(anchor="w", pady=(6, 0))
        ttk.Label(hero, textvariable=self.hero_var, style="Panel.TLabel", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(18, 4))
        ttk.Label(hero, textvariable=self.status_var, style="Muted.TLabel", font=("Segoe UI", 11)).pack(anchor="w")
        ttk.Label(hero, textvariable=self.network_var, style="Muted.TLabel", font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 0))

        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(18, 0))
        top.columnconfigure(0, weight=7)
        top.columnconfigure(1, weight=5)

        action_card = ttk.Frame(top, style="Panel.TFrame", padding=22)
        action_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(action_card, text="Ton nom DJ", style="Panel.TLabel", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Entry(action_card, textvariable=self.username_var, font=("Segoe UI", 12)).pack(fill="x", pady=(8, 18))

        actions = ttk.Frame(action_card, style="Panel.TFrame")
        actions.pack(fill="x")
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        self.create_button = ttk.Button(actions, text="Creer une session", command=self.create_session, style="Accent.TButton")
        self.create_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.join_button = ttk.Button(actions, text="Rejoindre une session", command=self.join_session_flow, style="Big.TButton")
        self.join_button.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(
            action_card,
            text="Le host lance le serveur automatiquement. Le guest colle juste le lien complet.",
            style="Muted.TLabel",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(16, 0))

        session_card = ttk.Frame(top, style="Panel.TFrame", padding=22)
        session_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ttk.Label(session_card, text="Session active", style="Panel.TLabel", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(session_card, text="Code", style="Muted.TLabel").pack(anchor="w", pady=(16, 0))
        ttk.Entry(session_card, textvariable=self.code_var, state="readonly", font=("Consolas", 18, "bold")).pack(fill="x", pady=(6, 10))
        ttk.Label(session_card, text="Lien d'invitation", style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(session_card, textvariable=self.link_var, state="readonly").pack(fill="x", pady=(6, 0))
        quick = ttk.Frame(session_card, style="Panel.TFrame")
        quick.pack(fill="x", pady=(14, 0))
        ttk.Button(quick, text="Copier le code", command=self.copy_code).pack(side="left")
        ttk.Button(quick, text="Copier le lien", command=self.copy_link).pack(side="left", padx=(8, 0))

        decks = ttk.Frame(outer)
        decks.pack(fill="both", expand=True, pady=(18, 0))
        decks.columnconfigure(0, weight=1)
        decks.columnconfigure(1, weight=1)

        self._build_deck_panel(decks, "Deck A", 0)
        self._build_deck_panel(decks, "Deck B", 1)

        log_card = ttk.Frame(outer, style="Panel.TFrame", padding=22)
        log_card.pack(fill="both", expand=True, pady=(18, 0))
        ttk.Label(log_card, text="Activite", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        self.log_text = tk.Text(
            log_card,
            height=10,
            bg="#0a0e14",
            fg="#eef2ff",
            insertbackground="white",
            relief="flat",
            font=("Consolas", 10),
        )
        self.log_text.pack(fill="both", expand=True, pady=(12, 0))
        self.log_text.configure(state="disabled")

    def _build_deck_panel(self, parent: ttk.Frame, deck: str, column: int) -> None:
        card = ttk.Frame(parent, style="Panel.TFrame", padding=20)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 10) if column == 0 else (10, 0))
        ttk.Label(card, text=deck, style="Panel.TLabel", font=("Segoe UI", 16, "bold")).pack(anchor="w")

        play_var = tk.StringVar(value="Play local: OFF")
        remote_var = tk.StringVar(value="Aucune action distante")
        volume_var = tk.DoubleVar(value=0.5)
        self.play_vars[deck] = play_var
        self.remote_status_vars[deck] = remote_var
        self.volume_vars[deck] = volume_var

        ttk.Label(card, textvariable=play_var, style="Muted.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 8))

        row = ttk.Frame(card, style="Panel.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="Play / Pause", command=lambda d=deck: self.toggle_play(d)).pack(side="left")
        ttk.Button(row, text="Cue", command=lambda d=deck: self.send_button(d, "cue")).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="Sync", command=lambda d=deck: self.send_button(d, "sync")).pack(side="left", padx=(8, 0))

        ttk.Label(card, text="Volume", style="Muted.TLabel").pack(anchor="w", pady=(14, 0))
        ttk.Scale(card, from_=0.0, to=1.0, variable=volume_var, command=lambda value, d=deck: self.change_volume(d, value)).pack(fill="x", pady=(8, 12))

        status_box = ttk.Frame(card, style="Glass.TFrame", padding=12)
        status_box.pack(fill="x")
        ttk.Label(status_box, textvariable=remote_var, style="Muted.TLabel", wraplength=420).pack(anchor="w")

    def create_session(self) -> None:
        if self.is_busy:
            return
        username = self.username_var.get().strip() or "DJ"
        self._set_busy(True)
        self._cleanup_host_stack()
        self.hero_var.set("Preparation du host")
        self.status_var.set("Creation du serveur local et du tunnel automatique...")
        self.network_var.set("Cloudflared essaie d'exposer automatiquement le host sur internet.")
        threading.Thread(target=self._create_session_worker, args=(username,), daemon=True).start()

    def _create_session_worker(self, username: str) -> None:
        try:
            self.local_relay = LocalRelayServer(host=LOCAL_RELAY_HOST, port=LOCAL_RELAY_PORT)
            self.local_relay.start()
            public_url = self.tunnel.start(LOCAL_RELAY_PORT)
            code, link = self.engine.create_session(username, public_url)
            self.root.after(0, lambda: self._on_session_created(username, public_url, code, link))
        except Exception as exc:
            self.root.after(0, lambda: self._on_create_failed(str(exc)))

    def _on_session_created(self, username: str, public_url: str, code: str, link: str) -> None:
        self.code_var.set(code)
        self.link_var.set(link)
        self.hero_var.set("Session ouverte")
        self.status_var.set("Partage le code ou le lien. Le tunnel est actif.")
        self.network_var.set(f"Tunnel public actif : {public_url}")
        self._log(f"Session creee par {username}")
        self._set_busy(False)

    def _on_create_failed(self, message: str) -> None:
        self._cleanup_host_stack()
        self.hero_var.set("Erreur reseau")
        self.status_var.set("Impossible de creer la session automatiquement.")
        self.network_var.set("Verifie cloudflared et la connexion internet.")
        self._set_busy(False)
        messagebox.showerror("Creation impossible", message)

    def join_session_flow(self) -> None:
        if self.is_busy:
            return
        username = self.username_var.get().strip() or "DJ"
        value = simpledialog.askstring(
            "Rejoindre une session",
            "Colle le lien B2B complet :",
            parent=self.root,
        )
        if not value:
            return

        if not value.startswith("b2bserv://"):
            messagebox.showerror("Lien requis", "Pour ce mode auto-tunnel, il faut coller le lien complet du host.")
            return

        relay_url, _, code = self._parse_link(value.strip())
        try:
            self.engine.join_session(username, relay_url, code)
        except Exception as exc:
            messagebox.showerror("Connexion impossible", str(exc))
            return

        self.code_var.set(code)
        self.link_var.set(value.strip())
        self.hero_var.set("Connexion en cours")
        self.status_var.set("Demande envoyee. En attente de validation.")
        self.network_var.set(f"Connexion au host via {relay_url}")
        self._log(f"{username} tente de rejoindre la session {code}")

    def copy_code(self) -> None:
        code = self.code_var.get().strip()
        if not code or code == "------":
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.status_var.set("Code copie dans le presse-papiers.")

    def copy_link(self) -> None:
        link = self.link_var.get().strip()
        if not link or link == "Le lien apparaitra ici":
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(link)
        self.status_var.set("Lien copie dans le presse-papiers.")

    def toggle_play(self, deck: str) -> None:
        current = self.play_vars[deck].get().endswith("ON")
        new_value = 0.0 if current else 1.0
        self.play_vars[deck].set(f"Play local: {'ON' if new_value else 'OFF'}")
        self.engine.send_control(deck, "play", new_value)
        self._log(f"Local {deck}: play -> {int(new_value)}")

    def change_volume(self, deck: str, value: str) -> None:
        volume = round(float(value), 3)
        self.engine.send_control(deck, "volume", volume)

    def send_button(self, deck: str, control: str) -> None:
        self.engine.send_control(deck, control, 1.0)
        self._log(f"Local {deck}: {control}")

    def _handle_event(self, event: str, payload: dict) -> None:
        self.root.after(0, lambda: self._handle_event_on_ui(event, payload))

    def _handle_event_on_ui(self, event: str, payload: dict) -> None:
        if event == "approval_needed":
            self.hero_var.set("Validation requise")
            self.status_var.set("Un DJ veut rejoindre ta session.")
            allowed = messagebox.askyesno("Autoriser la connexion ?", f"{payload['name']} veut rejoindre ta session.\nAutoriser ?")
            if allowed:
                self.engine.approve_pending()
                self._log(f"Connexion autorisee pour {payload['name']}")
                self.hero_var.set("Session connectee")
                self.status_var.set("Le B2B est actif.")
            else:
                self.engine.reject_pending()
                self._log(f"Connexion refusee pour {payload['name']}")
                self.hero_var.set("Connexion refusee")
                self.status_var.set("La demande a ete refusee.")
        elif event == "peer_connected":
            self.hero_var.set("Session connectee")
            self.status_var.set(f"Connecte avec {payload['name']}.")
            self._log(f"Session active avec {payload['name']}")
        elif event == "join_rejected":
            self.hero_var.set("Connexion refusee")
            self.status_var.set("L'hote a refuse la demande.")
            self._log("Connexion refusee par l'hote")
        elif event == "remote_control":
            deck = payload["deck"]
            text = f"Action distante de {payload['name']}: {payload['control']} -> {payload['value']}"
            self.remote_status_vars[deck].set(text)
            if payload["control"] == "play":
                state = "ON" if payload["value"] >= 0.5 else "OFF"
                self.play_vars[deck].set(f"Play distant recu: {state}")
            elif payload["control"] == "volume":
                self.volume_vars[deck].set(payload["value"])
            self._log(f"Remote {deck}: {payload['control']} -> {payload['value']}")
        elif event == "connection_error":
            self.hero_var.set("Erreur reseau")
            self.status_var.set("Impossible de maintenir la connexion.")
            self.network_var.set("La session reseau a rencontre une erreur.")
            self._log(payload["message"])

    def _check_updates_async(self) -> None:
        threading.Thread(target=self._check_updates_worker, daemon=True).start()

    def _check_updates_worker(self) -> None:
        update = check_for_update()
        if update:
            self.root.after(0, lambda: self._show_update_notice(update))

    def _show_update_notice(self, update: dict) -> None:
        self.network_var.set(f"Nouvelle version disponible : {update['latest_version']}")
        should_open = messagebox.askyesno(
            "Mise a jour disponible",
            f"Une nouvelle version ({update['latest_version']}) est disponible.\nOuvrir la page de telechargement ?",
        )
        if should_open:
            webbrowser.open(update["html_url"])

    def _set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        self.create_button.configure(state=state)
        self.join_button.configure(state=state)

    def _log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _log_tunnel(self, message: str) -> None:
        self.root.after(0, lambda: self._log(f"Tunnel: {message}"))

    def _parse_link(self, link: str) -> tuple[str, int, str]:
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        return (
            query.get("relay", [""])[0],
            int(query.get("port", ["443"])[0]),
            query.get("code", [""])[0].upper(),
        )

    def _cleanup_host_stack(self) -> None:
        self.engine.stop()
        self.tunnel.stop()
        if self.local_relay:
            self.local_relay.stop()
            self.local_relay = None

    def _on_close(self) -> None:
        self._cleanup_host_stack()
        self.root.destroy()


def run() -> None:
    root = tk.Tk()
    app = B2BServApp(root)
    root.mainloop()
