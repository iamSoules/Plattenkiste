# Windows-Pakete

Beide Launcher sind kleine C#-Programme (.NET Framework 4.8, auf jedem Windows 10/11 vorhanden). Sie starten
eine eingebettete Python-Laufzeit mit der App. Gemeinsamer Code und gemeinsame Einstellungen liegen in `shared/`.

| Ordner | Ergebnis |
|---|---|
| `portable/` | **eine einzelne EXE**. Die Laufzeit steckt als Ressource darin und wird beim ersten Start nach `%LOCALAPPDATA%\Plattenkiste\runtime-<version>` entpackt. Alte Versionen werden danach entfernt. |
| `ordner/` | **EXE + Ordner `runtime/`**. Nichts wird entpackt. Die EXE startet `runtime\python\pythonw.exe runtime\app\app.py` direkt. |

## Bauen

```bash
python packaging/windows/build.py --version 1.2.0
```

Das Skript läuft unter Windows, macOS und Linux und braucht Python 3.10+ und das .NET SDK (8 oder neuer). Es

1. lädt die Windows-„embeddable“ Python-Laufzeit (x64) von python.org,
2. installiert die Pakete aus `requirements.txt` als `win_amd64`-Wheels,
3. kopiert die App aus `src/` dazu,
4. baut beide Launcher und legt die Ergebnisse in `dist/` ab.

Stürzt die App ab, zeigt der Launcher die letzten Zeilen der Fehlermeldung an und speichert den kompletten
Bericht in `%TEMP%\plattenkiste-fehler.txt`.
