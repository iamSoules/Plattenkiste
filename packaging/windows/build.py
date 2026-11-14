"""Baut die beiden Windows-Pakete von Plattenkiste.

    python packaging/windows/build.py [--version 1.2.0]

Ergebnis in dist/:
    Plattenkiste-<version>-windows-portable.exe   einzelne EXE, entpackt sich beim ersten Start
    Plattenkiste-<version>-windows.zip            Ordner mit Plattenkiste.exe + runtime/

Läuft unter Windows, macOS und Linux. Benötigt: Python 3.10+, pip und das .NET SDK (dotnet).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PYTHON_VERSION = "3.13.9"  # eingebettete Windows-Laufzeit (x64)
APP_FILES = ["app.py", "core.py", "dupes.py", "tagger.py", "icon.png"]

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BUILD = ROOT / "build" / "windows"
DIST = ROOT / "dist"


def run(*cmd: str | Path) -> None:
    print("+", " ".join(map(str, cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], check=True)


def make_payload() -> Path:
    payload = BUILD / "payload"
    shutil.rmtree(payload, ignore_errors=True)
    py = payload / "python"
    py.mkdir(parents=True)

    # 1. eingebettete Python-Laufzeit
    url = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
    print("Lade", url, flush=True)
    with urllib.request.urlopen(url) as r:
        zipfile.ZipFile(io.BytesIO(r.read())).extractall(py)

    # site-packages aktivieren (in der eingebetteten Laufzeit standardmäßig aus)
    pth = next(py.glob("python3*._pth"))
    lines = [l for l in pth.read_text().splitlines() if l.strip() and not l.lstrip("#").strip() == "import site"]
    pth.write_text("\n".join(lines + ["Lib\\site-packages", "import site"]) + "\n")

    # 2. Abhängigkeiten als Windows-Wheels
    major, minor = PYTHON_VERSION.split(".")[:2]
    run(sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
        "--only-binary=:all:", "--platform", "win_amd64", "--python-version", f"{major}.{minor}",
        "--implementation", "cp", "--target", py / "Lib" / "site-packages",
        "-r", ROOT / "requirements.txt")
    for junk in (py / "Lib" / "site-packages").rglob("__pycache__"):
        shutil.rmtree(junk, ignore_errors=True)

    # 3. App
    app = payload / "app"
    app.mkdir()
    for f in APP_FILES:
        shutil.copy2(ROOT / "src" / f, app / f)
    return payload


def zip_dir(src: Path, dst: Path, prefix: str = "") -> None:
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                z.write(p, f"{prefix}{p.relative_to(src).as_posix()}")


def dotnet_build(project: Path, version: str) -> Path:
    shutil.rmtree(project / "bin", ignore_errors=True)
    shutil.rmtree(project / "obj", ignore_errors=True)
    run("dotnet", "build", project / "Launcher.csproj", "-c", "Release", "--nologo", "-v", "q", f"-p:Version={version}")
    return project / "bin" / "Release" / "net48" / "Plattenkiste.exe"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.1.0")
    version = ap.parse_args().version.lstrip("v")

    BUILD.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(exist_ok=True)
    payload = make_payload()

    # Portable: Laufzeit als Ressource in die EXE
    portable = HERE / "portable"
    zip_dir(payload, portable / "payload.zip")
    digest = hashlib.sha256((portable / "payload.zip").read_bytes()).hexdigest()[:12]
    (portable / "version.txt").write_text(f"{version}-{digest}")
    exe = dotnet_build(portable, version)
    out_exe = DIST / f"Plattenkiste-{version}-windows-portable.exe"
    shutil.copy2(exe, out_exe)

    # Ordner: EXE + runtime/ nebeneinander
    exe = dotnet_build(HERE / "ordner", version)
    folder = BUILD / "Plattenkiste"
    shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(payload, folder / "runtime")
    shutil.copy2(exe, folder / "Plattenkiste.exe")
    out_zip = DIST / f"Plattenkiste-{version}-windows.zip"
    zip_dir(folder, out_zip, "Plattenkiste/")

    for p in (out_exe, out_zip):
        print(f"{p.relative_to(ROOT)}  ({p.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
