# Windows-Pakete bauen

Beide Launcher sind kleine C#-Programme (.NET Framework 4.8), die eine eingebettete Python-Laufzeit starten.

## Laufzeit vorbereiten (`payload/`)

```
payload/
  python/   ← Windows-„embeddable“ Python 3.13 (x64), z. B. aus dem NuGet-Paket „python“
              + Pakete aus requirements.txt (win_amd64-Wheels) in python/Lib/site-packages
  app/      ← app.py, core.py, dupes.py, tagger.py, icon.png
```

## Portable EXE (`windows-portable/`)

Eine einzelne EXE. Beim ersten Start wird die Laufzeit nach
`%LOCALAPPDATA%\Plattenkiste\runtime-<version>` entpackt.

1. `payload/` als `payload.zip` neben `Launcher.csproj` legen.
2. Eine eindeutige Versionskennung in `version.txt` schreiben (z. B. die ersten 12 Zeichen des SHA-256 von `payload.zip`).
3. `dotnet build -c Release` ausführen. Die Ausgabe liegt in `bin/Release/net48/Plattenkiste.exe`.

## Ordner-Version (`windows-ordner/`)

Hier wird nichts entpackt: Die EXE startet `runtime\python\pythonw.exe runtime\app\app.py` direkt neben sich.

1. `dotnet build -c Release` ausführen.
2. Einen Ordner mit `Plattenkiste.exe` und `runtime/` (Inhalt von `payload/`) anlegen.
