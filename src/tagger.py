"""Tags (Genre, Gruppierung, Stimmung) für ausgewählte Songs setzen – als „Playlist“ für Geräte ohne M3U."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import core

try:
    import mutagen
    from mutagen.easymp4 import EasyMP4Tags
    try:
        EasyMP4Tags.RegisterFreeformKey("mood", "MOOD")
    except Exception:
        pass
except ImportError:  # pragma: no cover
    mutagen = None

FIELDS = {
    "genre": "Genre",
    "grouping": "Gruppierung",
    "mood": "Stimmung",
}

MODES = {
    "add": "Hinzufügen",
    "replace": "Ersetzen",
    "remove": "Entfernen",
}

_SPLIT = re.compile(r"\s*[;\u0000]\s*")


@dataclass
class TagFile:
    file: core.LocalFile
    values: dict = field(default_factory=dict)  # Feld → Liste der Werte (aufgeteilt)


def split_values(raw) -> list[str]:
    out: list[str] = []
    for v in raw or []:
        for part in _SPLIT.split(str(v)):
            part = part.strip()
            if part and part.casefold() not in (o.casefold() for o in out):
                out.append(part)
    return out


def read_values(path: str) -> dict:
    vals = {k: [] for k in FIELDS}
    if mutagen is None:
        return vals
    try:
        mf = mutagen.File(core._long(path), easy=True)
    except Exception:
        return vals
    tags = getattr(mf, "tags", None) if mf is not None else None
    if not tags:
        return vals
    for k in FIELDS:
        try:
            vals[k] = split_values(tags.get(k) or [])
        except Exception:
            vals[k] = []
    return vals


def scan(folder: str, recursive: bool = True, progress=None) -> list[TagFile]:
    files = core.scan_folder(folder, recursive=recursive, all_formats=True,
                             progress=(lambda i, n: progress(i, n * 2)) if progress else None)
    out = []
    n = len(files)
    for i, f in enumerate(files):
        out.append(TagFile(f, read_values(f.path)))
        if progress and (i % 25 == 0 or i == n - 1):
            progress(n + i + 1, n * 2)
    return out


def new_values(old: list[str], value: str, mode: str) -> list[str]:
    value = value.strip()
    cf = value.casefold()
    if mode == "replace":
        return [value] if value else []
    if mode == "remove":
        return [v for v in old if v.casefold() != cf]
    if any(v.casefold() == cf for v in old):
        return list(old)
    return list(old) + [value]


def _write(path: str, fld: str, values: list[str], joined: bool):
    mf = mutagen.File(core._long(path), easy=True)
    if mf is None:
        raise ValueError("Dateiformat wird nicht unterstützt")
    if mf.tags is None:
        mf.add_tags()
    if values:
        mf.tags[fld] = ["; ".join(values)] if joined else list(values)
    else:
        try:
            del mf.tags[fld]
        except KeyError:
            pass
    mf.save()


def apply(tag_files: list[TagFile], fld: str, value: str, mode: str, joined: bool = False, progress=None):
    """Schreibt den Tag. Gibt (geändert, Fehler, Undo-Liste) zurück. Undo: [(pfad, feld, alte Werte)]"""
    if mutagen is None:
        raise RuntimeError("mutagen fehlt – Tags können nicht geschrieben werden.")
    changed, errors, undo = 0, [], []
    n = len(tag_files)
    for i, tf in enumerate(tag_files):
        old = list(tf.values.get(fld, []))
        new = new_values(old, value, mode)
        if new != old:
            try:
                _write(tf.file.path, fld, new, joined)
                tf.values[fld] = new
                undo.append((tf.file.path, fld, old))
                changed += 1
            except Exception as e:
                errors.append(f"{os.path.basename(tf.file.path)}: {e}")
        if progress and (i % 10 == 0 or i == n - 1):
            progress(i + 1, n)
    return changed, errors, undo


def restore(undo, by_path: dict, joined: bool = False, progress=None):
    errors = []
    n = len(undo)
    for i, (path, fld, old) in enumerate(undo):
        try:
            _write(path, fld, old, joined)
            tf = by_path.get(path)
            if tf is not None:
                tf.values[fld] = list(old)
        except Exception as e:
            errors.append(f"{os.path.basename(path)}: {e}")
        if progress and (i % 10 == 0 or i == n - 1):
            progress(i + 1, n)
    return errors


def _key(p: str) -> str:
    return os.path.normcase(os.path.normpath(core._short(p)))


def read_m3u(path: str) -> list[str]:
    """Pfade aus einer M3U/M3U8 (relativ zur Datei aufgelöst)"""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    base = os.path.dirname(path)
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("file://"):
            from urllib.parse import unquote, urlparse
            line = unquote(urlparse(line).path)
            if re.match(r"^/[A-Za-z]:", line):
                line = line[1:]
        line = line.replace("\\", os.sep).replace("/", os.sep)
        if not os.path.isabs(line) and not re.match(r"^[A-Za-z]:", line):
            line = os.path.join(base, line)
        out.append(line)
    return out


def match_paths(paths: list[str], tag_files: list[TagFile]) -> tuple[list[TagFile], int]:
    """Ordnet Pfade den Bibliotheksdateien zu – exakt, sonst über die letzten Ordner + Dateiname."""
    by_key = {_key(t.file.path): t for t in tag_files}
    by_tail: dict = {}
    for t in tag_files:
        parts = _key(t.file.path).split(os.sep)
        for n in (3, 2, 1):
            by_tail.setdefault(tuple(parts[-n:]), []).append(t)
    found, missing, seen = [], 0, set()
    for p in paths:
        k = _key(p)
        t = by_key.get(k)
        if t is None:
            parts = k.split(os.sep)
            for n in (3, 2, 1):
                c = by_tail.get(tuple(parts[-n:]))
                if c and len(c) == 1:
                    t = c[0]
                    break
        if t is None:
            missing += 1
        elif id(t) not in seen:
            seen.add(id(t))
            found.append(t)
    return found, missing
