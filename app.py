"""Plattenkiste – Spotify-Playlist in eine M3U aus deinen lokalen FLAC-Dateien verwandeln."""
from __future__ import annotations

import os
import re
import sys
import traceback

from PySide6.QtCore import (QStandardPaths, QAbstractTableModel, QModelIndex, QObject, QRectF, QRunnable,
                            QSettings, QSize, QSortFilterProxyModel, Qt, QThreadPool, QTimer, Signal)
from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QDialog, QRadioButton,
                               QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
                               QProgressBar, QPushButton, QSlider, QStyle, QStyledItemDelegate, QTableView,
                               QTabWidget, QTreeWidget, QCompleter, QTreeWidgetItem, QComboBox, QListWidget, QListWidgetItem,
                               QVBoxLayout, QWidget)

import core
import json
from dataclasses import dataclass, field, asdict
import dupes
import tagger

# --------------------------------------------------------------------------- Farben
C = {
    "bg": "#15130F",
    "panel": "#1E1B16",
    "panel2": "#27231C",
    "line": "#383228",
    "text": "#F0E8D8",
    "muted": "#9C927F",
    "faint": "#6B6355",
    "accent": "#E9A23B",
    "accent_hi": "#F4B759",
    "accent_ink": "#1C1407",
    "ok": "#9BBF7E",
    "warn": "#E9A23B",
    "bad": "#D6694F",
}

QSS = f"""
* {{ font-family: "Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", sans-serif;
     font-size: 13px; color: {C['text']}; }}
QMainWindow, QWidget#root {{ background: {C['bg']}; }}
QDialog {{ background: {C['panel']}; }}
QLabel#title {{ font-family: "Georgia", "DejaVu Serif", "Noto Serif", serif; font-size: 30px;
               font-style: italic; color: {C['text']}; }}
QLabel#subtitle {{ color: {C['muted']}; font-size: 13px; }}
QLabel#step {{ color: {C['accent']}; font-size: 11px; font-weight: 700; letter-spacing: 2px; }}
QLabel#cardTitle {{ font-size: 16px; font-weight: 600; }}
QLabel#hint {{ color: {C['muted']}; }}
QLabel#hintOk {{ color: {C['ok']}; }}
QLabel#hintBad {{ color: {C['bad']}; }}
QFrame#card {{ background: {C['panel']}; border: 1px solid {C['line']}; border-radius: 14px; }}
QLineEdit {{ background: {C['bg']}; border: 1px solid {C['line']}; border-radius: 9px;
            padding: 9px 12px; selection-background-color: {C['accent']}; selection-color: {C['accent_ink']}; }}
QLineEdit:focus {{ border-color: {C['accent']}; }}
QPushButton {{ background: {C['panel2']}; border: 1px solid {C['line']}; border-radius: 9px;
              padding: 9px 16px; font-weight: 600; }}
QPushButton:hover {{ border-color: {C['muted']}; }}
QPushButton:disabled {{ color: {C['faint']}; }}
QPushButton#primary {{ background: {C['accent']}; color: {C['accent_ink']}; border: none; }}
QPushButton#primary:hover {{ background: {C['accent_hi']}; }}
QPushButton#primary:disabled {{ background: {C['panel2']}; color: {C['faint']}; }}
QPushButton#link {{ background: transparent; border: none; color: {C['muted']}; padding: 4px 2px;
                   font-weight: 500; text-decoration: underline; }}
QPushButton#link:hover {{ color: {C['accent']}; }}
QPushButton#seg {{ background: transparent; border: none; border-radius: 7px; padding: 6px 12px;
                  color: {C['muted']}; font-weight: 600; }}
QPushButton#seg:checked {{ background: {C['panel2']}; color: {C['text']}; }}
QFrame#segWrap {{ background: {C['bg']}; border: 1px solid {C['line']}; border-radius: 9px; }}
QCheckBox {{ color: {C['muted']}; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid {C['line']};
                       background: {C['bg']}; }}
QCheckBox::indicator:checked {{ background: {C['accent']}; border-color: {C['accent']}; }}
QRadioButton {{ color: {C['muted']}; spacing: 8px; }}
QRadioButton:checked {{ color: {C['text']}; font-weight: 700; }}
QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 9px; border: 1px solid {C['line']}; background: {C['bg']}; }}
QRadioButton::indicator:checked {{ background: {C['bg']}; border: 5px solid {C['accent']}; width: 8px; height: 8px; }}
QSlider::groove:horizontal {{ height: 4px; background: {C['line']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {C['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {C['text']}; width: 14px; height: 14px; margin: -5px 0;
                             border-radius: 7px; }}
QProgressBar {{ background: {C['panel2']}; border: none; border-radius: 2px; max-height: 4px; }}
QProgressBar::chunk {{ background: {C['accent']}; border-radius: 2px; }}
QTableView {{ background: {C['panel']}; border: 1px solid {C['line']}; border-radius: 14px;
             gridline-color: transparent; selection-background-color: {C['panel2']};
             selection-color: {C['text']}; outline: 0; }}
QTableView::item {{ padding: 0 10px; border-bottom: 1px solid {C['bg']}; }}
QHeaderView::section {{ background: {C['panel']}; color: {C['faint']}; border: none;
                       border-bottom: 1px solid {C['line']}; padding: 10px; font-size: 11px;
                       font-weight: 700; letter-spacing: 1px; }}
QTableCornerButton::section {{ background: {C['panel']}; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: {C['line']}; border-radius: 3px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QMenu {{ background: {C['panel2']}; border: 1px solid {C['line']}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {C['accent']}; color: {C['accent_ink']}; }}
QMenu::separator {{ height: 1px; background: {C['line']}; margin: 5px 8px; }}
QTabWidget::pane {{ border: none; background: {C['bg']}; }}
QWidget#page {{ background: {C['bg']}; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {C['muted']}; padding: 8px 2px 10px 2px; margin-right: 26px;
               border: none; border-bottom: 2px solid transparent; font-size: 14px; font-weight: 600; }}
QTabBar::tab:hover {{ color: {C['text']}; }}
QTabBar::tab:selected {{ color: {C['text']}; border-bottom: 2px solid {C['accent']}; }}
QPushButton#danger {{ background: {C['bad']}; color: #1A0B07; border: none; }}
QPushButton#danger:hover {{ background: #E07B62; }}
QPushButton#danger:disabled {{ background: {C['panel2']}; color: {C['faint']}; }}
QTreeWidget {{ background: {C['panel']}; border: 1px solid {C['line']}; border-radius: 14px; outline: 0;
              selection-background-color: {C['panel2']}; selection-color: {C['text']}; padding: 4px; }}
QTreeWidget::item {{ padding: 6px 4px; }}
QTableView::indicator {{ width: 15px; height: 15px; border-radius: 4px; border: 1px solid {C['line']}; background: {C['bg']}; }}
QTableView::indicator:checked {{ background: {C['accent']}; border-color: {C['accent']}; }}
QListWidget {{ background: transparent; border: none; outline: 0; }}
QListWidget::item {{ padding: 6px 6px; border-radius: 6px; color: {C['muted']}; }}
QListWidget::item:selected {{ background: {C['panel2']}; color: {C['text']}; }}
QTreeView::indicator {{ width: 15px; height: 15px; border-radius: 4px; border: 1px solid {C['line']}; background: {C['bg']}; }}
QTreeView::indicator:checked {{ background: {C['bad']}; border-color: {C['bad']}; }}
QComboBox {{ background: {C['panel2']}; border: 1px solid {C['line']}; border-radius: 9px; padding: 8px 12px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {C['panel2']}; border: 1px solid {C['line']}; selection-background-color: {C['accent']};
                              selection-color: {C['accent_ink']}; outline: 0; }}
QPushButton#queueToggle {{ background: transparent; border: none; padding: 4px 2px; font-size: 14px; font-weight: 700;
                         color: {C['text']}; text-align: left; }}
QPushButton#queueToggle:hover {{ color: {C['accent']}; }}
QListWidget#queueList {{ background: transparent; border: none; outline: 0; }}
QListWidget#queueList::item {{ border: none; padding: 0; margin: 0 0 2px 0; }}
QListWidget#queueList::item:selected, QListWidget#queueList::item:hover {{ background: transparent; }}
QWidget#queueRow {{ background: {C['bg']}; border: 1px solid {C['line']}; border-radius: 10px; }}
QWidget#queueRow:hover {{ border-color: {C['muted']}; }}
QWidget#queueRow[active="true"] {{ background: {C['panel2']}; border: 1px solid {C['accent']}; }}
QLabel#queueName {{ font-weight: 700; }}
QPushButton#queueRemove {{ background: transparent; border: none; color: {C['faint']}; padding: 2px 8px; font-size: 13px; }}
QPushButton#queueRemove:hover {{ color: {C['bad']}; }}
QToolTip {{ background: {C['panel2']}; color: {C['text']}; border: 1px solid {C['line']}; padding: 6px; }}
"""

OK, WARN, MISS = "ok", "warn", "miss"
STATUS_TXT = {OK: "Gefunden", WARN: "Prüfen", MISS: "Fehlt"}
STATUS_COL = {OK: C["ok"], WARN: C["warn"], MISS: C["bad"]}


# --------------------------------------------------------------------------- Hintergrundjobs
class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int)


class Job(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.s = _Signals()

    def _emit(self, sig, *args):
        try:
            sig.emit(*args)
        except RuntimeError:  # Fenster wurde inzwischen geschlossen
            raise _Closed()

    def run(self):
        try:
            res = self.fn(*self.args, progress=lambda i, n: self._emit(self.s.progress, i, n), **self.kwargs)
            self._emit(self.s.done, res)
        except _Closed:
            pass
        except core.SpotifyError as e:
            try:
                self._emit(self.s.failed, str(e))
            except _Closed:
                pass
        except Exception as e:  # noqa
            traceback.print_exc()
            try:
                self._emit(self.s.failed, f"{type(e).__name__}: {e}")
            except _Closed:
                pass


class _Closed(Exception):
    pass


# --------------------------------------------------------------------------- Tabelle
class MatchModel(QAbstractTableModel):
    HEAD = ["#", "STATUS", "SPOTIFY-TITEL", "INTERPRET", "LOKALE DATEI", "TREFFER"]

    def __init__(self):
        super().__init__()
        self.matches: list[core.Match] = []
        self.threshold = 70
        self.root = ""

    def status(self, m: core.Match) -> str:
        if not m.file:
            return MISS
        if m.manual or m.score >= max(88, self.threshold):
            return OK
        if m.score >= self.threshold:
            return WARN
        return MISS

    def set_matches(self, matches, root):
        self.beginResetModel()
        self.matches, self.root = matches, root
        self.endResetModel()

    def refresh(self):
        if self.matches:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.matches) - 1, len(self.HEAD) - 1))

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.matches)

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEAD)

    def headerData(self, s, o, role=Qt.DisplayRole):
        if o == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEAD[s]
        if o == Qt.Horizontal and role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def _rel(self, p):
        try:
            return os.path.relpath(p, self.root) if self.root else p
        except ValueError:
            return p

    def data(self, idx, role=Qt.DisplayRole):
        m = self.matches[idx.row()]
        col = idx.column()
        st = self.status(m)
        if role == Qt.UserRole:
            return st
        if role == Qt.DisplayRole:
            if col == 0:
                return str(idx.row() + 1)
            if col == 1:
                return STATUS_TXT[st]
            if col == 2:
                return m.track.title
            if col == 3:
                return m.track.artist_str
            if col == 4:
                if not m.file:
                    return "—"
                return self._rel(m.file.path) if st != MISS else f"({self._rel(m.file.path)})"
            if col == 5:
                if not m.file:
                    return ""
                return "manuell" if m.manual else f"{m.score:.0f} %"
        if role == Qt.ForegroundRole:
            if col in (0, 5):
                return QColor(C["faint"])
            if col == 4 and (not m.file or st == MISS):
                return QColor(C["faint"])
            if col == 3:
                return QColor(C["muted"])
        if role == Qt.ToolTipRole and col == 4 and m.file:
            f = m.file
            return f"{f.artist} – {f.title}\n{f.album}\n{f.path}"
        if role == Qt.TextAlignmentRole and col in (0, 5):
            return int(Qt.AlignRight | Qt.AlignVCenter) if col == 5 else int(Qt.AlignCenter)
        return None


class StatusDelegate(QStyledItemDelegate):
    def paint(self, p: QPainter, opt, idx):
        st = idx.data(Qt.UserRole)
        col = QColor(STATUS_COL[st])
        o = type(opt)(opt)
        self.initStyleOption(o, idx)
        o.text = ""
        w = o.widget
        (w.style() if w else QApplication.style()).drawControl(QStyle.CE_ItemViewItem, o, p, w)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        txt = STATUS_TXT[st]
        f = QFont(opt.font)
        f.setPointSizeF(max(8.0, f.pointSizeF() - 1))
        f.setBold(True)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(txt) + 26
        r = QRectF(opt.rect.x() + 8, opt.rect.center().y() - 11, w, 22)
        bg = QColor(col)
        bg.setAlpha(38)
        path = QPainterPath()
        path.addRoundedRect(r, 11, 11)
        p.fillPath(path, bg)
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(r.x() + 9, r.center().y() - 3, 6, 6))
        p.setPen(QPen(col))
        p.drawText(r.adjusted(19, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, txt)
        p.restore()


class FilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.mode = "all"

    def set_mode(self, mode):
        self.mode = mode
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        if self.mode == "all":
            return True
        st = self.sourceModel().index(row, 0, parent).data(Qt.UserRole)
        return st == self.mode


# --------------------------------------------------------------------------- Dialog API
class ApiDialog(QDialog):
    def __init__(self, parent, cid, secret):
        super().__init__(parent)
        self.setWindowTitle("Spotify-API (optional)")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 18)
        lay.setSpacing(12)
        info = QLabel("Ohne Zugangsdaten liest Plattenkiste die öffentliche Spotify-Seite – das reicht "
                      "für bis zu 100 Titel. Für größere Playlists und ISRC-Abgleich erstelle eine App "
                      "unter developer.spotify.com und trage Client-ID und Secret hier ein.")
        info.setWordWrap(True)
        info.setObjectName("hint")
        lay.addWidget(info)
        form = QFormLayout()
        form.setSpacing(10)
        self.cid = QLineEdit(cid)
        self.secret = QLineEdit(secret)
        self.secret.setEchoMode(QLineEdit.Password)
        form.addRow("Client-ID", self.cid)
        form.addRow("Client-Secret", self.secret)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setObjectName("primary")
        bb.button(QDialogButtonBox.Save).setText("Speichern")
        bb.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


# --------------------------------------------------------------------------- Hauptfenster
def card(step: str, title: str):
    fr = QFrame()
    fr.setObjectName("card")
    lay = QVBoxLayout(fr)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(10)
    s = QLabel(step)
    s.setObjectName("step")
    t = QLabel(title)
    t.setObjectName("cardTitle")
    lay.addWidget(s)
    lay.addWidget(t)
    return fr, lay



# --------------------------------------------------------------------------- Queue
@dataclass
class QueueItem:
    playlist: core.Playlist
    link: str = ""
    matches: list | None = None
    files_ref: int = 0                                   # zu welchem Ordner-Scan die Treffer gehören
    manual: dict = field(default_factory=dict)          # Titelnummer → von Hand gewählte Datei ("" = keine)
    busy: bool = False

    def key(self):
        try:
            return "spotify:" + core.parse_spotify_link(self.link)[1]
        except Exception:
            return "name:" + self.playlist.name


class QueueRow(QWidget):
    """Eine Zeile in der Queue: Name, Anzahl, Trefferquote, Entfernen"""

    def __init__(self, panel, it: QueueItem):
        super().__init__(objectName="queueRow")
        self.setAttribute(Qt.WA_StyledBackground, True)  # sonst zeichnet Qt Rahmen/Hintergrund nicht
        self.setCursor(Qt.PointingHandCursor)
        self.panel, self.it = panel, it
        h = QHBoxLayout(self)
        h.setContentsMargins(12, 8, 8, 8)
        h.setSpacing(10)
        self.dot = QLabel("●", objectName="queueDot")
        self.name = QLabel(objectName="queueName")
        self.info = QLabel(objectName="hint")
        self.state = QLabel(objectName="queueState")
        rm = QPushButton("✕", objectName="queueRemove")
        rm.setToolTip("Aus der Queue entfernen")
        rm.setCursor(Qt.PointingHandCursor)
        rm.clicked.connect(lambda: panel.main.remove_from_queue(it))
        h.addWidget(self.dot)
        h.addWidget(self.name, 1)
        h.addWidget(self.info)
        h.addWidget(self.state)
        h.addWidget(rm)
        self.refresh(False)

    def refresh(self, active: bool):
        it = self.it
        self.name.setText(it.playlist.name)
        self.info.setText(f"{len(it.playlist.tracks)} Titel")
        if it.busy or (it.matches is None and self.panel.main.files is not None):
            self.state.setText("gleiche ab …")
            self.state.setStyleSheet(f"color:{C['muted']}")
        elif it.matches is None:
            self.state.setText("wartet auf Ordner")
            self.state.setStyleSheet(f"color:{C['faint']}")
        else:
            model = self.panel.main.model
            ok = sum(1 for m in it.matches if model.status(m) != MISS)
            total = len(it.matches)
            col = C["ok"] if ok == total else C["warn"] if ok >= total * 0.7 else C["bad"]
            self.state.setText(f"{ok} von {total} gefunden")
            self.state.setStyleSheet(f"color:{col}; font-weight:700")
        self.dot.setStyleSheet(f"color:{C['accent'] if active else C['line']}; font-size:11px")
        self.setProperty("active", active)
        self.style().unpolish(self)
        self.style().polish(self)


class QueuePanel(QFrame):
    """Aufklappbare Queue unter der Tabelle – die angeklickte Playlist ist aktiv"""

    def __init__(self, main):
        super().__init__(objectName="card")
        self.main = main
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 8, 10, 8)
        v.setSpacing(6)
        head = QHBoxLayout()
        self.toggle = QPushButton(objectName="queueToggle")
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.clicked.connect(self.flip)
        self.toggle.setToolTip("Queue auf- oder zuklappen")
        head.addWidget(self.toggle)
        head.addStretch()
        self.save_all = QPushButton("Alle speichern")
        self.save_all.setToolTip("Für jede Playlist der Queue eine Playlist-Datei im gewählten Format speichern")
        self.save_all.clicked.connect(lambda: main.device_all() if main.fmt.currentData() == "transfer" else main.save_all())
        self.clear = QPushButton("Leeren", objectName="link")
        self.clear.clicked.connect(main.clear_queue)
        for b in (self.save_all, self.clear):
            head.addWidget(b)
        v.addLayout(head)
        self.list = QListWidget(objectName="queueList")
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.currentRowChanged.connect(self.picked)
        v.addWidget(self.list)
        self.open = main.settings.value("queue_open", True, type=bool)
        self.rows: list[QueueRow] = []
        self.rebuild()

    def flip(self):
        self.open = not self.open
        self.main.settings.setValue("queue_open", self.open)
        self.rebuild_visibility()

    def rebuild_visibility(self):
        q = self.main.queue
        self.list.setVisible(self.open and bool(q))
        arrow = "▾" if self.open else "▸"
        self.toggle.setText(f"{arrow}  Queue  ·  {len(q)} Playlist" + ("s" if len(q) != 1 else ""))
        for b in (self.save_all, self.clear):
            b.setVisible(bool(q))
        h = min(5, max(1, len(q))) * 46 + 6
        self.list.setFixedHeight(h)

    def rebuild(self):
        q = self.main.queue
        self.list.blockSignals(True)
        self.list.clear()
        self.rows = []
        for it in q:
            row = QueueRow(self, it)
            li = QListWidgetItem()
            li.setSizeHint(QSize(100, 44))
            self.list.addItem(li)
            self.list.setItemWidget(li, row)
            self.rows.append(row)
        if self.main.active in q:
            self.list.setCurrentRow(q.index(self.main.active))
        self.list.blockSignals(False)
        self.refresh()
        self.rebuild_visibility()

    def refresh(self):
        for r in self.rows:
            r.refresh(r.it is self.main.active)

    def picked(self, row):
        if 0 <= row < len(self.main.queue):
            self.main.activate(self.main.queue[row])


# --------------------------------------------------------------------------- Gerät / SD-Karte
class DeviceDialog(QDialog):
    """Übertragen auf MP3-Player/SD-Karte: Zielordner, Geräteprofil, Ordner, Pfadformat, Vorschau"""

    def __init__(self, main, count_text: str, sample: "core.Match | None", on_test):
        super().__init__(main)
        self.main, self.sample, self.on_test = main, sample, on_test
        st = main.settings
        self.setWindowTitle("Auf Gerät übertragen")
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(10)
        title = QLabel(count_text, objectName="cardTitle")
        lay.addWidget(title)
        form = QFormLayout()
        form.setSpacing(10)
        row = QHBoxLayout()
        self.target = QLineEdit(st.value("device_dir", ""), placeholderText="Hauptordner der SD-Karte / des Geräts, z. B. E:\\")
        pick = QPushButton("Wählen …")
        pick.clicked.connect(self.pick)
        row.addWidget(self.target, 1)
        row.addWidget(pick)
        form.addRow("SD-Karte / Gerät", row)
        self.profile = QComboBox()
        for k, p in core.DEVICE_PROFILES.items():
            self.profile.addItem(p["label"], k)
        self.profile.setCurrentIndex(max(0, self.profile.findData(st.value("device_profile", "generic"))))
        form.addRow("Gerät", self.profile)
        self.pl_dir = QLineEdit(st.value("device_playlist_dir", ""), placeholderText="leer = Hauptordner der Karte")
        self.mu_dir = QLineEdit(st.value("device_music_dir", ""), placeholderText="leer = Hauptordner der Karte")
        for label, edit, what in (("Playlist-Ordner", self.pl_dir, "Ordner für die Playlists"), ("Musik-Ordner", self.mu_dir, "Ordner für die Musik")):
            r = QHBoxLayout()
            b = QPushButton("Wählen …")
            b.setToolTip(f"{what} auf der Karte auswählen (oder neu anlegen)")
            b.clicked.connect(lambda _=False, e=edit, w=what: self.pick_sub(e, w))
            r.addWidget(edit, 1)
            r.addWidget(b)
            form.addRow(label, r)
        self.style_box = QComboBox()
        for k, label in core.PATH_STYLES.items():
            self.style_box.addItem(label, k)
        self.add_learned_item()
        self.style_box.setCurrentIndex(max(0, self.style_box.findData(st.value("device_style", "rel"))))
        form.addRow("Pfadformat", self.style_box)
        mode = QHBoxLayout()
        self.only = QRadioButton("Nur Playlist ausgeben")
        self.only.setToolTip("Schreibt nur die M3U. Die Songs werden auf der Karte gesucht\n"
                             "(gleicher Pfad, sonst gleicher Dateiname) – kopiert wird nichts.")
        self.copy = QRadioButton("Songs mitkopieren")
        self.copy.setToolTip("Kopiert fehlende Songs in den Musik-Ordner der Karte und schreibt die Playlist.")
        self.copy.setChecked(st.value("device_copy", False, type=bool))
        self.only.setChecked(not self.copy.isChecked())
        mode.addWidget(self.only)
        mode.addWidget(self.copy)
        mode.addStretch()
        form.addRow("Modus", mode)
        lay.addLayout(form)

        self.preview = QLabel(objectName="hint")
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.RichText)
        lay.addWidget(self.preview)
        self.note = QLabel(objectName="hint")
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        btns = QHBoxLayout()
        self.learn_btn = QPushButton("Format vom Gerät übernehmen …")
        self.learn_btn.setToolTip("Eine Playlist auswählen, die das Gerät selbst gespeichert hat –\n"
                                  "Plattenkiste schreibt danach alle Playlists exakt im gleichen Format.\n"
                                  "Empfohlen, wenn das Gerät Pfade statt Songtitel anzeigt.")
        self.learn_btn.clicked.connect(self.learn)
        btns.addWidget(self.learn_btn)
        self.test_btn = QPushButton("Testplaylists erstellen")
        self.test_btn.setToolTip("Schreibt „Test A“ bis „Test E“ (je 3 Songs, je ein Pfadformat) in den Playlist-Ordner.\n"
                                 "Am Gerät siehst du, welche Songs anzeigt – dieses Format stellst du dann hier ein.")
        self.test_btn.clicked.connect(self.test)
        btns.addWidget(self.test_btn)
        btns.addStretch()
        lay.addLayout(btns)
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Übertragen", objectName="primary")
        ok.clicked.connect(self.accept_checked)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self.profile.currentIndexChanged.connect(self.profile_changed)
        for w in (self.pl_dir, self.mu_dir, self.target):
            w.textChanged.connect(self.update_preview)
        self.style_box.currentIndexChanged.connect(self.update_preview)
        self.copy.toggled.connect(self.update_preview)
        if not st.value("device_profile", ""):
            self.profile_changed()
        self.update_preview()

    def pick(self):
        d = QFileDialog.getExistingDirectory(self, "SD-Karte / Gerät wählen", self.target.text() or os.path.expanduser("~"))
        if d:
            self.target.setText(d)

    def add_learned_item(self):
        i = self.style_box.findData("learned")
        if core.LEARNED:
            label = "Vom Gerät übernommen   (" + core.LEARNED.get("prefix", "") + "…)"
            if i < 0:
                self.style_box.addItem(label, "learned")
            else:
                self.style_box.setItemText(i, label)

    def learn(self):
        root = self.target.text().strip()
        if not root or not os.path.isdir(root):
            QMessageBox.information(self, "Format übernehmen", "Bitte zuerst oben die SD-Karte bzw. das Gerät wählen.")
            return
        QMessageBox.information(
            self, "Format vom Gerät übernehmen",
            "So geht's:\n\n"
            "1. Am Gerät eine Playlist mit mindestens einem Song erstellen und speichern\n"
            "    (beim HiBy R1 landet sie im Ordner „playlist_data“).\n"
            "2. Die SD-Karte wieder am PC anschließen.\n"
            "3. Im nächsten Fenster diese Playlist-Datei auswählen.\n\n"
            "Plattenkiste übernimmt dann genau das Pfadformat des Geräts.")
        start = os.path.join(root, *core._parts(self.pl_dir.text()))
        p, _ = QFileDialog.getOpenFileName(self, "Vom Gerät gespeicherte Playlist wählen",
                                           start if os.path.isdir(start) else root, "Playlists (*.m3u *.m3u8);;Alle Dateien (*)")
        if not p:
            return
        try:
            fmt = core.learn_device_format(root, p)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Format übernehmen", str(e))
            return
        core.LEARNED.clear()
        core.LEARNED.update(fmt)
        self.main.settings.setValue("device_learned", json.dumps(fmt))
        # Playlist-Ordner gleich dorthin, wo das Gerät seine Playlists ablegt
        rel = core._inside(os.path.dirname(p), root)
        if rel is not None:
            self.pl_dir.setText("/".join(rel))
        self.add_learned_item()
        self.style_box.setCurrentIndex(self.style_box.findData("learned"))
        self.update_preview()
        extras = []
        extras.append("mit #EXTM3U-Kopfzeile" if fmt["header"] else "ohne Kopfzeile")
        extras.append("mit #EXTINF-Titelzeilen" if fmt["extinf"] else "ohne #EXTINF-Zeilen")
        QMessageBox.information(self, "Format übernommen",
                                f"Gerät schreibt Pfade so:\n{fmt['example']}\n\n"
                                f"Präfix: {fmt['prefix'] or '(keins)'}   Trennzeichen: {fmt['sep']}\n"
                                f"Datei: {', '.join(extras)}\n\n"
                                "Alle Playlists werden jetzt in genau diesem Format geschrieben.")

    def pick_sub(self, edit: QLineEdit, what: str):
        """Unterordner auf der Karte wählen – gespeichert wird der Pfad relativ zur Karte"""
        root = self.target.text().strip()
        if not root or not os.path.isdir(root):
            QMessageBox.information(self, "Ordner wählen", "Bitte zuerst oben die SD-Karte bzw. das Gerät wählen.")
            self.pick()
            root = self.target.text().strip()
            if not root or not os.path.isdir(root):
                return
        start = os.path.join(root, *core._parts(edit.text()))
        d = QFileDialog.getExistingDirectory(self, f"{what} wählen", start if os.path.isdir(start) else root)
        if not d:
            return
        try:
            rel = os.path.relpath(os.path.abspath(d), os.path.abspath(root))
        except ValueError:  # anderes Laufwerk
            rel = ".."
        if rel.startswith(".."):
            QMessageBox.warning(self, "Ordner wählen", f"Der Ordner muss auf der gewählten Karte liegen:\n{root}")
            return
        edit.setText("" if rel == "." else rel.replace("\\", "/"))
        # Eigene Ordner → Profil „Eigene Einstellung“, damit nichts überschrieben wird
        if self.profile.currentData() != "custom":
            p = core.DEVICE_PROFILES[self.profile.currentData()]
            if (self.pl_dir.text(), self.mu_dir.text()) != (p["playlist_dir"], p["music_dir"]):
                self.profile.blockSignals(True)
                self.profile.setCurrentIndex(self.profile.findData("custom"))
                self.profile.blockSignals(False)
        self.update_preview()

    def profile_changed(self):
        k = self.profile.currentData()
        if k != "custom":
            p = core.DEVICE_PROFILES[k]
            self.pl_dir.setText(p["playlist_dir"])
            self.mu_dir.setText(p["music_dir"])
            style = "learned" if (k == "hiby" and core.LEARNED) else p["style"]
            self.style_box.setCurrentIndex(max(0, self.style_box.findData(style)))
        self.update_preview()

    def values(self):
        return dict(target=self.target.text().strip(), playlist_dir=self.pl_dir.text().strip().strip("/\\"),
                    music_dir=self.mu_dir.text().strip().strip("/\\"), style=self.style_box.currentData(),
                    copy=self.copy.isChecked())

    def update_preview(self):
        v = self.values()
        root = v["target"] or "SD-Karte"
        pl_loc = "/".join([root.rstrip("/\\")] + core._parts(v["playlist_dir"]) + ["Playlist.m3u"])
        if self.sample:
            parts = core.device_song_rel(self.sample.file.path, self.main.folder)
            line = core.device_path(parts, v["music_dir"], v["playlist_dir"], v["style"])
            song_loc = "/".join([root.rstrip("/\\")] + core._parts(v["music_dir"]) + parts)
        else:
            line = song_loc = "–"
        self.preview.setText(
            f"<b>Playlist:</b> {_esc(pl_loc)}<br><b>Song:</b> {_esc(song_loc)}"
            f"<br><b>Eintrag in der Playlist:</b> <span style='color:{C['accent']}'>{_esc(line)}</span>"
            + ("" if v["copy"] else f"<br><span style='color:{C['muted']}'>Es wird nur die Playlist geschrieben. Jeder Song wird auf der Karte gesucht – "
                                    "liegt er woanders als hier gezeigt, wird automatisch sein tatsächlicher Ort eingetragen.</span>"))
        if self.profile.currentData() == "hiby":
            self.note.setText("HiBy R1: Danach am Player unter Musik → Zahnrad → „Datenbank aktualisieren“ wählen. "
                              + ("Format ist vom Gerät übernommen ✓" if self.style_box.currentData() == "learned" else
                                 "Zeigt der Player Pfade statt Songtitel: am R1 eine Playlist mit einem Song speichern und hier "
                                 "„Format vom Gerät übernehmen …“ wählen – dann passt das Format exakt."))
        else:
            self.note.setText("")

    def save(self):
        v, st = self.values(), self.main.settings
        st.setValue("device_dir", v["target"])
        st.setValue("device_profile", self.profile.currentData())
        st.setValue("device_playlist_dir", v["playlist_dir"])
        st.setValue("device_music_dir", v["music_dir"])
        st.setValue("device_style", v["style"])
        st.setValue("device_copy", v["copy"])

    def check(self):
        if not self.values()["target"] or not os.path.isdir(self.values()["target"]):
            QMessageBox.warning(self, "Auf Gerät übertragen", "Bitte den Hauptordner der SD-Karte bzw. des Geräts wählen.")
            return False
        return True

    def accept_checked(self):
        if self.check():
            self.save()
            self.accept()

    def test(self):
        if self.check():
            self.save()
            self.on_test(self.values())


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plattenkiste")
        self.resize(1180, 820)
        self.settings = QSettings("Plattenkiste", "Plattenkiste")
        self.pool = QThreadPool.globalInstance()
        self.jobs = set()
        self.playlist: core.Playlist | None = None
        self.queue: list[QueueItem] = []
        self.active: QueueItem | None = None
        self.files: list[core.LocalFile] | None = None
        self.folder = ""

        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(32, 26, 32, 24)
        v.setSpacing(18)

        # Kopf
        head = QHBoxLayout()
        tv = QVBoxLayout()
        tv.setSpacing(2)
        tv.addWidget(QLabel("Plattenkiste", objectName="title"))
        tv.addWidget(QLabel("Spotify-Playlists als M3U aus deinen FLACs – doppelte Titel aufräumen und Songs taggen.", objectName="subtitle"))
        head.addLayout(tv)
        head.addStretch()
        api_btn = QPushButton("Spotify-API …", objectName="link")
        api_btn.clicked.connect(self.edit_api)
        head.addWidget(api_btn, alignment=Qt.AlignTop)
        v.addLayout(head)

        # Reiter
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        v.addWidget(self.tabs, 1)
        page = QWidget(objectName="page")
        self.tabs.addTab(page, "Playlist erstellen")
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 20, 0, 0)
        v.setSpacing(18)

        # Karten
        cards = QHBoxLayout()
        cards.setSpacing(16)
        c1, l1 = card("SCHRITT 1", "Spotify-Playlist")
        row = QHBoxLayout()
        self.link = QLineEdit(placeholderText="Spotify-Link einfügen (auch mehrere auf einmal)")
        self.link.returnPressed.connect(self.load_playlist)
        self.load_btn = QPushButton("Hinzufügen", objectName="primary")
        self.load_btn.setToolTip("Playlist laden und unten in die Queue legen")
        self.load_btn.clicked.connect(self.load_playlist)
        row.addWidget(self.link, 1)
        row.addWidget(self.load_btn)
        l1.addLayout(row)
        r2 = QHBoxLayout()
        self.pl_hint = QLabel("Link einfügen – die Playlist kommt in die Queue. Sie muss öffentlich sein.", objectName="hint")
        self.pl_hint.setWordWrap(True)
        csv_btn = QPushButton("oder CSV importieren", objectName="link")
        csv_btn.clicked.connect(self.import_csv)
        r2.addWidget(self.pl_hint, 1)
        r2.addWidget(csv_btn, alignment=Qt.AlignTop)
        l1.addLayout(r2)
        l1.addStretch()

        c2, l2 = card("SCHRITT 2", "Musikordner")
        row = QHBoxLayout()
        self.path = QLineEdit(placeholderText="Ordner mit deinen FLAC-Dateien")
        self.path.setReadOnly(True)
        pick = QPushButton("Ordner wählen …")
        pick.clicked.connect(self.pick_folder)
        row.addWidget(self.path, 1)
        row.addWidget(pick)
        l2.addLayout(row)
        r2 = QHBoxLayout()
        self.recursive = QCheckBox("Unterordner einbeziehen")
        self.recursive.setToolTip("Durchsucht alle Unterordner – beliebig tief, auch sehr lange Pfade und verknüpfte Ordner.")
        self.recursive.setChecked(self.settings.value("recursive", True, type=bool))
        self.allfmt = QCheckBox("auch MP3, M4A, OGG …")
        self.allfmt.setChecked(self.settings.value("allfmt", False, type=bool))
        for cb in (self.recursive, self.allfmt):
            cb.toggled.connect(self.rescan)
            r2.addWidget(cb)
        r2.addStretch()
        l2.addLayout(r2)
        self.dir_hint = QLabel("Noch kein Ordner gewählt.", objectName="hint")
        l2.addWidget(self.dir_hint)
        l2.addStretch()

        cards.addWidget(c1, 1)
        cards.addWidget(c2, 1)
        v.addLayout(cards)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setVisible(False)
        v.addWidget(self.bar)

        # Werkzeugleiste über der Tabelle
        tools = QHBoxLayout()
        seg = QFrame(objectName="segWrap")
        sl = QHBoxLayout(seg)
        sl.setContentsMargins(3, 3, 3, 3)
        sl.setSpacing(2)
        self.seg_group = QButtonGroup(self)
        self.seg_btns = {}
        for key, label in (("all", "Alle"), (OK, "Gefunden"), (WARN, "Prüfen"), (MISS, "Fehlt")):
            b = QPushButton(label, objectName="seg", checkable=True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self.proxy.set_mode(k))
            self.seg_group.addButton(b)
            self.seg_btns[key] = b
            sl.addWidget(b)
        self.seg_btns["all"].setChecked(True)
        tools.addWidget(seg)
        tools.addStretch()
        tools.addWidget(QLabel("Mindest-Treffer", objectName="hint"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(50, 95)
        self.slider.setFixedWidth(160)
        self.slider.setValue(self.settings.value("threshold", 70, type=int))
        self.thr_lbl = QLabel(f"{self.slider.value()} %")
        self.thr_lbl.setFixedWidth(40)
        self.slider.valueChanged.connect(self.threshold_changed)
        tools.addWidget(self.slider)
        tools.addWidget(self.thr_lbl)
        v.addLayout(tools)

        # Tabelle
        self.model = MatchModel()
        self.model.threshold = self.slider.value()
        self.proxy = FilterProxy()
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setItemDelegateForColumn(1, StatusDelegate(self.table))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setFocusPolicy(Qt.NoFocus)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(False)
        for col, w in ((0, 46), (1, 118), (2, 260), (3, 200), (5, 84)):
            self.table.setColumnWidth(col, w)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.row_menu)
        self.table.doubleClicked.connect(lambda i: self.row_menu(self.table.visualRect(i).center()))
        self.empty = QLabel("Lade eine Playlist und wähle einen Ordner –\n"
                            "der Abgleich startet dann automatisch.", alignment=Qt.AlignCenter)
        self.empty.setObjectName("hint")
        v.addWidget(self.table, 1)
        v.addWidget(self.empty, 1)
        self.queue_panel = QueuePanel(self)
        v.addWidget(self.queue_panel)
        self.table.setVisible(False)

        # Fußleiste
        foot = QHBoxLayout()
        self.summary = QLabel("", objectName="hint")
        foot.addWidget(self.summary)
        foot.addStretch()
        self.copy_btn = QPushButton("Fehlende kopieren")
        self.copy_btn.clicked.connect(self.copy_missing)
        self.fmt = QComboBox()
        self.fmt.addItem("M3U – für MP3-Player & Handy", "device")
        self.fmt.addItem("M3U – nur für diesen PC", "abs")
        self.fmt.addItem("MusicBee-Auto-Playlist", "xautopf")
        self.fmt.insertSeparator(self.fmt.count())
        self.fmt.addItem("Auf Gerät übertragen (SD-Karte / MP3-Player)", "transfer")
        self.fmt.setToolTip(
            "MP3-Player & Handy: Pfade relativ zur Playlist mit „/“. Die Playlist wird im Musikordner gespeichert –\n"
            "kopierst du den Musikordner samt Playlist aufs Gerät, findet der Player alle Songs.\n\n"
            "Nur für diesen PC: vollständige Pfade (C:\\…), funktioniert nur auf diesem Rechner.\n\n"
            "MusicBee-Auto-Playlist (.xautopf): sucht die Songs in deiner MusicBee-Bibliothek über Titel und Interpret.\n\n"
            "Auf Gerät übertragen: Songs und Playlist direkt auf SD-Karte / MP3-Player (z. B. HiBy R1) –\n"
            "mit wählbarem Playlist- und Musik-Ordner und Pfadformat.")
        saved = self.settings.value("fmt", "device")
        self.fmt.setCurrentIndex(max(0, self.fmt.findData("device" if saved == "m3u" else saved)))
        self.fmt.currentIndexChanged.connect(self.fmt_changed)
        self.fmt.setMinimumWidth(250)
        self.save_btn = QPushButton("Playlist speichern", objectName="primary")
        self.save_btn.setMinimumWidth(150)
        self.save_btn.clicked.connect(self.save_m3u)
        foot.addSpacing(8)
        foot.addWidget(self.copy_btn)
        foot.addWidget(self.fmt)
        foot.addWidget(self.save_btn)
        self.fmt_changed()
        v.addLayout(foot)
        self.update_footer()

        self.dup = DupTab(self)
        self.tabs.addTab(self.dup, "Duplikate")
        self.tagtab = TagTab(self)
        self.tabs.addTab(self.tagtab, "Tags")
        self.tabs.setCurrentIndex(self.settings.value("tab", 0, type=int))
        self.tabs.currentChanged.connect(lambda i: self.settings.setValue("tab", i))

        try:
            core.LEARNED.update(json.loads(self.settings.value("device_learned", "") or "{}"))
        except ValueError:
            pass
        self.load_queue()
        last = self.settings.value("folder", "")
        if last and os.path.isdir(last):
            self.set_folder(last)

    # ------------------------------------------------------------------ Jobs
    def run(self, fn, done, *args, **kw):
        job = Job(fn, *args, **kw)
        self.jobs.add(job)

        def fin(res):
            self.jobs.discard(job)
            self.bar.setVisible(bool(self.jobs))
            done(res)

        def fail(msg):
            self.jobs.discard(job)
            self.bar.setVisible(bool(self.jobs))
            self.on_error(fn, msg)

        def prog(i, n):
            self.bar.setRange(0, max(n, 1))
            self.bar.setValue(i)

        job.s.done.connect(fin)
        job.s.failed.connect(fail)
        job.s.progress.connect(prog)
        self.bar.setRange(0, 0)
        self.bar.setVisible(True)
        self.pool.start(job)

    def on_error(self, fn, msg):
        if fn is _fetch:
            self.pending_loads = max(0, getattr(self, "pending_loads", 1) - 1)
            self.set_hint(self.pl_hint, msg, "hintBad")
        elif fn is core.scan_folder:
            self.set_hint(self.dir_hint, msg, "hintBad")
        else:
            QMessageBox.warning(self, "Plattenkiste", msg)

    @staticmethod
    def set_hint(lbl, text, kind="hint"):
        lbl.setText(text)
        lbl.setObjectName(kind)
        lbl.style().unpolish(lbl)
        lbl.style().polish(lbl)

    # ------------------------------------------------------------------ Playlist
    def load_playlist(self):
        text = self.link.text().strip()
        if not text:
            return
        links = [l for l in re.split(r"[\s,;]+", text) if l]
        valid = []
        for l in links:
            try:
                core.parse_spotify_link(l)
                valid.append(l)
            except core.SpotifyError as e:
                self.set_hint(self.pl_hint, f"{_esc(l[:60])}: {e}", "hintBad")
        if not valid:
            return
        self.link.clear()
        self.set_hint(self.pl_hint, f"Lade {len(valid)} Playlist{'s' if len(valid) > 1 else ''} …")
        cid = self.settings.value("client_id", "")
        sec = self.settings.value("client_secret", "")
        self.pending_loads = getattr(self, "pending_loads", 0) + len(valid)
        for l in valid:
            self.run(_fetch, lambda pl, l=l: self.playlist_loaded(pl, l), l, cid, sec)

    def import_csv(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Playlist-CSV wählen", "", "CSV (*.csv *.tsv *.txt)")
        for p in paths:
            try:
                self.playlist_loaded(core.load_csv(p), "")
            except Exception as e:
                self.set_hint(self.pl_hint, f"CSV konnte nicht gelesen werden: {e}", "hintBad")

    def playlist_loaded(self, pl: core.Playlist, link: str = ""):
        self.pending_loads = max(0, getattr(self, "pending_loads", 1) - 1)
        it = QueueItem(pl, link)
        existing = next((q for q in self.queue if q.key() == it.key()), None)
        if existing:
            # Erneut eingefügt: Titel aktualisieren, eigene Zuordnungen behalten
            existing.playlist, existing.matches = pl, None
            it = existing
        else:
            self.queue.append(it)
        text = f"<b>{_esc(pl.name)}</b> · {len(pl.tracks)} Titel" + (" · aktualisiert" if existing else " · in der Queue")
        if pl.note:
            text += f"<br><span style='color:{C['warn']}'>{_esc(pl.note)}</span>"
        if self.pending_loads:
            text += f" · noch {self.pending_loads} …"
        self.set_hint(self.pl_hint, text, "hintOk")
        self.save_queue()
        self.activate(it)
        self.queue_panel.rebuild()

    # ------------------------------------------------------------------ Queue
    def activate(self, it: QueueItem):
        self.active = it
        self.playlist = it.playlist
        pl = it.playlist
        hint = f"Aktiv: <b>{_esc(pl.name)}</b> · {len(pl.tracks)} Titel"
        if pl.note:
            hint += f"<br><span style='color:{C['warn']}'>{_esc(pl.note)}</span>"
        if getattr(self, "pending_loads", 0):
            hint += f" · lade noch {self.pending_loads} …"
        self.set_hint(self.pl_hint, hint, "hintOk")
        if it.matches is not None and it.files_ref == id(self.files):
            self.show_matches(it.matches)
        else:
            self.model.set_matches([], self.folder)
            self.table.setVisible(False)
            self.empty.setVisible(True)
            self.empty.setText("Gleiche ab …" if self.files is not None else "Wähle einen Musikordner – der Abgleich startet dann automatisch.")
            self.update_footer()
            self.match_item(it)
        self.queue_panel.refresh()
        self.settings.setValue("queue_active", self.queue.index(it) if it in self.queue else 0)

    def match_item(self, it: QueueItem):
        if self.files is None or it.busy:
            return
        it.busy = True
        files = self.files
        self.run(_match, lambda ms, it=it, files=files: self.item_matched(it, ms, files), it.playlist.tracks, files)

    def item_matched(self, it: QueueItem, matches, files):
        it.busy = False
        if files is not self.files:  # Ordner wurde inzwischen gewechselt
            self.match_item(it)
            return
        # von Hand gewählte Dateien wiederherstellen
        by_path = {f.path: f for f in files}
        for idx, path in it.manual.items():
            i = int(idx)
            if 0 <= i < len(matches):
                if not path:
                    matches[i].file, matches[i].score, matches[i].manual = None, 0, False
                elif os.path.exists(path):
                    matches[i].file = by_path.get(path) or core.read_file(path)
                    matches[i].score, matches[i].manual = 100, True
        it.matches, it.files_ref = matches, id(files)
        if it is self.active:
            self.show_matches(matches)
        self.queue_panel.refresh()

    def show_matches(self, matches):
        self.model.set_matches(matches, self.folder)
        self.table.setVisible(True)
        self.empty.setVisible(False)
        self.update_footer()

    def remove_from_queue(self, it: QueueItem):
        if it not in self.queue:
            return
        i = self.queue.index(it)
        self.queue.remove(it)
        if it is self.active:
            self.active = None
            self.playlist = None
            if self.queue:
                self.activate(self.queue[min(i, len(self.queue) - 1)])
            else:
                self.model.set_matches([], self.folder)
                self.table.setVisible(False)
                self.empty.setVisible(True)
                self.empty.setText("Füge oben einen Playlist-Link hinzu.")
                self.update_footer()
        self.save_queue()
        self.queue_panel.rebuild()

    def clear_queue(self):
        if QMessageBox.question(self, "Queue leeren", f"Alle {len(self.queue)} Playlists aus der Queue entfernen?") != QMessageBox.Yes:
            return
        for it in list(self.queue):
            self.remove_from_queue(it)

    def queue_file(self):
        d = os.path.join(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation) or os.path.expanduser("~"), "Plattenkiste")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "queue.json")

    def save_queue(self):
        data = [{"link": it.link, "name": it.playlist.name, "note": it.playlist.note,
                 "tracks": [asdict(t) for t in it.playlist.tracks], "manual": it.manual} for it in self.queue]
        try:
            with open(self.queue_file(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass

    def load_queue(self):
        try:
            with open(self.queue_file(), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = []
        for d in data:
            try:
                pl = core.Playlist(d["name"], [core.Track(**t) for t in d["tracks"]], d.get("note", ""))
                self.queue.append(QueueItem(pl, d.get("link", ""), manual=d.get("manual", {})))
            except (KeyError, TypeError):
                continue
        if self.queue:
            i = min(self.settings.value("queue_active", 0, type=int), len(self.queue) - 1)
            self.active = self.queue[i]
            self.playlist = self.active.playlist
            self.set_hint(self.pl_hint, f"Aktiv: <b>{_esc(self.playlist.name)}</b> · {len(self.playlist.tracks)} Titel", "hintOk")
        self.queue_panel.rebuild()

    def all_matches(self):
        """Treffer für alle Playlists der Queue (fehlende werden jetzt berechnet)"""
        out = []
        for it in self.queue:
            if it.matches is None or it.files_ref != id(self.files):
                self.item_matched(it, core.match_tracks(it.playlist.tracks, self.files), self.files)
            out.append(it)
        return out

    def save_all(self):
        if not self.queue or self.files is None:
            return
        fmt = self.fmt.currentData()
        start = core.musicbee_playlist_dir() if fmt == "xautopf" else self.folder
        target = QFileDialog.getExistingDirectory(self, "Ordner für die Playlists wählen", start or self.folder or os.path.expanduser("~"))
        if not target:
            return
        ext = ".xautopf" if fmt == "xautopf" else ".m3u"
        outside = 0
        if fmt == "device":
            outside = sum(core.outside_paths(os.path.join(target, "x.m3u"), it.matches, self.model.threshold) for it in self.all_matches())
            if outside and QMessageBox.warning(
                    self, "Alle speichern",
                    f"{outside} Song(s) liegen nicht unterhalb von „{target}“ – auf einem MP3-Player würden sie fehlen.\n\n"
                    "Am besten im Musikordner speichern. Trotzdem fortfahren?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                return
        n = 0
        for it in self.all_matches():
            name = re.sub(r'[\\/:*?"<>|]+', "_", it.playlist.name).strip() or "Playlist"
            p = os.path.join(target, name + ext)
            if fmt == "xautopf":
                core.write_xautopf(p, it.playlist.name, it.matches, self.model.threshold)
            else:
                core.write_m3u(p, it.playlist.name, it.matches, self.model.threshold, relative=fmt == "device", sep="/")
            n += 1
        self.set_hint(self.dir_hint, f"<b>{n}</b> Playlists gespeichert in <b>{_esc(target)}</b>", "hintOk")

    def device_all(self):
        if not self.queue or self.files is None:
            return
        items = self.all_matches()
        jobs = [(it.playlist.name, it.matches) for it in items]
        songs = {m.file.path: m for _, ms in jobs for m in core.playlist_entries(ms, self.model.threshold)}
        sample = next(iter(songs.values()), None)
        d = DeviceDialog(self, f"{len(jobs)} Playlists · {len(songs)} Songs ({_fmt_size(sum(m.file.size for m in songs.values()))})",
                         sample, self.device_tests)
        if not d.exec():
            return
        v = d.values()
        self.set_hint(self.dir_hint, "Schreibe aufs Gerät …")
        self.run(_copy_device_all, self.device_all_done, v["target"], jobs, self.model.threshold, self.folder,
                 music_dir=v["music_dir"], playlist_dir=v["playlist_dir"], style=v["style"], copy=v["copy"])

    def device_all_done(self, res):
        copied, skipped, n, missing = res
        msg = f"{n} Playlists gespeichert"
        if copied or skipped:
            msg += f", {copied} Songs neu kopiert ({skipped} waren schon da)"
        msg += "."
        if missing:
            uniq = sorted(set(missing))
            msg += f"\n\n{len(uniq)} Song(s) nicht auf der Karte gefunden:\n" + "\n".join("• " + x for x in uniq[:15])
        self.set_hint(self.dir_hint, f"<b>{n}</b> Playlists aufs Gerät geschrieben" + (f" · {len(set(missing))} Songs nicht gefunden" if missing else ""), "hintOk")
        (QMessageBox.warning if missing else QMessageBox.information)(self, "Fertig", msg)

    def edit_api(self):
        d = ApiDialog(self, self.settings.value("client_id", ""), self.settings.value("client_secret", ""))
        if d.exec():
            self.settings.setValue("client_id", d.cid.text().strip())
            self.settings.setValue("client_secret", d.secret.text().strip())

    # ------------------------------------------------------------------ Ordner
    def pick_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Musikordner wählen", self.folder or os.path.expanduser("~"))
        if p:
            self.set_folder(p)

    def set_folder(self, p):
        self.folder = p
        self.path.setText(p)
        self.settings.setValue("folder", p)
        self.rescan()

    def rescan(self):
        self.settings.setValue("recursive", self.recursive.isChecked())
        self.settings.setValue("allfmt", self.allfmt.isChecked())
        if not self.folder:
            return
        self.files = None
        self.scan_id = getattr(self, "scan_id", 0) + 1
        sid = self.scan_id
        self.set_hint(self.dir_hint, "Lese Tags …")
        # Nur das Ergebnis des zuletzt gestarteten Scans zählt (schneller Ordnerwechsel)
        self.run(core.scan_folder, lambda files, sid=sid: sid == self.scan_id and self.folder_scanned(files), self.folder,
                 recursive=self.recursive.isChecked(), all_formats=self.allfmt.isChecked())

    def folder_scanned(self, files):
        self.files = files
        kind = "Audiodateien" if self.allfmt.isChecked() else "FLAC-Dateien"
        folders = getattr(files, "folders", 0)
        errors = getattr(files, "errors", [])
        where = f" in {folders:,} Ordnern".replace(",", ".") if folders > 1 else ""
        if files:
            text = f"<b>{len(files):,}</b> {kind} gefunden".replace(",", ".") + where
        else:
            text = f"Keine {kind} gefunden" + where + "."
        if errors:
            text += f"<br><span style='color:{C['warn']}'>⚠ {len(errors)} Ordner/Dateien nicht lesbar (Maus drüber für Details)</span>"
            self.dir_hint.setToolTip("\n".join(errors[:30]))
        else:
            self.dir_hint.setToolTip("")
        self.set_hint(self.dir_hint, text, "hintOk" if files else "hintBad")
        self.try_match()

    # ------------------------------------------------------------------ Abgleich
    def try_match(self):
        """Nach einem (neuen) Ordner-Scan: alle Playlists der Queue neu abgleichen, die aktive zuerst"""
        if self.files is None:
            return
        for it in self.queue:
            it.matches = None
        if self.active:
            self.activate(self.active)
        for it in self.queue:
            if it is not self.active:
                self.match_item(it)
        self.queue_panel.refresh()

    def matched(self, matches):
        self.show_matches(matches)

    def threshold_changed(self, v):
        self.thr_lbl.setText(f"{v} %")
        self.settings.setValue("threshold", v)
        self.model.threshold = v
        self.model.refresh()
        self.proxy.invalidateFilter()
        self.update_footer()
        self.queue_panel.refresh()

    def update_footer(self):
        ms = self.model.matches
        counts = {OK: 0, WARN: 0, MISS: 0}
        for m in ms:
            counts[self.model.status(m)] += 1
        if ms:
            dot = lambda k: f"<span style='color:{STATUS_COL[k]}'>●</span>"
            self.summary.setText(f"{dot(OK)} {counts[OK]} gefunden &nbsp;&nbsp; {dot(WARN)} {counts[WARN]} prüfen"
                                 f" &nbsp;&nbsp; {dot(MISS)} {counts[MISS]} fehlen"
                                 f" &nbsp;&nbsp;<span style='color:{C['faint']}'>· Doppelklick zum Ändern</span>")
        else:
            self.summary.setText("")
        for k, label in ((OK, "Gefunden"), (WARN, "Prüfen"), (MISS, "Fehlt")):
            self.seg_btns[k].setText(f"{label}  {counts[k]}" if ms else label)
        self.seg_btns["all"].setText(f"Alle  {len(ms)}" if ms else "Alle")
        self.save_btn.setEnabled(counts[OK] + counts[WARN] > 0)
        self.copy_btn.setEnabled(counts[MISS] > 0)

    def row_menu(self, pos):
        pidx = self.table.indexAt(pos)
        if not pidx.isValid():
            return
        row = self.proxy.mapToSource(pidx).row()
        m = self.model.matches[row]
        menu = QMenu(self)
        alts = [(f, s) for f, s in m.alternatives if s >= 40][:6]
        if alts:
            hdr = QAction("Vorschläge", menu)
            hdr.setEnabled(False)
            menu.addAction(hdr)
        for f, s in alts:
            mark = "✓  " if m.file and f.path == m.file.path else "    "
            a = menu.addAction(f"{mark}{f.artist} – {f.title}   ·  {s:.0f} %")
            a.triggered.connect(lambda _=False, f=f, s=s: self.assign(row, f, s, True))
        if alts:
            menu.addSeparator()
        menu.addAction("Andere Datei wählen …").triggered.connect(lambda: self.assign_file(row))
        if m.file:
            menu.addAction("Zuordnung entfernen").triggered.connect(lambda: self.assign(row, None, 0, False))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def assign(self, row, f, score, manual):
        m = self.model.matches[row]
        m.file, m.score, m.manual = f, score, manual
        if self.active is not None and (manual or f is None):
            # Zuordnung gehört zur Playlist und bleibt beim Wechseln/Neustart erhalten
            self.active.manual[str(row)] = f.path if f else ""
            self.save_queue()
        self.model.refresh()
        self.proxy.invalidateFilter()
        self.update_footer()
        self.queue_panel.refresh()

    def assign_file(self, row):
        exts = " ".join(f"*{e}" for e in sorted(core.FLAC_EXT | core.OTHER_EXT))
        p, _ = QFileDialog.getOpenFileName(self, "Datei zuordnen", self.folder, f"Audio ({exts})")
        if p:
            self.assign(row, core.read_file(p), 100, True)

    # ------------------------------------------------------------------ Export
    def fmt_changed(self, *_):
        fmt = self.fmt.currentData()
        self.settings.setValue("fmt", fmt)
        transfer = fmt == "transfer"
        self.save_btn.setText("Übertragen …" if transfer else "Playlist speichern")
        self.save_btn.setToolTip("Songs und Playlist auf SD-Karte / MP3-Player übertragen" if transfer else "Playlist-Datei im gewählten Format speichern")
        if hasattr(self, "queue_panel"):
            self.queue_panel.save_all.setText("Alle übertragen …" if transfer else "Alle speichern")
            self.queue_panel.save_all.setToolTip("Die Songs aller Playlists samt Playlist-Dateien aufs Gerät übertragen" if transfer
                                                 else "Für jede Playlist der Queue eine Datei im gewählten Format speichern")

    def save_m3u(self):
        if self.fmt.currentData() == "transfer":
            return self.copy_to_device()
        name = re.sub(r'[\\/:*?"<>|]+', "_", self.playlist.name if self.playlist else "playlist").strip() or "playlist"
        fmt = self.fmt.currentData()
        if fmt == "xautopf":
            folder = core.musicbee_playlist_dir() or self.settings.value("save_dir", self.folder) or self.folder
            start, filt = os.path.join(folder, f"{name}.xautopf"), "MusicBee-Auto-Playlist (*.xautopf)"
        elif fmt == "device":
            # Für Geräte gehört die Playlist in den Musikordner, damit alle Pfade „nach unten“ zeigen
            start, filt = os.path.join(self.folder or os.path.expanduser("~"), f"{name}.m3u"), "M3U-Playlist (*.m3u *.m3u8)"
        else:
            start = os.path.join(self.settings.value("save_dir", self.folder) or self.folder, f"{name}.m3u")
            filt = "M3U-Playlist (*.m3u *.m3u8)"
        p, _ = QFileDialog.getSaveFileName(self, "Playlist speichern", start, filt)
        if not p:
            return
        if not os.path.splitext(p)[1]:
            p += ".xautopf" if fmt == "xautopf" else ".m3u"
        if fmt == "device":
            outside = core.outside_paths(p, self.model.matches, self.model.threshold)
            if outside:
                box = QMessageBox(QMessageBox.Warning, "Playlist speichern",
                                  f"{outside} Song(s) liegen nicht unterhalb von „{os.path.dirname(p)}“.\n\n"
                                  "Auf einem MP3-Player oder Handy findet die Playlist diese Songs nicht. "
                                  "Speichere die Playlist am besten direkt im Musikordner – oder nutze „Auf MP3-Player kopieren“.",
                                  QMessageBox.Cancel, self)
                into = box.addButton("Im Musikordner speichern", QMessageBox.AcceptRole)
                anyway = box.addButton("Trotzdem hier speichern", QMessageBox.DestructiveRole)
                box.exec()
                if box.clickedButton() is into:
                    p = os.path.join(self.folder, os.path.basename(p))
                elif box.clickedButton() is not anyway:
                    return
        elif fmt == "abs":
            self.settings.setValue("save_dir", os.path.dirname(p))
        try:
            if fmt == "xautopf":
                n = core.write_xautopf(p, self.playlist.name, self.model.matches, self.model.threshold)
            else:
                n = core.write_m3u(p, self.playlist.name, self.model.matches, self.model.threshold,
                                   relative=fmt == "device", sep="/")
        except OSError as e:
            QMessageBox.warning(self, "Plattenkiste", f"Speichern fehlgeschlagen:\n{e}")
            return
        miss = len(self.model.matches) - n
        hint = f"Gespeichert: <b>{_esc(os.path.basename(p))}</b> · {n} Titel" + (f", {miss} ausgelassen" if miss else "")
        if fmt == "device":
            hint += "<br>Kopiere den Musikordner samt Playlist aufs Gerät – die Pfade passen dann."
        if fmt == "xautopf" and not core.musicbee_playlist_dir():
            hint += "<br>In MusicBee: Rechtsklick auf „Playlists“ → Playlist importieren."
        self.set_hint(self.dir_hint, hint, "hintOk")

    def copy_to_device(self):
        entries = core.playlist_entries(self.model.matches, self.model.threshold)
        if not entries:
            return
        size = sum(m.file.size for m in entries)
        d = DeviceDialog(self, f"„{self.playlist.name}“ · {len(entries)} Songs ({_fmt_size(size)})", entries[0], self.device_tests)
        if not d.exec():
            return
        v = d.values()
        self.set_hint(self.dir_hint, "Schreibe aufs Gerät …")
        self.run(_copy_device, self.device_done, v["target"], self.playlist.name, self.model.matches, self.model.threshold,
                 self.folder, music_dir=v["music_dir"], playlist_dir=v["playlist_dir"], style=v["style"], copy=v["copy"])

    def device_tests(self, v):
        try:
            paths = core.write_device_tests(v["target"], self.model.matches, self.model.threshold, self.folder,
                                            music_dir=v["music_dir"], playlist_dir=v["playlist_dir"], copy=v["copy"])
        except OSError as e:
            QMessageBox.warning(self, "Testplaylists", f"Konnte nicht schreiben:\n{e}")
            return
        styles = list(core.PATH_STYLES.values())
        QMessageBox.information(self, "Testplaylists erstellt",
                                "Im Playlist-Ordner liegen jetzt:\n\n" +
                                "\n".join(f"• Test {'ABCDE'[i]}: {styles[i]}" for i in range(len(paths))) +
                                "\n\nAm Player die Datenbank aktualisieren und nachsehen, welche Test-Playlist Songs zeigt. "
                                "Dieses Format dann hier unter „Pfadformat“ wählen. Die Test-Playlists kannst du danach löschen.")

    def device_done(self, res):
        copied, skipped, pl, missing = res
        hiby = "\n\nHiBy: am Player unter Musik → Zahnrad → „Datenbank aktualisieren“." if self.settings.value("device_profile") == "hiby" else ""
        total = len(core.playlist_entries(self.model.matches, self.model.threshold))
        put = total - len(missing)
        rel = os.path.relpath(pl, self.settings.value("device_dir", "") or os.path.dirname(pl))
        msg = f"Playlist gespeichert: {rel}\n{put} Songs eingetragen"
        if copied or skipped:
            msg += f" ({copied} neu kopiert, {skipped} waren schon da)"
        if missing:
            msg += f"\n\n{len(missing)} Song(s) nicht auf der Karte gefunden – sie fehlen in der Playlist:\n" + "\n".join("• " + x for x in missing[:15])
            if len(missing) > 15:
                msg += f"\n… und {len(missing) - 15} weitere"
        self.set_hint(self.dir_hint, f"Playlist <b>{_esc(os.path.basename(pl))}</b> gespeichert · {put} Songs"
                      + (f" · <span style='color:{C['warn']}'>{len(missing)} nicht auf der Karte</span>" if missing else ""), "hintOk")
        (QMessageBox.warning if missing else QMessageBox.information)(self, "Fertig", msg + hiby)

    def copy_missing(self):
        lines = [f"{m.track.artist_str} – {m.track.title}" for m in self.model.matches
                 if self.model.status(m) == MISS]
        QGuiApplication.clipboard().setText("\n".join(lines))
        self.summary.setText(self.summary.text().split("&nbsp;&nbsp;<span")[0]
                             + f" &nbsp;&nbsp;<span style='color:{C['faint']}'>· {len(lines)} Titel kopiert</span>")


# --------------------------------------------------------------------------- Reiter: Duplikate
def _fmt_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024


def _fmt_len(s):
    if not s:
        return ""
    s = int(round(s))
    return f"{s // 60}:{s % 60:02d}"


def _scan_dupes(folder, recursive, all_formats, include_comp, progress=None):
    files = core.scan_folder(folder, recursive, all_formats,
                             progress=lambda i, n: progress(i, n * 2) if progress else None)
    return dupes.find_duplicates(files, include_comp,
                                 progress=lambda i, n: progress(n + i, n * 2) if progress else None)


def _remove(paths, mode, root, progress=None):
    return dupes.remove_files(paths, mode, root, progress)


class DupTab(QWidget):
    COLS = ["TITEL / DATEI", "ALBUM", "FORMAT", "LÄNGE", "GRÖSSE", "AKTION"]

    def __init__(self, main: "Main"):
        super().__init__(objectName="page")
        self.main = main
        self.settings = main.settings
        self.groups: list[dupes.DupGroup] = []
        self.folder = ""
        self.busy = False
        self._updating = False
        self.jobs = set()

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 20, 0, 0)
        v.setSpacing(18)

        c, l = card("AUFRÄUMEN", "Doppelte Titel finden")
        row = QHBoxLayout()
        self.path = QLineEdit(placeholderText="Musikordner wählen")
        self.path.setReadOnly(True)
        pick = QPushButton("Ordner wählen …")
        pick.clicked.connect(self.pick_folder)
        self.search_btn = QPushButton("Duplikate suchen", objectName="primary")
        self.search_btn.clicked.connect(self.search)
        row.addWidget(self.path, 1)
        row.addWidget(pick)
        row.addWidget(self.search_btn)
        l.addLayout(row)
        opts = QHBoxLayout()
        self.recursive = QCheckBox("Unterordner")
        self.recursive.setChecked(True)
        self.allfmt = QCheckBox("auch MP3, M4A, OGG …")
        self.allfmt.setChecked(self.settings.value("dup_allfmt", True, type=bool))
        self.allfmt.setToolTip("Findet z. B. eine MP3-Kopie eines Songs, den du schon als FLAC hast.")
        self.comp = QCheckBox("Best-of und Sampler einbeziehen")
        self.comp.setChecked(self.settings.value("dup_comp", True, type=bool))
        self.comp.setToolTip("Songs auf „Greatest Hits“ & Co. gelten als Duplikat, das Original-Album wird behalten.")
        for cb in (self.recursive, self.allfmt, self.comp):
            opts.addWidget(cb)
        opts.addStretch()
        l.addLayout(opts)
        self.hint = QLabel("Behalten wird immer die vollständigste Edition (Deluxe, Expanded, Anniversary …), "
                           "danach das Original-Album statt Best-of, danach die bessere Qualität. "
                           "Live-, Remix- und Akustik-Versionen gelten nicht als Duplikat.", objectName="hint")
        self.hint.setWordWrap(True)
        l.addWidget(self.hint)
        v.addWidget(c)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setVisible(False)
        v.addWidget(self.bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(self.COLS)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setAllColumnsShowFocus(True)
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setTextElideMode(Qt.ElideMiddle)
        hh = self.tree.header()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, w in ((1, 230), (2, 100), (3, 60), (4, 80), (5, 250)):
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
            self.tree.setColumnWidth(col, w)
        self.tree.itemChanged.connect(self.item_changed)
        self.tree.setVisible(False)
        self.empty = QLabel("Ordner wählen und „Duplikate suchen“ klicken.", alignment=Qt.AlignCenter, objectName="hint")
        v.addWidget(self.tree, 1)
        v.addWidget(self.empty, 1)

        foot = QHBoxLayout()
        self.summary = QLabel("", objectName="hint")
        foot.addWidget(self.summary)
        foot.addStretch()
        self.mode = QComboBox()
        self.mode.addItem("In den Papierkorb", "trash")
        self.mode.addItem("In Ordner „_Duplikate“ verschieben", "move")
        if dupes.send2trash is None:
            self.mode.model().item(0).setEnabled(False)
            self.mode.setCurrentIndex(1)
        else:
            self.mode.setCurrentIndex(self.settings.value("dup_mode", 0, type=int))
        self.mode.currentIndexChanged.connect(lambda i: self.settings.setValue("dup_mode", i))
        self.remove_btn = QPushButton("Entfernen", objectName="danger")
        self.remove_btn.setMinimumWidth(150)
        self.remove_btn.clicked.connect(self.remove)
        foot.addWidget(self.mode)
        foot.addSpacing(8)
        foot.addWidget(self.remove_btn)
        v.addLayout(foot)
        self.update_summary()

        last = self.settings.value("dup_folder", "") or self.settings.value("folder", "")
        if last and os.path.isdir(last):
            self.folder = last
            self.path.setText(last)

    # ------------------------------------------------------------------ Hintergrund
    def run(self, fn, done, *args):
        job = Job(fn, *args)
        self.jobs.add(job)
        self.busy = True
        self.search_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)

        def end():
            self.jobs.discard(job)
            self.busy = False
            self.bar.setVisible(False)
            self.search_btn.setEnabled(True)

        def fin(res):
            end()
            done(res)

        def fail(msg):
            end()
            self.update_summary()
            QMessageBox.warning(self, "Plattenkiste", msg)

        def prog(i, n):
            self.bar.setRange(0, max(n, 1))
            self.bar.setValue(i)

        job.s.done.connect(fin)
        job.s.failed.connect(fail)
        job.s.progress.connect(prog)
        self.bar.setRange(0, 0)
        self.bar.setVisible(True)
        self.main.pool.start(job)

    # ------------------------------------------------------------------ Suche
    def pick_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Musikordner wählen", self.folder or os.path.expanduser("~"))
        if p:
            self.folder = p
            self.path.setText(p)
            self.settings.setValue("dup_folder", p)
            self.search()

    def search(self):
        if not self.folder:
            self.pick_folder()
            return
        self.settings.setValue("dup_allfmt", self.allfmt.isChecked())
        self.settings.setValue("dup_comp", self.comp.isChecked())
        self.summary.setText("Lese Tags und vergleiche …")
        self.run(_scan_dupes, self.found, self.folder, self.recursive.isChecked(),
                 self.allfmt.isChecked(), self.comp.isChecked())

    def found(self, groups):
        self.groups = groups
        self.fill()
        self.tree.setVisible(bool(groups))
        self.empty.setVisible(not groups)
        if not groups:
            self.empty.setText("Keine Duplikate gefunden – deine Sammlung ist sauber.")

    def _rel(self, p):
        try:
            return os.path.relpath(p, self.folder)
        except ValueError:
            return p

    def fill(self):
        self._updating = True
        self.tree.clear()
        bold = QFont(self.tree.font())
        bold.setBold(True)
        for g in self.groups:
            top = QTreeWidgetItem([f"{g.artist} – {g.title}", "", "", "", "", f"{len(g.files)} Kopien"])
            top.setFont(0, bold)
            top.setForeground(5, QColor(C["faint"]))
            top.setFlags(Qt.ItemIsEnabled)
            for d in g.files:
                f = d.file
                ch = QTreeWidgetItem([self._rel(f.path), f.album or "—", dupes.quality_label(f),
                                      _fmt_len(f.duration_s), _fmt_size(f.size), ""])
                ch.setData(0, Qt.UserRole, d)
                ch.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                ch.setCheckState(0, Qt.Unchecked if d.keep else Qt.Checked)
                ch.setToolTip(0, f.path)
                for col in (1, 2, 3, 4):
                    ch.setForeground(col, QColor(C["muted"]))
                top.addChild(ch)
                self._style_child(ch)
            self.tree.addTopLevelItem(top)
        if len(self.groups) <= 400:
            self.tree.expandAll()
        self._updating = False
        self.update_summary()

    def _style_child(self, ch):
        d: dupes.DupFile = ch.data(0, Qt.UserRole)
        remove = ch.checkState(0) == Qt.Checked
        if remove:
            ch.setText(5, "●  Entfernen")
            ch.setForeground(5, QColor(C["bad"]))
            ch.setForeground(0, QColor(C["muted"]))
        else:
            ch.setText(5, "●  Behalten" + (f" · {d.reason}" if d.keep and d.reason else ""))
            ch.setForeground(5, QColor(C["ok"]))
            ch.setForeground(0, QColor(C["text"]))

    def item_changed(self, item, col):
        if self._updating or col != 0 or item.parent() is None:
            return
        self._updating = True
        self._style_child(item)
        self._updating = False
        self.update_summary()

    def checked(self):
        out, orphans = [], 0
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            kids = [top.child(j) for j in range(top.childCount())]
            sel = [k for k in kids if k.checkState(0) == Qt.Checked]
            if kids and len(sel) == len(kids):
                orphans += 1
            out.extend(sel)
        return out, orphans

    def update_summary(self):
        if not self.groups:
            self.summary.setText("")
            self.remove_btn.setEnabled(False)
            self.remove_btn.setText("Entfernen")
            return
        sel, orphans = self.checked()
        size = sum(k.data(0, Qt.UserRole).file.size for k in sel)
        dot = lambda k: f"<span style='color:{STATUS_COL[k]}'>●</span>"
        txt = (f"<b>{len(self.groups)}</b> Gruppen &nbsp;&nbsp; {dot(MISS)} {len(sel)} zum Entfernen"
               f" &nbsp;&nbsp;<span style='color:{C['faint']}'>· {_fmt_size(size)} frei</span>")
        if orphans:
            txt += f" &nbsp;&nbsp;<span style='color:{C['warn']}'>⚠ in {orphans} Gruppe(n) bliebe nichts übrig</span>"
        self.summary.setText(txt)
        self.remove_btn.setText(f"Entfernen ({len(sel)})" if sel else "Entfernen")
        self.remove_btn.setEnabled(bool(sel) and not self.busy)

    # ------------------------------------------------------------------ Entfernen
    def remove(self):
        sel, orphans = self.checked()
        if not sel:
            return
        mode = self.mode.currentData()
        size = sum(k.data(0, Qt.UserRole).file.size for k in sel)
        where = "in den Papierkorb verschoben" if mode == "trash" else \
            f"nach „{os.path.join(self.folder, '_Duplikate')}“ verschoben"
        msg = f"{len(sel)} Dateien ({_fmt_size(size)}) werden {where}."
        if orphans:
            msg += f"\n\nAchtung: In {orphans} Gruppe(n) sind alle Kopien markiert – dort bliebe keine Datei übrig."
        box = QMessageBox(QMessageBox.Warning, "Duplikate entfernen", msg, QMessageBox.Cancel, self)
        go = box.addButton("Entfernen", QMessageBox.AcceptRole)
        go.setObjectName("danger")
        box.exec()
        if box.clickedButton() is not go:
            return
        self.summary.setText("Entferne …")
        paths = [k.data(0, Qt.UserRole).file.path for k in sel]
        self.run(_remove, lambda res: self.removed(res, paths), paths, mode, self.folder)

    def removed(self, res, paths):
        ok, errors = res
        gone = {p for p in paths if not os.path.exists(p)}
        for g in self.groups:
            g.files = [d for d in g.files if d.file.path not in gone]
        self.groups = [g for g in self.groups if len(g.files) > 1]
        self.fill()
        self.tree.setVisible(bool(self.groups))
        self.empty.setVisible(not self.groups)
        if not self.groups:
            self.empty.setText(f"{ok} Dateien entfernt – keine Duplikate mehr.")
        if errors:
            QMessageBox.warning(self, "Plattenkiste", f"{ok} entfernt, {len(errors)} Fehler:\n\n" + "\n".join(errors[:15]))
        # Playlist-Reiter neu einlesen, falls derselbe Ordner
        mf = os.path.abspath(self.main.folder) if self.main.folder else ""
        df = os.path.abspath(self.folder)
        if mf and (mf.startswith(df) or df.startswith(mf)):
            self.main.rescan()


# --------------------------------------------------------------------------- Tags
class TagModel(QAbstractTableModel):
    HEAD = ["TITEL", "INTERPRET", "ALBUM", "GENRE"]

    def __init__(self):
        super().__init__()
        self.rows: list[tagger.TagFile] = []
        self.checked: set[int] = set()
        self.field = "genre"
        self.changed_cb = None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.checked = {id(r) for r in rows if id(r) in self.checked}
        self.endResetModel()

    def set_field(self, fld):
        self.field = fld
        self.headerDataChanged.emit(Qt.Horizontal, 3, 3)
        self.refresh()

    def refresh(self):
        if self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows) - 1, 3))

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 4

    def headerData(self, s, o, role=Qt.DisplayRole):
        if o == Qt.Horizontal and role == Qt.DisplayRole:
            return tagger.FIELDS[self.field].upper() if s == 3 else self.HEAD[s]
        if o == Qt.Horizontal and role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def flags(self, idx):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        return f | Qt.ItemIsUserCheckable if idx.column() == 0 else f

    def data(self, idx, role=Qt.DisplayRole):
        r = self.rows[idx.row()]
        col = idx.column()
        if role == Qt.DisplayRole:
            f = r.file
            return (f.title, f.artist, f.album or "—", "; ".join(r.values.get(self.field, [])) or "—")[col]
        if role == Qt.CheckStateRole and col == 0:
            return Qt.Checked if id(r) in self.checked else Qt.Unchecked
        if role == Qt.ForegroundRole:
            if col == 3:
                return QColor(C["accent"] if r.values.get(self.field) else C["faint"])
            if col in (1, 2):
                return QColor(C["muted"])
        if role == Qt.ToolTipRole:
            return r.file.path
        if role == Qt.UserRole:
            return r
        return None

    def setData(self, idx, value, role=Qt.EditRole):
        if role == Qt.CheckStateRole and idx.column() == 0:
            self.set_checked([self.rows[idx.row()]], Qt.CheckState(value) == Qt.Checked)
            return True
        return False

    def set_checked(self, rows, on: bool):
        for r in rows:
            (self.checked.add if on else self.checked.discard)(id(r))
        self.refresh()
        if self.changed_cb:
            self.changed_cb()

    def checked_rows(self):
        return [r for r in self.rows if id(r) in self.checked]


class TagProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.text = ""
        self.value = None          # nur Songs mit diesem Wert ("" = ohne Wert)
        self.only_checked = False
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def update(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        m: TagModel = self.sourceModel()
        r = m.rows[row]
        if self.only_checked and id(r) not in m.checked:
            return False
        vals = r.values.get(m.field, [])
        if self.value is not None:
            if self.value == "":
                if vals:
                    return False
            elif self.value.casefold() not in (v.casefold() for v in vals):
                return False
        if self.text:
            f = r.file
            hay = f"{f.title} {f.artist} {f.album} {f.path} {' '.join(vals)}".casefold()
            return all(w in hay for w in self.text.casefold().split())
        return True


class TagTab(QWidget):
    def __init__(self, main: "Main"):
        super().__init__(objectName="page")
        self.main = main
        self.settings = main.settings
        self.folder = ""
        self.busy = False
        self.jobs = set()
        self.undo: list = []
        self.undo_label = ""

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 20, 0, 0)
        v.setSpacing(14)

        c, l = card("TAGS", "Songs per Tag zu einer Playlist machen")
        row = QHBoxLayout()
        self.path = QLineEdit(placeholderText="Musikordner wählen")
        self.path.setReadOnly(True)
        self.path.setToolTip("Tipp: Du kannst auch direkt den Musikordner auf der SD-Karte wählen –\n"
                             "dann landen die Tags sofort auf dem Gerät.")
        pick = QPushButton("Ordner wählen …")
        pick.setToolTip("Ordner mit deinen Songs (inkl. Unterordner)")
        pick.clicked.connect(self.pick_folder)
        self.load_btn = QPushButton("Songs laden", objectName="primary")
        self.load_btn.setToolTip("Liest alle Songs und ihre Tags aus dem Ordner")
        self.load_btn.clicked.connect(self.load)
        row.addWidget(self.path, 1)
        row.addWidget(pick)
        row.addWidget(self.load_btn)
        l.addLayout(row)
        hint = QLabel("Wähle Songs aus einer Playlist, einer M3U oder von Hand und gib ihnen einen gemeinsamen Tag, "
                      "z. B. das Genre „Roadtrip“. Auf Geräten ohne M3U-Unterstützung findest du die Songs dann "
                      "unter Genres wie eine Playlist.", objectName="hint")
        hint.setWordWrap(True)
        l.addWidget(hint)
        v.addWidget(c)

        # Auswahl-Quellen
        src = QHBoxLayout()
        src.setSpacing(8)
        src.addWidget(QLabel("Auswählen aus:", objectName="hint"))
        self.pl_combo = QComboBox()
        self.pl_combo.setMinimumWidth(240)
        self.pl_combo.setToolTip("Playlists aus der Queue im Reiter „Playlist erstellen“")
        self.pl_btn = QPushButton("Playlist übernehmen")
        self.pl_btn.setToolTip("Hakt alle Songs an, die in der gewählten Playlist gefunden wurden")
        self.pl_btn.clicked.connect(self.from_playlist)
        m3u_btn = QPushButton("M3U laden …")
        m3u_btn.setToolTip("Hakt alle Songs einer vorhandenen M3U/M3U8-Playlist an")
        m3u_btn.clicked.connect(self.from_m3u)
        src.addWidget(self.pl_combo)
        src.addWidget(self.pl_btn)
        src.addWidget(m3u_btn)
        src.addStretch()
        self.search = QLineEdit(placeholderText="Suchen: Titel, Interpret, Album …")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(260)
        self.search.textChanged.connect(lambda t: self.proxy.update(text=t.strip()))
        src.addWidget(self.search)
        v.addLayout(src)

        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setVisible(False)
        v.addWidget(self.bar)

        # Tabelle + vorhandene Werte
        mid = QHBoxLayout()
        mid.setSpacing(14)
        self.model = TagModel()
        self.model.changed_cb = self.update_summary
        self.proxy = TagProxy()
        self.proxy.setSourceModel(self.model)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, Qt.AscendingOrder)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(QHeaderView.Interactive)
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, w in ((1, 200), (2, 220), (3, 170)):
            self.table.setColumnWidth(col, w)
        self.table.doubleClicked.connect(self.toggle_row)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.table_menu)
        self.empty = QLabel("Ordner wählen und „Songs laden“ klicken.", alignment=Qt.AlignCenter, objectName="hint")
        left = QVBoxLayout()
        left.addWidget(self.table, 1)
        left.addWidget(self.empty, 1)
        sel_row = QHBoxLayout()
        for txt, tip, fn in (("Alle angezeigten anhaken", "Hakt alle Songs an, die gerade in der Liste stehen", lambda: self.check_visible(True)),
                             ("Angezeigte abhaken", "Entfernt die Haken bei allen angezeigten Songs", lambda: self.check_visible(False)),
                             ("Markierte anhaken", "Hakt die mit Maus/Shift/Strg markierten Zeilen an", self.check_selected),
                             ("Alle Haken entfernen", "Hebt die komplette Auswahl auf", self.clear_checks)):
            b = QPushButton(txt, objectName="link")
            b.setToolTip(tip)
            b.clicked.connect(fn)
            sel_row.addWidget(b)
        sel_row.addStretch()
        self.only_checked = QCheckBox("nur angehakte zeigen")
        self.only_checked.toggled.connect(lambda on: self.proxy.update(only_checked=on))
        sel_row.addWidget(self.only_checked)
        left.addLayout(sel_row)
        mid.addLayout(left, 1)

        side = QFrame(objectName="card")
        side.setFixedWidth(240)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 14, 14, 14)
        self.side_title = QLabel("VORHANDENE GENRES", objectName="step")
        sl.addWidget(self.side_title)
        self.values = QListWidget()
        self.values.setToolTip("Klick: nur Songs mit diesem Wert anzeigen\nDoppelklick: Wert ins Feld unten übernehmen")
        self.values.currentItemChanged.connect(self.value_filter)
        self.values.itemDoubleClicked.connect(lambda it: it.data(Qt.UserRole) and self.value.setText(it.data(Qt.UserRole)))
        sl.addWidget(self.values, 1)
        mid.addWidget(side)
        v.addLayout(mid, 1)

        # Fuß: Tag schreiben
        foot = QHBoxLayout()
        foot.setSpacing(8)
        self.summary = QLabel("", objectName="hint")
        foot.addWidget(self.summary)
        foot.addStretch()
        self.undo_btn = QPushButton("Rückgängig", objectName="link")
        self.undo_btn.setToolTip("Macht die letzte Tag-Änderung rückgängig")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self.do_undo)
        foot.addWidget(self.undo_btn)
        self.field = QComboBox()
        for k, name in tagger.FIELDS.items():
            self.field.addItem(name, k)
        self.field.setToolTip("Welches Feld beschrieben wird. Genre wird von fast allen Playern angezeigt.")
        self.field.setCurrentIndex(max(0, self.field.findData(self.settings.value("tag_field", "genre"))))
        self.field.currentIndexChanged.connect(self.field_changed)
        self.mode = QComboBox()
        for k, name in tagger.MODES.items():
            self.mode.addItem(name, k)
        self.mode.setItemData(0, "Tag zusätzlich zu den vorhandenen Werten eintragen", Qt.ToolTipRole)
        self.mode.setItemData(1, "Alle bisherigen Werte im Feld durch diesen ersetzen", Qt.ToolTipRole)
        self.mode.setItemData(2, "Diesen Tag aus den angehakten Songs löschen", Qt.ToolTipRole)
        self.mode.setToolTip("Hinzufügen behält das bisherige Genre, Ersetzen überschreibt es.")
        self.mode.setCurrentIndex(max(0, self.mode.findData(self.settings.value("tag_mode", "add"))))
        self.mode.currentIndexChanged.connect(self.update_summary)
        self.value = QLineEdit(placeholderText="Tag, z. B. Roadtrip 2026")
        self.value.setMinimumWidth(200)
        self.value.textChanged.connect(self.update_summary)
        self.value.returnPressed.connect(self.write)
        self.joined = QCheckBox("in einem Feld")
        self.joined.setToolTip("Mehrere Werte als „Rock; Roadtrip“ in einem einzigen Eintrag speichern.\n"
                               "Nötig für Player, die nur den ersten Genre-Eintrag lesen.")
        self.joined.setChecked(self.settings.value("tag_joined", False, type=bool))
        self.joined.toggled.connect(lambda on: self.settings.setValue("tag_joined", on))
        self.write_btn = QPushButton("Tag schreiben", objectName="primary")
        self.write_btn.setMinimumWidth(170)
        self.write_btn.clicked.connect(self.write)
        for w in (self.field, self.mode, self.value, self.joined, self.write_btn):
            foot.addWidget(w)
        v.addLayout(foot)

        self.model.field = self.field.currentData()
        self.show_table(False)
        self.update_summary()
        last = self.settings.value("tag_folder", "") or self.settings.value("folder", "")
        if last and os.path.isdir(last):
            self.folder = last
            self.path.setText(last)

    # ------------------------------------------------------------------ Hintergrund
    def run(self, fn, done, *args, **kw):
        job = Job(fn, *args, **kw)
        self.jobs.add(job)
        self.busy = True
        self.load_btn.setEnabled(False)
        self.update_summary()

        def end():
            self.jobs.discard(job)
            self.busy = False
            self.bar.setVisible(False)
            self.load_btn.setEnabled(True)
            self.update_summary()

        def fin(res):
            end()
            done(res)

        def fail(msg):
            end()
            QMessageBox.warning(self, "Plattenkiste", msg)

        def prog(i, n):
            self.bar.setRange(0, max(n, 1))
            self.bar.setValue(i)

        job.s.done.connect(fin)
        job.s.failed.connect(fail)
        job.s.progress.connect(prog)
        self.bar.setRange(0, 0)
        self.bar.setVisible(True)
        self.main.pool.start(job)

    def showEvent(self, e):
        super().showEvent(e)
        self.fill_playlists()
        if not self.model.rows and not self.busy and self.folder and os.path.isdir(self.folder):
            self.load()

    # ------------------------------------------------------------------ Laden
    def pick_folder(self):
        p = QFileDialog.getExistingDirectory(self, "Musikordner wählen", self.folder or os.path.expanduser("~"))
        if p:
            self.folder = p
            self.path.setText(p)
            self.settings.setValue("tag_folder", p)
            self.load()

    def load(self):
        if not self.folder:
            self.pick_folder()
            return
        self.summary.setText("Lese Songs und Tags …")
        self.run(tagger.scan, self.loaded, self.folder)

    def loaded(self, rows):
        self.model.set_rows(rows)
        self.by_path = {r.file.path: r for r in rows}
        self.show_table(bool(rows))
        if not rows:
            self.empty.setText("In diesem Ordner wurden keine Songs gefunden.")
        self.fill_values()
        self.update_summary()

    def show_table(self, on):
        self.table.setVisible(on)
        self.empty.setVisible(not on)

    # ------------------------------------------------------------------ Auswahl
    def fill_playlists(self):
        cur = self.pl_combo.currentText()
        self.pl_combo.clear()
        for it in self.main.queue:
            self.pl_combo.addItem(f"{it.playlist.name} · {len(it.playlist.tracks)} Songs", it)
        if not self.main.queue:
            self.pl_combo.addItem("– keine Playlist in der Queue –", None)
        i = self.pl_combo.findText(cur)
        if i < 0 and self.main.active in self.main.queue:
            i = self.main.queue.index(self.main.active)
        self.pl_combo.setCurrentIndex(max(0, i))
        self.pl_btn.setEnabled(bool(self.main.queue))

    def _need_rows(self):
        if self.model.rows:
            return True
        QMessageBox.information(self, "Plattenkiste", "Lade zuerst die Songs („Ordner wählen“ → „Songs laden“).")
        return False

    def select_found(self, found, missing, what):
        self.model.set_checked(found, True)
        self.only_checked.setChecked(True)
        msg = f"{len(found)} Songs aus {what} angehakt."
        if missing:
            msg += f" {missing} nicht in diesem Ordner gefunden."
        self.summary.setText(msg)
        QTimer.singleShot(2500, self.update_summary)

    def from_playlist(self):
        it = self.pl_combo.currentData()
        if it is None or not self._need_rows():
            return
        m = self.main
        if m.files is None:
            QMessageBox.information(self, "Plattenkiste", "Wähle im Reiter „Playlist erstellen“ einen Musikordner, "
                                    "damit die Songs der Playlist gefunden werden.")
            return
        if it.matches is None or it.files_ref != id(m.files):
            m.item_matched(it, core.match_tracks(it.playlist.tracks, m.files), m.files)
        entries = core.playlist_entries(it.matches, m.model.threshold)
        found, missing = tagger.match_paths([e.file.path for e in entries], self.model.rows)
        missing += len(it.playlist.tracks) - len(entries)
        self.select_found(found, missing, f"„{it.playlist.name}“")
        if not self.value.text().strip():
            self.value.setText(it.playlist.name)

    def from_m3u(self):
        if not self._need_rows():
            return
        p, _ = QFileDialog.getOpenFileName(self, "Playlist wählen", self.folder, "Playlists (*.m3u *.m3u8);;Alle Dateien (*)")
        if not p:
            return
        try:
            paths = tagger.read_m3u(p)
        except OSError as e:
            QMessageBox.warning(self, "Plattenkiste", str(e))
            return
        found, missing = tagger.match_paths(paths, self.model.rows)
        name = os.path.splitext(os.path.basename(p))[0]
        self.select_found(found, missing, f"„{name}“")
        if not self.value.text().strip():
            self.value.setText(name)

    def visible_rows(self):
        return [self.proxy.index(i, 0).data(Qt.UserRole) for i in range(self.proxy.rowCount())]

    def check_visible(self, on):
        self.model.set_checked(self.visible_rows(), on)
        self.proxy.invalidateFilter()

    def check_selected(self, on=True):
        rows = [i.data(Qt.UserRole) for i in self.table.selectionModel().selectedRows(0)]
        self.model.set_checked(rows, on)
        self.proxy.invalidateFilter()

    def clear_checks(self):
        self.model.set_checked(list(self.model.rows), False)
        self.proxy.invalidateFilter()

    def toggle_row(self, idx):
        r = idx.siblingAtColumn(0).data(Qt.UserRole)
        self.model.set_checked([r], id(r) not in self.model.checked)

    def table_menu(self, pos):
        if not self.table.selectionModel().selectedRows():
            return
        menu = QMenu(self)
        menu.addAction("Markierte anhaken", lambda: self.check_selected(True))
        menu.addAction("Markierte abhaken", lambda: self.check_selected(False))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------ Werte
    def field_changed(self):
        fld = self.field.currentData()
        self.settings.setValue("tag_field", fld)
        self.model.set_field(fld)
        self.fill_values()
        self.update_summary()

    def fill_values(self):
        fld = self.model.field
        name = tagger.FIELDS[fld]
        self.side_title.setText(("VORHANDENE GENRES" if fld == "genre" else f"VORHANDENE WERTE · {name.upper()}"))
        counts: dict = {}
        none = 0
        for r in self.model.rows:
            vals = r.values.get(fld, [])
            if not vals:
                none += 1
            for v in vals:
                k = v.casefold()
                c = counts.setdefault(k, [v, 0])
                c[1] += 1
        cur = self.proxy.value
        self.values.blockSignals(True)
        self.values.clear()
        items = [("Alle Songs", None, len(self.model.rows))]
        items += [(v, v, n) for v, n in sorted(counts.values(), key=lambda x: x[0].casefold())]
        if none:
            items.append(("(ohne Wert)", "", none))
        sel = 0
        for i, (label, data, n) in enumerate(items):
            it = QListWidgetItem(f"{label}   ·  {n}")
            it.setData(Qt.UserRole, data)
            self.values.addItem(it)
            if data is not None and cur is not None and data.casefold() == cur.casefold():
                sel = i
        self.values.setCurrentRow(sel)
        self.values.blockSignals(False)
        self.proxy.update(value=self.values.currentItem().data(Qt.UserRole) if self.values.currentItem() else None)
        comp = QCompleter([v for v, _ in counts.values()], self.value)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        self.value.setCompleter(comp)

    def value_filter(self, it, _prev=None):
        self.proxy.update(value=it.data(Qt.UserRole) if it else None)

    # ------------------------------------------------------------------ Schreiben
    def update_summary(self):
        if not hasattr(self, "write_btn"):
            return
        n = len(self.model.checked)
        total = len(self.model.rows)
        if total:
            self.summary.setText(f"<b>{n}</b> von {total} Songs angehakt")
        elif not self.busy:
            self.summary.setText("")
        mode = self.mode.currentData()
        verb = {"add": "Tag schreiben", "replace": "Tag setzen", "remove": "Tag entfernen"}[mode]
        self.write_btn.setText(f"{verb} ({n})" if n else verb)
        self.write_btn.setObjectName("danger" if mode == "remove" else "primary")
        self.write_btn.style().unpolish(self.write_btn)
        self.write_btn.style().polish(self.write_btn)
        self.write_btn.setEnabled(bool(n) and not self.busy and (bool(self.value.text().strip()) or mode == "replace"))
        self.undo_btn.setEnabled(bool(self.undo) and not self.busy)
        self.undo_btn.setText(f"Rückgängig: {self.undo_label}" if self.undo else "Rückgängig")

    def write(self):
        rows = self.model.checked_rows()
        value = self.value.text().strip()
        mode = self.mode.currentData()
        fld = self.field.currentData()
        if not rows or self.busy or (not value and mode != "replace"):
            return
        name = tagger.FIELDS[fld]
        if mode == "replace":
            text = (f"Bei {len(rows)} Songs wird {name} auf „{value}“ gesetzt – vorhandene Werte werden überschrieben."
                    if value else f"Bei {len(rows)} Songs wird {name} komplett gelöscht.")
        elif mode == "remove":
            text = f"„{value}“ wird bei {len(rows)} Songs aus {name} entfernt."
        else:
            text = f"„{value}“ wird bei {len(rows)} Songs zu {name} hinzugefügt."
        text += "\n\nDie Dateien werden direkt geändert. Mit „Rückgängig“ lässt sich das wieder zurücknehmen."
        if QMessageBox.question(self, "Tags schreiben", text, QMessageBox.Ok | QMessageBox.Cancel) != QMessageBox.Ok:
            return
        self.settings.setValue("tag_mode", mode)
        self.summary.setText("Schreibe Tags …")
        label = f"„{value}“" if value else name
        self.run(tagger.apply, lambda res: self.written(res, label, fld), rows, fld, value, mode, joined=self.joined.isChecked())

    def written(self, res, label, fld):
        changed, errors, undo = res
        if undo:
            self.undo, self.undo_label = undo, label
        self.model.refresh()
        self.fill_values()
        self.update_summary()
        msg = f"{changed} Songs geändert" + (", bei den übrigen war der Tag schon so gesetzt." if changed < len(self.model.checked) else ".")
        if errors:
            QMessageBox.warning(self, "Plattenkiste", msg + f"\n\n{len(errors)} Fehler:\n" + "\n".join(errors[:15]))
        elif changed:
            QMessageBox.information(self, "Plattenkiste", msg + "\n\nAuf dem Gerät: geänderte Songs neu draufkopieren "
                                    "(oder direkt die SD-Karte als Ordner wählen) und danach die Musik-Datenbank "
                                    f"aktualisieren. Dann erscheint {label} unter "
                                    f"{'Genres' if fld == 'genre' else tagger.FIELDS[fld]}.")
        else:
            self.summary.setText("Nichts zu ändern – der Tag war schon überall so gesetzt.")

    def do_undo(self):
        if not self.undo or self.busy:
            return
        undo, self.undo = self.undo, []
        self.summary.setText("Mache rückgängig …")
        self.run(tagger.restore, self.undone, undo, getattr(self, "by_path", {}), joined=self.joined.isChecked())

    def undone(self, errors):
        self.model.refresh()
        self.fill_values()
        self.update_summary()
        if errors:
            QMessageBox.warning(self, "Plattenkiste", f"{len(errors)} Fehler beim Zurücksetzen:\n" + "\n".join(errors[:15]))


def _copy_device(target, name, matches, threshold, root, progress=None, **kw):
    return core.copy_to_device(target, name, matches, threshold, root, progress, **kw)


def _copy_device_all(target, jobs, threshold, root, progress=None, **kw):
    copied = skipped = 0
    missing: list[str] = []
    for i, (name, matches) in enumerate(jobs):
        c, s, _, miss = core.copy_to_device(target, name, matches, threshold, root, **kw)
        copied += c
        skipped += s
        missing += miss
        if progress:
            progress(i + 1, len(jobs))
    return copied, skipped, len(jobs), missing


def _fetch(link, cid, sec, progress=None):
    return core.fetch_playlist(link, cid, sec)


def _match(tracks, files, progress=None):
    return core.match_tracks(tracks, files, progress)


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Plattenkiste")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))
    if sys.platform == "win32":
        try:  # eigenes Taskleisten-Icon statt dem von Python
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Plattenkiste.App")
        except Exception:
            pass
    w = Main()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
