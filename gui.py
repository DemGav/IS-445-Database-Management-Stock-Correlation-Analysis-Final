"""
IS 445 – Defensive Assets GUI
Run with:  python gui.py
Requires:  customtkinter, matplotlib, seaborn, data_pipeline.py in same folder
"""

import threading
import importlib.util
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

import customtkinter as ctk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import pandas as pd

# ── Try to import the pipeline ────────────────────────────────────────────────
PIPELINE_PATH = Path(__file__).parent / "dataextraction.py"
_pipe = None

def _load_pipeline():
    global _pipe
    try:
        spec = importlib.util.spec_from_file_location("data_pipeline", PIPELINE_PATH)
        _pipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_pipe)
    except Exception as e:
        _pipe = None
        print(f"[warn] Could not load data_pipeline: {e}")

_load_pipeline()

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

BG          = "#F2F2F2"
CARD_BG     = "#FFFFFF"
ACCENT      = "#2ECC71"
ACCENT_DIM  = "#27AE60"
TEXT_DARK   = "#1A1A1A"
TEXT_MID    = "#555555"
TEXT_LIGHT  = "#999999"
BORDER      = "#E0E0E0"
TAG_BG      = "#D5F5E3"
TAG_TEXT    = "#1A7A3A"
DANGER      = "#E74C3C"

MPLBG       = "#FFFFFF"
MPLLINE     = "#2ECC71"
MPLLINE2    = "#27AE60"
MPLGRID     = "#F0F0F0"
MPLTEXTC    = "#555555"

FONT_TITLE  = ("SF Pro Display", 22, "bold")
FONT_HEAD   = ("SF Pro Display", 14, "bold")
FONT_SUB    = ("SF Pro Text",    12)
FONT_SMALL  = ("SF Pro Text",    10)
FONT_TAG    = ("SF Pro Text",     9, "bold")
FONT_MONO   = ("Menlo",          11)

# Fallback fonts if SF Pro not installed
import tkinter.font as tkfont

def _safe_font(preferred, size, weight="normal"):
    return (preferred, size, weight) if weight != "normal" else (preferred, size)


TIMEFRAMES = {
    "Max": None,
    "5Y":  365 * 5,
    "1Y":  365,
    "6Mo": 182,
    "3Mo": 91,
    "1Mo": 30,
    "1Wk": 7,
}

DEFAULT_TICKERS = ["SPY", "QQQ", "TLT", "SGOV", "GLD", "USO", "XLE"]


# ─────────────────────────────────────────────────────────────────────────────
# HELPER WIDGETS
# ─────────────────────────────────────────────────────────────────────────────

def make_card(parent, **kwargs):
    defaults = dict(fg_color=CARD_BG, corner_radius=14,
                    border_width=1, border_color=BORDER)
    defaults.update(kwargs)
    return ctk.CTkFrame(parent, **defaults)


def make_label(parent, text, font=None, text_color=TEXT_DARK, **kwargs):
    return ctk.CTkLabel(parent, text=text,
                        font=font or FONT_SUB,
                        text_color=text_color, **kwargs)


def make_button(parent, text, command, width=120, **kwargs):
    defaults = dict(fg_color=CARD_BG, hover_color="#F0F0F0",
                    border_width=1, border_color=BORDER,
                    text_color=TEXT_DARK, corner_radius=20,
                    font=FONT_SUB, width=width, height=44)
    defaults.update(kwargs)
    return ctk.CTkButton(parent, text=text, command=command, **defaults)


def make_accent_button(parent, text, command, **kwargs):
    defaults = dict(fg_color=ACCENT, hover_color=ACCENT_DIM,
                    text_color="#FFFFFF", corner_radius=10,
                    font=FONT_SUB, height=36)
    defaults.update(kwargs)
    return ctk.CTkButton(parent, text=text, command=command, **defaults)


def sparkline_fig(prices_series, width_px=130, height_px=70):
    """Return a tiny matplotlib Figure for the sidebar ticker cards."""
    dpi = 100
    fig = Figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    fig.patch.set_facecolor(MPLBG)
    ax = fig.add_subplot(111)
    ax.set_facecolor(MPLBG)

    if prices_series is not None and len(prices_series) > 1:
        norm = prices_series / prices_series.iloc[0] * 100
        color = ACCENT if norm.iloc[-1] >= norm.iloc[0] else DANGER
        ax.plot(norm.values, color=color, linewidth=1.8, solid_capstyle="round")
        ax.fill_between(range(len(norm)), norm.values, norm.values.min(),
                        alpha=0.12, color=color)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                color=TEXT_LIGHT, fontsize=8, transform=ax.transAxes)

    ax.axis("off")
    fig.tight_layout(pad=0.1)
    return fig


def df_to_ctk_table(parent, df: pd.DataFrame, row_height=28):
    """Render a pandas DataFrame as a CustomTkinter scrollable grid."""
    frame = ctk.CTkScrollableFrame(parent, fg_color=CARD_BG, corner_radius=0)

    cols = [""] + list(df.columns)
    for c, col in enumerate(cols):
        lbl = ctk.CTkLabel(frame, text=str(col),
                           font=("SF Pro Text", 11, "bold"),
                           text_color=TEXT_MID,
                           anchor="w" if c == 0 else "center",
                           width=140 if c == 0 else 130)
        lbl.grid(row=0, column=c, padx=(8, 4), pady=(4, 2), sticky="w")

    # Separator
    sep = ctk.CTkFrame(frame, height=1, fg_color=BORDER)
    sep.grid(row=1, column=0, columnspan=len(cols), sticky="ew", padx=4)

    for r, (idx, row) in enumerate(df.iterrows()):
        bg = "#FAFAFA" if r % 2 == 0 else CARD_BG
        row_frame = ctk.CTkFrame(frame, fg_color=bg, corner_radius=0, height=row_height)
        row_frame.grid(row=r + 2, column=0, columnspan=len(cols),
                       sticky="ew", padx=2, pady=0)
        row_frame.grid_columnconfigure(list(range(len(cols))), weight=1)

        # Index cell
        ctk.CTkLabel(row_frame, text=str(idx),
                     font=("SF Pro Text", 11, "bold"),
                     text_color=TEXT_DARK, anchor="w",
                     width=140).grid(row=0, column=0, padx=(10, 4), pady=2, sticky="w")

        for c, val in enumerate(row):
            if isinstance(val, float):
                # Colour-code negative values
                is_neg = val < 0
                txt = f"{val:.4f}"
                clr = DANGER if is_neg and c > 0 else TEXT_DARK
            else:
                txt = str(val)
                clr = TEXT_DARK

            ctk.CTkLabel(row_frame, text=txt,
                         font=("Menlo", 10),
                         text_color=clr, anchor="center",
                         width=130).grid(row=0, column=c + 1, padx=4, pady=2)

    return frame


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

class DefensiveAssetsApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("IS 445 — Defensive Assets")
        self.geometry("1160x720")
        self.minsize(960, 620)
        self.configure(fg_color=BG)

        # ── State ─────────────────────────────────────────────
        self.db_tickers: list[str] = []
        self.selected_tickers: list[str] = []
        self.chart_mode  = ctk.StringVar(value="price")   # price | pct
        self.timeframe   = ctk.StringVar(value="1Y")
        self.active_tab  = ctk.StringVar(value="chart")   # chart | settings | portfolio | stats
        self.spy_weight  = ctk.DoubleVar(value=0.80)
        self.alt_weight  = ctk.DoubleVar(value=0.20)
        self.investment  = ctk.StringVar(value="10000")
        self.start_var   = ctk.StringVar(value="2015-01-01")
        self.end_var     = ctk.StringVar(value=datetime.today().strftime("%Y-%m-%d"))
        self.status_text = ctk.StringVar(value="Ready")
        self._spark_canvases: dict = {}
        self._ticker_cards:   dict = {}

        self._build_layout()
        self._refresh_db_tickers()

    # ── Layout scaffold ───────────────────────────────────────

    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left sidebar
        self.sidebar = ctk.CTkFrame(self, fg_color=BG, width=170, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(14, 0), pady=14)
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(1, weight=1)

        # Right content
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew", padx=14, pady=14)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self._build_sidebar()
        self._build_content()
        self._build_status_bar()

    def _build_sidebar(self):
        # Ticker list (scrollable)
        self.ticker_scroll = ctk.CTkScrollableFrame(
            self.sidebar, fg_color=BG, corner_radius=0, width=155)
        self.ticker_scroll.grid(row=1, column=0, sticky="nsew")
        self.ticker_scroll.grid_columnconfigure(0, weight=1)

        # Bottom: Stocks label + Add button
        bottom = ctk.CTkFrame(self.sidebar, fg_color=BG, corner_radius=0)
        bottom.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        stocks_lbl = ctk.CTkButton(
            bottom, text="≡  Stocks",
            font=("SF Pro Text", 13, "bold"),
            text_color=TEXT_DARK, fg_color=BG,
            hover_color="#E8E8E8", corner_radius=8,
            anchor="w", width=100, height=32,
            command=self._open_manage_dialog)
        stocks_lbl.grid(row=0, column=0, sticky="w")

        add_btn = ctk.CTkButton(
            bottom, text="+ Add",
            font=("SF Pro Text", 11),
            text_color=ACCENT_DIM, fg_color=BG,
            hover_color="#E8E8E8", corner_radius=8,
            width=55, height=32,
            command=self._open_add_ticker_dialog)
        add_btn.grid(row=0, column=1, sticky="e")

    def _build_content(self):
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=0)
        self.content.grid_columnconfigure(0, weight=1)

        # Main card (chart area)
        self.main_card = make_card(self.content)
        self.main_card.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.main_card.grid_rowconfigure(0, weight=1)
        self.main_card.grid_columnconfigure(0, weight=1)

        # Tab bar (bottom)
        self.tab_bar = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0, height=60)
        self.tab_bar.grid(row=1, column=0, sticky="ew")
        self.tab_bar.grid_columnconfigure((0, 1, 2, 3), weight=1)

        tabs = [
            ("Chart\nView",          "chart"),
            ("Portfolio\nSettings",  "settings"),
            ("Portfolio\nAnalysis",  "portfolio"),
            ("Statistical\nAnalysis","stats"),
        ]
        self._tab_buttons = {}
        for i, (label, key) in enumerate(tabs):
            btn = make_button(self.tab_bar, label, lambda k=key: self._switch_tab(k),
                              width=130, height=52,
                              font=("SF Pro Text", 12, "bold"))
            btn.grid(row=0, column=i, padx=6, sticky="ew")
            self._tab_buttons[key] = btn

        # Show default (chart) view and highlight its tab
        self._switch_tab("chart")

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color="#E8E8E8", height=24, corner_radius=0)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(bar, textvariable=self.status_text,
                     font=("SF Pro Text", 10), text_color=TEXT_LIGHT,
                     anchor="w").pack(side="left", padx=10)

    # ── Tab switching ─────────────────────────────────────────

    def _switch_tab(self, key):
        self.active_tab.set(key)
        for k, btn in self._tab_buttons.items():
            if k == key:
                btn.configure(fg_color=TAG_BG, text_color=TAG_TEXT,
                               border_color=ACCENT)
            else:
                btn.configure(fg_color=CARD_BG, text_color=TEXT_DARK,
                               border_color=BORDER)
        if key == "chart":
            self._show_stocks_view()
        elif key == "settings":
            self._show_settings_view()
        elif key == "portfolio":
            self._show_portfolio_view()
        elif key == "stats":
            self._show_stats_view()

    def _clear_main_card(self):
        for w in self.main_card.winfo_children():
            w.destroy()

    # ══════════════════════════════════════════════════════════
    # VIEW 1 — STOCKS (default chart view)
    # ══════════════════════════════════════════════════════════

    def _show_stocks_view(self):
        self._clear_main_card()
        self.main_card.grid_rowconfigure(0, weight=1)
        self.main_card.grid_rowconfigure(1, weight=0)
        self.main_card.grid_columnconfigure(0, weight=1)

        # Chart frame
        self.chart_frame = ctk.CTkFrame(self.main_card, fg_color=CARD_BG, corner_radius=0)
        self.chart_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 4))
        self.chart_frame.grid_rowconfigure(0, weight=1)
        self.chart_frame.grid_columnconfigure(0, weight=1)

        self._chart_canvas_widget = None
        self._draw_main_chart()

        # Bottom bar: ticker label + timeframe pills + mode toggle
        bottom = ctk.CTkFrame(self.main_card, fg_color=CARD_BG, corner_radius=0)
        bottom.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 14))
        bottom.grid_columnconfigure(1, weight=1)

        # Ticker label
        names = ", ".join(self.selected_tickers) if self.selected_tickers else "No selection"
        self._chart_title_lbl = make_label(bottom, names,
                                            font=("SF Pro Display", 20, "bold"))
        self._chart_title_lbl.grid(row=0, column=0, sticky="w")

        # Timeframe pills
        pill_frame = ctk.CTkFrame(bottom, fg_color=CARD_BG, corner_radius=0)
        pill_frame.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._tf_buttons = {}
        for tf in TIMEFRAMES:
            active = tf == self.timeframe.get()
            btn = ctk.CTkButton(
                pill_frame, text=tf,
                width=44, height=24, corner_radius=12,
                font=("SF Pro Text", 10, "bold"),
                fg_color=TAG_BG if active else "#F0F0F0",
                text_color=TAG_TEXT if active else TEXT_MID,
                hover_color=TAG_BG,
                command=lambda t=tf: self._set_timeframe(t))
            btn.pack(side="left", padx=3)
            self._tf_buttons[tf] = btn

        # Price / % toggle
        toggle = ctk.CTkSegmentedButton(
            bottom,
            values=["Price", "%"],
            command=self._toggle_chart_mode,
            font=("SF Pro Text", 11),
            fg_color="#F0F0F0",
            selected_color=ACCENT,
            selected_hover_color=ACCENT_DIM,
            unselected_color="#F0F0F0",
            unselected_hover_color="#E0E0E0",
            text_color=TEXT_DARK,
            width=90, height=28,
        )
        toggle.set("Price" if self.chart_mode.get() == "price" else "%")
        toggle.grid(row=0, column=2, sticky="e")

    def _draw_main_chart(self):
        if self._chart_canvas_widget:
            self._chart_canvas_widget.get_tk_widget().destroy()

        fig = Figure(facecolor=MPLBG)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(MPLBG)

        colors = [ACCENT, "#3498DB", "#E67E22", "#9B59B6", "#E74C3C", "#1ABC9C", "#F39C12"]

        if self.selected_tickers and _pipe:
            try:
                days = TIMEFRAMES.get(self.timeframe.get())
                end_d = datetime.today()
                start_d = (end_d - timedelta(days=days)).strftime("%Y-%m-%d") if days else None
                end_str = end_d.strftime("%Y-%m-%d")

                prices = _pipe.load_prices_from_db(self.selected_tickers, start_d, end_str)

                for i, ticker in enumerate(self.selected_tickers):
                    if ticker not in prices.columns:
                        continue
                    s = prices[ticker].dropna()
                    if len(s) < 2:
                        continue
                    clr = colors[i % len(colors)]
                    if self.chart_mode.get() == "pct":
                        y = (s / s.iloc[0] - 1) * 100
                        ax.set_ylabel("Return (%)", color=MPLTEXTC, fontsize=9)
                        ax.axhline(0, color=BORDER, linewidth=0.8, linestyle="--")
                    else:
                        y = s
                        ax.set_ylabel("Price ($)", color=MPLTEXTC, fontsize=9)

                    ax.plot(s.index, y.values, color=clr, linewidth=2,
                            label=ticker, solid_capstyle="round")

                legend = ax.legend(
                    fontsize=9, labelcolor=MPLTEXTC,
                    loc="upper left",
                    framealpha=0.85, facecolor=MPLBG,
                    edgecolor=BORDER, borderpad=0.6,
                    labelspacing=0.35, handlelength=1.6,
                )
                legend.get_frame().set_linewidth(0.6)
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                fig.autofmt_xdate(rotation=30, ha="right")
            except Exception as e:
                ax.text(0.5, 0.5, f"Error loading data:\n{e}",
                        ha="center", va="center", transform=ax.transAxes,
                        color=TEXT_MID, fontsize=10)
        else:
            ax.text(0.5, 0.5, "Select tickers from the sidebar",
                    ha="center", va="center", transform=ax.transAxes,
                    color=TEXT_LIGHT, fontsize=12)

        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(colors=MPLTEXTC, labelsize=8)
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.grid(axis="y", color=MPLGRID, linewidth=0.8)
        fig.tight_layout(pad=1.2)

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self._chart_canvas_widget = canvas

    def _set_timeframe(self, tf):
        self.timeframe.set(tf)
        for t, btn in self._tf_buttons.items():
            active = t == tf
            btn.configure(
                fg_color=TAG_BG if active else "#F0F0F0",
                text_color=TAG_TEXT if active else TEXT_MID)
        self._draw_main_chart()

    def _toggle_chart_mode(self, val):
        self.chart_mode.set("price" if val == "Price" else "pct")
        self._draw_main_chart()

    # ══════════════════════════════════════════════════════════
    # VIEW 2 — PORTFOLIO SETTINGS
    # ══════════════════════════════════════════════════════════

    def _show_settings_view(self):
        self._clear_main_card()
        self.main_card.grid_rowconfigure(0, weight=1)
        self.main_card.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self.main_card, fg_color=CARD_BG, corner_radius=14)
        scroll.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        scroll.grid_columnconfigure(0, weight=1)

        make_label(scroll, "Portfolio Settings",
                   font=("SF Pro Display", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 4))
        make_label(scroll, "Configure weights, investment size, and date range.",
                   text_color=TEXT_MID).grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 16))

        # ── Date range ────────────────────────────────────────
        date_card = make_card(scroll)
        date_card.grid(row=2, column=0, sticky="ew", padx=16, pady=6)
        date_card.grid_columnconfigure((1, 3), weight=1)

        make_label(date_card, "Date Range",
                   font=("SF Pro Text", 12, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(12, 6))

        make_label(date_card, "Start", text_color=TEXT_MID).grid(
            row=1, column=0, padx=(16, 6), pady=(0, 12), sticky="w")
        ctk.CTkEntry(date_card, textvariable=self.start_var,
                     width=140, font=FONT_MONO, corner_radius=8).grid(
            row=1, column=1, padx=4, sticky="w")
        make_label(date_card, "End", text_color=TEXT_MID).grid(
            row=1, column=2, padx=(20, 6), sticky="w")
        ctk.CTkEntry(date_card, textvariable=self.end_var,
                     width=140, font=FONT_MONO, corner_radius=8).grid(
            row=1, column=3, padx=(4, 16), sticky="w")

        # ── SPY Weight slider ─────────────────────────────────
        weight_card = make_card(scroll)
        weight_card.grid(row=3, column=0, sticky="ew", padx=16, pady=6)
        weight_card.grid_columnconfigure(1, weight=1)

        make_label(weight_card, "SPY Benchmark Weight",
                   font=("SF Pro Text", 12, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=16, pady=(12, 4))

        self._spy_wgt_lbl = make_label(weight_card, "80%",
                                        font=("SF Pro Display", 24, "bold"),
                                        text_color=ACCENT)
        self._spy_wgt_lbl.grid(row=1, column=0, padx=(16, 12), pady=(0, 12))

        slider = ctk.CTkSlider(weight_card, from_=0.5, to=0.95,
                                number_of_steps=9,
                                variable=self.spy_weight,
                                command=self._on_weight_slide,
                                button_color=ACCENT,
                                progress_color=ACCENT,
                                fg_color="#E0E0E0")
        slider.grid(row=1, column=1, sticky="ew", padx=(0, 8))

        make_label(weight_card, "Alt Weight",
                   text_color=TEXT_MID).grid(row=1, column=2, padx=(0, 6))
        self._alt_wgt_lbl = make_label(weight_card, "20%",
                                        font=("SF Pro Display", 16, "bold"),
                                        text_color=TEXT_MID)
        self._alt_wgt_lbl.grid(row=1, column=3, padx=(0, 16))

        # ── Investment amount ─────────────────────────────────
        inv_card = make_card(scroll)
        inv_card.grid(row=4, column=0, sticky="ew", padx=16, pady=6)
        inv_card.grid_columnconfigure(1, weight=1)

        make_label(inv_card, "Initial Investment ($)",
                   font=("SF Pro Text", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 6))

        ctk.CTkEntry(inv_card, textvariable=self.investment,
                     width=180, font=FONT_MONO, placeholder_text="e.g. 10000",
                     corner_radius=8).grid(
            row=1, column=0, padx=16, pady=(0, 14), sticky="w")

        # ── Active tickers ────────────────────────────────────
        tickers_card = make_card(scroll)
        tickers_card.grid(row=5, column=0, sticky="ew", padx=16, pady=6)

        make_label(tickers_card, "Active Tickers (in analysis)",
                   font=("SF Pro Text", 12, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 6))

        tag_row = ctk.CTkFrame(tickers_card, fg_color=CARD_BG, corner_radius=0)
        tag_row.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 12))
        for t in self.db_tickers:
            sel = t in self.selected_tickers
            pill = ctk.CTkButton(
                tag_row, text=t,
                width=52, height=26, corner_radius=13,
                font=("SF Pro Text", 10, "bold"),
                fg_color=TAG_BG if sel else "#F0F0F0",
                text_color=TAG_TEXT if sel else TEXT_MID,
                hover_color=TAG_BG,
                command=lambda tk=t: self._toggle_ticker(tk))
            pill.pack(side="left", padx=3)

        # ── Download new data ─────────────────────────────────
        data_card = make_card(scroll)
        data_card.grid(row=6, column=0, sticky="ew", padx=16, pady=(6, 16))
        data_card.grid_columnconfigure(1, weight=1)

        make_label(data_card, "Download & Store Data",
                   font=("SF Pro Text", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(12, 6))
        make_label(data_card, "Adds selected tickers to MySQL for the configured date range.",
                   text_color=TEXT_MID, font=("SF Pro Text", 10)).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))

        btn_row = ctk.CTkFrame(data_card, fg_color=CARD_BG, corner_radius=0)
        btn_row.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 14))

        make_accent_button(btn_row, "⬇  Download",
                           command=self._download_data, width=130).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="⚠  Reset DB",
                      width=110, height=36, corner_radius=10,
                      fg_color="#FDEDEC", hover_color="#FADBD8",
                      text_color=DANGER, font=FONT_SUB,
                      command=self._confirm_reset).pack(side="left", padx=4)

    def _on_weight_slide(self, val):
        w = round(val, 2)
        self.spy_weight.set(w)
        self.alt_weight.set(round(1.0 - w, 2))
        self._spy_wgt_lbl.configure(text=f"{int(w*100)}%")
        self._alt_wgt_lbl.configure(text=f"{int((1-w)*100)}%")

    # ══════════════════════════════════════════════════════════
    # VIEW 3 — PORTFOLIO ANALYSIS
    # ══════════════════════════════════════════════════════════

    def _show_portfolio_view(self):
        self._clear_main_card()
        self.main_card.grid_rowconfigure(0, weight=1)
        self.main_card.grid_columnconfigure(0, weight=1)

        outer = ctk.CTkScrollableFrame(self.main_card, fg_color=CARD_BG, corner_radius=14)
        outer.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        outer.grid_columnconfigure(0, weight=1)

        make_label(outer, "Portfolio Analysis",
                   font=("SF Pro Display", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 2))
        make_label(outer, f"SPY weight: {int(self.spy_weight.get()*100)}%  ·  "
                           f"Alt weight: {int(self.alt_weight.get()*100)}%  ·  "
                           f"Date: {self.start_var.get()} → {self.end_var.get()}",
                   text_color=TEXT_MID, font=("SF Pro Text", 10)).grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        if not self.selected_tickers:
            make_label(outer, "No tickers selected. Go to Portfolio Settings.",
                       text_color=TEXT_LIGHT).grid(row=2, padx=20, pady=20)
            return

        run_btn = make_accent_button(outer, "▶  Run Analysis",
                                      command=lambda: self._run_portfolio_analysis(outer),
                                      width=160)
        run_btn.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 12))

    def _run_portfolio_analysis(self, container):
        # Remove old results if any
        for w in container.winfo_children():
            if getattr(w, "_is_result", False):
                w.destroy()

        self._set_status("Running portfolio analysis…")

        def work():
            try:
                tickers = list(self.selected_tickers)
                if "SPY" not in tickers:
                    tickers = ["SPY"] + tickers
                start   = self.start_var.get() or None
                end     = self.end_var.get()   or None
                spy_wgt = self.spy_weight.get()

                perf   = _pipe.calculate_performance_table(tickers, start, end)
                port   = _pipe.run_portfolio_backtest(tickers, start, end, benchmark_wgt=spy_wgt)
                stress = _pipe.run_stress_test(tickers, start, end)

                classification = None
                try:
                    classification = _pipe.classify_assets(perf, stress, port)
                except Exception:
                    pass

                self.after(0, lambda: self._render_portfolio_results(
                    container, perf, port, classification))
            except Exception as e:
                import traceback; traceback.print_exc()
                self.after(0, lambda: self._set_status(f"Error: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def _render_portfolio_results(self, container, perf, port, classification=None):
        next_row = 3

        # ── Performance table ─────────────────────────────────
        sec1 = make_card(container)
        sec1._is_result = True
        sec1.grid(row=next_row, column=0, sticky="ew", padx=16, pady=6)
        sec1.grid_columnconfigure(0, weight=1)
        next_row += 1

        make_label(sec1, "Basic Performance Table",
                   font=("SF Pro Text", 13, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        if not perf.empty:
            tbl = df_to_ctk_table(sec1, perf.round(4))
            tbl.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 12))
        else:
            make_label(sec1, "No data available.", text_color=TEXT_LIGHT).grid(
                row=1, padx=16, pady=8)

        # ── Portfolio backtest ────────────────────────────────
        sec2 = make_card(container)
        sec2._is_result = True
        sec2.grid(row=next_row, column=0, sticky="ew", padx=16, pady=6)
        sec2.grid_columnconfigure(0, weight=1)
        next_row += 1

        make_label(sec2, "80/20 Portfolio Backtest",
                   font=("SF Pro Text", 13, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        if not port.empty:
            tbl2 = df_to_ctk_table(sec2, port.round(4))
            tbl2.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
            fig = self._make_portfolio_bar_chart(port)
            c = FigureCanvasTkAgg(fig, master=sec2)
            c.draw()
            c.get_tk_widget().grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 12))
        else:
            make_label(sec2, "No portfolio data.", text_color=TEXT_LIGHT).grid(
                row=1, padx=16, pady=8)

        # ── Dollar value card ──────────────────────────────────
        try:
            inv = float(self.investment.get())
        except ValueError:
            inv = None

        has_classification = classification is not None and not classification.empty

        if inv and not perf.empty:
            sec3 = make_card(container)
            sec3._is_result = True
            sec3.grid(row=next_row, column=0, sticky="ew", padx=16,
                      pady=6 if has_classification else (6, 16))
            sec3.grid_columnconfigure(0, weight=1)
            next_row += 1

            make_label(sec3, f"Ending Value of ${inv:,.0f} Investment",
                       font=("SF Pro Text", 13, "bold")).grid(
                row=0, column=0, sticky="w", padx=16, pady=(12, 6))

            val_row = ctk.CTkFrame(sec3, fg_color=CARD_BG, corner_radius=0)
            val_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

            for i, (ticker, row_data) in enumerate(perf.iterrows()):
                end_val = inv * (1 + row_data["Cumulative Return"])
                gain    = end_val - inv
                clr     = ACCENT if gain >= 0 else DANGER

                vc = make_card(val_row, border_color=BORDER)
                vc.pack(side="left", padx=6, pady=4, ipadx=8, ipady=6)

                make_label(vc, ticker,
                           font=("SF Pro Text", 11, "bold")).pack(pady=(6, 0))
                make_label(vc, f"${end_val:,.0f}",
                           font=("SF Pro Display", 15, "bold"),
                           text_color=clr).pack()
                make_label(vc, f"({'+' if gain>=0 else ''}{gain:,.0f})",
                           font=("SF Pro Text", 9),
                           text_color=clr).pack(pady=(0, 6))

        # ── Final asset role classification ───────────────────
        if has_classification:
            ROLE_COLORS = {
                "Safe-Haven / Diversifier":     "#1ABC9C",
                "Conditional Hedge":            "#F39C12",
                "Stabilizer":                   "#3498DB",
                "Risk Amplifier":               DANGER,
                "Inflation / Cyclical Exposure":"#9B59B6",
            }

            sec4 = make_card(container)
            sec4._is_result = True
            sec4.grid(row=next_row, column=0, sticky="ew", padx=16, pady=(6, 16))
            sec4.grid_columnconfigure(0, weight=1)

            make_label(sec4, "Final Asset Role Classification",
                       font=("SF Pro Text", 13, "bold")).grid(
                row=0, column=0, sticky="w", padx=16, pady=(12, 4))
            make_label(sec4,
                       "Roles derived from stress-day behavior, volatility, and portfolio impact.",
                       text_color=TEXT_MID, font=("SF Pro Text", 10)).grid(
                row=1, column=0, sticky="w", padx=16, pady=(0, 8))

            role_frame = ctk.CTkFrame(sec4, fg_color=CARD_BG, corner_radius=0)
            role_frame.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
            role_frame.grid_columnconfigure(0, weight=1)

            for i, (ticker, row_data) in enumerate(classification.iterrows()):
                role      = row_data["Role"]
                rationale = row_data["Rationale"]
                clr       = ROLE_COLORS.get(role, TEXT_MID)

                rc = make_card(role_frame, border_color=BORDER)
                rc.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
                rc.grid_columnconfigure(1, weight=1)

                make_label(rc, ticker,
                           font=("SF Pro Text", 12, "bold"),
                           text_color=TEXT_DARK).grid(
                    row=0, column=0, padx=(12, 8), pady=(8, 4), sticky="w")
                make_label(rc, role,
                           font=("SF Pro Text", 10, "bold"),
                           text_color=clr).grid(
                    row=0, column=1, padx=4, pady=(8, 4), sticky="w")
                make_label(rc, rationale,
                           font=("SF Pro Text", 9),
                           text_color=TEXT_MID,
                           wraplength=520, anchor="w").grid(
                    row=1, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="w")

        self._set_status("Portfolio analysis complete.")

    def _make_portfolio_bar_chart(self, port: pd.DataFrame) -> Figure:
        metrics = ["Cumulative Return", "Annualized Volatility", "Max Drawdown"]
        fig, axes = plt.subplots(1, 3, figsize=(9, 2.8), facecolor=MPLBG)
        colors = [ACCENT, "#3498DB", DANGER]

        for ax, metric, clr in zip(axes, metrics, colors):
            vals   = port[metric].values
            labels = [l.replace("% SPY /", "%\nSPY /") for l in port.index]
            bars = ax.bar(range(len(vals)), vals, color=clr, alpha=0.85,
                          edgecolor="white", linewidth=0.5)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, fontsize=6.5, rotation=35,
                                ha="right", color=MPLTEXTC)
            ax.set_title(metric, fontsize=9, color=MPLTEXTC, pad=4)
            ax.set_facecolor(MPLBG)
            ax.tick_params(colors=MPLTEXTC, labelsize=7)
            ax.axhline(0, color=BORDER, linewidth=0.7)
            for spine in ax.spines.values():
                spine.set_visible(False)
            ax.grid(axis="y", color=MPLGRID, linewidth=0.6)

        fig.tight_layout(pad=1.0)
        return fig

    # ══════════════════════════════════════════════════════════
    # VIEW 4 — STATISTICAL ANALYSIS
    # ══════════════════════════════════════════════════════════

    def _show_stats_view(self):
        self._clear_main_card()
        self.main_card.grid_rowconfigure(0, weight=1)
        self.main_card.grid_columnconfigure(0, weight=1)

        outer = ctk.CTkScrollableFrame(self.main_card, fg_color=CARD_BG, corner_radius=14)
        outer.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        outer.grid_columnconfigure(0, weight=1)

        make_label(outer, "Statistical Analysis",
                   font=("SF Pro Display", 18, "bold")).grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 2))
        make_label(outer, "Correlation, covariance, and SPY stress-day test.",
                   text_color=TEXT_MID, font=("SF Pro Text", 10)).grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        if not self.selected_tickers:
            make_label(outer, "No tickers selected.",
                       text_color=TEXT_LIGHT).grid(row=2, padx=20, pady=20)
            return

        run_btn = make_accent_button(outer, "▶  Run Analysis",
                                      command=lambda: self._run_stats_analysis(outer),
                                      width=160)
        run_btn.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 12))

    def _run_stats_analysis(self, container):
        for w in container.winfo_children():
            if getattr(w, "_is_result", False):
                w.destroy()

        self._set_status("Running statistical analysis…")

        def work():
            try:
                tickers = list(self.selected_tickers)
                if "SPY" not in tickers:
                    tickers = ["SPY"] + tickers
                start   = self.start_var.get() or None
                end     = self.end_var.get()   or None

                pc, rc, pv, rv = _pipe.calculate_correlations(tickers, start, end)
                spy_corr, full_corr = _pipe.calculate_spy_correlation(tickers, start, end)

                stress = None
                if len(tickers) > 1:
                    stress = _pipe.run_stress_test(tickers, start, end)

                self.after(0, lambda: self._render_stats_results(
                    container, rc, rv, spy_corr, full_corr, stress))
            except Exception as e:
                import traceback; traceback.print_exc()
                self.after(0, lambda: self._set_status(f"Error: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def _render_stats_results(self, container, returns_corr, returns_cov,
                               spy_corr, full_corr, stress):
        row = 3

        # ── Returns correlation heatmap ───────────────────────
        sec1 = make_card(container)
        sec1._is_result = True
        sec1.grid(row=row, column=0, sticky="ew", padx=16, pady=6)
        sec1.grid_columnconfigure(0, weight=1)
        make_label(sec1, "Daily Returns Correlation Matrix",
                   font=("SF Pro Text", 13, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        fig_hm = self._make_heatmap(returns_corr, "Returns Correlation")
        c1 = FigureCanvasTkAgg(fig_hm, master=sec1)
        c1.draw()
        c1.get_tk_widget().grid(row=1, column=0, padx=16, pady=(0, 12))
        row += 1

        # ── Returns covariance table ──────────────────────────
        sec2 = make_card(container)
        sec2._is_result = True
        sec2.grid(row=row, column=0, sticky="ew", padx=16, pady=6)
        sec2.grid_columnconfigure(0, weight=1)
        make_label(sec2, "Daily Returns Covariance",
                   font=("SF Pro Text", 13, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))
        tbl = df_to_ctk_table(sec2, returns_cov.round(6))
        tbl.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 12))
        row += 1

        # ── SPY correlation bar ───────────────────────────────
        if spy_corr is not None:
            sec3 = make_card(container)
            sec3._is_result = True
            sec3.grid(row=row, column=0, sticky="ew", padx=16, pady=6)
            sec3.grid_columnconfigure(0, weight=1)
            make_label(sec3, "Correlation vs SPY",
                       font=("SF Pro Text", 13, "bold")).grid(
                row=0, column=0, sticky="w", padx=16, pady=(12, 4))

            fig_bar = self._make_spy_corr_bar(spy_corr)
            c3 = FigureCanvasTkAgg(fig_bar, master=sec3)
            c3.draw()
            c3.get_tk_widget().grid(row=1, column=0, padx=16, pady=(0, 12))
            row += 1

        # ── Stress-day test ───────────────────────────────────
        if stress is not None and not stress.empty:
            sec4 = make_card(container)
            sec4._is_result = True
            sec4.grid(row=row, column=0, sticky="ew", padx=16, pady=(6, 16))
            sec4.grid_columnconfigure(0, weight=1)
            make_label(sec4, "SPY Stress-Day Test (Worst 5% of SPY Days)",
                       font=("SF Pro Text", 13, "bold")).grid(
                row=0, column=0, sticky="w", padx=16, pady=(12, 4))
            make_label(sec4,
                       "Hit Rate = % of stress days ETF was positive  ·  "
                       "Co-Crash Rate = % where ETF was also negative",
                       text_color=TEXT_MID, font=("SF Pro Text", 9)).grid(
                row=1, column=0, sticky="w", padx=16, pady=(0, 4))

            tbl4 = df_to_ctk_table(sec4, stress.round(4))
            tbl4.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))

            fig_stress = self._make_stress_chart(stress)
            c4 = FigureCanvasTkAgg(fig_stress, master=sec4)
            c4.draw()
            c4.get_tk_widget().grid(row=3, column=0, padx=16, pady=(0, 12))

        self._set_status("Statistical analysis complete.")

    def _make_heatmap(self, corr: pd.DataFrame, title: str) -> Figure:
        try:
            import seaborn as sns
        except ImportError:
            sns = None

        n = len(corr)
        sz = max(3.5, n * 0.9)
        fig, ax = plt.subplots(figsize=(sz, sz * 0.8), facecolor=MPLBG)
        ax.set_facecolor(MPLBG)

        if sns:
            sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdYlGn",
                        center=0, vmin=-1, vmax=1, square=True, ax=ax,
                        linewidths=0.5, linecolor=BG,
                        annot_kws={"size": 9, "color": TEXT_DARK},
                        cbar_kws={"shrink": 0.7})
        else:
            im = ax.imshow(corr.values, cmap="RdYlGn", vmin=-1, vmax=1)
            ax.set_xticks(range(n)); ax.set_yticks(range(n))
            ax.set_xticklabels(corr.columns, fontsize=8)
            ax.set_yticklabels(corr.index,   fontsize=8)
            for i in range(n):
                for j in range(n):
                    ax.text(j, i, f"{corr.iloc[i, j]:.2f}",
                            ha="center", va="center", fontsize=8)
            fig.colorbar(im, ax=ax, shrink=0.7)

        ax.set_title(title, fontsize=10, color=MPLTEXTC, pad=8)
        ax.tick_params(colors=MPLTEXTC, labelsize=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
        fig.tight_layout(pad=0.8)
        return fig

    def _make_spy_corr_bar(self, spy_corr: pd.Series) -> Figure:
        fig, ax = plt.subplots(figsize=(6, 2.2), facecolor=MPLBG)
        ax.set_facecolor(MPLBG)
        colors = [ACCENT if v >= 0 else DANGER for v in spy_corr.values]
        ax.barh(spy_corr.index, spy_corr.values, color=colors, edgecolor="white")
        ax.axvline(0, color=BORDER, linewidth=0.8)
        ax.set_xlabel("Correlation with SPY", fontsize=8, color=MPLTEXTC)
        ax.tick_params(colors=MPLTEXTC, labelsize=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(axis="x", color=MPLGRID, linewidth=0.6)
        fig.tight_layout(pad=0.8)
        return fig

    def _make_stress_chart(self, stress: pd.DataFrame) -> Figure:
        fig, axes = plt.subplots(1, 2, figsize=(7, 2.4), facecolor=MPLBG)
        tickers = stress.index.tolist()
        x = range(len(tickers))

        # Hit rate
        axes[0].bar(x, stress["Hit Rate"].values * 100,
                    color=ACCENT, alpha=0.85, edgecolor="white")
        axes[0].axhline(50, color=DANGER, linewidth=0.9, linestyle="--")
        axes[0].set_xticks(list(x)); axes[0].set_xticklabels(tickers, fontsize=8)
        axes[0].set_title("Hit Rate (%)", fontsize=9, color=MPLTEXTC)
        axes[0].set_facecolor(MPLBG)
        axes[0].tick_params(colors=MPLTEXTC, labelsize=7)
        for sp in axes[0].spines.values(): sp.set_visible(False)
        axes[0].grid(axis="y", color=MPLGRID)

        # Co-crash rate
        axes[1].bar(x, stress["Co-Crash Rate"].values * 100,
                    color=DANGER, alpha=0.75, edgecolor="white")
        axes[1].set_xticks(list(x)); axes[1].set_xticklabels(tickers, fontsize=8)
        axes[1].set_title("Co-Crash Rate (%)", fontsize=9, color=MPLTEXTC)
        axes[1].set_facecolor(MPLBG)
        axes[1].tick_params(colors=MPLTEXTC, labelsize=7)
        for sp in axes[1].spines.values(): sp.set_visible(False)
        axes[1].grid(axis="y", color=MPLGRID)

        fig.tight_layout(pad=0.8)
        return fig

    # ══════════════════════════════════════════════════════════
    # SIDEBAR — ticker cards
    # ══════════════════════════════════════════════════════════

    def _refresh_db_tickers(self):
        if _pipe:
            try:
                self.db_tickers = _pipe.get_available_tickers()
            except Exception:
                self.db_tickers = []
        if not self.selected_tickers and self.db_tickers:
            self.selected_tickers = list(self.db_tickers)
        self._rebuild_ticker_cards()

    def _rebuild_ticker_cards(self):
        for w in self.ticker_scroll.winfo_children():
            w.destroy()
        self._spark_canvases = {}
        self._ticker_cards   = {}

        for i, ticker in enumerate(self.db_tickers):
            self._build_ticker_card(i, ticker)

    def _build_ticker_card(self, row_idx: int, ticker: str):
        selected = ticker in self.selected_tickers
        card = make_card(
            self.ticker_scroll,
            border_color=ACCENT if selected else BORDER,
            fg_color=TAG_BG if selected else CARD_BG)
        card.grid(row=row_idx, column=0, sticky="ew", pady=4, padx=2)
        card.grid_columnconfigure(0, weight=1)
        card.bind("<Button-1>", lambda e, t=ticker: self._toggle_ticker(t))

        # Sparkline
        spark_frame = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
        spark_frame.grid(row=0, column=0, sticky="nsew", padx=6, pady=(8, 2))
        spark_frame.grid_columnconfigure(0, weight=1)

        prices = self._get_spark_prices(ticker)
        fig = sparkline_fig(prices)
        c = FigureCanvasTkAgg(fig, master=spark_frame)
        c.draw()
        widget = c.get_tk_widget()
        widget.configure(width=130, height=60)
        widget.grid(row=0, column=0)
        widget.bind("<Button-1>", lambda e, t=ticker: self._toggle_ticker(t))
        self._spark_canvases[ticker] = c

        # Ticker label
        lbl = make_label(card, ticker,
                         font=("SF Pro Text", 11, "bold"),
                         text_color=TAG_TEXT if selected else TEXT_DARK)
        lbl.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 8))
        lbl.bind("<Button-1>", lambda e, t=ticker: self._toggle_ticker(t))

        self._ticker_cards[ticker] = card

    def _get_spark_prices(self, ticker: str) -> pd.Series | None:
        if not _pipe:
            return None
        try:
            end = datetime.today().strftime("%Y-%m-%d")
            start = (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d")
            prices = _pipe.load_prices_from_db([ticker], start, end)
            if ticker in prices.columns and len(prices[ticker].dropna()) > 1:
                return prices[ticker].dropna()
        except Exception:
            pass
        return None

    def _toggle_ticker(self, ticker: str):
        if ticker in self.selected_tickers:
            self.selected_tickers.remove(ticker)
        else:
            self.selected_tickers.append(ticker)

        # Update card appearance
        if ticker in self._ticker_cards:
            selected = ticker in self.selected_tickers
            self._ticker_cards[ticker].configure(
                border_color=ACCENT if selected else BORDER,
                fg_color=TAG_BG if selected else CARD_BG)
            # Update label colour
            for child in self._ticker_cards[ticker].winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    child.configure(
                        text_color=TAG_TEXT if selected else TEXT_DARK)

        # Refresh current view
        if self.active_tab.get() in ("chart", "stocks"):
            if hasattr(self, "_chart_title_lbl"):
                names = ", ".join(self.selected_tickers) or "No selection"
                self._chart_title_lbl.configure(text=names)
            self._draw_main_chart()

    # ══════════════════════════════════════════════════════════
    # DIALOGS
    # ══════════════════════════════════════════════════════════

    def _open_add_ticker_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Add Ticker")
        dlg.geometry("380x220")
        dlg.resizable(False, False)
        dlg.configure(fg_color=BG)
        dlg.grab_set()

        make_label(dlg, "Add Ticker to Database",
                   font=("SF Pro Display", 14, "bold")).pack(pady=(20, 4), padx=20, anchor="w")
        make_label(dlg, "Ticker will be downloaded for the configured date range.",
                   text_color=TEXT_MID, font=("SF Pro Text", 10)).pack(padx=20, anchor="w")

        ticker_var = ctk.StringVar()
        entry = ctk.CTkEntry(dlg, textvariable=ticker_var,
                              placeholder_text="e.g. BIL", width=200,
                              font=FONT_MONO, corner_radius=8)
        entry.pack(pady=(12, 0), padx=20, anchor="w")
        entry.focus()

        def do_add():
            t = ticker_var.get().strip().upper()
            if not t:
                return
            if not _pipe:
                self._set_status("Pipeline not loaded — check data_pipeline / vibecodetest1.py")
                dlg.destroy()
                return
            dlg.destroy()
            self._set_status(f"Downloading {t}…")
            def work():
                try:
                    _pipe.download_and_insert_tickers(
                        [t],
                        self.start_var.get(),
                        self.end_var.get())
                    def after_add():
                        if t not in self.selected_tickers:
                            self.selected_tickers.append(t)
                        self._refresh_db_tickers()
                        if self.active_tab.get() in ("chart", "stocks"):
                            self._draw_main_chart()
                        self._set_status(f"✓ {t} added and selected.")
                    self.after(0, after_add)
                except Exception as e:
                    self.after(0, lambda: self._set_status(f"Error adding {t}: {e}"))
            threading.Thread(target=work, daemon=True).start()

        entry.bind("<Return>", lambda _: do_add())

        btn_row = ctk.CTkFrame(dlg, fg_color=BG, corner_radius=0)
        btn_row.pack(pady=16, padx=20, anchor="w")
        make_accent_button(btn_row, "Add", command=do_add, width=90).pack(side="left", padx=(0, 8))
        make_button(btn_row, "Cancel", command=dlg.destroy, width=80).pack(side="left")

    def _open_manage_dialog(self):
        """Show all tickers in DB with per-ticker delete and option to load defaults."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Manage Tickers")
        dlg.geometry("420x500")
        dlg.configure(fg_color=BG)
        dlg.grab_set()

        make_label(dlg, "Manage Tickers",
                   font=("SF Pro Display", 14, "bold")).pack(pady=(20, 4), padx=20, anchor="w")
        make_label(dlg, "Press × to permanently delete a ticker and all its price data.",
                   text_color=TEXT_MID, font=("SF Pro Text", 10),
                   wraplength=380).pack(padx=20, anchor="w")

        # Scrollable ticker list
        list_frame = ctk.CTkScrollableFrame(dlg, fg_color=CARD_BG, corner_radius=10, height=260)
        list_frame.pack(fill="x", padx=20, pady=(12, 4))
        list_frame.grid_columnconfigure(0, weight=1)

        ticker_row_widgets: dict = {}

        def _do_delete(t: str):
            if not _pipe:
                return
            if not _pipe.delete_ticker(t):
                self._set_status(f"✗ Could not delete {t}.")
                return
            if t in self.selected_tickers:
                self.selected_tickers.remove(t)
            self._refresh_db_tickers()
            if self.active_tab.get() in ("chart", "stocks"):
                self._draw_main_chart()
            if t in ticker_row_widgets:
                ticker_row_widgets[t].destroy()
                del ticker_row_widgets[t]
            self._set_status(f"✓ {t} deleted from database.")

        def _populate():
            for w in list_frame.winfo_children():
                w.destroy()
            ticker_row_widgets.clear()
            tickers = self.db_tickers
            if not tickers:
                make_label(list_frame, "No tickers in database.",
                           text_color=TEXT_LIGHT).grid(row=0, column=0, padx=12, pady=14)
                return
            for i, t in enumerate(tickers):
                row_f = ctk.CTkFrame(list_frame, fg_color=CARD_BG, corner_radius=0)
                row_f.grid(row=i, column=0, sticky="ew", pady=2, padx=4)
                row_f.grid_columnconfigure(0, weight=1)
                make_label(row_f, t, font=("SF Pro Text", 12, "bold"),
                           text_color=TEXT_DARK).grid(
                    row=0, column=0, sticky="w", padx=10, pady=6)
                ctk.CTkButton(
                    row_f, text="×", width=30, height=30, corner_radius=8,
                    font=("SF Pro Text", 15, "bold"),
                    fg_color="#FDEDEC", hover_color="#FADBD8",
                    text_color=DANGER, border_width=0,
                    command=lambda ticker=t: _do_delete(ticker)
                ).grid(row=0, column=1, padx=(4, 8), pady=4)
                ticker_row_widgets[t] = row_f

        _populate()

        # Load defaults
        make_label(dlg, "Load all default tickers (SPY QQQ TLT SGOV GLD USO XLE):",
                   text_color=TEXT_MID, font=("SF Pro Text", 10)).pack(
            padx=20, pady=(10, 4), anchor="w")

        def load_defaults():
            dlg.destroy()
            self._set_status("Downloading default tickers…")
            def work():
                try:
                    _pipe.download_and_insert_tickers(
                        _pipe.DEFAULT_TICKERS,
                        self.start_var.get(),
                        self.end_var.get())
                    self.after(0, self._refresh_db_tickers)
                    self.after(0, lambda: self._set_status("✓ Default tickers loaded."))
                except Exception as e:
                    self.after(0, lambda: self._set_status(f"Error: {e}"))
            threading.Thread(target=work, daemon=True).start()

        btn_row = ctk.CTkFrame(dlg, fg_color=BG, corner_radius=0)
        btn_row.pack(pady=(4, 16), padx=20, anchor="w")
        make_accent_button(btn_row, "Load Defaults",
                           command=load_defaults, width=130).pack(side="left", padx=(0, 8))
        make_button(btn_row, "Close", command=dlg.destroy, width=80).pack(side="left")

    def _confirm_reset(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Confirm Reset")
        dlg.geometry("340x160")
        dlg.configure(fg_color=BG)
        dlg.grab_set()

        make_label(dlg, "⚠  Reset Database?",
                   font=("SF Pro Display", 14, "bold"),
                   text_color=DANGER).pack(pady=(20, 6), padx=20, anchor="w")
        make_label(dlg, "This will delete all ticker and price data.",
                   text_color=TEXT_MID).pack(padx=20, anchor="w")

        def do_reset():
            dlg.destroy()
            if _pipe:
                _pipe.reset_db()
                self.db_tickers = []
                self.selected_tickers = []
                self._rebuild_ticker_cards()
                self._set_status("Database reset.")

        btn_row = ctk.CTkFrame(dlg, fg_color=BG, corner_radius=0)
        btn_row.pack(pady=16, padx=20, anchor="w")
        ctk.CTkButton(btn_row, text="Yes, Reset",
                      width=110, height=36, corner_radius=10,
                      fg_color=DANGER, hover_color="#C0392B",
                      text_color="white", font=FONT_SUB,
                      command=do_reset).pack(side="left", padx=(0, 8))
        make_button(btn_row, "Cancel", command=dlg.destroy, width=80).pack(side="left")

    # ── Utilities ─────────────────────────────────────────────

    def _download_data(self):
        if not self.selected_tickers:
            self._set_status("No tickers selected to download.")
            return
        self._set_status(f"Downloading {self.selected_tickers}…")

        def work():
            try:
                _pipe.download_and_insert_tickers(
                    self.selected_tickers,
                    self.start_var.get(),
                    self.end_var.get())
                self.after(0, self._refresh_db_tickers)
                self.after(0, lambda: self._set_status("✓ Download complete."))
            except Exception as e:
                self.after(0, lambda: self._set_status(f"Error: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def _set_status(self, msg: str):
        self.status_text.set(msg)


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = DefensiveAssetsApp()
    app.mainloop()