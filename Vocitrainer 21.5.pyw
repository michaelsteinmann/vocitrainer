"""
Vokabeltrainer GUI (Tkinter) – Excel/CSV einlesen und abfragen
- Mehrere Antwortspalten (Synonyme) + zwei Eingabefelder (eine reicht für „richtig“)
- Optional: Erläuterungs-Spalte (wird nach Auflösung angezeigt)
- Modus: Eingabe oder Multiple Choice (4 Optionen, große Buttons)
- Enter = prüfen | nochmals Enter = weiter
- Reihenfolge gemischt; „Neu mischen“
- Statistik + Schnellrunde (Timer)
- Titel oben = Dateiname (GROSS)
- Excel mit mehreren Registern: scrollbare Auswahl; Button „Alle an/aus“, „OK“, „Abbrechen“
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import re
import time
import traceback
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

# Häufigkeit (Spalte "Häufigkeit"): 1–5
FREQ_LABELS = {
    1: "sehr häufig",
    2: "häufig",
    3: "mittelhäufig",
    4: "selten",
    5: "sehr selten",
}

# Tooltip-Text für Häufigkeit (1–5)
FREQ_TOOLTIP = """1 = sehr häufig – alltägliche Basiswörter
2 = häufig – regelmässig im gesprochenen und geschriebenen Italienisch
3 = mittelhäufig – wichtig, aber nicht ständig präsent
4 = selten – gehoben, literarisch oder themenspezifisch
5 = sehr selten – fast nur Literatur, Fachsprache oder feste Wendungen"""


import tkinter as tk


# --- Tooltip-Helfer (mit Bildschirmrändern & Zeilenumbruch) ---
class _Tooltip:
    def __init__(self, widget, text, delay=400, wrap=280):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wrap = wrap
        self.tipwin = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def set_text(self, text: str):
        self.text = text

    def _schedule(self, _=None):
        self._after_id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self.tipwin or not self.text:
            return
        # Grundposition unter dem Widget
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tipwin = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        # Inhalt mit Zeilenumbruch
        label = tk.Label(tw, text=self.text, justify=tk.LEFT, relief=tk.SOLID,
                         borderwidth=1, background="#ffffe0", wraplength=self.wrap)
        label.pack(ipadx=6, ipady=4)
        tw.update_idletasks()
        # Bildschirmränder berücksichtigen
        sw = tw.winfo_screenwidth()
        sh = tw.winfo_screenheight()
        w = tw.winfo_reqwidth()
        h = tw.winfo_reqheight()
        # nach rechts begrenzen
        x = min(max(0, x), sw - w - 6)
        # falls unten zu wenig Platz, oberhalb anzeigen
        if y + h + 6 > sh:
            y = self.widget.winfo_rooty() - h - 8
        y = max(0, y)
        tw.wm_geometry(f"+{x}+{y}")

    def _hide(self, _=None):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
                # Wenn keine Synonyme vorhanden sind, informativen Hinweis setzen
                try:
                    ftext = self.synonyms_foreign.cget("text").replace("Fremdsprache:", "").strip()
                    gtext = self.synonyms_german.cget("text").replace("Deutsch:", "").strip()
                    if not ftext and not gtext:
                        self.synonyms_foreign.config(text="keine Synonyme")
                        self.synonyms_german.config(text="")
                except Exception:
                    pass
    
            self._after_id = None
        if self.tipwin is not None:
            try:
                self.tipwin.destroy()
            except Exception:
                pass
            self.tipwin = None

def attach_tooltip(widget, text):
    """Attach a tooltip and return the tooltip instance (or None)."""
    try:
        t = _Tooltip(widget, text)
        return t
    except Exception:
        return None

    def report_callback_exception(self, exc, val, tb):
        """Callback-Exceptions sichtbar machen (Python/Tk kompatibel)."""
        try:
            import traceback
            traceback.print_exception(exc, val, tb)
        except Exception:
            pass

from tkinter import ttk, filedialog, messagebox, simpledialog

# --- Abhängigkeiten prüfen ---
try:
    import pandas as pd
except Exception:
    try:
        tk.Tk().withdraw()
    except Exception:
        pass
    messagebox.showerror(
        "Fehlendes Paket",
        "Es fehlen Pakete. Bitte installieren:\n\npython -m pip install pandas openpyxl"
)
    sys.exit(1)


def normalize_answer(s: str) -> str:
    """
    Robuster Normalizer für Vergleiche:
    - Kleinschreibung
    - entfernt Steuer- & Sonderzeichen, Tabs/Zeilenumbrüche
    - behält nur Buchstaben (inkl. gängiger Akzentbuchstaben)
    - entfernt Mehrfach-Leerzeichen vollständig
    """
    if s is None:
        return ""
    import re, unicodedata
    s = str(s).replace("\r", "").replace("\n", "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("\u2026", "...")
    for sp in ["\u00A0","\u2009","\u200A","\u2002","\u2003","\u202F","\t"]:
        s = s.replace(sp, " ")
    s = re.sub(r"[^a-zàèéìíòóùúäöüß]", "", s)
    return s

@dataclass
class Card:
    prompt: str
    answers: List[str]
    explanation: Optional[str] = None
    example: Optional[str] = None  # Beispielsatz in der Fremdsprache
    german_example: Optional[str] = None  # Beispielsatz Deutsch
    prompt_is_german: bool = False
    german_synonyms: Optional[List[str]] = None
    row_index: Optional[int] = None
    pos_code: Optional[str] = None  # z.B. 'ADJ' oder 'ADV' (aus Excel-Spalte 'Wortart')


class Deck:
    def __init__(self, cards: List[Card], *, shuffle_on_init: bool = True, allow_wrap: bool = True):
        self.cards = cards[:]
        self.allow_wrap = bool(allow_wrap)
        if shuffle_on_init:
            random.shuffle(self.cards)
        self.index = 0

    def shuffle(self):
        random.shuffle(self.cards)
        self.index = 0

    def has_next(self) -> bool:
        return self.index < len(self.cards)

    def next_card(self) -> Optional[Card]:
        if not self.has_next():
            return None
        c = self.cards[self.index]
        self.index += 1
        return c

    def reinsert_soon(self, card: Card, offset: int = 2):
        pos = min(self.index + offset, len(self.cards))
        self.cards.insert(pos, card)


class FlashcardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(os.path.splitext(os.path.basename(__file__))[0])
        self.geometry("900x640")
        try:
            self.state("zoomed")
        except Exception:
            pass

        self.df: Optional['pd.DataFrame'] = None
        self.deck: Optional[Deck] = None
        self.current_card: Optional[Card] = None

        self.prompt_col = tk.StringVar()
        self.answer_cols: List[str] = []
        self.expl_col = tk.StringVar()
        self.show_expl_var = tk.BooleanVar(value=True)
        self.show_extra_synonyms_var = tk.BooleanVar(value=False)
        # Niveau-Filter (A1–C2)
        self.niveau_vars = {
            "A1": tk.BooleanVar(value=True),
            "A2": tk.BooleanVar(value=True),
            "B1": tk.BooleanVar(value=True),
            "B2": tk.BooleanVar(value=True),
            "C1": tk.BooleanVar(value=True),
            "C2": tk.BooleanVar(value=True),
        }
        # Häufigkeit 1–5
        self.freq_vars = {
            "1": tk.BooleanVar(value=True),
            "2": tk.BooleanVar(value=True),
            "3": tk.BooleanVar(value=True),
            "4": tk.BooleanVar(value=True),
            "5": tk.BooleanVar(value=True),
        }
        self.total_words_var = tk.StringVar(value="Total der Wörter in der Fremdsprache mit deiner Auswahl: 0")
        self.session_progress_var = tk.StringVar(value="In dieser Session bereits geprüft: 0 % (0 von 0 Wörtern)")
        self.mode_var = tk.StringVar(value="Eingabe")
        self.test_words_var = tk.StringVar(value="100")
        self.test_max_available = 0
        self.reverse_var = tk.BooleanVar(value=False)
        self.ready_for_next = False

        self.total_seen = 0
        self.total_correct = 0
        self.total_wrong = 0
        # Synonym-Bridge: merkt letzte korrekte italienische Varianten
        self._last_correct_it = []
        self._last_correct_de = []
        self.file_title_var = tk.StringVar(value="VOKABELTRAINER")

        self._build_ui()
        self._bind_keys()
        self.card_stats = {}
        self.session_seen_rows = set()


    # ---- Wortart: Ambiguität (Deutsch und Italienisch) nur dort anzeigen, wo nötig ----
    POS_LABELS_DE = {
        "ADJ": "Adjektiv",
        "ADV": "Adverb",
        "NOM": "Nomen",
    }

    def _pos_code_from_cell(self, cell) -> Optional[str]:
        """Mappt den Excel-Inhalt der Spalte 'Wortart' auf 'ADJ' / 'ADV' / 'NOM' (oder None).

        Hinweis: Bei Nomen wird alles, was auf "Sostantivo" folgt (Genus, invariabile, usw.)
        bewusst ignoriert.
        """
        try:
            s = "" if cell is None else str(cell).strip().lower()
        except Exception:
            return None
        if not s or s == "nan":
            return None
        # tolerant gegen verschiedene Schreibweisen
        if "sostantivo" in s or "substantiv" in s or re.search(r"\bnom(en)?\b", s):
            return "NOM"
        if any(k in s for k in ("adv", "adverb", "avv")):
            return "ADV"
        if any(k in s for k in ("adj", "adjektiv", "aggettivo", "agg")):
            return "ADJ"
        return None

    def _rebuild_de_ambiguous_pos_index(self):
        """Baut ein Set deutscher Lemmata, die im Korpus in mehr als einer Wortart vorkommen."""
        self._de_ambiguous_pos = set()
        try:
            if self.df is None:
                return
            # Deutsch-Spalten (alle, die mit 'Deutsch' beginnen)
            de_cols = [c for c in self.df.columns if str(c).strip().lower().startswith("deutsch")]
            if not de_cols:
                return
            # Wortart-Spalte ermitteln (robust)
            cols_lower = {str(c).strip().lower(): c for c in self.df.columns}
            pos_col = cols_lower.get("wortart")
            if pos_col is None:
                for k, c in cols_lower.items():
                    if "wortart" in k:
                        pos_col = c
                        break
            if pos_col is None:
                return

            from collections import defaultdict
            pos_sets = defaultdict(set)

            for _, row in self.df.iterrows():
                try:
                    pos = self._pos_code_from_cell(row.get(pos_col, ""))
                except Exception:
                    pos = self._pos_code_from_cell(row[pos_col]) if pos_col in self.df.columns else None
                if not pos:
                    continue
                for dc in de_cols:
                    try:
                        val = row.get(dc, "")
                    except Exception:
                        val = ""
                    # NaN/leer überspringen
                    try:
                        import pandas as pd
                        if pd.isna(val):
                            continue
                    except Exception:
                        if val is None:
                            continue
                    txt = str(val).strip()
                    if not txt or txt.lower() == "nan":
                        continue
                    # Mehrfachangaben splitten
                    for ch in "|;/,":
                        txt = txt.replace(ch, "|")
                    parts = [p.strip() for p in txt.split("|") if p.strip()]
                    for p in parts:
                        key = normalize_answer(p)
                        if key:
                            pos_sets[key].add(pos)

            for de_key, s in pos_sets.items():
                # Ambig, sobald mehr als eine Wortart auf demselben deutschen Lemma liegt
                if len(s) >= 2:
                    self._de_ambiguous_pos.add(de_key)
        except Exception:
            self._de_ambiguous_pos = set()

    def _rebuild_it_ambiguous_pos_index(self):
        """Baut ein Set italienischer Lemmata, die im Korpus in mehr als einer Wortart vorkommen.

        Relevanz: v.a. Aggettivo <-> Sostantivo mit identischer Form (z.B. "sfigato").
        """
        self._it_ambiguous_pos = set()
        try:
            if self.df is None:
                return

            # Italienisch-Spalten finden (robust)
            it_cols = []
            for c in self.df.columns:
                cl = str(c).strip().lower()
                if cl.startswith("italien") or cl.startswith("italiano") or cl in ("it", "ital"):
                    it_cols.append(c)
            if not it_cols:
                # Fallback: typische erste Spalte
                if "Italienisch" in self.df.columns:
                    it_cols = ["Italienisch"]
            if not it_cols:
                return

            # Wortart-Spalte ermitteln (robust)
            cols_lower = {str(c).strip().lower(): c for c in self.df.columns}
            pos_col = cols_lower.get("wortart")
            if pos_col is None:
                for k, c in cols_lower.items():
                    if "wortart" in k:
                        pos_col = c
                        break
            if pos_col is None:
                return

            from collections import defaultdict
            pos_sets = defaultdict(set)

            for _, row in self.df.iterrows():
                try:
                    pos = self._pos_code_from_cell(row.get(pos_col, ""))
                except Exception:
                    pos = self._pos_code_from_cell(row[pos_col]) if pos_col in self.df.columns else None
                if not pos:
                    continue

                for ic in it_cols:
                    try:
                        val = row.get(ic, "")
                    except Exception:
                        val = ""
                    try:
                        import pandas as pd
                        if pd.isna(val):
                            continue
                    except Exception:
                        if val is None:
                            continue

                    txt = str(val).strip()
                    if not txt or txt.lower() == "nan":
                        continue

                    # Mehrfachangaben splitten
                    for ch in "|;/,":
                        txt = txt.replace(ch, "|")
                    parts = [p.strip() for p in txt.split("|") if p.strip()]
                    for p in parts:
                        key = normalize_answer(p)
                        if key:
                            pos_sets[key].add(pos)

            for it_key, s in pos_sets.items():
                if len(s) >= 2:
                    self._it_ambiguous_pos.add(it_key)
        except Exception:
            self._it_ambiguous_pos = set()

    def _format_prompt_with_pos_if_ambiguous(self, card: 'Card', base_text: str) -> str:
        try:
            pos = getattr(card, "pos_code", None)
            if pos not in ("ADJ", "ADV", "NOM"):
                return base_text

            key = normalize_answer(getattr(card, "prompt", "") or "")
            if not key:
                return base_text

            # Deutsche Prompts: ADJ/ADV immer markieren
            if getattr(card, "prompt_is_german", False) and pos in ("ADJ", "ADV"):
                return f"{base_text} [{self.POS_LABELS_DE.get(pos, pos)}]"

            # Ambiguitaetslogik (Deutsch: z.B. NOM; Italienisch: z.B. NOM oder weitere)
            if getattr(card, "prompt_is_german", False):
                if key in getattr(self, "_de_ambiguous_pos", set()):
                    return f"{base_text} [{self.POS_LABELS_DE.get(pos, pos)}]"
                return base_text

            if key in getattr(self, "_it_ambiguous_pos", set()):
                return f"{base_text} [{self.POS_LABELS_DE.get(pos, pos)}]"

            return base_text
        except Exception:
            return base_text


    def _pos_suffix_if_needed(self, card: 'Card') -> str:
        """Gibt den Wortart-Suffix (z.B. ' [Adverb]') zurück – oder ''.

        Wichtig: Der Suffix wird als Meta-Info zum italienischen Lemma behandelt und deshalb
        in der UI immer separat formatiert (nicht zwischen Synonyme gemischt).
        """
        try:
            pos = getattr(card, "pos_code", None)
            if pos not in ("ADJ", "ADV", "NOM"):
                return ""

            key = normalize_answer(getattr(card, "prompt", "") or "")
            if not key:
                return ""

            label = self.POS_LABELS_DE.get(pos, pos)

            # Deutsche Prompts: Adjektiv/Adverb immer markieren (wie bisher gewünscht)
            if getattr(card, "prompt_is_german", False) and pos in ("ADJ", "ADV"):
                return f" [{label}]"

            # Ambiguitaetslogik fuer Nomen (Deutsch) und fuer italienische Prompts
            if getattr(card, "prompt_is_german", False):
                if key in getattr(self, "_de_ambiguous_pos", set()):
                    return f" [{label}]"
                return ""

            if key in getattr(self, "_it_ambiguous_pos", set()):
                return f" [{label}]"

            return ""
        except Exception:
            return ""
    def _report_callback_exception(self, exc, val, tb):
        details = "".join(traceback.format_exception(exc, val, tb))
        try:
            messagebox.showerror("Fehler", details)
        except Exception:
            pass

    # ---- Tastenkürzel ----
    def _bind_keys(self):
        try:
            self.unbind_all("<Tab>")
        except Exception:
            pass
        self.bind_all("<Return>", self._on_return)

    def _build_ui(self):
        # Titel (Dateiname groß)
        title_frame = ttk.Frame(self, padding=8)
        title_frame.pack(fill=tk.X)
        self.file_title_label = ttk.Label(title_frame, textvariable=self.file_title_var, font=("Segoe UI", 20, "bold"))
        self.file_title_label.pack()

        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)
        self.btn_open = ttk.Button(top, text="Datei öffnen…", command=self.on_open_file)
        self.btn_open.pack(side=tk.LEFT)
        attach_tooltip(self.btn_open, "Excel/CSV-Datei öffnen\n\nUm die schwierigen Wörter zu wiederholen, wähle die Datei \"Parole Sconosciute\"")

        self.lbl_prompt_lang = ttk.Label(top, text="ausgegebene Sprache:")
        self.lbl_prompt_lang.pack(side=tk.LEFT, padx=(10, 0))
        self.prompt_cb = ttk.Combobox(top, width=22, textvariable=self.prompt_col, state="disabled")
        self.prompt_cb.pack(side=tk.LEFT, padx=4)
        attach_tooltip(self.prompt_cb, "zu übersetzende Sprache")

        self.lbl_answer_lang = ttk.Label(top, text="abgefragte Sprache:")
        self.lbl_answer_lang.pack(side=tk.LEFT, padx=(10, 0))
        self.answer_listbox = tk.Listbox(top, selectmode=tk.MULTIPLE, exportselection=False, height=4, width=28)
        self.answer_listbox.pack(side=tk.LEFT, padx=4)
        attach_tooltip(self.answer_listbox, "Antworten aus den Spalten (Mehrfachwahl möglich)")

        self.btn_start = ttk.Button(top, text="Start", command=self.init_deck)
        self.btn_start.pack(side=tk.LEFT, padx=6)
        attach_tooltip(self.btn_start, "Abfrage starten")
        # Abfragerichtung umkehren (ersetzt "Neu mischen")
        self.btn_flip = ttk.Button(top, text="↔", width=3, command=self.toggle_reverse)
        self.btn_flip.pack(side=tk.LEFT)
        attach_tooltip(self.btn_flip, "Abfragerichtung umkehren")

        
        # --- Modus + Synonyme: zweizeiliger Block, Radio-Buttons exakt untereinander ---
        cfg = ttk.Frame(top)
        cfg.pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(cfg, text="Modus:").grid(row=0, column=0, sticky="w", padx=(0, 8))

        # Radiobuttons statt Dropdown (Eingabe / Multiple Choice / Test)
        self.mode_rb_frame = ttk.Frame(cfg)
        self.mode_rb_frame.grid(row=0, column=1, sticky="w")

        ttk.Radiobutton(self.mode_rb_frame, text="Eingabe", value="Eingabe",
                        variable=self.mode_var, command=self._update_mode_widgets).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(self.mode_rb_frame, text="Multiple Choice", value="Multiple Choice",
                        variable=self.mode_var, command=self._update_mode_widgets).pack(side=tk.LEFT, padx=(0, 12))

        # Test: Radiobutton + Eingabe "Anzahl Wörter"
        self.rb_test = ttk.Radiobutton(self.mode_rb_frame, text="Test mit Wörtern:", value="Test",
                                       variable=self.mode_var, command=self._update_mode_widgets)
        self.rb_test.pack(side=tk.LEFT, padx=(0, 6))

        self.test_words_entry = ttk.Entry(self.mode_rb_frame, textvariable=self.test_words_var, width=10)
        self.test_words_entry.pack(side=tk.LEFT, padx=(0, 6))
        self._test_words_tt = attach_tooltip(self.test_words_entry, "Maximal verfügbar mit aktueller Auswahl: 0")

        # Synonyme: zweite Zeile, Radio-Buttons beginnen exakt dort, wo die Modus-Radios beginnen (Spalte 1)
        ttk.Label(cfg, text="Zusätzlich Synonyme angeben:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))

        self.syn_rb_frame = ttk.Frame(cfg)
        self.syn_rb_frame.grid(row=1, column=1, sticky="w", pady=(6, 0))

        ttk.Radiobutton(
            self.syn_rb_frame,
            text="ja",
            variable=self.show_extra_synonyms_var,
            value=True,
            command=self._refresh_prompt_label,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(
            self.syn_rb_frame,
            text="nein",
            variable=self.show_extra_synonyms_var,
            value=False,
            command=self._refresh_prompt_label,
        ).pack(side=tk.LEFT)

        self.show_extra_synonyms_var.set(False)

        self._update_lang_labels()


        # Gelber Filter-/Statusbalken
        filters_frame = tk.Frame(self, bg="#fff7c0")
        filters_frame.pack(fill=tk.X, padx=8, pady=(0, 6))

        # Niveaus
        tk.Label(filters_frame, text="Abgefragte Niveaus:", bg="#fff7c0").pack(side=tk.LEFT, padx=(4, 4))
        for lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            tk.Checkbutton(
                filters_frame,
                text=lvl,
                variable=self.niveau_vars[lvl],
                bg="#fff7c0",
                command=self._on_niveau_filter_changed,
            ).pack(side=tk.LEFT, padx=(2, 2))

        # Häufigkeit 1–5
        freq_lbl = tk.Label(filters_frame, text="Abgefragte Häufigkeit:", bg="#fff7c0")
        freq_lbl.pack(side=tk.LEFT, padx=(14, 4))
        for f in ["1", "2", "3", "4", "5"]:
            cb = tk.Checkbutton(
                filters_frame,
                text=f,
                variable=self.freq_vars[f],
                bg="#fff7c0",
                command=self._on_freq_filter_changed,
            )
            cb.pack(side=tk.LEFT, padx=(2, 2))
            _Tooltip(cb, FREQ_TOOLTIP)

        # Total + Session-Fortschritt (rechts, gleiche Zeile)
        tk.Label(filters_frame, textvariable=self.total_words_var, bg="#fff7c0").pack(side=tk.LEFT, padx=(18, 12))
        tk.Label(filters_frame, textvariable=self.session_progress_var, bg="#fff7c0").pack(side=tk.LEFT, padx=(0, 4))


        mid = ttk.Frame(self, padding=12)
        mid.pack(fill=tk.BOTH, expand=True)

        # Prompt: Hauptwort + (optionaler) Wortart-Zusatz in dezenter Optik.
        # Hinweis: Tkinter unterstuetzt keine echte Text-Transparenz; wir simulieren
        # "~50% Deckkraft" ueber eine hellere Schriftfarbe.
        self.prompt_outer = ttk.Frame(mid)
        self.prompt_outer.pack(fill=tk.X, expand=False, pady=(4, 6))

        # Inneres Frame wird zentriert; darin liegen zwei Labels nebeneinander.
        # Wir zentrieren ueber ein 3-Spalten-Grid (links/rechts Spacer mit weight=1).
        self.prompt_outer.columnconfigure(0, weight=1)
        self.prompt_outer.columnconfigure(1, weight=0)
        self.prompt_outer.columnconfigure(2, weight=1)

        self.prompt_inner = ttk.Frame(self.prompt_outer)
        self.prompt_inner.grid(row=0, column=1)

        self.prompt_main_label = ttk.Label(self.prompt_inner, text="", font=("Segoe UI", 24, "bold"))
        self.prompt_main_label.pack(side=tk.LEFT)

        self.prompt_pos_label = ttk.Label(self.prompt_inner, text="", font=("Segoe UI", 20), foreground="#888888")
        self.prompt_pos_label.pack(side=tk.LEFT)

        self.entry1 = ttk.Entry(mid, font=("Segoe UI", 18))
        self.entry1.pack(fill=tk.X, padx=60, pady=(0, 8))

        # Zweites Eingabefeld (historisch) – bleibt unsichtbar
        self.entry2 = ttk.Entry(mid, font=("Segoe UI", 18))
        # nicht packen, damit keine zweite Eingabezeile angezeigt wird

        self.mc_frame = ttk.Frame(mid)
        self.mc_buttons: List[ttk.Button] = []
        for i in range(4):
            btn = ttk.Button(
                self.mc_frame,
                text=f"Option {i+1}",
                command=lambda ix=i: self._mc_pick(ix)
            )
            btn.configure(width=24)
            btn.configure(style="MC.TButton")
            btn.grid(row=i // 2, column=i % 2, padx=16, pady=14, sticky="nsew")
            self.mc_buttons.append(btn)
        for c in range(2):
            self.mc_frame.columnconfigure(c, weight=1)

        # Hinweiszeile
        self.hint = ttk.Label(mid, text="Enter = prüfen | nochmals Enter = weiter")
        self.hint.pack(pady=(0, 8))
        # Feedback direkt unter dem abgefragten Wort (zentriert)
        self.feedback = ttk.Label(mid, text="", font=("Segoe UI", 18, "bold"), anchor="center", justify="center")
        self.feedback.pack(fill=tk.X, pady=(0, 10))

        # Erläuterung direkt unter dem Feedback (zentriert, schwarz)
        self.expl_label = ttk.Label(mid, text="", font=("Segoe UI", 12), anchor="center", justify="center")
        self.expl_label.pack(fill=tk.X, pady=(0, 4))

        # Drei Spalten darunter: links Beispiele, rechts Synonyme, ganz rechts Grammatik
        self.two_col = ttk.Frame(mid)
        self.two_col.pack(fill=tk.BOTH, expand=True, padx=60, pady=(20, 10))
        self.left_col = tk.Frame(self.two_col, bg="#f0f0f0", width=520)
        self.left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 20))
        self.left_col.pack_propagate(False)

        self.right_col = tk.Frame(self.two_col, bg="#f0f0f0", width=420)
        self.right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(20, 0))
        self.right_col.pack_propagate(False)

        self.gram_col = tk.Frame(self.two_col, bg="#f0f0f0", width=320)
        self.gram_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(20, 0))
        self.gram_col.pack_propagate(False)
        
        self.left_title = ttk.Label(self.left_col, text="Beispiele", font=("Segoe UI", 16, "bold underline"), anchor="w", justify="left")
        self.left_title.pack(anchor="w", pady=(0, 6))
        self.right_title = ttk.Label(self.right_col, text="Synonyme", font=("Segoe UI", 16, "bold underline"), anchor="w", justify="left")
        self.right_title.pack(anchor="w", pady=(0, 6))
        # Grammatik-Spalte
        self.gram_title = ttk.Label(self.gram_col, text="Grammatik & Hinweise", font=("Segoe UI", 16, "bold underline"), anchor="w", justify="left")
        self.gram_title.pack(anchor="w", pady=(0, 6))
        self.gram_ipa = ttk.Label(self.gram_col, text="", font=("Segoe UI", 11), wraplength=340, justify="left")
        self.gram_ipa.pack(anchor="w")
        # Wortart (vor Grammatikalische Hinweise)
        self.gram_pos = ttk.Label(self.gram_col, text="", font=("Segoe UI", 11), wraplength=340, justify="left")
        self.gram_pos.pack(anchor="w")
        self.gram_hint = ttk.Label(self.gram_col, text="", font=("Segoe UI", 11), wraplength=340, justify="left")
        self.gram_hint.pack(anchor="w")
        self.gram_aux = ttk.Label(self.gram_col, text="", font=("Segoe UI", 11), wraplength=340, justify="left")
        self.gram_aux.pack(anchor="w")
        self.gram_pp = ttk.Label(self.gram_col, text="", font=("Segoe UI", 11), wraplength=340, justify="left")
        self.gram_pp.pack(anchor="w")
        self.gram_reg = ttk.Label(self.gram_col, text="", font=("Segoe UI", 11), wraplength=340, justify="left")
        self.gram_reg.pack(anchor="w")
        self.gram_freq = ttk.Label(self.gram_col, text="", font=("Segoe UI", 11), wraplength=340, justify="left")
        self.gram_freq.pack(anchor="w")
        _Tooltip(self.gram_freq, FREQ_TOOLTIP)
        self.gram_niveau = ttk.Label(self.gram_col, text="", font=("Segoe UI", 11), wraplength=340, justify="left")
        self.gram_niveau.pack(anchor="w")

        # Beispiel-Sätze links, linksbündig
        self.example_foreign = ttk.Label(self.left_col, text="", font=("Segoe UI", 11, "italic"), anchor="w", justify="left", wraplength=520)
        self.example_foreign.pack(anchor="w", pady=(4, 2))
        self.example_german = ttk.Label(self.left_col, text="", font=("Segoe UI", 11, "italic"), anchor="w", justify="left", wraplength=520)
        self.example_german.pack(anchor="w", pady=(0, 6))
        
        # Synonyme rechts (fester Block)
        self.synonyms_frame = ttk.Frame(self.right_col)
        self.synonyms_frame.pack(anchor="w", fill=tk.X, padx=(0, 0), pady=(0, 0))
        self.synonyms_foreign = ttk.Label(self.synonyms_frame, text="", font=("Segoe UI", 11), anchor="w", justify="left", wraplength=420)
        self.synonyms_foreign.pack(anchor="w", pady=(4, 2))
        self.synonyms_german = ttk.Label(self.synonyms_frame, text="", font=("Segoe UI", 11), anchor="w", justify="left", wraplength=420)
        self.synonyms_german.pack(anchor="w", pady=(0, 6))

        # Footer
        bot = ttk.Frame(self, padding=8)
        bot.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.stats_var = tk.StringVar(value="0 gesehen · 0 richtig · 0 falsch · 0%")
        ttk.Label(bot, textvariable=self.stats_var).pack(side=tk.RIGHT)

        style = ttk.Style()
        style.configure("MC.TButton", font=("Segoe UI", 16, "bold"), padding=12)

        self._update_mode_widgets()

    # ---- Datei / Setup ----
    def on_open_file(self):
        path = filedialog.askopenfilename(
            title="Excel/CSV öffnen",
            filetypes=[("Excel/CSV", "*.xlsx *.xls *.csv")]
        )
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                self.df = pd.read_csv(path)
            else:
                all_sheets = pd.read_excel(path, sheet_name=None)
                sheet_names = list(all_sheets.keys())

                win = tk.Toplevel(self)
                win.title("Blätter auswählen")
                win.geometry("420x500")

                sel_vars = {}
                all_var = tk.BooleanVar(value=True)

                # Buttons oben
                topbar = ttk.Frame(win)
                topbar.pack(fill=tk.X, pady=(6, 4))
                def toggle_all():
                    target = not all_var.get()
                    all_var.set(target)
                    for v in sel_vars.values():
                        v.set(target)
                btn_all = ttk.Button(topbar, text="Alle an/aus", command=toggle_all)
                btn_all.pack(side=tk.LEFT, padx=4)
                attach_tooltip(btn_all, "Alle Tabellenblätter an- oder abwählen")

                def confirm():
                    if all_var.get():
                        frames = list(all_sheets.values())
                    else:
                        selected = [name for name, v in sel_vars.items() if v.get()]
                        if not selected:
                            messagebox.showerror("Fehler", "Keine Blätter ausgewählt")
                            return
                        frames = [all_sheets[name] for name in selected]
                    try:
                        self.df = pd.concat(frames, ignore_index=True)
                    except Exception as e:
                        messagebox.showerror("Fehler", f"Blätter konnten nicht zusammengeführt werden.\n\n{e}")
                        return
                    win.destroy()
                btn_ok = ttk.Button(topbar, text="OK", command=confirm)
                btn_ok.pack(side=tk.RIGHT, padx=4)
                attach_tooltip(btn_ok, "Auswahl übernehmen")
                try:
                    btn_ok.focus_set()
                    win.bind("<Return>", lambda e: btn_ok.invoke())
                except Exception:
                    pass
                btn_cancel = ttk.Button(topbar, text="Abbrechen", command=win.destroy)
                btn_cancel.pack(side=tk.RIGHT)
                attach_tooltip(btn_cancel, "Fenster schließen ohne Auswahl")

                # Scrollbarer Bereich
                container = ttk.Frame(win)
                container.pack(fill=tk.BOTH, expand=True)
                canvas = tk.Canvas(container)
                scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
                canvas.configure(yscrollcommand=scrollbar.set)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                inner = ttk.Frame(canvas)
                canvas.create_window((0, 0), window=inner, anchor="nw")

                def on_configure(event=None):
                    canvas.configure(scrollregion=canvas.bbox("all"))
                inner.bind("<Configure>", on_configure)

                # Zeilenzahl pro Blatt ermitteln
                row_counts = {}
                for _sheet in sheet_names:
                    try:
                        df_sheet = all_sheets[_sheet]
                        row_counts[_sheet] = len(df_sheet.dropna(how="all"))
                    except Exception:
                        row_counts[_sheet] = 0

                for name in sheet_names:
                    var = tk.BooleanVar(value=True)
                    sel_vars[name] = var
                    label = f"{name} ({row_counts.get(name, 0)})"
                    tk.Checkbutton(inner, text=label, variable=var, anchor="w").pack(fill=tk.X, padx=6, pady=2)

                win.grab_set()
                self.wait_window(win)
        except Exception as e:
            messagebox.showerror("Fehler", f"Datei konnte nicht gelesen werden.\n\n{e}")
            return

        if self.df is None or len(self.df.columns) < 2:
            messagebox.showerror("Fehler", "Mindestens zwei Spalten nötig.")
            return

        cols = [str(c) for c in self.df.columns if str(c).lower() != 'nan']
        cols = [c for c in cols if not str(c).startswith('Unnamed') and c not in ["Erläuterung", "Erläuterung (optional)", "Erklärung", "explanation", "Erläuterung:", "Beispielsatz in der Fremdsprache"]]
        self.prompt_cb.configure(values=cols, state="readonly")
        self.answer_listbox.delete(0, tk.END)
        if cols:
            self.prompt_cb.set(cols[0])
        self._update_answer_choices()

        base = os.path.splitext(os.path.basename(path))[0]
        self.file_title_var.set(base.upper())

        # Wortart-Ambiguitaeten vorbereiten (DE: Adj/Adv/Nomen; IT: v.a. Adj/Nomen)
        try:
            self._rebuild_de_ambiguous_pos_index()
        except Exception:
            pass
        try:
            self._rebuild_it_ambiguous_pos_index()
        except Exception:
            pass

    # ---- Modus / Anzeige ----
    def _update_answer_choices(self):
        """Aktualisiert die Liste der Antwortspalten, sodass die aktuell
        gewählte Ausgabe-Spalte (Prompt) NICHT auswählbar ist."""
        try:
            if self.df is None:
                return
            # Basisliste wie beim Laden (gefiltert von Unnamed/Erläuterung/Beispielsatz)
            cols = [str(c) for c in self.df.columns if str(c).lower() != 'nan']
            cols = [c for c in cols if not str(c).startswith('Unnamed') and c not in ["Erläuterung", "Erläuterung (optional)", "Erklärung", "explanation", "Erläuterung:", "Beispielsatz in der Fremdsprache"]]
            # Gewählte Frage/ausgegebene Sprache entfernen
            current_prompt = self.prompt_cb.get().strip()
            cols_filtered = [c for c in cols if c != current_prompt]
            # Merke bisherige Auswahl
            selected_values = [self.answer_listbox.get(i) for i in self.answer_listbox.curselection()]
            # Neu aufbauen
            self.answer_listbox.delete(0, tk.END)
            for c in cols_filtered:
                self.answer_listbox.insert(tk.END, c)
            # Alte Auswahl wiederherstellen, soweit vorhanden
            for idx, val in enumerate(cols_filtered):
                if val in selected_values:
                    self.answer_listbox.selection_set(idx)
            # Standard: Wenn noch nichts ausgewählt ist, alle "Deutsch 1–X"-Spalten vorauswählen
            if not selected_values:
                for idx, val in enumerate(cols_filtered):
                    if str(val).strip().lower().startswith("deutsch"):
                        self.answer_listbox.selection_set(idx)
        except Exception:
            pass

    def _update_mode_widgets(self):
        mode = self.mode_var.get()
        is_mc = (mode == "Multiple Choice")
        is_test = (mode == "Test")

        # Test-Entry nur aktiv im Testmodus
        try:
            if hasattr(self, "test_words_entry"):
                self.test_words_entry.configure(state=("normal" if is_test else "disabled"))
        except Exception:
            pass

        # "Neu mischen" im Testmodus deaktivieren
        try:
            # Button existiert nicht mehr (wurde durch Richtungswechsel ersetzt)
            pass
        except Exception:
            pass

        if is_mc:
            self.entry1.pack_forget()
            self.entry2.pack_forget()
            self.mc_frame.pack(fill=tk.X, padx=80)
            if getattr(self, "current_card", None):
                self._populate_multiple_choice(self.current_card)
        else:
            self.mc_frame.pack_forget()
            self.entry1.pack(fill=tk.X, padx=60, pady=(0, 8))
            self.entry1.focus_set()

        # Tooltip "max verfügbar" aktualisieren (falls Daten geladen)
        try:
            self._update_test_max_available()
        except Exception:
            pass

    # ---- Quiz-Flow ----

    def _build_cards_from_selection(self) -> List[Card]:
        """Baut Karten aus der aktuellen Spaltenauswahl (ohne Deck/Shuffle)."""
        if self.df is None:
            return []
        pcol = self.prompt_cb.get()
        sel = [self.answer_listbox.get(i) for i in self.answer_listbox.curselection()]
        if not pcol or not sel:
            return []

        reverse = bool(self.reverse_var.get())

        # Erklärungsspalte (optional, wie bisher)
        expl_col = ""
        if self.show_expl_var.get():
            candidates = [
                "Erläuterung", "Erläuterung (optional)", "Erklärung",
                "explanation", "Erläuterung:"
            ]
            for c in candidates:
                if c in self.df.columns:
                    expl_col = c
                    break

        example_col_name = "Beispielsatz in der Fremdsprache"
        german_example_col_name = "Beispielsatz Deutsch"
        de_syn_cols = [c for c in self.df.columns if str(c).strip().lower().startswith('deutsch')]

        # Wortart-Spalte (optional) ermitteln, damit wir bei ambigen deutschen Prompts [Adjektiv]/[Adverb] anzeigen können
        cols_lower = {str(c).strip().lower(): c for c in self.df.columns}
        pos_col = cols_lower.get("wortart")
        if pos_col is None:
            for k, c in cols_lower.items():
                if "wortart" in k:
                    pos_col = c
                    break


        cards: List[Card] = []

        # Normal direction
        if not reverse:
            for idx, row in self.df.iterrows():
                prompt = str(row[pcol]).strip() if pcol in self.df.columns and pd.notna(row[pcol]) else ""
                if not prompt:
                    continue
                # Wortart-Code dieser Zeile (ADJ/ADV), falls Spalte vorhanden
                pos_code = None
                try:
                    if "pos_col" in locals() and pos_col and pos_col in self.df.columns:
                        pos_code = self._pos_code_from_cell(row.get(pos_col, ""))
                except Exception:
                    pos_code = None
                answers: List[str] = []
                for c in sel:
                    if c in self.df.columns and pd.notna(row[c]):
                        s = str(row[c]).strip()
                        if not s:
                            continue
                        parts = [p.strip() for p in str(s).split(";") if str(p).strip()]
                        answers.extend(parts if parts else [s])
                if not answers:
                    continue

                explanation = ""
                if expl_col and expl_col in self.df.columns and pd.notna(row[expl_col]):
                    explanation = str(row[expl_col]).strip()

                example = None
                if example_col_name in self.df.columns and pd.notna(row[example_col_name]):
                    example = str(row[example_col_name])

                german_example = None
                if german_example_col_name in self.df.columns and pd.notna(row[german_example_col_name]):
                    german_example = str(row[german_example_col_name])

                german_synonyms: Optional[List[str]] = None
                try:
                    tmp = []
                    for c in de_syn_cols:
                        if c in self.df.columns and pd.notna(row[c]):
                            s = str(row[c]).strip()
                            if s:
                                tmp.append(s)
                    german_synonyms = tmp or None
                except Exception:
                    german_synonyms = None

                cards.append(Card(
                    row_index=idx,
                    prompt=prompt,
                    answers=answers,
                    explanation=explanation,
                    example=example,
                    german_example=german_example,
                    german_synonyms=german_synonyms,
                    prompt_is_german=(pcol in de_syn_cols),
                    pos_code=pos_code,
                ))
        else:
            # Reversed direction: create cards with prompts from each selected answer column
            for idx, row in self.df.iterrows():
                answer_value = ""
                if pcol in self.df.columns and pd.notna(row[pcol]):
                    answer_value = str(row[pcol]).strip()
                if not answer_value:
                    continue

                # Wortart-Code dieser Zeile (ADJ/ADV), falls Spalte vorhanden
                pos_code = None
                try:
                    if "pos_col" in locals() and pos_col and pos_col in self.df.columns:
                        pos_code = self._pos_code_from_cell(row.get(pos_col, ""))
                except Exception:
                    pos_code = None

                explanation = ""
                if expl_col and expl_col in self.df.columns and pd.notna(row[expl_col]):
                    explanation = str(row[expl_col]).strip()

                example = None
                if example_col_name in self.df.columns and pd.notna(row[example_col_name]):
                    example = str(row[example_col_name])

                german_example = None
                if german_example_col_name in self.df.columns and pd.notna(row[german_example_col_name]):
                    german_example = str(row[german_example_col_name])

                row_de_syns = []
                try:
                    for c in de_syn_cols:
                        if c in self.df.columns and pd.notna(row[c]):
                            s = str(row[c]).strip()
                            if s:
                                row_de_syns.append(s)
                except Exception:
                    pass

                for c in sel:
                    if c not in self.df.columns or not pd.notna(row[c]):
                        continue
                    prompt = str(row[c]).strip()
                    if not prompt:
                        continue

                    german_synonyms: Optional[List[str]] = None
                    if c in de_syn_cols and row_de_syns:
                        german_synonyms = [s for s in row_de_syns if s != prompt] or None

                    cards.append(Card(
                        row_index=idx,
                        prompt=prompt,
                        answers=[answer_value],
                        explanation=explanation,
                        example=example,
                        german_example=german_example,
                        german_synonyms=german_synonyms,
                        prompt_is_german=(c in de_syn_cols),
                        pos_code=pos_code,
                    ))
        return cards

    def init_deck(self):
        """
        (Re)builds the deck from the selected columns.
        Now respects self.reverse_var:
          - Normal: prompt = prompt column; answers = selected answer columns (possibly multiple)
          - Reversed: we create one card per selected answer column where
              prompt = value from that answer column
              answers = value from the prompt column (single expected)
              Plus, when reversed and the prompt is in a German "Deutsch X" column,
              we attach other "Deutsch X" values from the same row as synonyms so
              the UI can show them as "Synonyme in der abgefragten Sprache".
        """
        if self.df is None:
            return
        pcol = self.prompt_cb.get()
        sel = [self.answer_listbox.get(i) for i in self.answer_listbox.curselection()]
        if not pcol or not sel:
            messagebox.showwarning("Hinweis", "Bitte Frage- UND Antwortspalten wählen.")
            return
        self.answer_cols = sel

        reverse = bool(self.reverse_var.get())

        # If explanation display is enabled, try to auto-detect an explanation column
        expl_col = ""
        if self.show_expl_var.get():
            candidates = [
                "Erläuterung", "Erläuterung (optional)", "Erklärung",
                "explanation", "Erläuterung:"
            ]
            for c in candidates:
                if c in self.df.columns:
                    expl_col = c
                    break

        example_col_name = "Beispielsatz in der Fremdsprache"
        german_example_col_name = "Beispielsatz Deutsch"
        de_syn_cols = [c for c in self.df.columns if str(c).strip().lower().startswith('deutsch')]

        cards: List[Card] = self._build_cards_from_selection()

        # Testmodus: Reihenfolge nach Niveau aufsteigend (innerhalb der Auswahl), ohne Wrap und ohne "Neu mischen".
        # Die eigentliche Limitierung auf N Karten erfolgt weiter unten nach dem Filtern.
# === Build global accept index: German prompt -> ALL Italian answers across all rows (selected answer cols) ===
        try:
            self._accept_index = {}
            self._accept_display = {}
            de_cols = [c for c in self.df.columns if str(c).strip().lower().startswith('deutsch')]
            ans_cols = [c for c in self.df.columns if str(c).strip().lower().startswith('italien')]  # always use Italian column(s)
            def _split_multi(cell: str):
                if not isinstance(cell, str):
                    cell = str(cell) if cell is not None else ""
                txt = cell.strip()
                for ch in "|;/,":
                    txt = txt.replace(ch, "|")
                parts = [p.strip() for p in txt.split("|")]
                return [p for p in parts if p]
            for idx, row in self.df.iterrows():
                # Collect italian answers from selected answer columns for this row
                it_values = []
                for ac in ans_cols:
                    if ac in self.df.columns and pd.notna(row.get(ac, None)):
                        it_values.extend(_split_multi(str(row[ac])))
                if not it_values:
                    continue
                it_norms = {normalize_answer(x) for x in it_values if x}
                # Map each German value in the row to these italian answers
                for gcol in de_cols:
                    if gcol in self.df.columns and pd.notna(row.get(gcol, None)):
                        g = str(row[gcol]).strip()
                        if not g:
                            continue
                        gkey = normalize_answer(g)
                        self._accept_index.setdefault(gkey, set()).update(it_norms)
                        self._accept_display.setdefault(gkey, set()).update(it_values)
            # --- Italienische Meta-Daten: Variante -> (Erläuterung, Beispiel IT, Beispiel DE) ---
            try:
                self._italian_meta = {}
                self._italian_gram = {}
                # Wir verwenden die italienischen Antwortspalten (ans_cols) aus dem Block oben
                # und lesen zusaetzlich die Grammatikfelder aus derselben Zeile, damit bei korrekten Synonymen
                # auch der Bereich "Grammatik & Hinweise" variantenbezogen umschalten kann.
                cols_lower_all = {str(c).lower(): c for c in self.df.columns}

                def _get_from_row(row_obj, name_list):
                    for nm in name_list:
                        key = str(nm).strip().lower()
                        c = cols_lower_all.get(key)
                        if c is None:
                            for k, colname in cols_lower_all.items():
                                if key and key in k:
                                    c = colname
                                    break
                        if c is not None:
                            try:
                                val = row_obj.get(c, "")
                            except Exception:
                                try:
                                    val = row_obj[c]
                                except Exception:
                                    val = ""
                            s = "" if str(val).strip().lower() in ("", "nan") else str(val).strip()
                            if s:
                                return s
                    return ""

                for idx, row in self.df.iterrows():
                    # Beispiele/Erläuterung aus der Zeile holen (falls vorhanden)
                    example_it = ""
                    example_de = ""
                    explanation_row = ""
                    try:
                        if 'example_col_name' in locals() and example_col_name in self.df.columns and pd.notna(row.get(example_col_name)):
                            example_it = str(row[example_col_name]).strip()
                    except Exception:
                        pass
                    try:
                        if 'german_example_col_name' in locals() and german_example_col_name in self.df.columns and pd.notna(row.get(german_example_col_name)):
                            example_de = str(row[german_example_col_name]).strip()
                    except Exception:
                        pass
                    try:
                        if expl_col and expl_col in self.df.columns and pd.notna(row.get(expl_col)):
                            explanation_row = str(row[expl_col]).strip()
                    except Exception:
                        pass

                    # Grammatikfelder dieser Zeile (falls vorhanden)
                    gram = {
                        "ipa": _get_from_row(row, ["IPA", "ipa"]),
                        "hint": _get_from_row(row, ["Grammatikalische Hinweise", "Grammatik", "grammatikalische hinweise"]),
                        "pos": _get_from_row(row, ["Wortart"]),
                        "aux": _get_from_row(row, ["Hilfsverb", "hilfsverb"]),
                        "pp": _get_from_row(row, ["Partizip Perfekt", "partizip perfekt", "p.p.", "pp", "participio passato"]),
                        "reg": _get_from_row(row, ["Stil|Register", "Stil/Register", "Stil", "Register", "stil|register", "stil/register"]),
                        "niveau": _get_from_row(row, ["Niveau", "niveau"]),
                        "freq_raw": _get_from_row(row, ["Häufigkeit", "haeufigkeit", "häufigkeit", "Haeufigkeit"]),
                    }

                    # Alle italienischen Varianten dieser Zeile sammeln
                    it_values = []
                    try:
                        for ac in ans_cols:
                            cell = row.get(ac) if hasattr(row, 'get') else row[ac]
                            txt = "" if cell is None else str(cell).strip()
                            for ch in "|;/,":
                                txt = txt.replace(ch, "|")
                            for part in [p.strip() for p in txt.split("|")]:
                                if part:
                                    it_values.append(part)
                    except Exception:
                        pass

                    # In die Maps schreiben
                    for it in it_values:
                        key = normalize_answer(it)
                        self._italian_meta[key] = (explanation_row, example_it, example_de)
                        self._italian_gram[key] = gram
            except Exception:
                self._italian_meta = {}
                self._italian_gram = {}

        except Exception:
            self._accept_index = {}
            self._accept_display = {}

        if not cards:
            messagebox.showwarning("Keine Karten", "In den gewählten Spalten wurden keine gültigen Paare gefunden.")
            return

        # Filter (Niveau + Häufigkeit) anwenden
        try:
            cards = [c for c in cards if self._card_filter_allows(c)]
        except Exception:
            pass

        # Duplikate entfernen (stabil)
        try:
            seen = set()
            uniq = []
            for c in cards:
                key = (getattr(c, "row_index", None), c.prompt, tuple(c.answers), bool(getattr(c, "prompt_is_german", False)))
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(c)
            cards = uniq
        except Exception:
            pass

        # Testmodus: aufsteigend innerhalb der aktivierten Auswahl + N limitieren + kein Wrap
        if (str(self.mode_var.get()) or "").startswith("Test"):
            # Max verfügbar aktualisieren (Tooltip + Cap)
            try:
                self.test_max_available = len(cards)
                if hasattr(self, "_test_words_tt") and self._test_words_tt is not None:
                    self._test_words_tt.set_text(f"Maximal verfügbar mit aktueller Auswahl: {self.test_max_available}")
            except Exception:
                pass

            if not cards:
                messagebox.showinfo("Keine Karten", "0 Wörter verfügbar (Filter zu streng?)")
                return

            # gewünschte Anzahl lesen + Auto-Cap
            try:
                raw = (self.test_words_var.get() or "").strip()
                n_user = int(float(raw)) if raw else 100
            except Exception:
                n_user = 100
            if n_user <= 0:
                n_user = 100
            n = min(n_user, len(cards))

            # Niveau-Reihenfolge: nur aktivierte Niveaus, sonst Standard
            order_all = ["A1", "A2", "B1", "B2", "C1", "C2"]
            active = self._get_active_niveaus()
            order = [lvl for lvl in order_all if (not active) or (lvl in active)]

            def _card_level(c: Card) -> str:
                try:
                    idx = getattr(c, "row_index", None)
                    if idx is None or self.df is None:
                        return ""
                    row = self.df.iloc[idx]
                    cols_lower = {str(col).strip().lower(): col for col in self.df.columns}
                    col = cols_lower.get("niveau")
                    if col is None:
                        return ""
                    val = row.get(col, "")
                    s = str(val).strip()
                    if not s or s.lower() == "nan":
                        return ""
                    return s
                except Exception:
                    return ""

            # gruppieren + innerhalb Niveau zufällig (aber kein "Neu mischen" Button)
            by = {lvl: [] for lvl in order_all}
            rest = []
            for c in cards:
                lv = _card_level(c)
                if lv in by:
                    by[lv].append(c)
                else:
                    rest.append(c)
            for lvl in order_all:
                random.shuffle(by[lvl])
            random.shuffle(rest)

            ordered = []
            for lvl in order:
                ordered.extend(by.get(lvl, []))
            # Karten ohne Niveau ans Ende
            ordered.extend(rest)

            cards = ordered[:n]
            self.total_italian_words = len(cards)
            self.deck = Deck(cards, shuffle_on_init=False, allow_wrap=False)
        else:
            self.total_italian_words = len(cards)
            self.deck = Deck(cards)
        self.total_seen = self.total_correct = self.total_wrong = 0
        self.ready_for_next = False
        try:
            self.session_seen_rows.clear()
        except Exception:
            self.session_seen_rows = set()
        self._update_mode_widgets()
        # Nach dem Neuaufbau des Decks den Zähler aktualisieren
        try:
            self._update_total_words_label()
        except Exception:
            pass
        try:
            self._update_test_max_available()
        except Exception:
            pass
        self.next_card()

    def _get_active_niveaus(self):
        """Gibt die aktuell aktivierten Niveaus (A1–C2) als Liste zurück."""
        try:
            return [lvl for lvl, var in getattr(self, "niveau_vars", {}).items() if var.get()]
        except Exception:
            return []

    def _get_active_frequencies(self):
        """Gibt die aktivierten Häufigkeiten ('1'–'5') als Liste zurück."""
        try:
            return [f for f, var in getattr(self, "freq_vars", {}).items() if var.get()]
        except Exception:
            return []

    def _niveau_allows_card(self, card: Card) -> bool:
        """
        Prüft, ob die gegebene Karte dem aktuell gewählten Niveau-Filter entspricht.
        Wenn kein Filter gesetzt ist oder kein Niveau gefunden wird, ist die Karte erlaubt.
        """
        try:
            active = self._get_active_niveaus()
            if not active:
                return True  # kein Filter aktiv
            if self.df is None or card is None:
                return True
            idx = getattr(card, "row_index", None)
            if idx is None:
                return True
            row = self.df.iloc[idx]
            cols_lower = {str(c).strip().lower(): c for c in self.df.columns}
            col = cols_lower.get("niveau")
            if col is None:
                return True
            val = row.get(col, "")
            s = str(val).strip()
            if not s or s.lower() == "nan":
                return True  # Karten ohne Niveau nicht filtern
            return s in active
        except Exception:
            return True

    def _freq_allows_card(self, card: Card) -> bool:
        """
        Prüft, ob die Karte dem aktuell gewählten Häufigkeits-Filter entspricht.
        Spalte: 'Häufigkeit' (oder 'Haufigkeit' als Fallback), Werte 1–5.
        Wenn kein Filter gesetzt ist oder Spalte fehlt, wird nicht gefiltert.
        """
        try:
            active = self._get_active_frequencies()
            if not active:
                return True  # kein Filter aktiv
            if self.df is None or card is None:
                return True
            idx = getattr(card, "row_index", None)
            if idx is None:
                return True
            row = self.df.iloc[idx]
            cols_lower = {str(c).lower(): c for c in self.df.columns}
            col = cols_lower.get("häufigkeit")
            if col is None:
                col = cols_lower.get("haufigkeit")
            if col is None:
                return True  # keine Spalte: nicht filtern
            val = row.get(col, "")
            # NaN / leer zulassen
            try:
                import pandas as pd
                if pd.isna(val):
                    return True
            except Exception:
                if val is None:
                    return True
            s = str(val).strip()
            if not s or s.lower() == "nan":
                return True
            # Versuche numerisch zu interpretieren
            freq_str = None
            try:
                freq_str = str(int(float(s)))
            except Exception:
                freq_str = s
            return freq_str in active
        except Exception:
            return True

    def _card_filter_allows(self, card: Card) -> bool:
        """Kombinierter Filter: Niveau + Häufigkeit."""
        try:
            return self._niveau_allows_card(card) and self._freq_allows_card(card)
        except Exception:
            return True

    def _update_total_words_label(self):
        """Aktualisiert Labels: Gesamtzahl + Session-Fortschritt in %."""
        try:
            deck = getattr(self, "deck", None)
            total_count = 0
            seen_count = 0

            if deck is not None:
                cards = getattr(deck, "cards", None)
                if cards is not None:
                    row_ids_total = set()
                    row_ids_seen = set()
                    fallback_total = 0
                    fallback_seen = set()
                    seen_rows = getattr(self, "session_seen_rows", set())

                    for c in cards:
                        try:
                            if not self._card_filter_allows(c):
                                continue
                            rid = getattr(c, "row_index", None)
                            key = getattr(c, "prompt", None)
                            if rid is not None:
                                row_ids_total.add(rid)
                                if rid in seen_rows:
                                    row_ids_seen.add(rid)
                            else:
                                # Fallback über Textschlüssel, falls kein row_index vorhanden
                                if key is not None:
                                    fallback_total += 1
                                    if hasattr(self, "card_stats"):
                                        seen, _corr = self.card_stats.get(key, (0, 0))
                                        if seen > 0:
                                            fallback_seen.add(key)
                        except Exception:
                            continue

                    if row_ids_total:
                        total_count = len(row_ids_total)
                        seen_count = len(row_ids_seen)
                    else:
                        total_count = fallback_total
                        seen_count = len(fallback_seen)

            if total_count > 0:
                pct = int(round((seen_count / total_count) * 100))
                self.session_progress_var.set(
                    f"In dieser Session bereits geprüft: {pct} % ({seen_count} von {total_count} Wörtern)"
                )
            else:
                self.session_progress_var.set("In dieser Session bereits geprüft: 0 % (0 von 0 Wörtern)")

            self.total_words_var.set(
                f"Total der Wörter in der Fremdsprache mit deiner Auswahl: {total_count}"
            )
        except Exception:
            try:
                self.total_words_var.set("Total der Wörter in der Fremdsprache mit deiner Auswahl: ?")
                self.session_progress_var.set("In dieser Session bereits geprüft: ?")
            except Exception:
                pass

    def _update_test_max_available(self):
        """Berechnet die maximal verfügbare Anzahl Karten für den Testmodus (mit aktueller Auswahl) und aktualisiert Tooltip."""
        try:
            if self.df is None:
                self.test_max_available = 0
            else:
                # Erzeuge eine Kartenliste wie in init_deck, aber ohne Shuffle/Deck-Aufbau.
                cards = self._build_cards_from_selection()
                # Filter anwenden (Niveau/Häufigkeit)
                cards = [c for c in cards if self._card_filter_allows(c)]
                # Duplikate entfernen (stabil)
                seen = set()
                uniq = []
                for c in cards:
                    key = (getattr(c, "row_index", None), c.prompt, tuple(c.answers), bool(getattr(c, "prompt_is_german", False)))
                    if key in seen:
                        continue
                    seen.add(key)
                    uniq.append(c)
                self.test_max_available = len(uniq)
        except Exception:
            self.test_max_available = 0

        try:
            if hasattr(self, "_test_words_tt") and self._test_words_tt is not None:
                self._test_words_tt.set_text(f"Maximal verfügbar mit aktueller Auswahl: {self.test_max_available}")
        except Exception:
            pass

    def _on_niveau_filter_changed(self):
        """
        Reagiert auf Änderungen der Niveau-Checkboxen.
        Die aktuelle Karte bleibt, aber bei der nächsten Karte
        wird der Filter berücksichtigt. Falls die aktuelle Karte
        nicht mehr passt, springen wir direkt weiter.
        """
        try:
            if getattr(self, "current_card", None) and not self._card_filter_allows(self.current_card):
                self.next_card()
        except Exception:
            pass
        # Zähler für die aktuell gewählte Auswahl aktualisieren
        try:
            self._update_total_words_label()
        except Exception:
            pass
        try:
            self._update_test_max_available()
        except Exception:
            pass

    def _on_freq_filter_changed(self):
        """
        Reagiert auf Änderungen der Häufigkeits-Checkboxen.
        """
        try:
            if getattr(self, "current_card", None) and not self._card_filter_allows(self.current_card):
                self.next_card()
        except Exception:
            pass
        try:
            self._update_total_words_label()
        except Exception:
            pass
        try:
            self._update_test_max_available()
        except Exception:
            pass

    def _refresh_prompt_label(self):
        """Aktualisiert die große Wort-Anzeige in der Mitte je nach Synonym-Schalter."""
        try:
            card = getattr(self, "current_card", None)
            if not card:
                self._set_prompt_display("")
                return

            base = (getattr(card, "prompt", "") or "").strip()

            # POS-Suffix getrennt (Meta-Info bezieht sich auf das italienische Lemma, nicht auf die Synonymliste)
            suffix = ""
            try:
                suffix = self._pos_suffix_if_needed(card)
            except Exception:
                suffix = ""

            # Wenn Deutsch-Prompt + "Synonyme anzeigen": Prompt + deutsche Synonyme zusammenfassen,
            # aber POS-Suffix NICHT zwischen die Wörter mischen.
            if getattr(card, "prompt_is_german", False) and self.show_extra_synonyms_var.get():
                syns = list(getattr(card, "german_synonyms", None) or [])
                parts = [base] + [s for s in syns if str(s).strip()]
                # Duplikate entfernen, Reihenfolge behalten
                seen = set()
                uniq = []
                for p in parts:
                    p = str(p).strip()
                    if not p:
                        continue
                    if p not in seen:
                        seen.add(p)
                        uniq.append(p)
                main_text = " | ".join(uniq) if uniq else base
            else:
                main_text = base

            # Direkt setzen, damit POS immer separat formatiert werden kann (grau, kleiner).
            if hasattr(self, "prompt_main_label") and hasattr(self, "prompt_pos_label"):
                self.prompt_main_label.config(text=main_text)
                self.prompt_pos_label.config(text=suffix)
            else:
                # Fallback (sollte praktisch nie greifen)
                self._set_prompt_display((main_text + suffix).strip())
        except Exception:
            pass

    def _set_prompt_display(self, text: str):
        """Setzt die Prompt-Anzeige: Hauptteil normal/bold, Wortart-Zusatz dezent (grau, nicht fett).

        Erwartet entweder reinen Prompt (z.B. "deutlich") oder Prompt mit
        genau einem Wortart-Anhang am Ende (z.B. "deutlich [Adjektiv]").
        Bei mehrfachen Synonymen ("a | b | c") wird nichts speziell getrennt.
        """
        try:
            t = (text or "").strip()
            main = t
            suffix = ""

            # Nur dann splitten, wenn GENAU ein POS-Anhang am Ende steht.
            # Beispiel: "deutlich [Adjektiv]" -> main="deutlich", suffix=" [Adjektiv]"
            # Bei "deutlich [Adjektiv] | klar" wuerde das sonst falsch werden.
            if "|" not in t:
                m = re.match(r"^(.*?)(\s\[[^\]]+\])$", t)
                if m:
                    main = m.group(1)
                    suffix = m.group(2)

            # Fallback, falls Labels (noch) nicht existieren
            if hasattr(self, "prompt_main_label"):
                self.prompt_main_label.config(text=main)
            if hasattr(self, "prompt_pos_label"):
                self.prompt_pos_label.config(text=suffix)
        except Exception:
            pass

    def next_card(self):

        if not self.deck:
            return
        self.ready_for_next = False

        card = None
        max_tries = len(getattr(self.deck, "cards", [])) or 0
        if max_tries == 0:
            return
        for _ in range(max_tries):
            c = self.deck.next_card()
            if not c:
                if getattr(self.deck, 'allow_wrap', True):
                    self.deck.shuffle()
                    c = self.deck.next_card()
                else:
                    c = None
                if not c:
                    break
            if self._card_filter_allows(c):
                card = c
                break

        if card is None:
            # Im Testmodus (kein Wrap) bedeutet "keine nächste Karte": Test beendet.
            try:
                if getattr(self.deck, "allow_wrap", True) is False:
                    seen = int(getattr(self, "total_seen", 0) or 0)
                    correct = int(getattr(self, "total_correct", 0) or 0)
                    wrong = int(getattr(self, "total_wrong", 0) or 0)
                    pct = (correct / seen * 100.0) if seen else 0.0
                    # Note (1–6): linear skaliert, auf halbe Noten gerundet
                    note = (round((1 + 5 * (correct / seen)) * 2) / 2) if seen else 1
                    msg = (
                        f"Anzahl abgefragter Wörter: {seen}\n"
                        f"Anzahl richtig beantworteter Wörter: {correct}\n"
                        f"Anzahl falsch beantworteter Wörter: {wrong}\n"
                        f"Prozent richtig beantworteter Wörter: {pct:.0f} %\n\n"
                        f"Note: {note}"
                    )
                    messagebox.showinfo("Test beendet", msg)
                else:
                    messagebox.showinfo("Keine Karten", "Für die gewählten Filter stehen derzeit keine Karten zur Verfügung.")
            except Exception:
                pass
            return

        self.current_card = card

        self._refresh_prompt_label()
        self.entry1.delete(0, tk.END)
        self.entry2.delete(0, tk.END)
        self.feedback.config(text="")

        # Reset variant-specific overrides for explanation and examples
        self._override_expl = None
        self._override_example_it = None
        self._override_example_de = None
        self._override_grammar = None
        self.expl_label.config(text="")
        # Synonyme verbergen bis zur Auswertung
        try:
            self.synonyms_foreign.config(text=""); self.synonyms_german.config(text="")
        except Exception:
            pass
        # Beispiele leeren
        try:
            self.example_foreign.config(text="")
            self.example_german.config(text="")
            self._revealed = False
            try:
                self.example_foreign.config(text="")
                self.example_german.config(text="")
                self.synonyms_foreign.config(text="")
                self.synonyms_german.config(text="")
            except Exception:
                pass
        except Exception:
            pass
        # Grammatik-Bereich leeren (IPA, Hinweise etc.), damit nichts stehen bleibt
        try:
            for lbl in (self.gram_ipa, self.gram_hint, self.gram_pos, self.gram_aux, self.gram_pp, self.gram_reg, self.gram_freq, self.gram_niveau):
                try:
                    lbl.config(text="")
                except Exception:
                    pass
        except Exception:
            pass

        self._update_stats()
        self._render_example()
        try:
            self._update_total_words_label()
        except Exception:
            pass
        try:
            self._update_test_max_available()
        except Exception:
            pass

        if self.mode_var.get() == "Multiple Choice":
            self._populate_multiple_choice(card)

    def _populate_multiple_choice(self, card: Card):
        all_answers = []
        if self.deck:
            for c in self.deck.cards:
                all_answers.extend(c.answers)
        correct_norm = {normalize_answer(x) for x in card.answers}
        pool = [a for a in set(all_answers) if normalize_answer(a) not in correct_norm]
        random.shuffle(pool)
        options = [random.choice(card.answers)] + pool[:3]
        random.shuffle(options)
        self._mc_solution = card.answers
        for btn, text in zip(self.mc_buttons, options):
            btn.configure(text=text)


    def _mc_pick(self, index: int):
        choice = self.mc_buttons[index].cget("text")

        # Variante B: classify
        status = self._classify_answer_status(choice)
        ok = status in ("correct", "synonym")

        # For MC we still respect the generated solution set as a hard correctness constraint:
        # if it does not match the intended solution, it is wrong (even if it is a synonym in the broader cloud).
        try:
            ok_mc = any(self._answers_equal(choice, ans) for ans in self._mc_solution)
            if ok_mc:
                status = "correct"
                ok = True
            else:
                status = "wrong"
                ok = False
        except Exception:
            pass

        self._finalize_answer(choice, ok, status=status)


    def _synonym_norms_for_current(self) -> set:
        """Returns a normalized set of acceptable *synonyms* for the current card.

        This is used for Variante B (✔️ / ◑ / ❌):
        - ✔️ correct  : user input matches the target answer(s) of the current card
        - ◑ synonym   : user input matches an alternative acceptable synonym (meaning-space), but not the target
        - ❌ wrong    : user input matches neither
        """
        syn_norms: set = set()
        card = getattr(self, "current_card", None)
        if card is None:
            return syn_norms

        # Case 1: Prompt is German (Deutsch → Italienisch):
        # Use the global accept index (all Italian variants for this German lemma).
        try:
            if getattr(card, "prompt_is_german", False) and hasattr(self, "_accept_index"):
                gkey = normalize_answer(getattr(card, "prompt", "") or "")
                syn_norms |= set(self._accept_index.get(gkey, set()) or set())
        except Exception:
            pass

        # Case 2: Prompt is NOT German (Italienisch → Deutsch):
        # If we have explicit German synonyms for the row, treat them as acceptable synonyms.
        try:
            if (not getattr(card, "prompt_is_german", False)) and getattr(card, "german_synonyms", None):
                for s in (card.german_synonyms or []):
                    n = normalize_answer(s)
                    if n:
                        syn_norms.add(n)
        except Exception:
            pass

        # Case 3 (both directions): Meaning-cloud synonyms across rows (Deutsch-Lemma overlap)
        # This is exactly what the UI shows under "Synonyme → Fremdsprache".
        try:
            rid = getattr(card, "row_index", None)
            if rid is not None and hasattr(self, "_italian_synonyms_from_rowindex"):
                for s in (self._italian_synonyms_from_rowindex(rid) or []):
                    n = normalize_answer(s)
                    if n:
                        syn_norms.add(n)
        except Exception:
            pass

        return syn_norms

    def _classify_answer_status(self, user_input: str) -> str:
        """Classifies the user input into: 'correct' | 'synonym' | 'wrong'."""
        card = getattr(self, "current_card", None)
        if card is None:
            return "wrong"
        u = normalize_answer(user_input)

        # Target answers of the current card
        try:
            target_norms = {normalize_answer(a) for a in (getattr(card, "answers", []) or []) if str(a).strip()}
        except Exception:
            target_norms = set()

        if u and u in target_norms:
            return "correct"

        syn_norms = set()
        try:
            syn_norms = self._synonym_norms_for_current()
        except Exception:
            syn_norms = set()

        # If synonyms contain the input (but it is not a target), it's a synonym-hit.
        if u and u in syn_norms:
            return "synonym"

        return "wrong"


    def check_answer(self):
        if not self.current_card:
            return
        if self.mode_var.get() == "Multiple Choice":
            return

        user1 = self.entry1.get()
        user2 = self.entry2.get()

        # Variante B: classify as correct / synonym / wrong
        status = self._classify_answer_status(user1)
        ok = status in ("correct", "synonym")

        # Backward compatibility / legacy: if the prompt is German, also accept any Italian variant from the global index
        # (this will typically be captured by _classify_answer_status already, but we keep it as a safety net)
        if not ok:
            try:
                if getattr(self.current_card, "prompt_is_german", False) and hasattr(self, "_accept_index"):
                    gkey = normalize_answer(self.current_card.prompt)
                    opts = self._accept_index.get(gkey, set()) or set()
                    u1 = normalize_answer(user1)
                    u2 = normalize_answer(user2)
                    if opts and (u1 in opts or (user2.strip() and u2 in opts)):
                        status = "synonym" if u1 not in {normalize_answer(a) for a in (self.current_card.answers or [])} else "correct"
                        ok = True
            except Exception:
                pass

        # If a second field is ever used, treat a hit there also as acceptable.
        if not ok and user2.strip():
            status2 = self._classify_answer_status(user2)
            if status2 in ("correct", "synonym"):
                status = status2
                ok = True
                user1 = user2  # use the matching input for downstream displays

        self._finalize_answer(user1, ok, status=status)

    def _finalize_answer(self, user_input: str, ok: bool, status: str = None):
        self.total_seen += 1
        # Variante B: if status is not provided, derive from ok; otherwise enforce ok from status.
        if status not in ("correct", "synonym", "wrong"):
            status = "correct" if ok else "wrong"
        ok = status in ("correct", "synonym")
        self._last_status = status
        self._last_ok = ok
        # Pro-Wort-Stats aktualisieren
        try:
            key = self.current_card.prompt if self.current_card else None
            if key is not None:
                seen, corr = self.card_stats.get(key, (0, 0))
                seen += 1
                corr += 1 if ok else 0
                self.card_stats[key] = (seen, corr)
        except Exception:
            pass

        # Für die Session-Prozentanzeige: Zeilenindex merken (ohne Dubletten)
        try:
            rid = getattr(self.current_card, "row_index", None)
            if rid is not None:
                self.session_seen_rows.add(rid)
        except Exception:
            pass

        if ok:
            self.total_correct += 1
            self.feedback.config(text="Richtig!", foreground="#0a7d16")
            # Bridge: Varianten speichern (für Synonyme unten)
            try:
                if getattr(self.current_card, "prompt_is_german", False) and hasattr(self, "_accept_display"):
                    gkey = normalize_answer(self.current_card.prompt)
                    self._last_correct_it = sorted(self._accept_display.get(gkey, set()))
                else:
                    self._last_correct_it = list(getattr(self.current_card, "answers", []) or [])
            except Exception:
                self._last_correct_it = []

            # Variantenbezogene Beispiele/Erläuterung mit Fallback
            try:
                if getattr(self.current_card, 'prompt_is_german', False) and hasattr(self, "_italian_meta"):
                    entered_key = normalize_answer(user_input)
                    expl_out = ex_it_out = ex_de_out = ""
                    meta = self._italian_meta.get(entered_key)
                    if meta:
                        expl_out, ex_it_out, ex_de_out = meta
                    try:
                        gkey = normalize_answer(self.current_card.prompt)
                        variants = sorted(self._accept_display.get(gkey, set())) if hasattr(self, "_accept_display") else []
                    except Exception:
                        variants = []
                    for v in variants:
                        if expl_out and ex_it_out and ex_de_out:
                            break
                        m = self._italian_meta.get(normalize_answer(v))
                        if not m:
                            continue
                        e2, it2, de2 = m
                        if not expl_out and e2:
                            expl_out = e2
                        if not ex_it_out and it2:
                            ex_it_out = it2
                        if not ex_de_out and de2:
                            ex_de_out = de2
                    if expl_out:
                        try:
                            self.expl_label.config(text=f"Erläuterung: {expl_out}")
                        except Exception:
                            pass
                    try:
                        self.example_foreign.config(text=ex_it_out if ex_it_out else "")
                        self.example_german.config(text=ex_de_out if ex_de_out else "")
                    except Exception:
                        pass
            except Exception:
                pass
            # Store variant-specific overrides for final rendering
            try:
                if 'expl_out' in locals() or 'ex_it_out' in locals() or 'ex_de_out' in locals():
                    if expl_out:
                        self._override_expl = expl_out
                    if 'ex_it_out' in locals() and ex_it_out:
                        self._override_example_it = ex_it_out
                    if 'ex_de_out' in locals() and ex_de_out:
                        self._override_example_de = ex_de_out
            except Exception:
                pass

            # Variantenbezogene Beispiele/Erläuterung konkret für die eingegebene italienische Form
            try:
                if getattr(self.current_card, 'prompt_is_german', False) and hasattr(self, "_italian_meta"):
                    entered_key = normalize_answer(user_input)
                    meta = self._italian_meta.get(entered_key)
                    if meta:
                        expl, ex_it, ex_de = meta
                        if expl:
                            try:
                                self.expl_label.config(text=f"Erläuterung: {expl}")
                            except Exception:
                                pass
                        try:
                            if ex_it:
                                self.example_foreign.config(text=ex_it)
                            if ex_de:
                                self.example_german.config(text=ex_de)
                        except Exception:
                            pass
            except Exception:
                pass
            # Store exact-variant overrides
            try:
                if 'meta' in locals() and meta:
                    expl, ex_it, ex_de = meta
                    if expl:
                        self._override_expl = expl
                    if ex_it:
                        self._override_example_it = ex_it
                    if ex_de:
                        self._override_example_de = ex_de
            except Exception:
                pass

            # Variantenbezogene Grammatik-Overrides (IPA, Hinweise, Wortart, Hilfsverb, Partizip, Stil/Register, Niveau, Häufigkeit)
            try:
                self._override_grammar = None
                if getattr(self.current_card, 'prompt_is_german', False) and hasattr(self, "_italian_gram"):
                    entered_key = normalize_answer(user_input)
                    g = self._italian_gram.get(entered_key)

                    # Fallback: wenn fuer exakt die Eingabe keine Grammatikdaten hinterlegt sind,
                    # die erste bekannte Variante mit Daten verwenden
                    if not g:
                        try:
                            gkey = normalize_answer(self.current_card.prompt)
                            variants = sorted(self._accept_display.get(gkey, set())) if hasattr(self, "_accept_display") else []
                        except Exception:
                            variants = []
                        for v in variants:
                            g = self._italian_gram.get(normalize_answer(v))
                            if g:
                                break

                    if g:
                        self._override_grammar = g
            except Exception:
                pass

            # If prompt is German, show other accepted Italian synonyms (excluding the one just entered)
            try:
                if getattr(self.current_card, 'prompt_is_german', False) and hasattr(self, '_accept_display'):
                    gkey = normalize_answer(self.current_card.prompt)
                    opts_disp = sorted(self._accept_display.get(gkey, set()))
                    # Bridge: vollständige Liste merken
                    try:
                        self._last_correct_it = list(opts_disp)
                    except Exception:
                        self._last_correct_it = list(opts_disp)
                    # Exclude the entered form (normalized compare)
                    entered_n = normalize_answer(user_input)
                    filtered = []
                    seen = set()
                    for s in opts_disp:
                        n = normalize_answer(s)
                        if n == entered_n or n in seen:
                            continue
                        seen.add(n)
                        filtered.append(s)
                    if filtered:
                        self.feedback.config(text="Richtig. Andere mögliche Antworten: " + ", ".join(filtered), foreground="#0a7d16")
            except Exception:
                pass

            # Italienische Synonyme aus Accept-Map oder Bedeutungswolke
            try:
                def _norm_txt(t):
                    import re
                    t = str(t).lower()
                    t = re.sub(r"[\.,;:!?()\"'`´]", "", t)
                    t = re.sub(r"\s+", " ", t).strip()
                    return t
                ital_opts = []
                if hasattr(self, "_accept_display"):
                    if getattr(self.current_card, 'prompt_is_german', False):
                        gkey = normalize_answer(self.current_card.prompt)
                    else:
                        ans = (self.current_card.answers[0] if getattr(self.current_card, 'answers', []) else "")
                        gkey = normalize_answer(ans)
                    ital_opts = sorted(self._accept_display.get(gkey, set()))
                entered_n = _norm_txt(user_input)
                filtered = [w for w in ital_opts if _norm_txt(w) != entered_n]
                if filtered:
                    self.synonyms_foreign.config(text="Fremdsprache:\n   • " + "\n   • ".join(filtered))
                else:
                    self.synonyms_foreign.config(text=""); self.synonyms_german.config(text="")
            except Exception:
                pass

            # Deutsche Synonyme anzeigen (falls vorhanden) – gefiltert gegen die eingegebene Antwort
            try:
                syns = getattr(self.current_card, 'german_synonyms', None)
                if syns:
                    def _norm_de(s):
                        import re
                        s = str(s).lower()
                        s = re.sub(r"[\.,;:!?()\"'`´]", "", s)
                        s = re.sub(r"\s+", " ", s).strip()
                        return s
                    user_n = _norm_de(user_input)
                    filtered_de = []
                    seen_de = set()
                    for s in syns:
                        n = _norm_de(s)
                        if n == user_n or n in seen_de:
                            continue
                        seen_de.add(n)
                        filtered_de.append(s)
                    if filtered_de:
                        self.synonyms_german.config(text="Deutsch:\n   • " + "\n   • ".join(filtered_de))
                    else:
                        self.synonyms_german.config(text="")
                else:
                    self.synonyms_german.config(text="")
            except Exception:
                pass

        else:
            self.total_wrong += 1
            # Enhanced failure feedback: if German prompt, show ALL accepted italian variants
            try:
                if getattr(self.current_card, 'prompt_is_german', False) and hasattr(self, '_accept_display'):
                    gkey = normalize_answer(self.current_card.prompt)
                    opts_disp = sorted(self._accept_display.get(gkey, set()))
                    # Bridge: für Synonyme unten merken
                    try:
                        self._last_correct_it = list(opts_disp)
                    except Exception:
                        self._last_correct_it = list(opts_disp)
                    if opts_disp:
                        self.feedback.config(text="Nicht ganz. Richtig wären: " + ", ".join(opts_disp), foreground="#b00020")
                    else:
                        self.feedback.config(text=f"Nicht ganz. Richtig wäre...: {', '.join(self.current_card.answers)}", foreground="#b00020")
                else:
                    self.feedback.config(text=f"Nicht ganz. Richtig wäre...: {', '.join(self.current_card.answers)}", foreground="#b00020")
            except Exception:
                self.feedback.config(text=f"Nicht ganz. Richtig wäre...: {', '.join(self.current_card.answers)}", foreground="#b00020")

            # Italienische Synonyme aus Accept-Map ableiten
            try:
                def _norm_txt(t):
                    import re
                    t = str(t).lower()
                    t = re.sub(r"[\.,;:!?()\"'`´]", "", t)
                    t = re.sub(r"\s+", " ", t).strip()
                    return t
                ital_opts = []
                if hasattr(self, "_accept_display"):
                    if getattr(self.current_card, 'prompt_is_german', False):
                        gkey = normalize_answer(self.current_card.prompt)
                    else:
                        ans = (self.current_card.answers[0] if getattr(self.current_card, 'answers', []) else "")
                        gkey = normalize_answer(ans)
                    ital_opts = sorted(self._accept_display.get(gkey, set()))
                entered_n = _norm_txt(user_input)
                filtered = [w for w in ital_opts if _norm_txt(w) != entered_n]
                if filtered:
                    self.synonyms_foreign.config(text="Fremdsprache:\n   • " + "\n   • ".join(filtered))
                else:
                    self.synonyms_foreign.config(text=""); self.synonyms_german.config(text="")
            except Exception:
                pass

            if not (str(self.mode_var.get()) or "").startswith("Test"):
                if self.deck and self.current_card:
                    self.deck.reinsert_soon(self.current_card, offset=2)

        if self.current_card and self.current_card.explanation:
            self.expl_label.config(text=f"Erläuterung: {self.current_card.explanation}")

        # --- Italienische Synonyme auf Basis aller Deutsch-Spalten (Deutsch 1–4) ---
        try:
            if getattr(self, "df", None) is not None and getattr(self, "current_card", None) is not None:
                idx_row = getattr(self.current_card, "row_index", None)
                it_syns = self._italian_synonyms_from_rowindex(idx_row)
                if it_syns:
                    try:
                        self.synonyms_foreign.config(text="Fremdsprache:\n   • " + "\n   • ".join(it_syns))
                    except Exception:
                        pass
        except Exception:
            pass

        # --- Final zentrierte Feedback-Formatierung ---
        try:
            status = getattr(self, "_last_status", "correct" if getattr(self, "_last_ok", False) else "wrong")

            if status == "correct":
                # Correct: green 'Richtig.' centered; explanation in black below (if any)
                self.feedback.config(text="● richtig", foreground="#6b7a00", font=("Segoe UI", 18, "bold"))
                if getattr(self, "_override_expl", None):
                    self.expl_label.config(text=f"Erläuterung: {self._override_expl}", foreground="#000000")
                elif self.current_card and self.current_card.explanation:
                    self.expl_label.config(text=f"Erläuterung: {self.current_card.explanation}", foreground="#000000")
                else:
                    self.expl_label.config(text="", foreground="#000000")

            elif status == "synonym":
                # Synonym: amber '◑' centered; expected target answer(s) below
                expected = ", ".join(getattr(self.current_card, "answers", []) or [])
                self.feedback.config(text="◑ korrektes Synonym", foreground="#8a6d00", font=("Segoe UI", 18, "bold"))
                if expected:
                    self.expl_label.config(text=f"Erwartet war: {expected}", foreground="#8a6d00")
                else:
                    self.expl_label.config(text="", foreground="#8a6d00")

            else:
                # Wrong: red 'Falsch.' centered; correct answer(s) in red below
                self.feedback.config(text="○ falsch", foreground="#8b2f2f", font=("Segoe UI", 18, "bold"))
                try:
                    if getattr(self.current_card, "prompt_is_german", False) and hasattr(self, "_accept_display"):
                        gkey = normalize_answer(self.current_card.prompt)
                        opts_disp = sorted(self._accept_display.get(gkey, set()))
                        if opts_disp:
                            self.expl_label.config(text="Richtig wäre: " + ", ".join(opts_disp), foreground="#8b2f2f")
                        else:
                            self.expl_label.config(text="Richtig wäre: " + ", ".join(self.current_card.answers), foreground="#8b2f2f")
                    else:
                        self.expl_label.config(text="Richtig wäre: " + ", ".join(self.current_card.answers), foreground="#8b2f2f")
                except Exception:
                    self.expl_label.config(text="Richtig wäre: " + ", ".join(self.current_card.answers), foreground="#b00020")
        except Exception:
            pass


        self._update_stats()
        self._render_example()
        self.ready_for_next = True
        try:
            self._render_example()
            self._render_grammar()
            self._render_synonyms_after_answer(user_input)
            self._fill_synonyms_after_reveal()
        except Exception:
            pass
        # Nach Auswertung anzeigen
        try:
            self._revealed = True
            self._render_example()
            self._render_grammar()
            self._render_synonyms_after_answer(user_input)
        except Exception:
            pass

    def _render_synonyms_after_answer(self, user_input: str = ""):
        """
        Zentrale Routine für die Anzeige der Synonyme nach der Auswertung.
        - Italienische Synonyme: Bedeutungswolke (Cross-Lemma) über _italian_synonyms_from_rowindex
        - Deutsche Synonyme: self.current_card.german_synonyms
        Darstellung:
        - Fremdsprache: ...   (nur wenn italienische Synonyme vorhanden)
        - Deutsch: ...        (nur wenn deutsche Synonyme vorhanden)
        Wenn keine Synonyme existieren, bleiben die Felder leer.
        """
        # Labels zunächst leeren, damit wir von einem definierten Zustand ausgehen
        try:
            self.synonyms_foreign.config(text="")
            self.synonyms_german.config(text="")
        except Exception:
            # Falls die Labels im aktuellen Kontext noch nicht existieren
            return

        card = getattr(self, "current_card", None)
        df = getattr(self, "df", None)
        if card is None or df is None:
            return

        # ---------- Italienische Synonyme (Fremdsprache) ----------
        it_syns = []
        row_index = getattr(card, "row_index", None)
        if row_index is not None:
            try:
                syns = self._italian_synonyms_from_rowindex(row_index) or []
                it_syns = [str(s).strip() for s in syns if str(s).strip()]
            except Exception:
                it_syns = []

        # Duplikate entfernen und sortieren
        if it_syns:
            seen = set()
            cleaned = []
            for s in it_syns:
                if s not in seen:
                    seen.add(s)
                    cleaned.append(s)
            it_syns = sorted(cleaned, key=lambda x: x.lower())

        if it_syns:
            try:
                self.synonyms_foreign.config(text="Fremdsprache:\n   • " + "\n   • ".join(it_syns))
            except Exception:
                pass

        # ---------- Deutsche Synonyme ----------
        syn_de = getattr(card, "german_synonyms", None) or []
        syn_de = [str(s).strip() for s in syn_de if str(s).strip()]

        import re as _re

        def _norm(text: str) -> str:
            text = _re.sub(r"\s+", " ", text.strip().lower())
            text = _re.sub(r"[\.,;:!?()\[\]]", "", text)
            return text

        if user_input:
            ui_norm = _norm(str(user_input))
            syn_de = [s for s in syn_de if _norm(s) != ui_norm]

        # Duplikate entfernen und sortieren
        if syn_de:
            seen_de = set()
            cleaned_de = []
            for s in syn_de:
                if s not in seen_de:
                    seen_de.add(s)
                    cleaned_de.append(s)
            syn_de = sorted(cleaned_de, key=lambda x: x.lower())

        if syn_de:
            try:
                self.synonyms_german.config(text="Deutsch:\n   • " + "\n   • ".join(syn_de))
            except Exception:
                pass

    def _fill_synonyms_after_reveal(self):
        """
        Früher wurden hier bei Deutsch→Italienisch alle Varianten aus dem
        _accept_display-Mapping angezeigt. Diese Logik ist abgeschaltet.
        Die Synonymanzeige erfolgt jetzt ausschliesslich über
        _render_synonyms_after_answer() und die Bedeutungswolke (Cross-Lemma).
        """
        return

    def _collect_de_lemmas_for_row(self, row):
        """
        Hilfsfunktion: sammelt alle deutschen Lemmata einer Zeile aus allen
        Spalten, die mit 'Deutsch' beginnen. Mehrfachangaben werden an
        | / ; , gesplittet und normalisiert.
        """
        lemmas = set()
        try:
            de_cols = [c for c in self.df.columns if str(c).strip().lower().startswith("deutsch")]
        except Exception:
            return lemmas
        for col in de_cols:
            try:
                if col not in row.index:
                    continue
                val = row[col]
            except Exception:
                continue
            # NaN oder leer überspringen
            try:
                import pandas as pd
                if pd.isna(val):
                    continue
            except Exception:
                if val is None:
                    continue
            txt = str(val).strip()
            if not txt or txt.lower() == "nan":
                continue
            for ch in "|;/,":
                txt = txt.replace(ch, "|")
            parts = [p.strip() for p in txt.split("|")]
            for p in parts:
                if p:
                    lemmas.add(normalize_answer(p))
        return lemmas

    def _italian_synonyms_from_rowindex(self, idx):
        """
        Liefert italienische Synonyme für die Zeile idx, indem alle
        Zeilen gesucht werden, die mindestens ein deutsches Lemma mit
        dieser Zeile teilen (Deutsch 1–4 als Bedeutungswolke).
        Die italienischen Formen der aktuellen Zeile selbst werden
        herausgefiltert.
        """
        syns = []
        try:
            if self.df is None:
                return syns
            if idx is None or idx < 0 or idx >= len(self.df.index):
                return syns
            df = self.df
            row = df.iloc[idx]

            # Wortart der aktuellen Zeile (für POS-Filter bei Synonymen)
            pos_col = None
            for c in df.columns:
                if "wortart" in str(c).strip().lower():
                    pos_col = c
                    break
            current_pos = self._pos_code_from_cell(row.get(pos_col, "")) if pos_col else None
            # Italienische Formen der aktuellen Zeile sammeln
            it_cols = [c for c in df.columns if str(c).strip().lower().startswith("italien")]
            current_it_raw = []
            current_it_norm = set()
            for col in it_cols:
                try:
                    if col not in row.index:
                        continue
                    val = row[col]
                except Exception:
                    continue
                try:
                    import pandas as pd
                    if pd.isna(val):
                        continue
                except Exception:
                    if val is None:
                        continue
                txt = str(val).strip()
                if not txt or txt.lower() == "nan":
                    continue
                for ch in "|;/,":
                    txt = txt.replace(ch, "|")
                parts = [p.strip() for p in txt.split("|")]
                for p in parts:
                    if p:
                        current_it_raw.append(p)
                        current_it_norm.add(normalize_answer(p))
            # Deutsches Bedeutungsset der aktuellen Zeile
            current_de = self._collect_de_lemmas_for_row(row)
            if not current_de:
                return syns
            syn_set = []
            for j, other in df.iterrows():
                if j == idx:
                    continue

                # Synonyme nur innerhalb derselben Wortart wie die aktuelle Zeile
                if current_pos and pos_col:
                    other_pos = self._pos_code_from_cell(other.get(pos_col, ""))
                    if other_pos and other_pos != current_pos:
                        continue
                other_de = self._collect_de_lemmas_for_row(other)
                if not other_de or not (current_de & other_de):
                    continue
                for col in it_cols:
                    try:
                        if col not in other.index:
                            continue
                        val = other[col]
                    except Exception:
                        continue
                    try:
                        import pandas as pd
                        if pd.isna(val):
                            continue
                    except Exception:
                        if val is None:
                            continue
                    txt = str(val).strip()
                    if not txt or txt.lower() == "nan":
                        continue
                    for ch in "|;/,":
                        txt = txt.replace(ch, "|")
                    parts = [p.strip() for p in txt.split("|")]
                    for p in parts:
                        if not p:
                            continue
                        n = normalize_answer(p)
                        if n and n not in current_it_norm:
                            syn_set.append(p)
            # Duplikate entfernen, Reihenfolge beibehalten
            seen = set()
            result = []
            for s in syn_set:
                if s not in seen:
                    seen.add(s)
                    result.append(s)
            return result
        except Exception:
            return []

    def _answers_equal(self, a: str, b: str) -> bool:
        return normalize_answer(a) == normalize_answer(b)

    # ---- Statistik ----
    def _success_pct(self) -> float:
        return (self.total_correct / self.total_seen) * 100 if self.total_seen else 0.0

    # ---- Kenntnis-Filter ----
    def filter_by_knowledge(self):
        dlg = tk.Toplevel(self)
        dlg.title("Nach Kenntnis filtern")
        dlg.transient(self)
        ttk.Label(dlg, text="Trefferquote zum Ausschließen (in %):").pack(padx=12, pady=(12, 2))
        thresh_var = tk.IntVar(value=80)
        ttk.Entry(dlg, textvariable=thresh_var, width=6).pack(padx=12, pady=(0, 8))

        ttk.Label(dlg, text="Mindestanzahl Versuche (empfohlen: 3):").pack(padx=12, pady=(4, 2))
        min_var = tk.StringVar(value="3")
        ttk.Entry(dlg, textvariable=min_var, width=6).pack(padx=12, pady=(0, 12))

        info_var = tk.StringVar(value="Karten werden nur ausgeschlossen, wenn sie mindestens N-mal gesehen wurden.")
        ttk.Label(dlg, textvariable=info_var, foreground="#555").pack(padx=12, pady=(0, 8))

        btns = ttk.Frame(dlg)
        btns.pack(pady=(0, 12))
        def do_apply():
            try:
                thr = int(thresh_var.get())
            except Exception:
                thr = 80
            thr = max(0, min(100, thr))
            try:
                mn = int(min_var.get().strip()) if min_var.get().strip() != "" else 3
            except Exception:
                mn = 3
            if mn < 2:
                mn = 2

            cards_source = self.deck.cards[:] if self.deck else []
            kept, removed = [], 0
            for c in cards_source:
                seen, corr = self.card_stats.get(c.prompt, (0, 0))
                if seen < mn:
                    kept.append(c)
                    continue
                rate = (corr / seen) * 100.0 if seen else 0.0
                if rate >= thr:
                    removed += 1
                else:
                    kept.append(c)

            if kept and len(kept) != len(cards_source):
                self.deck = Deck(kept)
                self.ready_for_next = False
                self.current_card = None
                self.next_card()
            info_var.set(f"Gefiltert: {removed} ausgeschlossen, {len(kept)} übrig.")

        btn_apply = ttk.Button(btns, text="Anwenden", command=do_apply)
        btn_apply.pack(side=tk.LEFT, padx=6)
        attach_tooltip(btn_apply, "Filter anwenden")
        btn_close = ttk.Button(btns, text="Schließen", command=dlg.destroy)
        btn_close.pack(side=tk.LEFT, padx=6)
        attach_tooltip(btn_close, "Filter schließen")

    def _render_grammar(self):
        if not getattr(self, "_revealed", False):
            return
        try:
            # Alle Grammatiklabels zuerst leeren
            for lbl in (self.gram_ipa, self.gram_hint, self.gram_pos, self.gram_aux, self.gram_pp, self.gram_reg, self.gram_niveau):
                try:
                    lbl.config(text="")
                except Exception:
                    pass
            if not getattr(self, "current_card", None):
                return
            idx = getattr(self.current_card, "row_index", None)
            if idx is None or self.df is None:
                return

            # Variantenspezifische Overrides bevorzugen (nach korrekter Synonym-Antwort)
            try:
                if getattr(self, "_override_grammar", None):
                    g = self._override_grammar

                    # Häufigkeit labeln wie bisher
                    freq_label = ""
                    freq_raw = (g.get("freq_raw") or "").strip() if isinstance(g, dict) else ""
                    if freq_raw:
                        try:
                            s = freq_raw.replace(",", ".")
                            freq_num = int(float(s))
                            freq_label = FREQ_LABELS.get(freq_num, "")
                        except Exception:
                            freq_label = ""
                    try:
                        self.gram_freq.config(text=(f"Häufigkeit: {freq_label}" if freq_label else ""))
                    except Exception:
                        pass

                    try:
                        if isinstance(g, dict) and g.get("ipa"):
                            self.gram_ipa.config(text=g["ipa"])
                    except Exception:
                        pass
                    try:
                        if isinstance(g, dict) and g.get("hint"):
                            self.gram_hint.config(text=g["hint"])
                    except Exception:
                        pass
                    try:
                        if isinstance(g, dict) and g.get("pos"):
                            self.gram_pos.config(text=g["pos"])
                    except Exception:
                        pass
                    try:
                        if isinstance(g, dict) and g.get("aux"):
                            self.gram_aux.config(text=f"Hilfsverb: {g['aux']}")
                    except Exception:
                        pass
                    try:
                        if isinstance(g, dict) and g.get("pp"):
                            self.gram_pp.config(text=f"Partizip Perfekt: {g['pp']}")
                    except Exception:
                        pass
                    try:
                        if isinstance(g, dict) and g.get("reg"):
                            self.gram_reg.config(text=f"Stil/Register: {g['reg']}")
                    except Exception:
                        pass
                    try:
                        if isinstance(g, dict) and g.get("niveau"):
                            self.gram_niveau.config(text=f"Niveau: {g['niveau']}")
                    except Exception:
                        pass
                    return
            except Exception:
                pass

            row = self.df.iloc[idx]
            cols_lower = {str(c).lower(): c for c in self.df.columns}
            def get(name_list):
                # name_list: mögliche Spaltennamen (Strings)
                for nm in name_list:
                    key = str(nm).strip().lower()
                    c = cols_lower.get(key)
                    if c is None:
                        # Fallback: Teiltreffer (z.B. 'Häufigkeit ' mit Leerzeichen oder Varianten)
                        for k, colname in cols_lower.items():
                            if key and key in k:
                                c = colname
                                break
                    if c is not None:
                        val = row.get(c, "")
                        s = "" if str(val).strip().lower() in ("", "nan") else str(val).strip()
                        if s:
                            return s
                return ""
            ipa = get(["IPA","ipa"])
            hint = get(["Grammatikalische Hinweise","Grammatik","grammatikalische hinweise"])
            pos = get(["Wortart"])
            aux = get(["Hilfsverb","hilfsverb"])
            pp = get(["Partizip Perfekt","partizip perfekt","p.p.","pp","participio passato"])
            reg = get(["Stil|Register","Stil/Register","Stil","Register","stil|register","stil/register"])
            niveau = get(["Niveau","niveau"])
            freq_raw = get(["Häufigkeit","haeufigkeit","Haeufigkeit"])  # Spalte O
            freq_label = ""
            if freq_raw not in (None, ""):
                try:
                    s = str(freq_raw).strip()
                    # Excel/Pandas liefert oft 1.0; akzeptiere auch Komma
                    s = s.replace(",", ".")
                    freq_num = int(float(s))
                    freq_label = FREQ_LABELS.get(freq_num, "")
                except Exception:
                    freq_label = ""
            # immer setzen, damit nichts „hängen bleibt“
            self.gram_freq.config(text=(f"Häufigkeit: {freq_label}" if freq_label else ""))

            if ipa:
                self.gram_ipa.config(text=ipa)
            if hint:
                self.gram_hint.config(text=hint)
            if pos:
                self.gram_pos.config(text=pos)
            if aux:
                self.gram_aux.config(text=f"Hilfsverb: {aux}")
            if pp:
                self.gram_pp.config(text=f"Partizip Perfekt: {pp}")
            if reg:
                self.gram_reg.config(text=f"Stil/Register: {reg}")
            if niveau:
                self.gram_niveau.config(text=f"Niveau: {niveau}")
        except Exception:
            pass

    def _render_example(self):
        """Vor der Antwort: Prompt-Sprache; nach der Antwort: beide Sprachen (Prompt + Antwortsprache)."""
        try:
            # zurücksetzen
            try:
                self.example_foreign.config(text="")
                self.example_german.config(text="")
            except Exception:
                pass
            if not self.current_card:
                return

            ex_it = getattr(self.current_card, "example", "") or ""
            ex_de = getattr(self.current_card, "german_example", "") or ""

            # Variantenspezifische Overrides erst nach Auswertung
            try:
                if getattr(self, "_revealed", False):
                    if getattr(self, "_override_example_it", None):
                        ex_it = self._override_example_it or ex_it
                    if getattr(self, "_override_example_de", None):
                        ex_de = self._override_example_de or ex_de
            except Exception:
                pass

            is_de = bool(getattr(self.current_card, "prompt_is_german", False))
            if not getattr(self, "_revealed", False):
                # Vor dem Prüfen: nur Prompt-Sprache
                if is_de:
                    self.example_german.config(text=str(ex_de) if str(ex_de).strip() else "")
                    self.example_foreign.config(text="")
                else:
                    self.example_foreign.config(text=str(ex_it) if str(ex_it).strip() else "")
                    self.example_german.config(text="")
            else:
                # Nach dem Prüfen: beide Sprachen anzeigen
                self.example_german.config(text=str(ex_de) if str(ex_de).strip() else "")
                self.example_foreign.config(text=str(ex_it) if str(ex_it).strip() else "")
        except Exception:
            pass

    def _on_toggle_example(self):
        """Checkbox-Handler: sofort zeigen/ausblenden für die aktuelle Karte."""
        try:
            if self.__deleted_var.get():
                self._render_example()
                self._render_grammar()
                self._render_synonyms_after_answer(user_input)
            else:
                self.example_foreign.config(text="")
                self.example_german.config(text="")
        except Exception:
            pass

    def _update_lang_labels(self):
        """Passt die Beschriftung der Sprachauswahl an die aktuelle Abfragerichtung an."""
        try:
            if getattr(self, 'reverse_var', None) is not None and self.reverse_var.get():
                # Umgekehrte Richtung: was vorher ausgegeben wurde, wird jetzt abgefragt – Labels tauschen
                try:
                    self.lbl_prompt_lang.config(text="abgefragte Sprache:")
                except Exception:
                    pass
                try:
                    self.lbl_answer_lang.config(text="ausgegebene Sprache:")
                except Exception:
                    pass
            else:
                try:
                    self.lbl_prompt_lang.config(text="ausgegebene Sprache:")
                except Exception:
                    pass
                try:
                    self.lbl_answer_lang.config(text="abgefragte Sprache:")
                except Exception:
                    pass
        except Exception:
            pass

    def toggle_reverse(self):
        """Abfragerichtung umkehren (↔)."""
        try:
            # Richtung umschalten
            self.reverse_var.set(not self.reverse_var.get())

            # Button-Beschriftung bleibt fix (nur Pfeil)
            try:
                self.btn_flip.config(text="↔")
            except Exception:
                pass

            # Labels der Sprachauswahl an neue Richtung anpassen
            try:
                self._update_lang_labels()
            except Exception:
                pass

            # Deck in neuer Richtung neu aufbauen
            if getattr(self, "df", None) is not None:
                self.init_deck()
        except Exception:
            pass



    def _update_stats(self):
        self.stats_var.set(
            f"{self.total_seen} gesehen · {self.total_correct} richtig · {self.total_wrong} falsch · {self._success_pct():.0f}% · IT gesamt: {self.total_italian_words}"
        )

    def _on_return(self, event):
        if self.ready_for_next:
            self.next_card()
        else:
            self.check_answer()
        return "break"

    def shuffle_now(self):
        if not self.deck:
            return
        self.deck.shuffle()
        self.ready_for_next = False
        self.next_card()


# ===== Erweiterungen: PatchedApp =====
from typing import List, Optional
import os, datetime
import tkinter as tk
from tkinter import ttk, messagebox

class PatchedApp(FlashcardApp):
    def __init__(self):
        super().__init__()
        if not hasattr(self, "source_dir"):
            self.source_dir: Optional[str] = None
        self._orig_title_backup: Optional[str] = None
        # Add-ons
        self.auto_pot_var = tk.BooleanVar(value=True)
        self.unknown_count_var = tk.StringVar(value="Parole sconosciute: 0")

    # ---- parole sconosciute ----
    def _unknowns_path(self) -> str:
        base_dir = getattr(self, "source_dir", None) or os.getcwd()
        return os.path.join(base_dir, "Excel-Files als Quellen", "Parole Sconosciute.xlsx")

    def _decorate_unknowns_df(self, df):
        """Bringt die Datei 'Parole Conosciute.xlsx' in das gleiche Spaltenformat
        wie die normalen Wörterlisten, damit sie ohne Anpassungen geladen werden kann."""
        try:
            # Grunddaten aus den internen Spalten übernehmen, falls vorhanden
            if "prompt" in df.columns and "Italienisch" not in df.columns:
                df["Italienisch"] = df["prompt"]
            if "answers" in df.columns and "Deutsch 1" not in df.columns:
                df["Deutsch 1"] = df["answers"]
            if "example" in df.columns and "Beispielsatz in der Fremdsprache" not in df.columns:
                df["Beispielsatz in der Fremdsprache"] = df["example"]
            if "example_de" in df.columns and "Beispielsatz Deutsch" not in df.columns:
                df["Beispielsatz Deutsch"] = df["example_de"]

            # Sicherstellen, dass alle gewünschten Header existieren
            header_order = [
                "Italienisch",
                "Deutsch 1",
                "Deutsch 2",
                "Deutsch 3",
                "Deutsch 4",
                "IPA",
                "Wortart",
                "Grammatikalische Hinweise",
                "Hilfsverb",
                "Partizip Perfekt",
                "Stil|Register",
                "Beispielsatz in der Fremdsprache",
                "Beispielsatz Deutsch",
            ]
            for col in header_order:
                if col not in df.columns:
                    df[col] = ""
        except Exception:
            # Falls irgendetwas schiefgeht, lieber still weitermachen,
            # damit das Speichern der unbekannten Wörter nicht blockiert wird.
            pass

    def _update_unknown_count(self):
        try:
            import pandas as pd
            path = self._unknowns_path()
            if not os.path.exists(path):
                self.unknown_count_var.set("Parole sconosciute: 0")
                return
            df = pd.read_excel(path)
            self.unknown_count_var.set(f"Parole sconosciute: {len(df.index)}")
        except Exception:
            self.unknown_count_var.set("Parole sconosciute: ?")

    def add_current_to_unknowns(self, silent: bool = False):
        if not getattr(self, 'current_card', None):
            try:
                messagebox.showinfo('Hinweis', 'Kein aktives Wort.')
            except Exception:
                pass
            return
        try:
            import pandas as pd
            import os
            path = self._unknowns_path()
            # Ordner sicherstellen
            unk_dir = os.path.dirname(path)
            if unk_dir and not os.path.exists(unk_dir):
                os.makedirs(unk_dir, exist_ok=True)

            # Bestehende Datei laden oder neue mit Ziel-Headern anlegen
            try:
                df = pd.read_excel(path)
            except Exception:
                df = pd.DataFrame(columns=['Italienisch', 'Deutsch 1', 'Deutsch 2', 'Deutsch 3', 'Deutsch 4', 'IPA', 'Wortart', 'Grammatikalische Hinweise', 'Hilfsverb', 'Partizip Perfekt', 'Stil|Register', 'Beispielsatz in der Fremdsprache', 'Beispielsatz Deutsch'])

            card = self.current_card
            row_data = {col: '' for col in df.columns}

            # Wenn möglich, die Originalzeile aus self.df übernehmen
            src_row = None
            try:
                idx = getattr(card, 'row_index', None)
                if idx is not None and self.df is not None and 0 <= idx < len(self.df):
                    src_row = self.df.iloc[int(idx)]
            except Exception:
                src_row = None

            if src_row is not None:
                for col in row_data.keys():
                    if col in src_row.index and pd.notna(src_row[col]):
                        row_data[col] = src_row[col]
            else:
                # Fallback: Minimale Infos aus der Karte übernehmen
                row_data['Italienisch'] = getattr(card, 'prompt', '') or ''
                answers = getattr(card, 'answers', None) or []
                if answers:
                    row_data['Deutsch 1'] = '; '.join(str(a) for a in answers)
                row_data['Beispielsatz in der Fremdsprache'] = getattr(card, 'example', '') or ''
                row_data['Beispielsatz Deutsch'] = getattr(card, 'german_example', '') or ''

            # An bestehende Tabelle anhängen
            df = pd.concat([df, pd.DataFrame([row_data])], ignore_index=True)
            # Optionale Dubletten-Bereinigung
            try:
                if 'Italienisch' in df.columns and 'Deutsch 1' in df.columns:
                    df.drop_duplicates(subset=['Italienisch', 'Deutsch 1'], inplace=True)
            except Exception:
                pass

            df.to_excel(path, index=False)
            try:
                self._update_unknown_count()
            except Exception:
                pass
            if not silent:
                try:
                    self.feedback.config(text=f"→ aggiunto a 'parole sconosciute': {card.prompt}", foreground='#444')
                except Exception:
                    pass
        except Exception as e:
            try:
                messagebox.showerror('Errore', f"Non è stato possibile salvare in 'parole sconosciute'.\n\n{e}")
            except Exception:
                pass

    def export_unknowns(self):
        try:
            import pandas as pd
            path = self._unknowns_path()
            if not os.path.exists(path):
                messagebox.showinfo("Info", "Nessun file 'parole sconosciute' trovato.")
                return
            df = pd.read_excel(path)
            base_dir = getattr(self, "source_dir", None) or os.getcwd()
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            out_csv = os.path.join(base_dir, f"parole sconosciute (export {ts}).csv")
            df.to_csv(out_csv, index=False, encoding="utf-8-sig")
            messagebox.showinfo("Esportato", f"Esportazione completata:\n{out_csv}")
        except Exception as e:
            messagebox.showerror("Errore", f"Esportazione fallita.\n\n{e}")

    def reset_unknowns(self):
        try:
            path = self._unknowns_path()
            if not os.path.exists(path):
                messagebox.showinfo("Info", "Nessun file 'parole sconosciute' trovato.")
                return
            if not messagebox.askyesno("Conferma", "Vuoi davvero Liste zurücksetzenre 'parole sconosciute'?"):
                return
            import pandas as pd
            df = pd.DataFrame(columns=["prompt", "answers", "explanation", "example", "example_de"])
            self._decorate_unknowns_df(df)
            df.to_excel(path, index=False)
            self._update_unknown_count()
            messagebox.showinfo("Fatto", "Il file 'parole sconosciute' è stato Liste zurücksetzento.")
        except Exception as e:
            messagebox.showerror("Errore", f"Azzera fallito.\n\n{e}")

    def quiz_unknowns(self):
        try:
            import pandas as pd
            path = self._unknowns_path()
            if not os.path.exists(path):
                messagebox.showinfo("Info", "Nessun file 'parole sconosciute' trovato.")
                return
            df = pd.read_excel(path)
            cards: List[Card] = []
            for idx, row in df.iterrows():
                prompt = str(row.get("prompt", "")).strip()
                answers_raw = row.get("answers", "")
                try:
                    if pd.isna(answers_raw):
                        answers_raw = ""
                except Exception:
                    pass
                answers = [a.strip() for a in str(answers_raw).split(";") if a.strip()]
                explanation = str(row.get("explanation", "")).strip() or None
                if prompt and answers:
                    cards.append(Card(row_index=idx, prompt=prompt, answers=answers, explanation=explanation, example=str(row.get('example','')) or None, german_example=str(row.get('example_de','')) or None))
            if not cards:
                messagebox.showinfo("Info", "Il file 'parole sconosciute' è vuoto.")
                return
            try:
                self._orig_title_backup = self.file_title_var.get()
            except Exception:
                self._orig_title_backup = None
            self.deck = Deck(cards)
            self.total_seen = 0
            self.total_correct = 0
            self.total_wrong = 0
            self.card_stats = {}
            try:
                self.file_title_var.set("PAROLE SCONOSCIUTE")
            except Exception:
                pass
            self.ready_for_next = False
            self.next_card()
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare 'parole sconosciute'.\n\n{e}")

    def return_to_original(self):
        try:
            if getattr(self, "df", None) is None:
                messagebox.showinfo("Hinweis", "Kein Hauptfile geladen.")
                return
            try:
                if self._orig_title_backup:
                    self.file_title_var.set(self._orig_title_backup)
            except Exception:
                pass
            self.ready_for_next = False
            self.init_deck()
        except Exception as e:
            messagebox.showerror("Fehler", f"Ritorno non riuscito.\n\n{e}")

    # ---- UI-Erweiterungen ----
    def _build_ui(self):
        # Basis-Oberfläche aus der Elternklasse
        super()._build_ui()
        # frühere Zusatzleiste für „parole sconosciute“ entfernt

    # ---- Multiple Choice: Nummern + Shortcuts ----
    def _populate_multiple_choice(self, card):
        try:
            super()._populate_multiple_choice(card)
        except Exception:
            return
        try:
            for i, btn in enumerate(getattr(self, "mc_buttons", [])):
                text = btn.cget("text")
                if not text:
                    continue
                already = text[:3].replace(".", "").isdigit()
                if not already:
                    btn.configure(text=f"{i+1}. {text}")
        except Exception:
            pass

    def _mc_pick(self, index: int):
        try:
            text = self.mc_buttons[index].cget("text")
            choice = text.split(". ", 1)[1] if ". " in text[:3] else text
        except Exception:
            choice = getattr(self.mc_buttons[index], "cget", lambda x:"")("text")

        ok = any(self._answers_equal(choice, ans) for ans in getattr(self, "_mc_solution", []))
        status = "correct" if ok else "wrong"
        self._finalize_answer(choice, ok, status=status)

    def _finalize_answer(self, user_input: str, ok: bool, status: str = None):
        try:
            super()._finalize_answer(user_input, ok, status=status)
        except Exception:
            return
        try:
            if not ok and bool(self.auto_pot_var.get()):
                self.add_current_to_unknowns(silent=True)
        except Exception:
            pass

    def _bind_keys(self):
        try:
            super()._bind_keys()
        except Exception:
            try:
                self.unbind_all("<Tab>")
            except Exception:
                pass
            self.bind_all("<Return>", self._on_return)
        # Safety: ensure A/R are not bound
        try:
            self.unbind_all("<Key-a>"); self.unbind_all("<Key-A>")
            self.unbind_all("<Key-r>"); self.unbind_all("<Key-R>")
        except Exception:
            pass
        # Safety: ensure T is not bound
        try:
            self.unbind_all("<Key-t>"); self.unbind_all("<Key-T>")
        except Exception:
            pass
        self.bind_all("<Key-1>", lambda e: self._mc_digit(0))
        self.bind_all("<Key-2>", lambda e: self._mc_digit(1))
        self.bind_all("<Key-3>", lambda e: self._mc_digit(2))
        self.bind_all("<Key-4>", lambda e: self._mc_digit(3))

    def _mc_digit(self, idx: int):
        try:
            if self.mode_var.get() != "Multiple Choice":
                return
        except Exception:
            return
        if getattr(self, "ready_for_next", False):
            return
        if hasattr(self, "mc_buttons") and 0 <= idx < len(self.mc_buttons):
            self._mc_pick(idx)

    def on_open_file(self):
        try:
            return super().on_open_file()
        finally:
            try:
                if not hasattr(self, "source_dir"):
                    self.source_dir = None
                try:
                    self._orig_title_backup = self.file_title_var.get()
                except Exception:
                    self._orig_title_backup = None
                try:
                    self._update_unknown_count()
                except Exception:
                    pass
            except Exception:
                pass

# ===== Ende PatchedApp =====
if __name__ == "__main__":
    # --- CLI options ---
    parser = argparse.ArgumentParser(description="Vokabeltrainer GUI (Tkinter)")
    parser.add_argument("--reset-unknowns", action="store_true",
                        help="Löscht die Datei 'parole sconosciute.xlsx' im aktuellen Ordner vor dem Start.")
    parser.add_argument("--purge-unknown", type=str, default=None,
                        help="Entfernt alle Zeilen aus 'parole sconosciute.xlsx', deren 'answers' den angegebenen Text enthalten.")
    args, _ = parser.parse_known_args()

    # Handle unknowns reset/purge BEFORE launching the GUI
    try:
        base_dir = os.getcwd()
        unk_path = os.path.join(base_dir, "parole sconosciute.xlsx")
        if args.reset_unknowns and os.path.exists(unk_path):
            os.remove(unk_path)
            print("🗑️  'parole sconosciute.xlsx' gelöscht.")
        if (args.purge_unknown is not None) and os.path.exists(unk_path):
            try:
                df = pd.read_excel(unk_path)
                if not df.empty:
                    # Be tolerant w/ col names
                    cols = {c.lower(): c for c in df.columns}
                    answers_col = cols.get("answers") or cols.get("antworten") or list(df.columns)[1]
                    before = len(df)
                    mask = ~df[answers_col].astype(str).str.contains(args.purge_unknown, case=False, na=False)
                    df2 = df[mask].copy()
                    if before != len(df2):
                        df2.to_excel(unk_path, index=False)
                        print(f"🔧 Einträge mit '{args.purge_unknown}' entfernt ({before-len(df2)} Zeile(n)).")
                    else:
                        print("ℹ️  Keine passenden Einträge in 'parole sconosciute.xlsx' gefunden.")
            except Exception as _e:
                print("Warnung: purge-unknown fehlgeschlagen:", _e)
    except Exception as _e:
        print("Warnung: Vorbereitungs-CLI fehlgeschlagen:", _e)

    try:
        app = PatchedApp()
        app.mainloop()
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        log_path = os.path.join(os.path.dirname(__file__), "vokabeltrainer_error.log")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(err)
        except Exception:
            pass
        try:
            messagebox.showerror("Startfehler", err)
        except Exception:
            pass
        raise
