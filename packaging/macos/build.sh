#!/usr/bin/env bash
# Baut Plattenkiste.app für macOS und packt sie als ZIP nach dist/.
#
#   packaging/macos/build.sh [version]   (Standard: Inhalt der Datei VERSION)
#
# Muss auf einem Mac laufen (Python 3.10+). Die Architektur (Apple Silicon / Intel)
# richtet sich nach dem Python, mit dem gebaut wird.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="${1:-$(cat "$ROOT/VERSION")}"; VERSION="${VERSION#v}"
BUILD="$ROOT/build/macos"
ARCH="$(uname -m)"; [ "$ARCH" = "x86_64" ] && ARCH_NAME="intel" || ARCH_NAME="apple-silicon"

rm -rf "$BUILD"; mkdir -p "$BUILD" "$ROOT/dist"
python3 -m venv "$BUILD/venv"
"$BUILD/venv/bin/pip" install -q --disable-pip-version-check -r "$ROOT/requirements.txt" pyinstaller

# App-Icon (.icns) aus icon.png erzeugen
ICONSET="$BUILD/icon.iconset"; mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$ROOT/src/icon.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$ROOT/src/icon.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$BUILD/icon.icns"

"$BUILD/venv/bin/pyinstaller" --noconfirm --clean --windowed \
  --name Plattenkiste \
  --icon "$BUILD/icon.icns" \
  --osx-bundle-identifier de.plattenkiste.app \
  --add-data "$ROOT/src/icon.png:." \
  --distpath "$BUILD/dist" --workpath "$BUILD/work" --specpath "$BUILD" \
  "$ROOT/src/app.py"

PLIST="$BUILD/dist/Plattenkiste.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $VERSION" "$PLIST" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :NSHighResolutionCapable bool true" "$PLIST" 2>/dev/null || true
codesign --force --deep --sign - "$BUILD/dist/Plattenkiste.app"   # Ad-hoc-Signatur (nötig auf Apple Silicon)

OUT="$ROOT/dist/Plattenkiste-$VERSION-macos-$ARCH_NAME.zip"
ditto -c -k --keepParent "$BUILD/dist/Plattenkiste.app" "$OUT"
echo "$OUT"
