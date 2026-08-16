from __future__ import annotations

import re
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from urllib.parse import parse_qs, urlparse

from relay_server import LocalRelayServer

from .logging_utils import append_log, log_file_path, read_logs
from .midi_bridge import MidiBridge
from .models import SessionState
from .network import SessionEngine
from .runtime import launch_uninstaller
from .tunnel import CloudflaredTunnel
from .updater import check_for_update, download_and_launch_update
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
        self.midi_bridge = MidiBridge(self._on_local_midi_message, self._on_midi_status)
        self.local_relay: LocalRelayServer | None = None
        self.tunnel = CloudflaredTunnel(self._log_tunnel)
        self.is_busy = False

        self.username_var = tk.StringVar(value="Mon blaze DJ")
        self.code_var = tk.StringVar(value="------")
        self.link_var = tk.StringVar(value="Le lien apparaitra ici")
        self.status_var = tk.StringVar(value="Choisis une action pour commencer.")
        self.hero_var = tk.StringVar(value=f"Session inactive - v{__version__}")
        self.network_var = tk.StringVar(value="Le host cree automatiquement son serveur et son tunnel.")
        self.profile_var = tk.StringVar(value="VirtualDJ")
        self.midi_input_var = tk.StringVar(value="")
        self.midi_output_var = tk.StringVar(value="")
        self.midi_status_var = tk.StringVar(value="MIDI inactif.")
        self.setup_hint_var = tk.StringVar(
            value="Mode VirtualDJ : active ton controleur ici, puis le receveur choisit la sortie MIDI recommandee."
        )
        self.local_controller_var = tk.StringVar(value="Controleur local : aucun")
        self.remote_controller_var = tk.StringVar(value="Controleur distant : inconnu")

        self.play_vars: dict[str, tk.StringVar] = {}
        self.volume_vars: dict[str, tk.DoubleVar] = {}
        self.remote_status_vars: dict[str, tk.StringVar] = {}
        self.midi_input_combo: ttk.Combobox
        self.midi_output_combo: ttk.Combobox
        self.log_text: tk.Text
        self.create_button: ttk.Button
        self.join_button: ttk.Button
        self.log_window: tk.Toplevel | None = None
        self.log_window_text: tk.Text | None = None

        self._build_ui()
        self.root.after(1200, self._check_updates_async)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._log(f"Application demarree en version {__version__}")

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
        ttk.Button(action_card, text="Desinstaller l'application", command=self.uninstall_app).pack(anchor="w", pady=(14, 0))
        ttk.Button(action_card, text="Ouvrir les logs", command=self.open_logs_window).pack(anchor="w", pady=(10, 0))

        ttk.Label(
            action_card,
            text="Le host lance le serveur automatiquement. Le guest colle juste le lien complet.",
            style="Muted.TLabel",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(16, 0))
        setup_actions = ttk.Frame(action_card, style="Panel.TFrame")
        setup_actions.pack(anchor="w", pady=(12, 0))
        ttk.Button(setup_actions, text="Assistant VirtualDJ", command=self.open_virtualdj_guide).pack(side="left")
        ttk.Button(setup_actions, text="Optimiser VirtualDJ", command=self.optimize_for_virtualdj).pack(side="left", padx=(8, 0))

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

        midi_card = ttk.Frame(outer, style="Panel.TFrame", padding=22)
        midi_card.pack(fill="x", pady=(18, 0))
        midi_card.columnconfigure(0, weight=1)
        midi_card.columnconfigure(1, weight=1)
        ttk.Label(midi_card, text="Controleur MIDI universel", style="Panel.TLabel", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            midi_card,
            text="Branche ton controleur, active l'entree MIDI, puis choisis une sortie distante si ton logiciel ecoute un port MIDI.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 14))
        ttk.Label(midi_card, text="Entree controleur", style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(midi_card, text="Sortie distante", style="Muted.TLabel").grid(row=2, column=1, sticky="w")
        ttk.Label(midi_card, text="Profil logiciel", style="Muted.TLabel").grid(row=2, column=2, sticky="w", padx=(8, 0))
        self.midi_input_combo = ttk.Combobox(midi_card, textvariable=self.midi_input_var, state="readonly")
        self.midi_input_combo.grid(row=3, column=0, sticky="ew", padx=(0, 8))
        self.midi_output_combo = ttk.Combobox(midi_card, textvariable=self.midi_output_var, state="readonly")
        self.midi_output_combo.grid(row=3, column=1, sticky="ew", padx=(8, 0))
        profile_combo = ttk.Combobox(midi_card, textvariable=self.profile_var, state="readonly", values=["VirtualDJ"])
        profile_combo.grid(row=3, column=2, sticky="ew", padx=(8, 0))
        midi_card.columnconfigure(2, weight=0)
        midi_actions = ttk.Frame(midi_card, style="Panel.TFrame")
        midi_actions.grid(row=4, column=0, columnspan=3, sticky="w", pady=(12, 0))
        ttk.Button(midi_actions, text="Rafraichir les ports", command=self.refresh_midi_ports).pack(side="left")
        ttk.Button(midi_actions, text="Activer le controleur", command=self.activate_midi).pack(side="left", padx=(8, 0))
        ttk.Button(midi_actions, text="Appliquer la sortie distante", command=self.apply_midi_output).pack(side="left", padx=(8, 0))
        ttk.Button(midi_actions, text="Couper le MIDI", command=self.disable_midi).pack(side="left", padx=(8, 0))
        ttk.Label(midi_card, textvariable=self.midi_status_var, style="Muted.TLabel", wraplength=920).grid(row=5, column=0, columnspan=3, sticky="w", pady=(14, 0))
        ttk.Label(midi_card, textvariable=self.setup_hint_var, style="Muted.TLabel", wraplength=920).grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(midi_card, textvariable=self.local_controller_var, style="Muted.TLabel", wraplength=920).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(midi_card, textvariable=self.remote_controller_var, style="Muted.TLabel", wraplength=920).grid(row=8, column=0, columnspan=3, sticky="w", pady=(4, 0))

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
        self.refresh_midi_ports()
        self.optimize_for_virtualdj(initial=True)

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
            self._log(f"Debut creation session pour {username}")
            self.local_relay = LocalRelayServer(host=LOCAL_RELAY_HOST, port=LOCAL_RELAY_PORT)
            self.local_relay.start()
            public_url = self.tunnel.start(LOCAL_RELAY_PORT)
            code, link = self.engine.create_session(
                username=username,
                local_relay_base_url=f"http://{LOCAL_RELAY_HOST}:{LOCAL_RELAY_PORT}",
                public_relay_url=public_url,
            )
            self.root.after(0, lambda: self._on_session_created(username, public_url, code, link))
        except Exception as exc:
            message = str(exc) or repr(exc) or "Erreur inconnue pendant la creation de session."
            self.root.after(0, lambda msg=message: self._on_create_failed(msg))

    def _on_session_created(self, username: str, public_url: str, code: str, link: str) -> None:
        self.code_var.set(code)
        self.link_var.set(link)
        self.hero_var.set("Session ouverte")
        self.status_var.set("Partage le code ou le lien. Le tunnel est actif.")
        self.network_var.set(f"Tunnel public actif : {public_url}")
        self._share_controller_name()
        self._log(f"Session creee par {username}")
        self._set_busy(False)

    def _on_create_failed(self, message: str) -> None:
        self._cleanup_host_stack()
        self.hero_var.set("Erreur reseau")
        self.status_var.set("Impossible de creer la session automatiquement.")
        self.network_var.set(message if message else "Verifie cloudflared et la connexion internet.")
        self._set_busy(False)
        messagebox.showerror("Creation impossible", message or "Erreur inconnue.")

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

        cleaned_link = self._sanitize_link(value.strip())
        relay_url, _, code = self._parse_link(cleaned_link)
        try:
            self.engine.join_session(username, relay_url, code)
        except Exception as exc:
            self._log(f"Echec connexion guest a {relay_url} pour le code {code}: {exc}")
            messagebox.showerror("Connexion impossible", str(exc))
            return

        self.code_var.set(code)
        self.link_var.set(cleaned_link)
        self.hero_var.set("Connexion en cours")
        self.status_var.set("Demande envoyee. En attente de validation.")
        self.network_var.set(f"Connexion au host via {relay_url}")
        self.remote_controller_var.set("Controleur distant : en attente de connexion")
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
        self._log(f"Evenement recu: {event} {payload}")
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
            if self.profile_var.get() == "VirtualDJ":
                self._auto_prepare_virtualdj_output()
            self._share_controller_name()
            self._log(f"Session active avec {payload['name']}")
        elif event == "join_rejected":
            self.hero_var.set("Connexion refusee")
            self.status_var.set("L'hote a refuse la demande.")
            self._log("Connexion refusee par l'hote")
        elif event == "remote_controller_name":
            controller_name = payload["controller_name"] or "aucun"
            self.remote_controller_var.set(f"Controleur distant : {controller_name}")
            self._log(f"Controleur distant de {payload['name']} : {controller_name}")
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
        elif event == "remote_midi":
            message = payload["message"]
            self.midi_bridge.send_remote_message(message)
            summary = self._format_midi_message(message)
            self.midi_status_var.set(f"MIDI distant recu de {payload['name']} : {summary}")
            self._log(f"MIDI distant {payload['name']}: {summary}")
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
        should_install = messagebox.askyesno(
            "Mise a jour disponible",
            f"Une nouvelle version ({update['latest_version']}) est disponible.\nTelecharger et installer maintenant ?",
        )
        if should_install:
            self._install_update_async(update)

    def _install_update_async(self, update: dict) -> None:
        if self.is_busy:
            return
        self._set_busy(True)
        self.hero_var.set("Mise a jour en cours")
        self.status_var.set("Telechargement de l'installateur...")
        threading.Thread(target=self._install_update_worker, args=(update,), daemon=True).start()

    def _install_update_worker(self, update: dict) -> None:
        try:
            download_and_launch_update(update["installer_url"], update["installer_name"])
            self.root.after(0, self._on_update_started)
        except Exception as exc:
            message = str(exc) or repr(exc) or "Erreur inconnue pendant la mise a jour."
            self.root.after(0, lambda msg=message: self._on_update_failed(msg))

    def _on_update_started(self) -> None:
        self._set_busy(False)
        self.hero_var.set("Mise a jour lancee")
        self.status_var.set("Mise a jour en cours...")
        self.network_var.set("Une petite fenetre de progression a ete ouverte. L'app va se relancer automatiquement.")
        self.root.after(800, self._close_for_update)

    def _close_for_update(self) -> None:
        self._cleanup_host_stack()
        self.root.destroy()

    def uninstall_app(self) -> None:
        should_uninstall = messagebox.askyesno(
            "Desinstaller B2B Serv",
            "Veux-tu lancer la desinstallation de B2B Serv ?",
        )
        if not should_uninstall:
            return
        try:
            launch_uninstaller()
        except FileNotFoundError as exc:
            messagebox.showerror("Desinstallation impossible", str(exc))
            return
        self.root.after(500, self._on_close)

    def _on_update_failed(self, message: str) -> None:
        self._set_busy(False)
        self.hero_var.set(f"Session inactive - v{__version__}")
        self.status_var.set("La mise a jour automatique a echoue.")
        self.network_var.set("Essaie de telecharger la release manuellement si besoin.")
        messagebox.showerror("Mise a jour impossible", message)

    def _set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        state = "disabled" if busy else "normal"
        self.create_button.configure(state=state)
        self.join_button.configure(state=state)

    def _log(self, message: str) -> None:
        timestamped = append_log(message)
        self.log_text.configure(state="normal")
        self.log_text.insert("end", timestamped + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        if self.log_window_text:
            self.log_window_text.configure(state="normal")
            self.log_window_text.insert("end", timestamped + "\n")
            self.log_window_text.see("end")
            self.log_window_text.configure(state="disabled")

    def _log_tunnel(self, message: str) -> None:
        self.root.after(0, lambda: self._log(f"Tunnel: {message}"))

    def open_logs_window(self) -> None:
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.lift()
            return
        self.log_window = tk.Toplevel(self.root)
        self.log_window.title("Logs B2B Serv")
        self.log_window.geometry("900x520")
        self.log_window.configure(bg="#0d1016")
        header = ttk.Frame(self.log_window, padding=14)
        header.pack(fill="x")
        ttk.Label(header, text=f"Fichier log : {log_file_path()}", font=("Segoe UI", 10)).pack(anchor="w")
        actions = ttk.Frame(header)
        actions.pack(anchor="w", pady=(10, 0))
        ttk.Button(actions, text="Rafraichir", command=self.refresh_logs_window).pack(side="left")
        ttk.Button(actions, text="Copier les logs", command=self.copy_logs).pack(side="left", padx=(8, 0))
        body = ttk.Frame(self.log_window, padding=(14, 0, 14, 14))
        body.pack(fill="both", expand=True)
        self.log_window_text = tk.Text(
            body,
            bg="#0a0e14",
            fg="#eef2ff",
            insertbackground="white",
            relief="flat",
            font=("Consolas", 10),
        )
        self.log_window_text.pack(fill="both", expand=True)
        self.refresh_logs_window()

    def refresh_logs_window(self) -> None:
        if not self.log_window_text:
            return
        self.log_window_text.configure(state="normal")
        self.log_window_text.delete("1.0", "end")
        self.log_window_text.insert("end", read_logs())
        self.log_window_text.see("end")
        self.log_window_text.configure(state="disabled")

    def copy_logs(self) -> None:
        logs = read_logs()
        self.root.clipboard_clear()
        self.root.clipboard_append(logs)
        self.status_var.set("Logs copies dans le presse-papiers.")

    def optimize_for_virtualdj(self, initial: bool = False) -> None:
        self.profile_var.set("VirtualDJ")
        self.refresh_midi_ports()
        recommended = self._find_virtualdj_output()
        if recommended:
            self.midi_output_var.set(recommended)
            self._try_apply_midi_output(recommended, quiet=True)
            hint = (
                f"Mode VirtualDJ pret. Sur le PC receveur, laisse la sortie distante sur '{recommended}' "
                "et active ce meme port dans les controleurs de VirtualDJ."
            )
        else:
            hint = (
                "Mode VirtualDJ actif. Si aucun port virtuel n'apparait, cree ou active un port MIDI Windows "
                "puis choisis-le dans 'Sortie distante'."
            )
        self.setup_hint_var.set(hint)
        if not initial:
            self.status_var.set("Profil VirtualDJ applique.")
            self._log("Profil VirtualDJ applique")

    def open_virtualdj_guide(self) -> None:
        messagebox.showinfo(
            "Assistant VirtualDJ",
            "1. Sur le PC qui a la vraie platine, clique sur 'Activer le controleur'.\n\n"
            "2. Sur le PC receveur, clique sur 'Optimiser VirtualDJ', puis laisse la 'Sortie distante' recommandee.\n\n"
            "3. Dans VirtualDJ, ouvre Parametres > Controleurs et active ce port MIDI comme controleur d'entree.\n\n"
            "4. Si VirtualDJ ne voit aucun port MIDI, il faudra un port MIDI virtuel Windows. "
            "B2B Serv enverra alors les commandes dessus.\n\n"
            "5. Le nom exact de ta platine distante n'apparaitra pas comme USB natif. "
            "VirtualDJ verra une entree MIDI de controle.",
        )

    def refresh_midi_ports(self) -> None:
        snapshot = self.midi_bridge.list_ports()
        if not self.midi_bridge.available:
            self.midi_input_combo["values"] = []
            self.midi_output_combo["values"] = []
            self.midi_status_var.set("Support MIDI indisponible dans cette installation. Reinstalle la derniere mise a jour si besoin.")
            self.local_controller_var.set("Controleur local : indisponible")
            return
        self.midi_input_combo["values"] = snapshot.inputs
        self.midi_output_combo["values"] = [""] + snapshot.outputs
        recommended_input = self._find_preferred_input(snapshot.inputs)
        if recommended_input:
            self.midi_input_var.set(recommended_input)
        elif snapshot.inputs and not self.midi_input_var.get():
            self.midi_input_var.set(snapshot.inputs[0])
        if snapshot.outputs and not self.midi_output_var.get():
            self.midi_output_var.set(snapshot.outputs[0])
        if not snapshot.inputs:
            self.midi_status_var.set("Aucune entree MIDI detectee.")
            self._update_local_controller_name("")
        else:
            self.midi_status_var.set(f"{len(snapshot.inputs)} entree(s) MIDI detectee(s).")
            self._update_local_controller_name(self.midi_input_var.get().strip())
        if self.profile_var.get() == "VirtualDJ":
            recommended = self._find_virtualdj_output(snapshot.outputs)
            if recommended and not self.midi_output_var.get():
                self.midi_output_var.set(recommended)

    def activate_midi(self) -> None:
        port_name = self.midi_input_var.get().strip()
        if not port_name:
            messagebox.showerror("Controleur requis", "Choisis une entree MIDI pour activer le controleur.")
            return
        try:
            self.midi_bridge.start_input(port_name)
            self.midi_status_var.set(f"Controleur actif : {port_name}")
            self._update_local_controller_name(port_name)
            self._share_controller_name()
            self._log(f"Capture MIDI active sur {port_name}")
        except Exception as exc:
            self.midi_status_var.set("Impossible d'activer le controleur.")
            self._log(f"Echec activation MIDI: {exc}")
            messagebox.showerror("MIDI indisponible", str(exc))

    def apply_midi_output(self) -> None:
        port_name = self.midi_output_var.get().strip()
        try:
            self._try_apply_midi_output(port_name)
        except Exception as exc:
            self._log(f"Echec sortie MIDI: {exc}")
            messagebox.showerror("Sortie MIDI impossible", str(exc))

    def disable_midi(self) -> None:
        self.midi_bridge.shutdown()
        self.midi_status_var.set("MIDI coupe.")
        self._update_local_controller_name("")
        self._share_controller_name()
        self._log("Pont MIDI coupe")

    def _on_local_midi_message(self, message: dict) -> None:
        self.engine.send_midi(message)
        self.root.after(0, lambda: self._update_local_midi_status(message))

    def _update_local_midi_status(self, message: dict) -> None:
        summary = self._format_midi_message(message)
        self.midi_status_var.set(f"Message local envoye : {summary}")
        self._log(f"MIDI local: {summary}")

    def _on_midi_status(self, message: str) -> None:
        self.root.after(0, lambda: self._apply_midi_status(message))

    def _apply_midi_status(self, message: str) -> None:
        self.midi_status_var.set(message)
        self._log(message)

    def _format_midi_message(self, message: dict) -> str:
        message_type = message.get("type", "unknown")
        parts = [message_type]
        for key in ("channel", "note", "velocity", "control", "value", "program", "pitch"):
            if key in message:
                parts.append(f"{key}={message[key]}")
        return ", ".join(parts)

    def _find_virtualdj_output(self, outputs: list[str] | None = None) -> str:
        output_names = outputs if outputs is not None else list(self.midi_output_combo.cget("values"))
        if not output_names:
            return ""
        preferred_tokens = [
            "loopmidi",
            "virtual",
            "loopbe",
            "b2b",
            "midi",
        ]
        for token in preferred_tokens:
            for name in output_names:
                if name and token in name.lower():
                    return name
        for name in output_names:
            if name:
                return name
        return ""

    def _find_preferred_input(self, inputs: list[str]) -> str:
        preferred_tokens = [
            "hercules",
            "impulse",
            "inpulse",
            "numark",
            "ns4fx",
            "ddj",
            "traktor",
            "midi",
        ]
        for token in preferred_tokens:
            for name in inputs:
                if token in name.lower():
                    return name
        return ""

    def _try_apply_midi_output(self, port_name: str, quiet: bool = False) -> None:
        self.midi_bridge.set_output(port_name)
        if port_name:
            self.midi_status_var.set(f"Sortie distante active : {port_name}")
            self._log(f"Sortie MIDI distante active sur {port_name}")
        else:
            self.midi_status_var.set("Sortie distante desactivee.")
            self._log("Sortie MIDI distante desactivee")
        if not quiet:
            self.status_var.set("Sortie MIDI appliquee.")

    def _auto_prepare_virtualdj_output(self) -> None:
        recommended = self._find_virtualdj_output()
        if not recommended:
            return
        self.midi_output_var.set(recommended)
        try:
            self._try_apply_midi_output(recommended, quiet=True)
        except Exception as exc:
            self._log(f"Auto-config VirtualDJ impossible: {exc}")

    def _sanitize_link(self, raw_link: str) -> str:
        markdown_match = re.search(r"\((b2bserv://[^)]+)\)", raw_link)
        if markdown_match:
            return markdown_match.group(1).strip()
        direct_match = re.search(r"(b2bserv://\S+)", raw_link)
        if direct_match:
            return direct_match.group(1).strip().rstrip("/")
        return raw_link.strip()

    def _update_local_controller_name(self, port_name: str) -> None:
        controller_name = port_name or "aucun"
        self.local_controller_var.set(f"Controleur local : {controller_name}")

    def _share_controller_name(self) -> None:
        controller_name = self.midi_input_var.get().strip() or "aucun"
        self.engine.send_controller_name(controller_name)

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
        self.midi_bridge.shutdown()
        self.local_controller_var.set("Controleur local : aucun")
        self.remote_controller_var.set("Controleur distant : inconnu")
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
