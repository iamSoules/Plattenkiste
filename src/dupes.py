"""Doppelte Titel finden – inkl. Deluxe-/Normal-Editionen. Deluxe wird immer bevorzugt."""
from __future__ import annotations

import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

import core

try:
    from send2trash import send2trash
except ImportError:  # pragma: no cover
    send2trash = None

# Stufen: je höher, desto „vollständiger“ die Edition
_EDITION = [
    (3, re.compile(r"super\s*deluxe|ultimate|complete\s+edition|box\s*set", re.I)),
    (2, re.compile(r"deluxe|expanded|anniversary|legacy\s+edition|collector'?s?|platinum|tour\s+edition|"
                   r"special\s+edition|edition\s+speciale|extended\s+edition", re.I)),
    (1, re.compile(r"bonus|limited|extended|edition|reissue|remaster", re.I)),
]
_COMPILATION = re.compile(r"greatest\s+hits|best\s+of|the\s+very\s+best|collection|anthology|"
                          r"essentials|hits\b|singles\b|compilation|bravo|now\s+that'?s|kuschelrock", re.I)
_VARIOUS = re.compile(r"^(various( artists)?|va|diverse( interpreten)?|verschiedene interpreten|sampler)$", re.I)

# Zusätze, die NICHT zu einer anderen Aufnahme machen (anders als live, remix, acoustic …)
_SAME_RECORDING = re.compile(
    r"[\(\[][^\)\]]*\b(remaster(ed)?|deluxe|expanded|anniversary|bonus( track)?|explicit|clean|"
    r"album version|lp version|single version|original version|mono|stereo|\d{4} mix|"
    r"feat\.?|ft\.?|featuring|with)\b[^\)\]]*[\)\]]", re.I)
_SAME_RECORDING_DASH = re.compile(
    r"\s[-–—]\s+(\d{4}\s+)?(remaster(ed)?|digital(ly)? remaster(ed)?|album version|single version|"
    r"mono|stereo|bonus track|explicit)\b.*$", re.I)
_FEAT = re.compile(r"\s(feat\.?|ft\.?|featuring|with|x|&|,|/|;)\s.*$", re.I)
_LOSSLESS = {".flac", ".wav", ".aiff", ".aif", ".alac", ".wv", ".ape"}


@dataclass
class DupFile:
    file: core.LocalFile
    edition: int
    compilation: bool
    quality: tuple
    keep: bool = False
    reason: str = ""


@dataclass
class DupGroup:
    artist: str
    title: str
    files: list[DupFile] = field(default_factory=list)

    @property
    def removable(self) -> list[DupFile]:
        return [f for f in self.files if not f.keep]


def album_core(album: str) -> str:
    a = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", album or "")
    a = re.sub(r"\s[-–—:]\s.*(edition|deluxe|remaster|version|expanded|anniversary).*$", " ", a, flags=re.I)
    return core.norm(a)


def edition_level(album: str, folder: str) -> int:
    text = f"{album} {folder}"
    for lvl, rx in _EDITION:
        if rx.search(text):
            return lvl
    return 0


def dup_title(title: str) -> str:
    t = _SAME_RECORDING.sub(" ", title or "")
    t = _SAME_RECORDING_DASH.sub(" ", t)
    return core.norm(t)


def dup_artist(artist: str) -> str:
    return core.norm(_FEAT.sub("", artist or ""))


def quality(f: core.LocalFile) -> tuple:
    ext = os.path.splitext(f.path)[1].lower()
    lossless = ext in _LOSSLESS
    return (1 if lossless else 0, f.bits or 0, f.sample_rate or 0, f.bitrate or 0)


def quality_label(f: core.LocalFile) -> str:
    ext = os.path.splitext(f.path)[1].lstrip(".").upper()
    if ext in ("FLAC", "WAV", "AIFF", "AIF", "WV", "APE", "ALAC") and f.bits and f.sample_rate:
        return f"{ext} {f.bits}/{f.sample_rate / 1000:g}"
    if f.bitrate:
        return f"{ext} {round(f.bitrate / 1000)}k"
    return ext


def _rank(d: DupFile) -> tuple:
    # Reihenfolge der Kriterien: Deluxe > kein Best-of > Qualität > längerer Albumname (meist die Edition)
    return (d.edition, 0 if d.compilation else 1, d.quality, len(d.file.album or ""))


def _reason(keeper: DupFile, others: list[DupFile]) -> str:
    if any(keeper.edition > o.edition for o in others):
        return "Deluxe-Edition"
    if any(o.compilation for o in others) and not keeper.compilation:
        return "Original statt Best-of"
    if any(keeper.quality > o.quality for o in others):
        return "bessere Qualität"
    return "erste Fundstelle"


def find_duplicates(files: list[core.LocalFile], include_compilations: bool = True,
                    max_len_diff: float = 6.0,
                    progress: Callable[[int, int], None] | None = None) -> list[DupGroup]:
    buckets: dict[tuple, list[DupFile]] = defaultdict(list)
    for i, f in enumerate(files):
        folder = os.path.basename(os.path.dirname(f.path))
        comp = bool(_COMPILATION.search(f.album or "") or _VARIOUS.match((f.albumartist or "").strip()))
        if comp and not include_compilations:
            continue
        artist = f.artist
        if _VARIOUS.match((artist or "").strip()):
            continue
        key = (dup_artist(artist), dup_title(f.title))
        if not key[0] or not key[1]:
            continue
        buckets[key].append(DupFile(f, edition_level(f.album, folder), comp, quality(f)))
        if progress and i % 200 == 0:
            progress(i, len(files))

    groups: list[DupGroup] = []
    for (_a, _t), items in buckets.items():
        if len(items) < 2:
            continue
        # gleiche Titel mit sehr unterschiedlicher Länge sind verschiedene Aufnahmen
        items.sort(key=lambda d: d.file.duration_s or 0)
        clusters: list[list[DupFile]] = [[items[0]]]
        for d in items[1:]:
            prev = clusters[-1][-1]
            a, b = prev.file.duration_s, d.file.duration_s
            if a and b and abs(a - b) > max_len_diff:
                clusters.append([d])
            else:
                clusters[-1].append(d)
        for cl in clusters:
            if len(cl) < 2:
                continue
            cl.sort(key=_rank, reverse=True)
            cl[0].keep = True
            cl[0].reason = _reason(cl[0], cl[1:])
            for o in cl[1:]:
                o.reason = "Duplikat"
            title = min((x.file.title for x in cl), key=len)
            groups.append(DupGroup(artist=cl[0].file.artist, title=title, files=cl))
    groups.sort(key=lambda g: (core.norm(g.artist), core.norm(g.title)))
    if progress:
        progress(len(files), len(files))
    return groups


def remove_files(paths: list[str], mode: str, root: str,
                 progress: Callable[[int, int], None] | None = None) -> tuple[int, list[str]]:
    """mode: 'trash' (Papierkorb) oder 'move' (nach <root>/_Duplikate, Ordnerstruktur bleibt)."""
    ok, errors = 0, []
    quarantine = os.path.join(root, "_Duplikate")
    for i, p in enumerate(paths):
        try:
            if mode == "trash":
                if send2trash is None:
                    raise RuntimeError("Papierkorb nicht verfügbar (Paket send2trash fehlt)")
                send2trash(p)
            else:
                try:
                    rel = os.path.relpath(p, root)
                except ValueError:
                    rel = os.path.basename(p)
                if rel.startswith(".."):
                    rel = os.path.basename(p)
                dst = os.path.join(quarantine, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                base, ext = os.path.splitext(dst)
                n = 1
                while os.path.exists(dst):
                    dst = f"{base} ({n}){ext}"
                    n += 1
                shutil.move(p, dst)
            ok += 1
            _prune_empty(os.path.dirname(p), root)
        except Exception as e:  # noqa
            errors.append(f"{os.path.basename(p)}: {e}")
        if progress:
            progress(i + 1, len(paths))
    return ok, errors


_JUNK = {"thumbs.db", ".ds_store", "desktop.ini"}


def _prune_empty(folder: str, root: str):
    """Löscht Ordner, die nach dem Entfernen leer sind (nur Systemmüll übrig)."""
    root = os.path.abspath(root)
    folder = os.path.abspath(folder)
    while folder.startswith(root) and folder != root:
        try:
            rest = [f for f in os.listdir(folder) if f.lower() not in _JUNK]
        except OSError:
            return
        if rest:
            return
        for f in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, f))
            except OSError:
                return
        try:
            os.rmdir(folder)
        except OSError:
            return
        folder = os.path.dirname(folder)
