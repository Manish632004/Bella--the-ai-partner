"""
BELLA — Desktop Voice Agent Widget
A futuristic, minimalist, hands-free voice assistant widget.
Single-column 450x600 layout with animated circular visualizer,
glassmorphic dark violet aesthetic, and live caption overlays.
"""

import math
import queue
import sys
import tkinter as tk
import customtkinter as ctk

from bella.gui.voice_loop import VoiceLoop
from bella.core.config import config

# Set global CustomTkinter appearance settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ━━━ Design Tokens ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_BG_DEEP     = "#06060e"   # near-black base
_BG_PANEL    = "#0c0f1a"   # slightly lighter panel
_BG_GLASS    = "#11142a"   # glassmorphic surface
_BORDER      = "#1a1e3a"   # subtle border
_VIOLET_DIM  = "#4f46e5"   # idle / dim accent
_VIOLET      = "#8b5cf6"   # primary violet accent
_VIOLET_GLOW = "#a78bfa"   # light glow
_VIOLET_PALE = "#c4b5fd"   # text highlights
_GREEN       = "#10b981"   # listening / active
_GREEN_DIM   = "#059669"
_RED         = "#ef4444"   # stop / alert
_TEXT_PRIMARY = "#f1f5f9"
_TEXT_MUTED   = "#94a3b8"
_TEXT_DIM     = "#64748b"
_FONT_FAMILY  = "Inter"


class AnimatedVisualizer(ctk.CTkCanvas):
    """Circular animated canvas representing BELLA's voice agent status."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            bg=_BG_DEEP,
            highlightthickness=0,
            bd=0,
            **kwargs
        )
        self.state = "idle"
        self.volume = 0.0
        self.anim_frame = 0
        self.animate()

    def update_state(self, state):
        self.state = state

    def update_volume(self, volume):
        # Scale volume input for visual appeal (usually range 0.0 to ~0.5)
        self.volume = min(volume * 2.0, 1.0)

    def animate(self):
        self.delete("all")
        self.anim_frame += 1

        width = self.winfo_width()
        height = self.winfo_height()

        # Default fallback dimensions if canvas is not yet packed/sized
        if width <= 1:
            width, height = 340, 340

        cx, cy = width / 2, height / 2
        base_radius = 70

        if self.state == "sleeping":
            # Ultra-slow, deep breathing glow — the "dormant sentinel" look
            breath = 0.06 * math.sin(self.anim_frame * 0.02)
            scale = 1.0 + breath
            r = base_radius * scale

            # Very faint concentric rings that pulse outward
            for i in range(5):
                ring_r = r + (i + 1) * 14
                phase = math.sin(self.anim_frame * 0.015 + i * 0.6)
                # Only draw rings that are "visible" in the current phase
                if phase > -0.3:
                    self.create_oval(
                        cx - ring_r, cy - ring_r,
                        cx + ring_r, cy + ring_r,
                        fill="", outline="#1e1b4b", width=1
                    )

            # Core circle — very dark indigo
            self.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill="#0f0d2e", outline="#312e81", width=2
            )

            # Inner logo symbol
            self.create_text(
                cx, cy - 2,
                text="✦", fill="#6366f1",
                font=(_FONT_FAMILY, 32, "bold")
            )

            # Small subtle "zzz" indicator
            z_alpha = 0.5 + 0.5 * math.sin(self.anim_frame * 0.03)
            z_color = "#312e81" if z_alpha < 0.7 else "#4338ca"
            self.create_text(
                cx + r * 0.6, cy - r * 0.55,
                text="ᶻᶻ", fill=z_color,
                font=(_FONT_FAMILY, 14)
            )

        elif self.state == "listening":
            # Reactive pulse with listening green color
            pulse_vol = self.volume * 50
            r_inner = base_radius + pulse_vol
            glow_color = _GREEN

            # Concentric soft glow rings
            for i in range(3):
                alpha_r = r_inner + (i + 1) * 15
                self.create_oval(
                    cx - alpha_r, cy - alpha_r,
                    cx + alpha_r, cy + alpha_r,
                    fill="", outline=glow_color, width=2,
                    state=tk.HIDDEN if i == 0 else tk.NORMAL
                )

            # Core inner circle
            self.create_oval(
                cx - r_inner, cy - r_inner,
                cx + r_inner, cy + r_inner,
                fill=glow_color, outline=_GREEN_DIM, width=2
            )

        elif self.state == "thinking":
            # Rotating electric purple border rings
            angle_offset = self.anim_frame * 0.08
            r_inner = base_radius + 5 * math.sin(self.anim_frame * 0.1)

            # Draw rotating segments representing thinking
            for i in range(4):
                start_angle = math.degrees(angle_offset + i * (math.pi / 2))
                self.create_arc(
                    cx - (r_inner + 12), cy - (r_inner + 12),
                    cx + (r_inner + 12), cy + (r_inner + 12),
                    start=start_angle, extent=45,
                    style=tk.ARC, outline="#8b5cf6", width=4
                )

            # Central core breathing
            self.create_oval(
                cx - r_inner, cy - r_inner,
                cx + r_inner, cy + r_inner,
                fill="#6366f1", outline="#4f46e5", width=2
            )

        elif self.state == "speaking":
            # Violet wavy rings syncing with time-series oscillations
            r_inner = base_radius + 6 * math.sin(self.anim_frame * 0.25)
            glow_color = _VIOLET_GLOW

            # Wavy outline representation
            points = []
            num_points = 60
            for i in range(num_points):
                angle = i * (2 * math.pi / num_points)
                # Apply sine waves to outer circle vertices
                wave_offset = 6 * math.sin(angle * 6 + self.anim_frame * 0.2)
                r_point = r_inner + wave_offset
                x = cx + r_point * math.cos(angle)
                y = cy + r_point * math.sin(angle)
                points.extend([x, y])

            self.create_polygon(points, fill="#8b5cf6", outline=glow_color, width=2)

        else:  # "idle"
            # Slow, deep dark-purple breathing glow animation
            scale = 1.0 + 0.08 * math.sin(self.anim_frame * 0.04)
            r_inner = base_radius * scale
            glow_color = _VIOLET_DIM

            # Outer soft glow circles
            for i in range(4):
                alpha_r = r_inner + (i + 1) * 12
                # Simple color transition for concentric rings
                color = "#312e81" if i == 2 else ("#3730a3" if i == 1 else "#4338ca")
                self.create_oval(
                    cx - alpha_r, cy - alpha_r,
                    cx + alpha_r, cy + alpha_r,
                    fill="", outline=color, width=1
                )

            # Central solid core
            self.create_oval(
                cx - r_inner, cy - r_inner,
                cx + r_inner, cy + r_inner,
                fill="#1e1b4b", outline=glow_color, width=2
            )

            # Logo symbol indicator "✦" inside the core
            self.create_text(
                cx, cy - 2,
                text="✦", fill=_VIOLET_GLOW,
                font=(_FONT_FAMILY, 32, "bold")
            )

        # Re-schedule canvas update loop (approx 30fps)
        self.after(30, self.animate)


class BellaApp(ctk.CTk):
    """Minimalist voice agent widget — single-column 450x600 layout."""

    # ── State display config ─────────────────────────────────────
    _STATE_META = {
        "idle":      {"label": "IDLE",                  "color": _VIOLET_GLOW,  "detail": "Press Start Voice Mode to talk."},
        "sleeping":  {"label": "SLEEPING",              "color": "#6366f1",     "detail": "Waiting for \"Hey Jarvis\"…"},
        "listening": {"label": "LISTENING",             "color": _GREEN,        "detail": "Hearing speech…"},
        "thinking":  {"label": "THINKING",              "color": "#6366f1",     "detail": "Processing…"},
        "speaking":  {"label": "SPEAKING",              "color": _VIOLET_GLOW,  "detail": ""},
    }

    def __init__(self):
        super().__init__()

        # ── Window chrome ────────────────────────────────────────
        self.title("BELLA")
        self.geometry("450x600")
        self.configure(fg_color=_BG_DEEP)
        self.minsize(380, 520)
        self.resizable(False, False)

        # Thread-safe Communication Queue
        self.gui_queue = queue.Queue()

        # Voice loop engine initialization
        self.voice_loop = VoiceLoop(
            session_id="desktop-session",
            on_state_change=self._queue_state_change,
            on_transcript=self._queue_transcript,
            on_volume=self._queue_volume,
            on_caption=self._queue_caption,
        )

        # Build UI
        self._create_widgets()

        # Poll queue regularly (thread safe check)
        self.poll_queue()

        # Handle window closure cleanly
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ─────────────────────────────────────────────────────────────
    #  Widget Construction
    # ─────────────────────────────────────────────────────────────
    def _create_widgets(self):
        # Single-column layout, everything stacks vertically
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)   # visualizer gets the stretch

        # ── Top Bar: Brand + Model Badge ─────────────────────────
        top_bar = ctk.CTkFrame(self, fg_color="transparent", height=44)
        top_bar.grid(row=0, column=0, padx=20, pady=(14, 0), sticky="ew")
        top_bar.grid_columnconfigure(1, weight=1)

        logo_lbl = ctk.CTkLabel(
            top_bar, text="✦", text_color=_VIOLET,
            font=(_FONT_FAMILY, 20, "bold")
        )
        logo_lbl.grid(row=0, column=0, padx=(0, 6))

        title_lbl = ctk.CTkLabel(
            top_bar, text="BELLA", text_color=_TEXT_PRIMARY,
            font=(_FONT_FAMILY, 16, "bold")
        )
        title_lbl.grid(row=0, column=1, sticky="w")

        model_badge = ctk.CTkLabel(
            top_bar,
            text=config.OLLAMA_MODEL.split(":")[0],
            text_color=_TEXT_DIM,
            font=("JetBrains Mono", 9),
            fg_color=_BG_GLASS,
            corner_radius=6,
            padx=8, pady=2
        )
        model_badge.grid(row=0, column=2, sticky="e")

        # ── Status Pill ──────────────────────────────────────────
        self.status_lbl = ctk.CTkLabel(
            self, text="IDLE", text_color=_VIOLET_GLOW,
            font=(_FONT_FAMILY, 13, "bold"),
            fg_color=_BG_GLASS, corner_radius=10,
            padx=14, pady=4
        )
        self.status_lbl.grid(row=1, column=0, pady=(10, 0))

        # ── Central Visualizer ───────────────────────────────────
        viz_container = ctk.CTkFrame(self, fg_color="transparent")
        viz_container.grid(row=2, column=0, padx=20, pady=6, sticky="nsew")
        viz_container.grid_columnconfigure(0, weight=1)
        viz_container.grid_rowconfigure(0, weight=1)

        self.visualizer = AnimatedVisualizer(viz_container, width=340, height=260)
        self.visualizer.grid(row=0, column=0, sticky="nsew")

        # ── Caption Area (glassmorphic card) ─────────────────────
        caption_card = ctk.CTkFrame(
            self, fg_color=_BG_GLASS,
            corner_radius=14, border_color=_BORDER, border_width=1
        )
        caption_card.grid(row=3, column=0, padx=20, pady=(4, 6), sticky="ew")
        caption_card.grid_columnconfigure(0, weight=1)

        # User caption line
        user_row = ctk.CTkFrame(caption_card, fg_color="transparent")
        user_row.pack(fill="x", padx=14, pady=(10, 2))

        ctk.CTkLabel(
            user_row, text="YOU", text_color=_GREEN,
            font=(_FONT_FAMILY, 9, "bold"), anchor="w"
        ).pack(side="left")

        self.user_caption_lbl = ctk.CTkLabel(
            caption_card, text="…", text_color=_TEXT_MUTED,
            font=(_FONT_FAMILY, 12), anchor="w",
            wraplength=380, justify="left"
        )
        self.user_caption_lbl.pack(fill="x", padx=14, pady=(0, 6))

        # Separator
        sep = ctk.CTkFrame(caption_card, fg_color=_BORDER, height=1)
        sep.pack(fill="x", padx=14)

        # BELLA caption line
        bella_row = ctk.CTkFrame(caption_card, fg_color="transparent")
        bella_row.pack(fill="x", padx=14, pady=(6, 2))

        ctk.CTkLabel(
            bella_row, text="BELLA", text_color=_VIOLET_GLOW,
            font=(_FONT_FAMILY, 9, "bold"), anchor="w"
        ).pack(side="left")

        self.bella_caption_lbl = ctk.CTkLabel(
            caption_card, text="…", text_color=_TEXT_PRIMARY,
            font=(_FONT_FAMILY, 12), anchor="w",
            wraplength=380, justify="left"
        )
        self.bella_caption_lbl.pack(fill="x", padx=14, pady=(0, 10))

        # ── Detail sub-label ─────────────────────────────────────
        self.detail_lbl = ctk.CTkLabel(
            self, text="Press Start Voice Mode to talk.",
            text_color=_TEXT_DIM, font=(_FONT_FAMILY, 10),
            wraplength=380
        )
        self.detail_lbl.grid(row=4, column=0, pady=(2, 4))

        # ── Sensitivity slider ───────────────────────────────────
        sens_row = ctk.CTkFrame(self, fg_color="transparent")
        sens_row.grid(row=5, column=0, padx=30, pady=(0, 2), sticky="ew")

        ctk.CTkLabel(
            sens_row, text="Mic Sensitivity",
            text_color=_TEXT_DIM, font=(_FONT_FAMILY, 9)
        ).pack(side="left")

        self.sens_slider = ctk.CTkSlider(
            sens_row,
            from_=0.005, to=0.08,
            number_of_steps=100,
            button_color=_VIOLET, button_hover_color=_VIOLET_GLOW,
            progress_color=_VIOLET_DIM,
            command=self._on_sens_changed,
            width=180
        )
        self.sens_slider.set(self.voice_loop.silence_threshold)
        self.sens_slider.pack(side="right")

        # ── Bottom Button Row ────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=6, column=0, padx=20, pady=(4, 16), sticky="ew")
        btn_row.grid_columnconfigure(0, weight=3)
        btn_row.grid_columnconfigure(1, weight=1)

        self.start_btn = ctk.CTkButton(
            btn_row,
            text="Start Voice Mode",
            fg_color=_VIOLET, hover_color="#7c3aed",
            font=(_FONT_FAMILY, 13, "bold"),
            height=38, corner_radius=10,
            command=self.toggle_voice_mode
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.mute_btn = ctk.CTkButton(
            btn_row,
            text="🔇", width=42,
            fg_color="#1f2937", hover_color="#374151",
            font=(_FONT_FAMILY, 16),
            height=38, corner_radius=10,
            command=self.toggle_mute_output
        )
        self.mute_btn.grid(row=0, column=1, sticky="ew")

    # ─────────────────────────────────────────────────────────────
    #  UI Actions / Callbacks
    # ─────────────────────────────────────────────────────────────
    def toggle_voice_mode(self):
        """Starts or stops the hands-free voice loop engine."""
        if not self.voice_loop.running:
            self.voice_loop.start()
            self.start_btn.configure(
                text="Stop Voice Mode",
                fg_color=_RED, hover_color="#dc2626"
            )
        else:
            self.voice_loop.stop()
            self.start_btn.configure(
                text="Start Voice Mode",
                fg_color=_VIOLET, hover_color="#7c3aed"
            )
            self._apply_state("idle")

    def toggle_mute_output(self):
        """Toggles assistant audio output synthesis."""
        is_muted = self.voice_loop.toggle_mute()
        if is_muted:
            self.mute_btn.configure(text="🔇", fg_color="#b91c1c", hover_color="#991b1b")
        else:
            self.mute_btn.configure(text="🔇", fg_color="#1f2937", hover_color="#374151")

    def _on_sens_changed(self, val):
        """Updates mic volume threshold sensitivity."""
        self.voice_loop.silence_threshold = float(val)

    # ─────────────────────────────────────────────────────────────
    #  State / Caption application helpers
    # ─────────────────────────────────────────────────────────────
    def _apply_state(self, state, detail=None):
        """Update all state-dependent UI elements."""
        meta = self._STATE_META.get(state, self._STATE_META["idle"])
        self.visualizer.update_state(state)
        self.status_lbl.configure(text=meta["label"], text_color=meta["color"])
        self.detail_lbl.configure(text=detail or meta["detail"])

    # ─────────────────────────────────────────────────────────────
    #  Thread-Safe Queue System
    # ─────────────────────────────────────────────────────────────
    def _queue_state_change(self, state, detail):
        self.gui_queue.put(("state", state, detail))

    def _queue_transcript(self, role, text):
        self.gui_queue.put(("transcript", role, text))

    def _queue_volume(self, val):
        self.gui_queue.put(("volume", val))

    def _queue_caption(self, role, text):
        self.gui_queue.put(("caption", role, text))

    def poll_queue(self):
        """Regularly checks the communication queue for background thread updates."""
        try:
            while True:
                task = self.gui_queue.get_nowait()
                task_type = task[0]

                if task_type == "state":
                    state, detail = task[1], task[2]
                    self._apply_state(state, detail if detail else None)

                elif task_type == "transcript":
                    role, text = task[1], task[2]
                    if role == "user":
                        self.user_caption_lbl.configure(text=text)
                    else:
                        self.bella_caption_lbl.configure(text=text)

                elif task_type == "caption":
                    role, text = task[1], task[2]
                    if role == "user":
                        self.user_caption_lbl.configure(text=text)
                    else:
                        self.bella_caption_lbl.configure(text=text)

                elif task_type == "volume":
                    val = task[1]
                    self.visualizer.update_volume(val)

                self.gui_queue.task_done()
        except queue.Empty:
            pass

        # Re-schedule queue checking (every 50ms)
        self.after(50, self.poll_queue)

    def on_close(self):
        """Graciously releases resources and terminates threads when UI is closed."""
        self.voice_loop.stop()
        self.destroy()
        sys.exit(0)


def main():
    """Application main GUI launcher entry point."""
    app = BellaApp()
    app.mainloop()
    return 0
