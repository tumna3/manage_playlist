#!/usr/bin/env python3
"""
╔════════════════════════════════════════╗
║ Playlist Manager Pro by Tum Na...แจกฟรี ║
║   M3U/W3U Playlist Management Tool     ║
╚════════════════════════════════════════╝
Requires: pip install python-vlc
VLC media player must be installed on system.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import subprocess
import urllib.request
import urllib.error
import os
import sys
import re
import time
import json
from pathlib import Path
from datetime import datetime

# ─── Try importing python-vlc ────────────────────────────────────────────────
VLC_AVAILABLE = False
vlc = None
try:
    import vlc as _vlc
    vlc = _vlc
    VLC_AVAILABLE = True
except ImportError:
    pass
except Exception:
    pass


# ─── THEME COLORS ────────────────────────────────────────────────────────────
C = {
    "bg":           "#0d0f14",
    "bg2":          "#13161e",
    "bg3":          "#1a1e2a",
    "panel":        "#1e2230",
    "card":         "#252a3a",
    "border":       "#2e3450",
    "accent":       "#6c63ff",
    "accent2":      "#ff6584",
    "accent3":      "#43e97b",
    "teal":         "#38f9d7",
    "text":         "#e8eaf6",
    "text_dim":     "#8892b0",
    "text_muted":   "#4a5580",
    "good":         "#43e97b",
    "bad":          "#ff4757",
    "warning":      "#ffa502",
    "checking":     "#f9ca24",
    "select_bg":    "#3d3580",
    "select_fg":    "#ffffff",
    "btn_hover":    "#7c73ff",
    "scrollbar":    "#2e3450",
    "player_bg":    "#080a10",
}

FONT_TITLE   = ("Segoe UI", 18, "bold")
FONT_HEADER  = ("Segoe UI", 11, "bold")
FONT_NORMAL  = ("Segoe UI", 10)
FONT_SMALL   = ("Segoe UI", 9)
FONT_MONO    = ("Consolas", 9)
FONT_LABEL   = ("Segoe UI", 8)


# ─── PLAYLIST PARSER ─────────────────────────────────────────────────────────

def parse_playlist(filepath: str) -> list:
    channels = []
    ext = Path(filepath).suffix.lower()

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    lines = content.splitlines()

    if ext in (".m3u", ".m3u8"):
        current_info = {}
        for line in lines:
            line = line.strip()
            if not line or line == "#EXTM3U":
                continue
            if line.startswith("#EXTINF:"):
                current_info = {}
                m = re.match(r'#EXTINF:(-?\d+)(.*?),(.*)', line)
                if m:
                    current_info["name"]     = m.group(3).strip()
                    current_info["duration"] = m.group(1)
                    for key, val in re.findall(r'([\w-]+)="([^"]*)"', m.group(2)):
                        current_info[key.lower().replace("-", "_")] = val
                else:
                    current_info["name"] = line.replace("#EXTINF:", "")
            elif line.startswith("#"):
                continue
            else:
                ch = {
                    "url":        line,
                    "name":       current_info.get("name", line),
                    "group":      current_info.get("group_title", "Uncategorized"),
                    "tvg_logo":   current_info.get("tvg_logo", ""),
                    "tvg_id":     current_info.get("tvg_id", ""),
                    "duration":   current_info.get("duration", "-1"),
                    "status":     "unchecked",
                    "latency_ms": None,
                    "raw_extinf": current_info.copy(),
                }
                channels.append(ch)
                current_info = {}

    elif ext == ".w3u":
        try:
            data = json.loads(content)
            items = data.get("playlist", data.get("items", data.get("channels", [])))
            for item in items:
                ch = {
                    "url":        item.get("url", item.get("stream", "")),
                    "name":       item.get("name", item.get("title", "Unknown")),
                    "group":      item.get("group", item.get("category", "Uncategorized")),
                    "tvg_logo":   item.get("logo", item.get("icon", "")),
                    "tvg_id":     item.get("id", ""),
                    "duration":   "-1",
                    "status":     "unchecked",
                    "latency_ms": None,
                    "raw_extinf": {},
                }
                channels.append(ch)
        except json.JSONDecodeError:
            current_info = {}
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("#EXTINF:"):
                    m = re.match(r'#EXTINF:(-?\d+)(.*?),(.*)', line)
                    if m:
                        current_info["name"] = m.group(3).strip()
                        for key, val in re.findall(r'([\w-]+)="([^"]*)"', m.group(2)):
                            current_info[key.lower().replace("-", "_")] = val
                elif not line.startswith("#"):
                    ch = {
                        "url":        line,
                        "name":       current_info.get("name", line),
                        "group":      current_info.get("group_title", "Uncategorized"),
                        "tvg_logo":   current_info.get("tvg_logo", ""),
                        "tvg_id":     current_info.get("tvg_id", ""),
                        "duration":   "-1",
                        "status":     "unchecked",
                        "latency_ms": None,
                        "raw_extinf": current_info.copy(),
                    }
                    channels.append(ch)
                    current_info = {}
    return channels


def export_m3u(channels: list, filepath: str):
    lines = ["#EXTM3U"]
    for ch in channels:
        attrs = f' tvg-id="{ch["tvg_id"]}" tvg-logo="{ch["tvg_logo"]}" group-title="{ch["group"]}"'
        lines.append(f'#EXTINF:{ch["duration"]}{attrs},{ch["name"]}')
        lines.append(ch["url"])
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def export_w3u(channels: list, filepath: str):
    items = [{"name": ch["name"], "url": ch["url"], "group": ch["group"],
              "logo": ch["tvg_logo"], "id": ch["tvg_id"]} for ch in channels]
    data = {"playlist": items, "name": "Exported Playlist", "version": "1.0"}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_url(url: str, timeout: int = 8):
    try:
        start = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (IPTV-Checker/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(512)
        latency = int((time.monotonic() - start) * 1000)
        return True, latency
    except Exception:
        return False, None


# ─── TOOLTIP ─────────────────────────────────────────────────────────────────

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text   = text
        self.tip    = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _=None):
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#2e3450",
                 foreground=C["text"], font=FONT_SMALL,
                 relief="flat", padx=8, pady=4).pack()

    def hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ─── STYLED WIDGETS ──────────────────────────────────────────────────────────

def make_btn(parent, text, command, color=None, icon="", width=None, tooltip=None):
    bg = color or C["accent"]
    fr = tk.Frame(parent, background=C["bg2"], cursor="hand2")

    def on_enter(_): inner.config(background=_lighten(bg))
    def on_leave(_): inner.config(background=bg)

    inner = tk.Frame(fr, background=bg, padx=12, pady=7, cursor="hand2")
    inner.pack(fill="both", expand=True)
    label_text = f"{icon}  {text}" if icon else text
    lbl = tk.Label(inner, text=label_text, background=bg,
                   foreground="white", font=FONT_SMALL, cursor="hand2")
    if width:
        lbl.config(width=width)
    lbl.pack()

    for w in (fr, inner, lbl):
        w.bind("<Button-1>", lambda e: command())
        w.bind("<Enter>", on_enter)
        w.bind("<Leave>", on_leave)

    if tooltip:
        Tooltip(fr, tooltip)
    return fr


def make_icon_btn(parent, text, command, size=28, bg=None, fg=None):
    """Small square icon button."""
    bg = bg or C["card"]
    fg = fg or C["text"]
    btn = tk.Label(parent, text=text, background=bg, foreground=fg,
                   font=("Segoe UI", 11), width=2, cursor="hand2",
                   relief="flat", padx=4, pady=2)
    btn.bind("<Button-1>", lambda e: command())
    btn.bind("<Enter>",    lambda e: btn.config(background=_lighten(bg)))
    btn.bind("<Leave>",    lambda e: btn.config(background=bg))
    return btn


def _lighten(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{min(255,r+30):02x}{min(255,g+30):02x}{min(255,b+30):02x}"


def separator(parent, orient="h", pad=8):
    if orient == "h":
        fr = tk.Frame(parent, height=1, background=C["border"])
        fr.pack(fill="x", padx=pad, pady=4)
    else:
        fr = tk.Frame(parent, width=1, background=C["border"])
        fr.pack(fill="y", pady=pad)
    return fr


# ─── EMBEDDED VLC PLAYER ─────────────────────────────────────────────────────

class VLCPlayer:
    """Embedded VLC player that renders into a tk.Frame."""

    def __init__(self, parent_frame):
        self.frame     = parent_frame
        self.instance  = None
        self.player    = None
        self._current  = None
        self._volume   = 80
        self._ready    = False

        if not VLC_AVAILABLE:
            return
        try:
            # --no-video-title-show keeps VLC quiet; --quiet suppresses console spam
            self.instance = vlc.Instance(
                "--no-xlib",
                "--quiet",
                "--no-video-title-show",
                "--network-caching=3000",
                "--live-caching=3000",
            )
            self.player = self.instance.media_player_new()
            self._ready = True
        except Exception as e:
            self._ready = False

    def attach(self):
        """Bind the VLC output to the tk frame's window handle."""
        if not self._ready:
            return
        try:
            win_id = self.frame.winfo_id()
            plat   = sys.platform
            if plat.startswith("win"):
                self.player.set_hwnd(win_id)
            elif plat == "darwin":
                self.player.set_nsobject(win_id)
            else:
                self.player.set_xwindow(win_id)
        except Exception:
            pass

    def play(self, url: str):
        if not self._ready:
            return False
        try:
            self._current = url
            media = self.instance.media_new(url)
            self.player.set_media(media)
            self.player.audio_set_volume(self._volume)
            self.attach()
            self.player.play()
            return True
        except Exception:
            return False

    def pause_resume(self):
        if not self._ready or not self.player:
            return
        self.player.pause()

    def stop(self):
        if not self._ready or not self.player:
            return
        self.player.stop()

    def set_volume(self, vol: int):
        self._volume = max(0, min(200, vol))
        if self._ready and self.player:
            self.player.audio_set_volume(self._volume)

    def is_playing(self):
        if not self._ready or not self.player:
            return False
        return self.player.is_playing()

    def release(self):
        try:
            if self.player:
                self.player.stop()
                self.player.release()
            if self.instance:
                self.instance.release()
        except Exception:
            pass


# ─── MAIN APPLICATION ─────────────────────────────────────────────────────────

class PlaylistManagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📂Playlist Manager Pro by Tum Na...แจกฟรี")
        self.configure(bg=C["bg"])
        self.geometry("1440x860")
        self.minsize(1100, 640)

        # State
        self.channels: list      = []
        self.filtered: list      = []
        self.check_thread        = None
        self._check_stop         = threading.Event()
        self._checking           = False
        self.sort_col            = "name"
        self.sort_rev            = False
        self._search_var         = tk.StringVar()
        self._group_var          = tk.StringVar(value="All Groups")
        self._status_var         = tk.StringVar(value="All Status")
        self._vol_var            = tk.IntVar(value=80)
        self._now_playing        = None   # current channel dict
        self._auto_play          = tk.BooleanVar(value=False)

        self._search_var.trace_add("write", lambda *_: self.apply_filters())
        self._group_var .trace_add("write", lambda *_: self.apply_filters())
        self._status_var.trace_add("write", lambda *_: self.apply_filters())

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # VLC player (must be created after window is mapped)
        self._vlc: VLCPlayer | None = None
        self.after(200, self._init_vlc)

    # ── VLC INIT ──────────────────────────────────────────────────────────────

    def _init_vlc(self):
        if not VLC_AVAILABLE:
            self._show_no_vlc_placeholder()
            return
        self._vlc = VLCPlayer(self._video_frame)
        if self._vlc._ready:
            self._vlc.attach()
            self._update_player_label("Ready — select a channel to preview")
        else:
            self._show_no_vlc_placeholder()

    def _show_no_vlc_placeholder(self):
        tk.Label(self._video_frame,
                 text="⚠  python-vlc not available\n\npip install python-vlc\nVLC must be installed",
                 background=C["player_bg"], foreground=C["text_muted"],
                 font=FONT_NORMAL, justify="center").place(relx=0.5, rely=0.5, anchor="center")
        self.log("python-vlc not found. Install with: pip install python-vlc")

    # ── UI CONSTRUCTION ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, background=C["bg2"], height=58)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="📂Playlist Manager Pro by Tum Na...แจกฟรี",
                 font=FONT_TITLE, background=C["bg2"],
                 foreground=C["accent"]).pack(side="left", padx=20, pady=10)
        tk.Label(hdr, text="v3.0  |  M3U & W3U",
                 font=FONT_SMALL, background=C["bg2"],
                 foreground=C["text_muted"]).pack(side="left", pady=10)
        self._stat_total = self._stat_badge(hdr, "TOTAL",     "0", C["accent"])
        self._stat_good  = self._stat_badge(hdr, "GOOD",      "0", C["good"])
        self._stat_bad   = self._stat_badge(hdr, "BAD",       "0", C["bad"])
        self._stat_unchk = self._stat_badge(hdr, "UNCHECKED", "0", C["text_muted"])
        separator(self, pad=0)

        # Toolbar
        toolbar = tk.Frame(self, background=C["bg3"], pady=8)
        toolbar.pack(fill="x")
        btn_row = tk.Frame(toolbar, background=C["bg3"])
        btn_row.pack(fill="x", padx=12)

        make_btn(btn_row, "Import Playlist",  self.import_playlist,
                 icon="📂", color=C["accent"],
                 tooltip="Open a new .m3u or .w3u playlist").pack(side="left", padx=4)
        make_btn(btn_row, "Append Playlist",  self.append_playlist,
                 icon="➕", color="#4a90d9",
                 tooltip="Append another playlist to current list").pack(side="left", padx=4)
        tk.Frame(btn_row, width=1, background=C["border"]).pack(side="left", padx=8, fill="y")
        make_btn(btn_row, "Check Links",      self.start_check,
                 icon="🔍", color="#f9ca24",
                 tooltip="Check all unchecked links").pack(side="left", padx=4)
        make_btn(btn_row, "Check Selected",   self.check_selected,
                 icon="🎯", color="#e67e22",
                 tooltip="Check only selected links").pack(side="left", padx=4)
        self._stop_btn = make_btn(btn_row, "Stop Check", self.stop_check,
                 icon="⏹", color=C["bad"], tooltip="Stop link checking")
        self._stop_btn.pack(side="left", padx=4)
        self._stop_btn.pack_forget()
        tk.Frame(btn_row, width=1, background=C["border"]).pack(side="left", padx=8, fill="y")
        make_btn(btn_row, "Remove Bad Links", self.remove_bad,
                 icon="🗑", color=C["bad"],
                 tooltip="Delete all links marked as BAD").pack(side="left", padx=4)
        make_btn(btn_row, "Clear All",        self.clear_all,
                 icon="💥", color="#57606f",
                 tooltip="Clear entire playlist").pack(side="left", padx=4)

        make_btn(btn_row, "Export Selected", self.export_selected,
                 icon="💾", color=C["accent3"],
                 tooltip="Export selected channels").pack(side="right", padx=4)
        make_btn(btn_row, "Export All",      self.export_all,
                 icon="📤", color=C["accent"],
                 tooltip="Export all visible channels").pack(side="right", padx=4)
        separator(self, pad=0)

        # Filter bar
        fbar = tk.Frame(self, background=C["bg2"], pady=6)
        fbar.pack(fill="x")
        fbar_in = tk.Frame(fbar, background=C["bg2"])
        fbar_in.pack(fill="x", padx=12)
        tk.Label(fbar_in, text="🔎", background=C["bg2"],
                 foreground=C["text_dim"], font=("Segoe UI", 11)).pack(side="left")
        se = tk.Entry(fbar_in, textvariable=self._search_var,
                      background=C["card"], foreground=C["text"],
                      insertbackground=C["accent"], font=FONT_NORMAL,
                      relief="flat", width=30)
        se.pack(side="left", padx=(4, 12), ipady=5, ipadx=8)
        se.bind("<FocusIn>",  lambda e: se.config(background=C["bg3"]))
        se.bind("<FocusOut>", lambda e: se.config(background=C["card"]))
        tk.Label(fbar_in, text="Group:", background=C["bg2"],
                 foreground=C["text_dim"], font=FONT_SMALL).pack(side="left")
        self._group_cb = ttk.Combobox(fbar_in, textvariable=self._group_var,
                                      state="readonly", width=22, font=FONT_SMALL)
        self._group_cb["values"] = ["All Groups"]
        self._group_cb.pack(side="left", padx=(4, 12), ipady=3)
        tk.Label(fbar_in, text="Status:", background=C["bg2"],
                 foreground=C["text_dim"], font=FONT_SMALL).pack(side="left")
        scb = ttk.Combobox(fbar_in, textvariable=self._status_var,
                           state="readonly", width=16, font=FONT_SMALL)
        scb["values"] = ["All Status", "good", "bad", "unchecked", "checking"]
        scb.pack(side="left", padx=(4, 12), ipady=3)

        # Auto-play toggle
        tk.Checkbutton(fbar_in, text="Auto-play on select",
                       variable=self._auto_play,
                       background=C["bg2"], foreground=C["text_dim"],
                       selectcolor=C["card"], activebackground=C["bg2"],
                       font=FONT_SMALL).pack(side="left", padx=8)

        self._filter_label = tk.Label(fbar_in, text="Showing 0 / 0",
                                      background=C["bg2"],
                                      foreground=C["text_muted"], font=FONT_SMALL)
        self._filter_label.pack(side="right", padx=8)
        tk.Label(fbar_in, text="Ctrl+A: Select All  |  Del: Remove  |  Enter/DblClick: Play",
                 background=C["bg2"], foreground=C["text_muted"],
                 font=FONT_SMALL).pack(side="right", padx=12)
        separator(self, pad=0)

        # ── Main three-pane layout ──
        main_pane = tk.PanedWindow(self, orient="horizontal",
                                   background=C["bg"], sashwidth=5,
                                   sashrelief="flat")
        main_pane.pack(fill="both", expand=True)

        # Left: channel list
        table_frame = tk.Frame(main_pane, background=C["bg"])
        self._build_table(table_frame)
        main_pane.add(table_frame, minsize=520)

        # Right pane (vertical: player on top, details + log below)
        right_pane = tk.PanedWindow(main_pane, orient="vertical",
                                    background=C["bg"], sashwidth=5,
                                    sashrelief="flat")
        main_pane.add(right_pane, minsize=380)

        # Video player panel
        player_outer = tk.Frame(right_pane, background=C["panel"])
        self._build_player_panel(player_outer)
        right_pane.add(player_outer, minsize=220)

        # Info + log panel
        info_frame = tk.Frame(right_pane, background=C["panel"])
        self._build_info_panel(info_frame)
        right_pane.add(info_frame, minsize=180)

        # Status bar
        self._statusbar = tk.Label(self,
                                   text="Ready  —  Import a playlist to get started",
                                   background=C["bg2"], foreground=C["text_dim"],
                                   font=FONT_SMALL, anchor="w", pady=5)
        self._statusbar.pack(fill="x", side="bottom", padx=12)

        # Progress bar (hidden by default)
        self._progress_frame = tk.Frame(self, background=C["bg2"])
        self._progress_bar   = tk.Canvas(self._progress_frame, height=3,
                                          background=C["bg2"], highlightthickness=0)
        self._progress_bar.pack(fill="x")

        # Keyboard shortcuts
        self.bind("<Control-a>", lambda e: self._select_all())
        self.bind("<Delete>",    lambda e: self.remove_selected())
        self.bind("<Control-o>", lambda e: self.import_playlist())
        self.bind("<Control-e>", lambda e: self.export_selected())
        self.bind("<Return>",    lambda e: self.play_vlc())
        self.bind("<space>",     lambda e: self._toggle_pause())

        self._style_comboboxes()

    def _build_player_panel(self, parent):
        # Header row
        hdr = tk.Frame(parent, background=C["panel"])
        hdr.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(hdr, text="▶  Preview",
                 font=FONT_HEADER, background=C["panel"],
                 foreground=C["accent"]).pack(side="left")
        self._now_playing_lbl = tk.Label(hdr, text="No channel selected",
                                         font=FONT_SMALL, background=C["panel"],
                                         foreground=C["text_muted"])
        self._now_playing_lbl.pack(side="left", padx=10)

        # Video canvas — VLC renders directly into this frame
        video_border = tk.Frame(parent, background=C["accent"], padx=1, pady=1)
        video_border.pack(fill="both", expand=True, padx=10, pady=4)
        self._video_frame = tk.Frame(video_border, background=C["player_bg"],
                                     cursor="hand2")
        self._video_frame.pack(fill="both", expand=True)
        # Click on video → pause/resume
        self._video_frame.bind("<Button-1>", lambda e: self._toggle_pause())

        # Overlay "click to play" hint
        self._video_hint = tk.Label(self._video_frame,
                                    text="🎬\n\nSelect a channel and press Play\nor enable Auto-play",
                                    background=C["player_bg"],
                                    foreground=C["text_muted"],
                                    font=FONT_NORMAL, justify="center")
        self._video_hint.place(relx=0.5, rely=0.5, anchor="center")

        # Controls row
        ctrl = tk.Frame(parent, background=C["panel"])
        ctrl.pack(fill="x", padx=10, pady=(0, 8))

        self._play_btn = make_icon_btn(ctrl, "▶", self.play_vlc,
                                       bg=C["good"],  fg="white")
        self._play_btn.pack(side="left", padx=2)
        make_icon_btn(ctrl, "⏸", self._toggle_pause,
                      bg=C["accent"], fg="white").pack(side="left", padx=2)
        make_icon_btn(ctrl, "⏹", self._stop_player,
                      bg="#57606f", fg="white").pack(side="left", padx=2)

        tk.Frame(ctrl, width=12, background=C["panel"]).pack(side="left")

        # Volume
        tk.Label(ctrl, text="🔊", background=C["panel"],
                 foreground=C["text_dim"], font=("Segoe UI", 10)).pack(side="left")
        vol_slider = tk.Scale(ctrl, variable=self._vol_var,
                              from_=0, to=200,
                              orient="horizontal",
                              command=self._on_volume_change,
                              length=110, showvalue=True,
                              background=C["panel"],
                              foreground=C["text_dim"],
                              troughcolor=C["card"],
                              activebackground=C["accent"],
                              highlightthickness=0,
                              bd=0, font=FONT_LABEL,
                              sliderrelief="flat",
                              sliderlength=14)
        vol_slider.pack(side="left", padx=4)

        self._player_state_lbl = tk.Label(ctrl, text="●  Stopped",
                                          background=C["panel"],
                                          foreground=C["text_muted"],
                                          font=FONT_SMALL)
        self._player_state_lbl.pack(side="right", padx=8)

    def _build_info_panel(self, parent):
        # Split horizontally: details left, log right
        pane = tk.PanedWindow(parent, orient="horizontal",
                              background=C["panel"], sashwidth=4,
                              sashrelief="flat")
        pane.pack(fill="both", expand=True)

        # Details
        det = tk.Frame(pane, background=C["panel"])
        pane.add(det, minsize=180)

        tk.Label(det, text="Channel Info",
                 font=FONT_HEADER, background=C["panel"],
                 foreground=C["accent"]).pack(pady=(10, 4), padx=12, anchor="w")
        separator(det)

        self._detail_vars = {}
        fields = [("name","Name"), ("group","Group"), ("tvg_id","TVG-ID"),
                  ("status","Status"), ("latency_ms","Latency"),
                  ("url","URL"), ("tvg_logo","Logo URL")]
        for key, label in fields:
            row = tk.Frame(det, background=C["panel"])
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=label + ":", font=FONT_SMALL,
                     background=C["panel"], foreground=C["text_muted"],
                     width=9, anchor="w").pack(side="left")
            var = tk.StringVar(value="—")
            tk.Entry(row, textvariable=var,
                     background=C["card"], foreground=C["text"],
                     font=FONT_SMALL, relief="flat",
                     state="readonly", readonlybackground=C["card"]).pack(
                         side="left", fill="x", expand=True, ipady=3, ipadx=4)
            self._detail_vars[key] = var

        separator(det)
        for text, cmd, color in [
            ("📋  Copy URL",           self._copy_url,      C["accent"]),
            ("✏️  Edit Name",          self._edit_name,     "#4a90d9"),
            ("🗑  Remove Entry",       self.remove_selected, C["bad"]),
        ]:
            make_btn(det, text, cmd, color=color).pack(fill="x", padx=12, pady=2)

        # Log
        log_fr = tk.Frame(pane, background=C["panel"])
        pane.add(log_fr, minsize=160)

        tk.Label(log_fr, text="Activity Log",
                 font=FONT_HEADER, background=C["panel"],
                 foreground=C["accent"]).pack(pady=(10, 4), padx=12, anchor="w")
        separator(log_fr)
        lf2 = tk.Frame(log_fr, background=C["panel"])
        lf2.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        log_vsb = ttk.Scrollbar(lf2, orient="vertical")
        self._log = tk.Text(lf2, background=C["card"],
                            foreground=C["text_dim"],
                            font=FONT_MONO, relief="flat",
                            state="disabled", wrap="word",
                            yscrollcommand=log_vsb.set)
        log_vsb.config(command=self._log.yview)
        log_vsb.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True)

    # ── TABLE ─────────────────────────────────────────────────────────────────

    def _build_table(self, parent):
        cols = ("#", "status", "name", "group", "url", "latency")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings",
                                 selectmode="extended")
        col_conf = {
            "#":       (44,  44,  "#"),
            "status":  (72,  72,  "Status"),
            "name":    (240, 240, "Channel Name"),
            "group":   (140, 140, "Group"),
            "url":     (340, 340, "URL"),
            "latency": (82,  82,  "Latency"),
        }
        for col, (w, mw, heading) in col_conf.items():
            self.tree.heading(col, text=heading,
                              command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=w, minwidth=mw, anchor="w")

        vsb = ttk.Scrollbar(parent, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.pack(side="bottom", fill="x")
        vsb.pack(side="right",  fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>",         lambda e: self.play_vlc())
        self.tree.bind("<Return>",           lambda e: self.play_vlc())
        self.tree.bind("<Button-3>",         self._context_menu)

        self._style_treeview()
        self._make_context_menu()

    def _stat_badge(self, parent, label, value, color):
        fr = tk.Frame(parent, background=C["bg3"], padx=10, pady=6)
        fr.pack(side="right", padx=6, pady=8)
        val = tk.Label(fr, text=value, font=("Segoe UI", 15, "bold"),
                       background=C["bg3"], foreground=color)
        val.pack()
        tk.Label(fr, text=label, font=FONT_LABEL,
                 background=C["bg3"], foreground=C["text_muted"]).pack()
        return val

    def _style_treeview(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
                        background=C["bg3"], foreground=C["text"],
                        fieldbackground=C["bg3"], rowheight=28,
                        font=FONT_NORMAL, borderwidth=0)
        style.configure("Treeview.Heading",
                        background=C["card"], foreground=C["text_dim"],
                        font=FONT_SMALL, relief="flat", borderwidth=0)
        style.map("Treeview",
                  background=[("selected", C["select_bg"])],
                  foreground=[("selected", C["select_fg"])])
        self.tree.tag_configure("good",      foreground=C["good"])
        self.tree.tag_configure("bad",       foreground=C["bad"])
        self.tree.tag_configure("checking",  foreground=C["checking"])
        self.tree.tag_configure("unchecked", foreground=C["text_muted"])
        self.tree.tag_configure("playing",   background="#1a3320",
                                             foreground=C["good"])

    def _style_comboboxes(self):
        style = ttk.Style(self)
        style.configure("TCombobox",
                        fieldbackground=C["card"], background=C["card"],
                        foreground=C["text"],
                        selectbackground=C["select_bg"],
                        selectforeground=C["select_fg"],
                        arrowcolor=C["accent"])
        style.map("TCombobox", fieldbackground=[("readonly", C["card"])])
        style.configure("TScrollbar",
                        background=C["scrollbar"], troughcolor=C["bg2"],
                        borderwidth=0, arrowcolor=C["accent"])

    def _make_context_menu(self):
        self._ctx = tk.Menu(self, tearoff=0,
                            background=C["card"], foreground=C["text"],
                            activebackground=C["select_bg"],
                            activeforeground=C["select_fg"],
                            font=FONT_SMALL)
        self._ctx.add_command(label="▶  Play in Preview",      command=self.play_vlc)
        self._ctx.add_command(label="🔍  Check Selected",      command=self.check_selected)
        self._ctx.add_separator()
        self._ctx.add_command(label="📋  Copy URL",            command=self._copy_url)
        self._ctx.add_command(label="✏️  Edit Name",           command=self._edit_name)
        self._ctx.add_separator()
        self._ctx.add_command(label="💾  Export Selected",     command=self.export_selected)
        self._ctx.add_separator()
        self._ctx.add_command(label="🗑  Remove Selected",     command=self.remove_selected)

    # ── PLAYER CONTROLS ───────────────────────────────────────────────────────

    def play_vlc(self, channel: dict = None):
        if channel is None:
            sel = self._get_selected_channels()
            if not sel:
                messagebox.showinfo("Info", "Select a channel first.")
                return
            channel = sel[0]

        if not VLC_AVAILABLE or not self._vlc or not self._vlc._ready:
            # Fallback: open external VLC
            self._open_external_vlc(channel["url"])
            return

        self._now_playing = channel
        ok = self._vlc.play(channel["url"])

        if ok:
            self._video_hint.place_forget()
            name = channel["name"]
            self._update_player_label(name)
            self.log(f"▶ Playing: {name}")
            self._set_player_state("playing")
            self._highlight_playing_row()
        else:
            self.log(f"❌ Failed to start playback: {channel['url']}")

    def _toggle_pause(self):
        if not self._vlc or not self._vlc._ready:
            return
        if self._vlc.is_playing():
            self._vlc.pause_resume()
            self._set_player_state("paused")
            self.log("⏸ Paused")
        else:
            self._vlc.pause_resume()
            self._set_player_state("playing")
            self.log("▶ Resumed")

    def _stop_player(self):
        if self._vlc:
            self._vlc.stop()
        self._set_player_state("stopped")
        self._update_player_label("Stopped")
        self._video_hint.place(relx=0.5, rely=0.5, anchor="center")
        self._video_hint.config(text="⏹  Stopped")
        self.log("⏹ Stopped")
        self._clear_playing_highlight()

    def _set_player_state(self, state: str):
        icons = {"playing": ("●  Playing", C["good"]),
                 "paused":  ("⏸  Paused",  C["warning"]),
                 "stopped": ("●  Stopped", C["text_muted"]),
                 "error":   ("✗  Error",   C["bad"])}
        text, color = icons.get(state, ("●  Unknown", C["text_muted"]))
        self._player_state_lbl.config(text=text, foreground=color)

    def _update_player_label(self, text: str):
        short = text if len(text) <= 55 else text[:52] + "…"
        self._now_playing_lbl.config(text=short)

    def _on_volume_change(self, val):
        if self._vlc:
            self._vlc.set_volume(int(val))

    def _open_external_vlc(self, url: str):
        """Fallback: open URL in external VLC process."""
        vlc_paths = [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
            "/usr/bin/vlc", "/usr/local/bin/vlc",
            "/Applications/VLC.app/Contents/MacOS/VLC", "vlc",
        ]
        for p in vlc_paths:
            if Path(p).exists() or p == "vlc":
                try:
                    subprocess.Popen([p, url])
                    return
                except Exception:
                    continue
        messagebox.showerror("VLC Not Found",
                             "VLC not found.\nhttps://www.videolan.org/")

    def _highlight_playing_row(self):
        """Mark the currently-playing row green."""
        for item in self.tree.get_children():
            tags = list(self.tree.item(item, "tags"))
            if "playing" in tags:
                tags.remove("playing")
                self.tree.item(item, tags=tags)
        # find iid of now_playing in filtered
        if self._now_playing:
            try:
                idx = self.filtered.index(self._now_playing)
                item = str(idx)
                tags = list(self.tree.item(item, "tags")) + ["playing"]
                self.tree.item(item, tags=tags)
            except (ValueError, tk.TclError):
                pass

    def _clear_playing_highlight(self):
        for item in self.tree.get_children():
            tags = [t for t in self.tree.item(item, "tags") if t != "playing"]
            self.tree.item(item, tags=tags)

    # ── SELECTION ─────────────────────────────────────────────────────────────

    def _get_selected_channels(self) -> list:
        sel = self.tree.selection()
        return [self.filtered[int(i)] for i in sel if int(i) < len(self.filtered)]

    def _select_all(self):
        self.tree.selection_set(self.tree.get_children())

    def _on_select(self, _=None):
        sel = self._get_selected_channels()
        if not sel:
            return
        ch = sel[0]
        # Update detail panel
        self._detail_vars["name"]      .set(ch["name"])
        self._detail_vars["group"]     .set(ch["group"])
        self._detail_vars["tvg_id"]    .set(ch["tvg_id"] or "—")
        self._detail_vars["status"]    .set(ch["status"])
        self._detail_vars["latency_ms"].set(
            f"{ch['latency_ms']} ms" if ch["latency_ms"] else "—")
        self._detail_vars["url"]       .set(ch["url"])
        self._detail_vars["tvg_logo"]  .set(ch["tvg_logo"] or "—")

        # Auto-play if enabled
        if self._auto_play.get():
            self.play_vlc(ch)

    def _context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item and item not in self.tree.selection():
            self.tree.selection_set(item)
        if self.tree.selection():
            self._ctx.post(event.x_root, event.y_root)

    # ── TABLE RENDERING ───────────────────────────────────────────────────────

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for i, ch in enumerate(self.filtered):
            status = ch["status"]
            icon   = {"good":"✅","bad":"❌","checking":"⏳","unchecked":"⬜"}.get(status,"⬜")
            lat    = f"{ch['latency_ms']} ms" if ch["latency_ms"] else "—"
            tag    = status if status in ("good","bad","checking") else "unchecked"
            tags   = [tag]
            if ch is self._now_playing:
                tags.append("playing")
            self.tree.insert("", "end", iid=str(i),
                             values=(i+1, icon, ch["name"],
                                     ch["group"], ch["url"], lat),
                             tags=tags)
        self._update_stats()
        self._filter_label.config(text=f"Showing {len(self.filtered)} / {len(self.channels)}")

    def _update_stats(self):
        total = len(self.channels)
        good  = sum(1 for c in self.channels if c["status"] == "good")
        bad   = sum(1 for c in self.channels if c["status"] == "bad")
        unchk = sum(1 for c in self.channels if c["status"] == "unchecked")
        self._stat_total.config(text=str(total))
        self._stat_good .config(text=str(good))
        self._stat_bad  .config(text=str(bad))
        self._stat_unchk.config(text=str(unchk))

    def _update_progress(self, done: int, total: int):
        if total == 0:
            return
        self._progress_frame.pack(fill="x", side="bottom", before=self._statusbar)
        self._progress_bar.config(width=self.winfo_width())
        self._progress_bar.delete("all")
        w = int(self.winfo_width() * done / total)
        self._progress_bar.create_rectangle(0, 0, w, 3, fill=C["accent"], outline="")

    def _hide_progress(self):
        self._progress_frame.pack_forget()

    def apply_filters(self):
        q      = self._search_var.get().lower()
        grp    = self._group_var.get()
        status = self._status_var.get()
        self.filtered = [
            c for c in self.channels
            if (q in c["name"].lower() or q in c["url"].lower() or q in c["group"].lower())
            and (grp    == "All Groups"  or c["group"]  == grp)
            and (status == "All Status" or c["status"] == status)
        ]
        self._refresh_table()

    def _update_group_dropdown(self):
        groups = sorted(set(c["group"] for c in self.channels))
        self._group_cb["values"] = ["All Groups"] + groups

    def _sort_by(self, col: str):
        if self.sort_col == col:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col = col
            self.sort_rev = False
        key_map = {
            "#":       lambda c: self.channels.index(c) if c in self.channels else 0,
            "status":  lambda c: c["status"],
            "name":    lambda c: c["name"].lower(),
            "group":   lambda c: c["group"].lower(),
            "url":     lambda c: c["url"],
            "latency": lambda c: c["latency_ms"] or 99999,
        }
        self.filtered.sort(key=key_map.get(col, lambda c: c["name"].lower()),
                           reverse=self.sort_rev)
        self._refresh_table()

    # ── LOG ───────────────────────────────────────────────────────────────────

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.config(state="normal")
        self._log.insert("end", f"[{ts}] {msg}\n")
        self._log.see("end")
        self._log.config(state="disabled")
        self._statusbar.config(text=msg)

    def set_status(self, msg: str):
        self._statusbar.config(text=msg)

    # ── IMPORT / APPEND ───────────────────────────────────────────────────────

    def _open_file_dialog(self):
        return filedialog.askopenfilename(
            title="Select Playlist File",
            filetypes=[("Playlist files", "*.m3u *.m3u8 *.w3u"),
                       ("M3U files",      "*.m3u *.m3u8"),
                       ("W3U files",      "*.w3u"),
                       ("All files",      "*.*")])

    def import_playlist(self):
        path = self._open_file_dialog()
        if not path:
            return
        try:
            ch = parse_playlist(path)
            if not ch:
                messagebox.showwarning("Empty", "No channels found.")
                return
            self.channels = ch
            self._update_group_dropdown()
            self.apply_filters()
            self.log(f"Imported {len(ch)} channels from: {Path(path).name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file:\n{e}")

    def append_playlist(self):
        path = self._open_file_dialog()
        if not path:
            return
        try:
            new_ch = parse_playlist(path)
            if not new_ch:
                messagebox.showwarning("Empty", "No channels found.")
                return
            self.channels.extend(new_ch)
            self._update_group_dropdown()
            self.apply_filters()
            self.log(f"Appended {len(new_ch)} channels. Total: {len(self.channels)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file:\n{e}")

    # ── LINK CHECKER ─────────────────────────────────────────────────────────

    def start_check(self):
        if self._checking:
            messagebox.showinfo("Info", "Check already in progress.")
            return
        targets = [c for c in self.channels if c["status"] != "good"]
        if not targets:
            messagebox.showinfo("Info", "All links already checked / good.")
            return
        self._run_check(targets)

    def check_selected(self):
        targets = self._get_selected_channels()
        if not targets:
            messagebox.showinfo("Info", "No channels selected.")
            return
        self._run_check(targets)

    def _run_check(self, targets: list):
        self._checking = True
        self._check_stop.clear()
        self._stop_btn.pack(side="left", padx=4)

        def worker():
            total = len(targets)
            for i, ch in enumerate(targets):
                if self._check_stop.is_set():
                    self.after(0, lambda: self.log("Link check stopped by user."))
                    break
                ch["status"] = "checking"
                self.after(0, self.apply_filters)
                self.after(0, lambda m=f"Checking {i+1}/{total}: {ch['name'][:50]}":
                           self.set_status(m))
                is_alive, latency = check_url(ch["url"])
                ch["status"]     = "good" if is_alive else "bad"
                ch["latency_ms"] = latency
                self.after(0, self.apply_filters)
                self.after(0, lambda d=i+1, t=total: self._update_progress(d, t))
            self.after(0, self._check_done)

        self.check_thread = threading.Thread(target=worker, daemon=True)
        self.check_thread.start()

    def _check_done(self):
        self._checking = False
        self._stop_btn.pack_forget()
        self._hide_progress()
        good = sum(1 for c in self.channels if c["status"] == "good")
        bad  = sum(1 for c in self.channels if c["status"] == "bad")
        self.apply_filters()
        self.log(f"Check complete — ✅ Good: {good}  ❌ Bad: {bad}")

    def stop_check(self):
        self._check_stop.set()

    # ── REMOVE ────────────────────────────────────────────────────────────────

    def remove_bad(self):
        bad = [c for c in self.channels if c["status"] == "bad"]
        if not bad:
            messagebox.showinfo("Info", "No bad links to remove.")
            return
        if messagebox.askyesno("Confirm", f"Remove {len(bad)} bad link(s)?"):
            self.channels = [c for c in self.channels if c["status"] != "bad"]
            self._update_group_dropdown()
            self.apply_filters()
            self.log(f"Removed {len(bad)} bad links.")

    def remove_selected(self):
        sel = self._get_selected_channels()
        if not sel:
            return
        sel_ids = set(id(c) for c in sel)
        self.channels = [c for c in self.channels if id(c) not in sel_ids]
        self._update_group_dropdown()
        self.apply_filters()
        self.log(f"Removed {len(sel)} channel(s).")

    def clear_all(self):
        if not self.channels:
            return
        if messagebox.askyesno("Confirm", "Clear entire playlist?"):
            self._stop_player()
            self.channels.clear()
            self.filtered.clear()
            self._now_playing = None
            self._update_group_dropdown()
            self._refresh_table()
            self.log("Playlist cleared.")

    # ── EXPORT ────────────────────────────────────────────────────────────────

    def _export_channels(self, channels: list):
        if not channels:
            messagebox.showinfo("Info", "Nothing to export.")
            return
        fmt_var = tk.StringVar(value="m3u")
        dlg = tk.Toplevel(self)
        dlg.title("Export Options")
        dlg.configure(background=C["bg"])
        dlg.geometry("340x200")
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text=f"Export {len(channels)} channels",
                 font=FONT_HEADER, background=C["bg"],
                 foreground=C["text"]).pack(pady=(16, 4))
        tk.Label(dlg, text="Choose output format:",
                 font=FONT_SMALL, background=C["bg"],
                 foreground=C["text_dim"]).pack()
        row = tk.Frame(dlg, background=C["bg"])
        row.pack(pady=8)
        for fmt, lbl in [("m3u", ".M3U — Standard playlist"),
                         ("w3u", ".W3U — JSON playlist")]:
            tk.Radiobutton(row, text=lbl, variable=fmt_var, value=fmt,
                           background=C["bg"], foreground=C["text"],
                           selectcolor=C["card"], activebackground=C["bg"],
                           font=FONT_SMALL).pack(anchor="w", padx=20, pady=2)

        def do_export():
            fmt = fmt_var.get()
            path = filedialog.asksaveasfilename(
                defaultextension=f".{fmt}",
                filetypes=[(f"{fmt.upper()} files", f"*.{fmt}"),
                           ("All files", "*.*")],
                initialfile=f"playlist.{fmt}")
            if not path:
                dlg.destroy()
                return
            try:
                (export_m3u if fmt == "m3u" else export_w3u)(channels, path)
                dlg.destroy()
                self.log(f"Exported {len(channels)} channels → {Path(path).name}")
                messagebox.showinfo("Done", f"Exported to:\n{path}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

        make_btn(dlg, "Export", do_export, color=C["accent"], icon="💾").pack(pady=4)

    def export_selected(self):
        self._export_channels(self._get_selected_channels())

    def export_all(self):
        self._export_channels(self.filtered)

    # ── UTILITIES ─────────────────────────────────────────────────────────────

    def _copy_url(self):
        sel = self._get_selected_channels()
        if not sel:
            return
        self.clipboard_clear()
        self.clipboard_append(sel[0]["url"])
        self.log(f"Copied URL: {sel[0]['url'][:70]}")

    def _edit_name(self):
        sel = self._get_selected_channels()
        if not sel:
            return
        ch = sel[0]
        dlg = tk.Toplevel(self)
        dlg.title("Edit Channel Name")
        dlg.configure(background=C["bg"])
        dlg.geometry("420x130")
        dlg.resizable(False, False)
        dlg.grab_set()
        tk.Label(dlg, text="Channel Name:", font=FONT_SMALL,
                 background=C["bg"], foreground=C["text_dim"]).pack(pady=(16, 4))
        var = tk.StringVar(value=ch["name"])
        entry = tk.Entry(dlg, textvariable=var, font=FONT_NORMAL,
                         background=C["card"], foreground=C["text"],
                         insertbackground=C["accent"], relief="flat", width=48)
        entry.pack(padx=20, ipady=6)
        entry.focus()

        def save():
            ch["name"] = var.get().strip() or ch["name"]
            self.apply_filters()
            self.log(f"Renamed → {ch['name']}")
            dlg.destroy()

        entry.bind("<Return>", lambda e: save())
        make_btn(dlg, "Save", save, color=C["accent"]).pack(pady=8)

    def _on_close(self):
        self._check_stop.set()
        if self._vlc:
            self._vlc.release()
        self.destroy()


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not VLC_AVAILABLE:
        print("=" * 60)
        print("  python-vlc not found.")
        print("  Install with:  pip install python-vlc")
        print("  VLC player must also be installed:")
        print("  https://www.videolan.org/")
        print("=" * 60)
        print("  Starting anyway (embedded preview unavailable)...")
        print()
    app = PlaylistManagerApp()
    app.mainloop()
