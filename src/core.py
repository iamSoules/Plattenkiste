"""Logik ohne GUI: Spotify-Playlist laden, Musikordner scannen, abgleichen, M3U schreiben."""
from __future__ import annotations

import base64
import csv
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Iterable

import requests
from rapidfuzz import fuzz, process

try:
    import mutagen
except ImportError:  # pragma: no cover
    mutagen = None

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

FLAC_EXT = {".flac"}
OTHER_EXT = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".aiff", ".aif", ".alac", ".wv", ".ape"}


# --------------------------------------------------------------------------- Datentypen
@dataclass
class Track:
    title: str
    artists: list[str]
    album: str = ""
    duration_ms: int | None = None
    isrc: str | None = None

    @property
    def artist_str(self) -> str:
        return ", ".join(self.artists)


@dataclass
class LocalFile:
    path: str
    title: str
    artist: str
    album: str = ""
    duration_s: float | None = None
    isrc: str | None = None
    albumartist: str = ""
    bits: int = 0
    sample_rate: int = 0
    bitrate: int = 0
    size: int = 0
    # vorberechnet für den Abgleich
    n_title: str = ""
    n_title_core: str = ""
    n_artist: str = ""
    n_full: str = ""


@dataclass
class Playlist:
    name: str
    tracks: list[Track]
    note: str = ""


@dataclass
class Match:
    track: Track
    file: LocalFile | None = None
    score: float = 0.0
    manual: bool = False
    alternatives: list[tuple[LocalFile, float]] = field(default_factory=list)


class SpotifyError(Exception):
    pass


# --------------------------------------------------------------------------- Spotify
_ID_RE = re.compile(r"(playlist|album)[/:]([A-Za-z0-9]{22})")


def parse_spotify_link(link: str) -> tuple[str, str]:
    m = _ID_RE.search(link.strip())
    if not m:
        raise SpotifyError("Das sieht nicht nach einem Spotify-Playlist- oder Album-Link aus.")
    return m.group(1), m.group(2)


def fetch_playlist(link: str, client_id: str = "", client_secret: str = "") -> Playlist:
    kind, sid = parse_spotify_link(link)
    if client_id and client_secret:
        return _fetch_api(kind, sid, client_id, client_secret)
    return _fetch_embed(kind, sid)


def _find_key(obj, key):
    """Sucht rekursiv nach dem ersten Vorkommen eines Schlüssels."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def _split_artists(subtitle: str) -> list[str]:
    subtitle = subtitle.replace(" ", " ")
    parts = [p.strip() for p in re.split(r",\s*", subtitle) if p.strip()]
    return parts or [subtitle.strip()]


def _fetch_embed(kind: str, sid: str) -> Playlist:
    url = f"https://open.spotify.com/embed/{kind}/{sid}"
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "de,en;q=0.8"}, timeout=20)
    except requests.RequestException as e:
        raise SpotifyError(f"Spotify nicht erreichbar: {e}") from e
    if r.status_code == 404:
        raise SpotifyError("Playlist nicht gefunden – ist sie öffentlich?")
    if r.status_code != 200:
        raise SpotifyError(f"Spotify antwortete mit HTTP {r.status_code}.")
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        raise SpotifyError("Konnte die Trackliste nicht aus der Spotify-Seite lesen. "
                           "Nutze API-Zugangsdaten oder einen CSV-Export.")
    data = json.loads(m.group(1))
    entity = _find_key(data, "entity") or {}
    track_list = entity.get("trackList") or _find_key(data, "trackList") or []
    tracks = []
    for t in track_list:
        title = (t.get("title") or "").strip()
        if not title:
            continue
        tracks.append(Track(
            title=title,
            artists=_split_artists(t.get("subtitle") or ""),
            album=entity.get("name", "") if kind == "album" else "",
            duration_ms=t.get("duration"),
        ))
    if not tracks:
        raise SpotifyError("Die Playlist scheint leer zu sein.")
    name = entity.get("name") or entity.get("title") or "Spotify Playlist"
    note = ""
    if len(tracks) >= 100:
        note = ("Ohne API-Zugang liefert Spotify höchstens 100 Titel. Für größere Playlists "
                "API-Zugangsdaten eintragen oder eine CSV importieren.")
    return Playlist(name=name, tracks=tracks, note=note)


def _fetch_api(kind: str, sid: str, cid: str, secret: str) -> Playlist:
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    try:
        tr = requests.post("https://accounts.spotify.com/api/token",
                           data={"grant_type": "client_credentials"},
                           headers={"Authorization": f"Basic {auth}"}, timeout=20)
    except requests.RequestException as e:
        raise SpotifyError(f"Spotify nicht erreichbar: {e}") from e
    if tr.status_code != 200:
        raise SpotifyError("API-Anmeldung fehlgeschlagen – Client-ID/Secret prüfen.")
    h = {"Authorization": f"Bearer {tr.json()['access_token']}"}
    base = "https://api.spotify.com/v1"

    meta = requests.get(f"{base}/{kind}s/{sid}", headers=h, params={"fields": "name"}, timeout=20)
    if meta.status_code != 200:
        raise SpotifyError(f"Spotify-API: HTTP {meta.status_code} – ist die Playlist öffentlich?")
    meta = meta.json()
    name = meta.get("name", "Spotify Playlist")

    tracks: list[Track] = []
    url = f"{base}/{kind}s/{sid}/tracks?limit=50"
    while url:
        r = requests.get(url, headers=h, timeout=20)
        if r.status_code != 200:
            raise SpotifyError(f"Spotify-API: HTTP {r.status_code}")
        page = r.json()
        for item in page.get("items", []):
            t = item.get("track") if kind == "playlist" else item
            if not t or not t.get("name"):
                continue
            tracks.append(Track(
                title=t["name"],
                artists=[a["name"] for a in t.get("artists", [])],
                album=(t.get("album") or {}).get("name", meta.get("name", "") if kind == "album" else ""),
                duration_ms=t.get("duration_ms"),
                isrc=(t.get("external_ids") or {}).get("isrc"),
            ))
        url = page.get("next")
    return Playlist(name=name, tracks=tracks)


def load_csv(path: str) -> Playlist:
    """CSV-Import, z. B. von Exportify (exportify.net) oder TuneMyMusic."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.DictReader(f, dialect=dialect))
    if not rows:
        raise SpotifyError("Die CSV-Datei ist leer.")

    def col(*names):
        keys = {k.lower().strip(): k for k in rows[0].keys() if k}
        for n in names:
            if n in keys:
                return keys[n]
        for n in names:
            for lk, k in keys.items():
                if n in lk:
                    return k
        return None

    c_title = col("track name", "title", "titel", "name", "song")
    c_artist = col("artist name(s)", "artist name", "artists", "artist", "interpret", "künstler")
    c_album = col("album name", "album")
    c_dur = col("duration (ms)", "track duration (ms)", "duration_ms")
    c_isrc = col("isrc")
    if not c_title:
        raise SpotifyError("Keine Titel-Spalte in der CSV gefunden.")
    tracks = []
    for r in rows:
        title = (r.get(c_title) or "").strip()
        if not title:
            continue
        artists_raw = (r.get(c_artist) or "") if c_artist else ""
        dur = None
        if c_dur and (r.get(c_dur) or "").strip().isdigit():
            dur = int(r[c_dur])
        tracks.append(Track(
            title=title,
            artists=[a.strip() for a in re.split(r"[,;]", artists_raw) if a.strip()],
            album=(r.get(c_album) or "").strip() if c_album else "",
            duration_ms=dur,
            isrc=(r.get(c_isrc) or "").strip() or None if c_isrc else None,
        ))
    name = os.path.splitext(os.path.basename(path))[0]
    return Playlist(name=name, tracks=tracks)


# --------------------------------------------------------------------------- Normalisieren
_PAREN_NOISE = re.compile(
    r"[\(\[][^\)\]]*\b(remaster(ed)?|feat\.?|ft\.?|featuring|with|mono|stereo|deluxe|bonus|"
    r"single|album|radio|version|explicit|clean|anniversary|edition|\d{4})\b[^\)\]]*[\)\]]",
    re.I)
_DASH_NOISE = re.compile(
    r"\s[-–—]\s.*\b(remaster(ed)?|mono|stereo|single|radio|version|edition|\d{4}|bonus)\b.*$", re.I)
_FEAT = re.compile(r"\s(feat\.?|ft\.?|featuring)\s.*$", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ").replace("ß", "ss")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(the|a)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def title_core(s: str) -> str:
    s = _PAREN_NOISE.sub(" ", s or "")
    s = _DASH_NOISE.sub(" ", s)
    s = _FEAT.sub(" ", s)
    return norm(s)


# --------------------------------------------------------------------------- Ordner scannen
def _first(tags, *keys):
    for k in keys:
        v = tags.get(k) if tags else None
        if v:
            return str(v[0]) if isinstance(v, list) else str(v)
    return ""


def _from_filename(path: str) -> tuple[str, str]:
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"^\s*(\d{1,3}[\s.\-_]+)+", "", stem)  # Tracknummern
    if " - " in stem:
        a, t = stem.split(" - ", 1)
        return a.strip(), t.strip()
    parent = os.path.basename(os.path.dirname(os.path.dirname(path)))
    return parent, stem.strip()


def read_file(path: str) -> LocalFile:
    title = artist = album = isrc = albumartist = ""
    dur = None
    bits = rate = br = 0
    if mutagen is not None:
        try:
            mf = mutagen.File(_long(path), easy=True)
            if mf is not None:
                tags = mf.tags or {}
                title = _first(tags, "title")
                artist = _first(tags, "artist", "albumartist", "performer")
                album = _first(tags, "album")
                isrc = _first(tags, "isrc")
                albumartist = _first(tags, "albumartist")
                info = mf.info
                dur = getattr(info, "length", None)
                bits = getattr(info, "bits_per_sample", 0) or 0
                rate = getattr(info, "sample_rate", 0) or 0
                br = getattr(info, "bitrate", 0) or 0
        except Exception:
            pass
    if not title:
        fa, ft = _from_filename(path)
        title = ft
        artist = artist or fa
    lf = LocalFile(path=path, title=title, artist=artist, album=album,
                   duration_s=dur, isrc=isrc.upper().replace("-", "") or None,
                   albumartist=albumartist, bits=bits, sample_rate=rate, bitrate=br)
    try:
        lf.size = os.path.getsize(_long(path))
    except OSError:
        pass
    lf.n_title = norm(title)
    lf.n_title_core = title_core(title)
    lf.n_artist = norm(artist)
    lf.n_full = f"{lf.n_artist} {lf.n_title_core}".strip()
    return lf


def _long(p: str) -> str:
    """Windows: Präfix für Pfade über 260 Zeichen (tief verschachtelte Musikordner)"""
    if os.name == "nt":
        p = os.path.abspath(p)
        if not p.startswith("\\\\?\\"):
            p = "\\\\?\\UNC\\" + p[2:] if p.startswith("\\\\") else "\\\\?\\" + p
    return p


def _short(p: str) -> str:
    if p.startswith("\\\\?\\UNC\\"):
        return "\\\\" + p[8:]
    return p[4:] if p.startswith("\\\\?\\") else p


SCAN_ERRORS: list[str] = []
SCAN_FOLDERS = 0


def list_audio(folder: str, recursive: bool = True, all_formats: bool = False) -> list[str]:
    """Alle Audiodateien – auf Wunsch inklusive aller Unterordner (auch sehr tiefe und verknüpfte)."""
    global SCAN_FOLDERS
    exts = FLAC_EXT | (OTHER_EXT if all_formats else set())
    out: list[str] = []
    SCAN_ERRORS.clear()
    SCAN_FOLDERS = 0
    seen: set = set()

    def walk(d: str, depth: int):
        global SCAN_FOLDERS
        try:
            st = os.stat(d)
            key = (st.st_dev, st.st_ino)
            if key in seen and st.st_ino:  # Schleife durch Verknüpfungen vermeiden
                return
            seen.add(key)
            # echte Ordner vor Verknüpfungen, damit Pfade auf den echten Speicherort zeigen
            entries = sorted(os.scandir(d), key=lambda e: (e.is_symlink(), e.name.lower()))
        except OSError as e:
            SCAN_ERRORS.append(f"{_short(d)}: {e.strerror or e}")
            return
        SCAN_FOLDERS += 1
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=True):
                    if recursive and e.name != "_Duplikate" and not e.name.startswith("$") and depth < 64:
                        walk(e.path, depth + 1)
                elif os.path.splitext(e.name)[1].lower() in exts:
                    out.append(_short(e.path))
            except OSError as err:
                SCAN_ERRORS.append(f"{_short(e.path)}: {err.strerror or err}")

    walk(_long(folder), 0)
    out.sort(key=lambda s: s.lower())
    return out


class ScanResult(list):
    """Liste der gelesenen Dateien plus Statistik dieses einen Scans"""
    folder = ""
    folders = 0
    errors: list[str] = []


def scan_folder(folder: str, recursive=True, all_formats=False,
                progress: Callable[[int, int], None] | None = None) -> list[LocalFile]:
    paths = list_audio(folder, recursive, all_formats)
    files = ScanResult()
    files.folder, files.folders, files.errors = folder, SCAN_FOLDERS, list(SCAN_ERRORS)
    for i, p in enumerate(paths):
        files.append(read_file(p))
        if progress and (i % 25 == 0 or i == len(paths) - 1):
            progress(i + 1, len(paths))
    return files


# --------------------------------------------------------------------------- Abgleich
def _score(track: Track, n_title: str, n_core: str, n_artists: list[str], f: LocalFile) -> float:
    if track.isrc and f.isrc and track.isrc.upper().replace("-", "") == f.isrc:
        return 100.0
    t = max(fuzz.ratio(n_core, f.n_title_core), fuzz.ratio(n_title, f.n_title) - 2)
    # Titel wie "Song (Live)" vs "Song" – leicht abwerten statt verwerfen
    if t < 90 and n_core and f.n_title_core and (n_core in f.n_title_core or f.n_title_core in n_core):
        t = max(t, 82)
    if f.n_artist and n_artists:
        a = max(max(fuzz.token_set_ratio(x, f.n_artist) for x in n_artists),
                fuzz.token_set_ratio(" ".join(n_artists), f.n_artist))
    else:
        a = 60.0
    s = 0.65 * t + 0.35 * a
    if track.duration_ms and f.duration_s:
        diff = abs(track.duration_ms / 1000 - f.duration_s)
        if diff <= 3:
            s += 4
        elif diff > 20:
            s -= 12
        elif diff > 8:
            s -= 5
    return max(0.0, min(100.0, s))


def match_tracks(tracks: Iterable[Track], files: list[LocalFile],
                 progress: Callable[[int, int], None] | None = None) -> list[Match]:
    tracks = list(tracks)
    by_isrc = {f.isrc: f for f in files if f.isrc}
    cores = [f.n_title_core for f in files]
    fulls = [f.n_full for f in files]
    used: set[str] = set()
    results: list[Match] = []
    # 1. Kandidaten pro Track bestimmen
    cands_all = []
    for i, tr in enumerate(tracks):
        n_title, n_core = norm(tr.title), title_core(tr.title)
        n_artists = [norm(a) for a in tr.artists]
        idx = set()
        if files:
            for _, _, j in process.extract(n_core, cores, scorer=fuzz.ratio, limit=12):
                idx.add(j)
            full = f"{' '.join(n_artists)} {n_core}"
            for _, _, j in process.extract(full, fulls, scorer=fuzz.token_set_ratio, limit=12):
                idx.add(j)
        cands = [(files[j], _score(tr, n_title, n_core, n_artists, files[j])) for j in idx]
        if tr.isrc and tr.isrc.upper().replace("-", "") in by_isrc:
            f = by_isrc[tr.isrc.upper().replace("-", "")]
            cands.append((f, 100.0))
        cands.sort(key=lambda c: -c[1])
        cands_all.append(cands)
        if progress and (i % 10 == 0 or i == len(tracks) - 1):
            progress(i + 1, len(tracks))
    # 2. Beste Paare zuerst vergeben, damit eine Datei nicht zwei Titeln zugeordnet wird
    order = sorted(range(len(tracks)), key=lambda i: -(cands_all[i][0][1] if cands_all[i] else 0))
    chosen: dict[int, Match] = {}
    for i in order:
        cands = cands_all[i]
        pick = next(((f, s) for f, s in cands if f.path not in used), None)
        if pick is None and cands:  # doppelter Titel in der Playlist -> Datei wiederverwenden
            pick = cands[0]
        m = Match(track=tracks[i], alternatives=cands[:8])
        if pick:
            m.file, m.score = pick
            used.add(pick[0].path)
        chosen[i] = m
    results = [chosen[i] for i in range(len(tracks))]
    return results


# --------------------------------------------------------------------------- M3U
def playlist_entries(matches: list[Match], threshold: float) -> list[Match]:
    return [m for m in matches if m.file and (m.manual or m.score >= threshold)]


def _ascii_safe(s: str) -> str:
    return s.replace("\n", " ").replace("\r", " ")


def write_m3u(path: str, name: str, matches: list[Match], threshold: float, relative: bool = True,
              sep: str = "/", path_map: dict[str, str] | None = None) -> int:
    """
    relative=True: Pfade relativ zum Ort der Playlist, mit „/“ getrennt – so funktioniert die Liste
    auch auf MP3-Playern, Handys und anderen Rechnern, solange sie im (bzw. über dem) Musikordner liegt.
    path_map: Zuordnung Quelle → kopierte Datei (beim Export aufs Gerät)
    """
    base = os.path.dirname(os.path.abspath(path))
    lines = ["#EXTM3U", f"#PLAYLIST:{_ascii_safe(name)}"]
    n = 0
    for m in playlist_entries(matches, threshold):
        dur = int(round(m.file.duration_s)) if m.file.duration_s else (
            int(m.track.duration_ms / 1000) if m.track.duration_ms else -1)
        lines.append(f"#EXTINF:{dur},{_ascii_safe(m.track.artist_str)} - {_ascii_safe(m.track.title)}")
        p = os.path.abspath((path_map or {}).get(m.file.path, m.file.path))
        if relative:
            try:
                rel = os.path.relpath(p, base)
                if not rel.startswith(".."):
                    p = rel
            except ValueError:  # anderes Laufwerk unter Windows
                pass
            p = p.replace("\\", sep).replace("/", sep)
        lines.append(p)
        n += 1
    # UTF-8 ohne BOM, Windows-Zeilenenden: das verstehen praktisch alle Player
    with open(path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    return n


def outside_paths(path: str, matches: list[Match], threshold: float) -> int:
    """Wie viele Songs liegen NICHT unterhalb des Playlist-Ordners (→ auf Geräten nicht auffindbar)?"""
    base = os.path.dirname(os.path.abspath(path))
    bad = 0
    for m in playlist_entries(matches, threshold):
        try:
            if os.path.relpath(os.path.abspath(m.file.path), base).startswith(".."):
                bad += 1
        except ValueError:
            bad += 1
    return bad


_FAT_BAD = re.compile(r'[<>:"|?*\x00-\x1f]')


def _fat_safe(part: str) -> str:
    """Dateinamen für FAT32/exFAT (typisch auf MP3-Playern und SD-Karten) gültig machen"""
    part = _FAT_BAD.sub("_", part).rstrip(" .")
    return part or "_"


# Pfadformate für Playlists auf Geräten (Playlist liegt in eigenem Ordner, Musik woanders)
PATH_STYLES = {
    "rel": "Relativ zur Playlist, mit /   (../music/flac/…)",
    "relbs": "Relativ zur Playlist, mit \\   (..\\music\\flac\\…)",
    "root": "Ab Kartenstamm, mit /   (music/flac/…)",
    "rootbs": "Ab Kartenstamm, mit \\   (music\\flac\\…)",
    "abs": "Ab Kartenstamm mit führendem /   (/music/flac/…)",
}

DEVICE_PROFILES = {
    "generic": {"label": "Allgemein (Playlist im Hauptordner)", "playlist_dir": "", "music_dir": "", "style": "rel"},
    "hiby": {"label": "HiBy R1 / HiBy OS", "playlist_dir": "playlist_data", "music_dir": "music/flac", "style": "rel"},
    "custom": {"label": "Eigene Einstellung", "playlist_dir": "", "music_dir": "", "style": "rel"},
}


def _parts(p: str) -> list[str]:
    return [x for x in re.split(r"[\\/]+", p or "") if x and x != "."]


def device_song_rel(src: str, music_root: str) -> list[str]:
    """Pfadteile eines Songs relativ zum Musikordner am PC (FAT-tauglich)"""
    src = os.path.abspath(src)
    try:
        rel = os.path.relpath(src, os.path.abspath(music_root)) if music_root else os.path.basename(src)
    except ValueError:
        rel = os.path.basename(src)
    if rel.startswith(".."):
        rel = os.path.basename(src)
    return [_fat_safe(p) for p in _parts(rel)]


LEARNED: dict = {}  # vom Gerät übernommenes Format (wird von der App gesetzt)


def path_from_root(from_root: list[str], playlist_dir: str, style: str) -> str:
    """Pfad in der Playlist für eine Datei, deren Ort ab Kartenstamm bekannt ist"""
    if style == "learned" and LEARNED:
        return LEARNED.get("prefix", "") + LEARNED.get("sep", "/").join(from_root)
    if style in ("rel", "relbs"):
        parts = [".."] * len(_parts(playlist_dir)) + from_root
        return ("/" if style == "rel" else "\\").join(parts)
    if style == "rootbs":
        return "\\".join(from_root)
    if style == "abs":
        return "/" + "/".join(from_root)
    return "/".join(from_root)


def device_path(song_parts: list[str], music_dir: str, playlist_dir: str, style: str) -> str:
    """Pfad, wie er in der Playlist auf dem Gerät stehen muss"""
    return path_from_root([_fat_safe(p) for p in _parts(music_dir)] + song_parts, playlist_dir, style)


def write_device_playlist(path: str, name: str, entries: list[Match], lines_for: Callable[[Match], str],
                          fmt: dict | None = None):
    """fmt: vom Gerät übernommenes Format (header/extinf/playlist_tag/bom/crlf) – sonst Standard-M3U"""
    f = {"header": True, "extinf": True, "playlist_tag": True, "bom": False, "crlf": True, **(fmt or {})}
    lines = []
    if f["header"]:
        lines.append("#EXTM3U")
    if f["playlist_tag"]:
        lines.append(f"#PLAYLIST:{_ascii_safe(name)}")
    for m in entries:
        if f["extinf"]:
            dur = int(round(m.file.duration_s)) if m.file.duration_s else (
                int(m.track.duration_ms / 1000) if m.track.duration_ms else -1)
            lines.append(f"#EXTINF:{dur},{_ascii_safe(m.track.artist_str)} - {_ascii_safe(m.track.title)}")
        lines.append(lines_for(m))
    os.makedirs(_long(os.path.dirname(path)), exist_ok=True)
    with open(_long(path), "w", encoding="utf-8-sig" if f["bom"] else "utf-8", newline="\r\n" if f["crlf"] else "\n") as fh:
        fh.write("\n".join(lines) + "\n")


def _inside(path: str, root: str) -> list[str] | None:
    """Pfadteile von path ab root – oder None, wenn path nicht unter root liegt"""
    try:
        rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    except ValueError:
        return None
    return None if rel.startswith("..") else _parts(rel)


class CardIndex:
    """Alle Audiodateien im Musik-Ordner der Karte – zum Wiederfinden von Songs, die schon drauf sind"""

    def __init__(self, target: str, music_dir: str):
        self.target = target
        base = os.path.join(target, *_parts(music_dir))
        self.by_name_size: dict[tuple[str, int], str] = {}
        self.by_name: dict[str, list[str]] = {}
        if os.path.isdir(base):
            for p in list_audio(base, True, True):
                n = os.path.basename(p).lower()
                try:
                    self.by_name_size[(n, os.path.getsize(_long(p)))] = p
                except OSError:
                    pass
                self.by_name.setdefault(n, []).append(p)

    def find(self, src: str, size: int) -> str | None:
        n = os.path.basename(src).lower()
        hit = self.by_name_size.get((n, size))
        if hit:
            return hit
        same = self.by_name.get(n, [])
        if len(same) == 1:
            return same[0]
        if same:  # mehrere gleichnamige (01 - Intro.flac …) → den mit passendem Ordnernamen nehmen
            parent = os.path.basename(os.path.dirname(src)).lower()
            for p in same:
                if os.path.basename(os.path.dirname(p)).lower() == parent:
                    return p
        return None


def copy_to_device(target: str, name: str, matches: list[Match], threshold: float, music_root: str,
                   progress: Callable[[int, int], None] | None = None, *, music_dir: str = "",
                   playlist_dir: str = "", style: str = "rel", copy: bool = False) -> tuple[int, int, str, list[str]]:
    """
    Schreibt eine Playlist für ein Gerät/eine SD-Karte – auf Wunsch samt Songs.
    target       Hauptordner der Karte (z. B. E:\\)
    music_dir    Musikordner auf der Karte (z. B. „music/flac“)
    playlist_dir Ordner für die Playlist (z. B. „playlist_data“)
    style        Pfadformat in der Playlist (siehe PATH_STYLES)
    copy=False   nur die Playlist schreiben; jeder Song wird auf der Karte gesucht
                 (liegt der Musikordner schon auf der Karte, wird direkt dessen Ort verwendet)
    Rückgabe: (kopiert, übersprungen, Playlist-Pfad, nicht gefundene Songs)
    """
    import shutil
    entries = playlist_entries(matches, threshold)
    copied = skipped = 0
    where: dict[str, list[str]] = {}      # Song → Pfadteile ab Kartenstamm
    missing: list[str] = []
    index: CardIndex | None = None
    for i, m in enumerate(entries):
        src = os.path.abspath(m.file.path)
        on_card = _inside(src, target)
        if on_card is not None:
            where[m.file.path] = on_card            # Song liegt bereits auf der Karte
        else:
            parts = device_song_rel(src, music_root)
            dst = os.path.join(target, *_parts(music_dir), *parts)
            if copy:
                if not (os.path.exists(_long(dst)) and os.path.getsize(_long(dst)) == os.path.getsize(_long(src))):
                    os.makedirs(_long(os.path.dirname(dst)), exist_ok=True)
                    shutil.copyfile(_long(src), _long(dst))
                    copied += 1
                else:
                    skipped += 1
                where[m.file.path] = _parts(music_dir) + parts
            elif os.path.exists(_long(dst)):
                where[m.file.path] = _parts(music_dir) + parts
            else:
                if index is None:
                    index = CardIndex(target, music_dir)
                hit = index.find(src, m.file.size)
                if hit:
                    where[m.file.path] = _inside(hit, target) or []
                else:
                    missing.append(f"{m.track.artist_str} – {m.track.title}")
        if progress:
            progress(i + 1, len(entries))
    pl = os.path.join(target, *_parts(playlist_dir), (_fat_safe(name) or "Playlist") + ".m3u")
    found = [m for m in entries if m.file.path in where]
    write_device_playlist(pl, name, found, lambda m: path_from_root(where[m.file.path], playlist_dir, style),
                          LEARNED if style == "learned" else None)
    return copied, skipped, pl, missing


def learn_device_format(card_root: str, m3u_path: str) -> dict:
    """
    Analysiert eine Playlist, die das Gerät selbst gespeichert hat, und leitet daraus ab,
    wie Pfade aussehen müssen: Präfix vor dem Pfad ab Kartenstamm, Trennzeichen, Kopfzeilen,
    Kodierung und Zeilenende. Der Song in der Playlist muss auf der Karte liegen.
    """
    raw = open(_long(m3u_path), "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    entries = [l for l in lines if not l.startswith("#")]
    if not entries:
        raise ValueError("In der Playlist steht kein Song. Bitte am Gerät mindestens einen Song hinzufügen.")
    for e in entries:
        sep = "\\" if "\\" in e and "/" not in e else "/"
        parts = [p for p in re.split(r"[\\/]", e)]
        for i in range(len(parts)):
            rest = [p for p in parts[i:] if p]
            if rest and os.path.isfile(_long(os.path.join(card_root, *rest))):
                tail = sep.join(rest)
                prefix = e[: len(e) - len(tail)] if e.endswith(tail) else e[: e.find(rest[0])]
                return {
                    "prefix": prefix, "sep": sep, "example": e,
                    "header": bool(lines) and lines[0].upper().startswith("#EXTM3U"),
                    "extinf": any(l.upper().startswith("#EXTINF") for l in lines),
                    "playlist_tag": any(l.upper().startswith("#PLAYLIST") for l in lines),
                    "bom": bom, "crlf": b"\r\n" in raw,
                }
    raise ValueError("Der Song aus der Playlist wurde auf der gewählten Karte nicht gefunden.\n"
                     "Bitte prüfen, ob oben die richtige SD-Karte gewählt ist.\n\nErster Eintrag:\n" + entries[0])


def write_device_tests(target: str, matches: list[Match], threshold: float, music_root: str, *,
                       music_dir: str, playlist_dir: str, copy: bool = False, count: int = 3) -> list[str]:
    """
    Schreibt je Pfadformat eine kleine Test-Playlist (gleiche Songs), damit man am Gerät sieht,
    welches Format es versteht.
    """
    entries = playlist_entries(matches, threshold)[:count]
    out = []
    for i, style in enumerate(PATH_STYLES):
        name = f"Test {'ABCDE'[i]}"
        _, _, p, _ = copy_to_device(target, name, entries, threshold, music_root,
                                    music_dir=music_dir, playlist_dir=playlist_dir, style=style, copy=copy and i == 0)
        out.append(p)
    return out


# --------------------------------------------------------------------------- MusicBee-Auto-Playlist
def _primary_artist(s: str) -> str:
    """Erster Interpret – MusicBee trennt mehrere Interpreten standardmäßig mit „;“."""
    return re.split(r"\s*;\s*", s or "")[0].strip()


def write_xautopf(path: str, name: str, matches: list[Match], threshold: float) -> int:
    """
    MusicBee-Auto-Playlist (.xautopf). Jeder Song wird über Titel UND Interpret in der
    MusicBee-Bibliothek gesucht – deshalb nehmen wir die Tags der gefundenen lokalen Datei,
    denn genau so kennt MusicBee den Song. Doppelte Treffer filtert MusicBee selbst.
    """
    import xml.etree.ElementTree as ET

    root = ET.Element("SmartPlaylist", SaveStaticCopy="False", LiveUpdating="True", Layout="4",
                      LayoutGroupBy="0", ShuffleMode="None", ShuffleSameArtistWeight="0.5",
                      GroupBy="track", ConsolidateAlbums="False", MusicLibraryPath="")
    source = ET.SubElement(root, "Source", Type="1")
    conds = ET.SubElement(source, "Conditions", CombineMethod="Any")
    n = 0
    seen = set()
    for m in matches:
        if not m.file or (not m.manual and m.score < threshold):
            continue
        title = (m.file.title or m.track.title).strip()
        artist = _primary_artist(m.file.artist) or (m.track.artists[0] if m.track.artists else "")
        key = (title.lower(), artist.lower())
        if not title or key in seen:
            continue
        seen.add(key)
        c = ET.SubElement(conds, "Condition", Field="Title", Comparison="Contains", Value=title)
        if artist:
            both = ET.SubElement(c, "And", CombineMethod="All")
            ET.SubElement(both, "Condition", Field="ArtistPeople", Comparison="Is", Value=artist)
        n += 1
    ET.SubElement(source, "Limit", FilterDuplicates="True", Enabled="False", Count="25", Type="Items", SelectedBy="Random")
    ET.SubElement(source, "SortBy", Field="30", Order="Ascending")
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return n


def musicbee_playlist_dir() -> str | None:
    """Standard-Playlist-Ordner von MusicBee, falls vorhanden"""
    for p in (os.path.join(os.path.expanduser("~"), "Music", "MusicBee", "Playlists"),
              os.path.join(os.path.expanduser("~"), "Musik", "MusicBee", "Playlists")):
        if os.path.isdir(p):
            return p
    return None
