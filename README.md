# 🕐 Cron Manager

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Unix-lightgrey.svg)](https://www.linux.org/)

Ein modernes, benutzerfreundliches CLI-Tool zur Verwaltung von Cronjobs unter Linux/Unix-Systemen. Mit einer eleganten Terminal-Oberfläche, umfangreichen Logging-Funktionen, E-Mail-Benachrichtigungen und Job-Überwachung.


## ✨ Features

### 🎯 Kernfunktionen
- **Intuitive Benutzeroberfläche** - Moderne CLI mit Rich-Library für ansprechende Darstellung
- **Vollständige Cron-Verwaltung** - Erstellen, Bearbeiten, Löschen von User- und System-Cronjobs
- **Job-Templates** - Vordefinierte Vorlagen für häufige Aufgaben (Backup, Reboot, Updates)
- **Einfache Zeitplanung** - Vordefinierte Zeitpläne oder benutzerdefiniert
- **Sofort-Ausführung** - Jobs direkt aus dem Tool heraus testen

### 📊 Erweiterte Features
- **📜 Job-Logging** - Automatische Protokollierung aller Job-Ausführungen in SQLite
- **👁️ Fehler-Überwachung** - Automatische Erkennung und Benachrichtigung bei Fehlern
- **📧 E-Mail-Benachrichtigungen** - SMTP-Integration für Alarme und Reports
- **📈 Statistiken & Reports** - Detaillierte Analysen mit nächsten Ausführungszeiten
- **💾 Backup & Export** - Drei Backup-Modi: Benutzer, System, Komplett
- **🔍 Suchfunktion** - Durchsuchen aller Cronjobs nach Stichwörtern

### 🎯 Job-Templates Kategorien
- **🔄 System-Neustart** - Tägliche, wöchentliche, monatliche Neustarts
- **🔌 System-Shutdown** - Automatisches Herunterfahren
- **💾 Backup-Scripts** - Home, MySQL, Rsync Backups
- **🧹 Wartung** - Log-Bereinigung, Temp-Dateien, Papierkorb
- **📊 Monitoring** - Speicherplatz, System-Status, Netzwerk
- **🔧 Eigene Scripts** - Vorlagen für eigene Bash-Scripts
- **🔄 Updates** - APT, Snap, Flatpak Updates
- **🌐 Web-Server** - Apache, Nginx, SSL-Zertifikate

### 🔐 System-Features (Root)
- Verwaltung von `/etc/crontab`
- Jobs in `/etc/cron.d/` erstellen
- Periodische Jobs (`hourly`, `daily`, `weekly`, `monthly`)
- Multi-User Job-Verwaltung

## 📋 Voraussetzungen

- Python 3.7 oder höher
- Linux/Unix-basiertes Betriebssystem
- Root-Rechte für System-Cronjobs (optional)
- Terminal mit mindestens 120 Zeichen Breite (empfohlen)

## 🚀 Installation

### 1. Repository klonen
```bash
git clone https://github.com/DAI-SW/cron-manager.git
cd cron-manager
```

### 2. Abhängigkeiten installieren

#### Option A: In virtueller Umgebung (empfohlen)
```bash
# Virtuelle Umgebung erstellen
python3 -m venv venv
source venv/bin/activate

# Pakete installieren
pip install -r requirements.txt
```

#### Option B: Systemweit
```bash
sudo pip install rich questionary python-crontab
```

### 3. Ausführbar machen
```bash
chmod +x cron_manager.py
```

### 4. Wrapper-Script für Root-Zugriff (bei virtueller Umgebung)

Wenn du eine virtuelle Python-Umgebung verwendest und Root-Features benötigst, erstelle ein Wrapper-Script:

```bash
nano cron-manager-wrapper.sh
```

Füge folgenden Inhalt ein und passe die Pfade an:

```bash
#!/bin/bash
# cron-manager-wrapper.sh
# Wrapper für Cron Manager mit virtualenv Support

# Pfad zur virtuellen Umgebung anpassen
VENV_PATH="/pfad/zu/ihrer/venv"  # z.B. /home/user/cron-manager/venv
SCRIPT_PATH="$VENV_PATH/../cron_manager.py"  # Pfad zum Hauptscript

# Aktiviere virtualenv und führe Script aus
if [ "$EUID" -eq 0 ]; then
    # Als Root: Verwende die virtualenv Python-Umgebung direkt
    "$VENV_PATH/bin/python" "$SCRIPT_PATH" "$@"
else
    # Als normaler User
    source "$VENV_PATH/bin/activate"
    python "$SCRIPT_PATH" "$@"
fi
```

Mache das Wrapper-Script ausführbar:
```bash
chmod +x cron-manager-wrapper.sh
```

## 📖 Verwendung

### Grundlegende Verwendung

#### Mit Wrapper-Script (empfohlen bei virtueller Umgebung):
```bash
# Als normaler Benutzer
./cron-manager-wrapper.sh

# Mit Root-Rechten für System-Cronjobs
sudo ./cron-manager-wrapper.sh
```

#### Direkte Ausführung (bei systemweiter Installation):
```bash
# Als normaler Benutzer
./cron_manager.py

# Mit Root-Rechten
sudo ./cron_manager.py
```

### Command-Line Optionen

```bash
./cron_manager.py --help        # Hilfe anzeigen
./cron_manager.py --version     # Version anzeigen
./cron_manager.py --backup      # Schnelles Backup erstellen
./cron_manager.py --list        # Jobs auflisten
./cron_manager.py --stats       # Statistiken anzeigen
./cron_manager.py --validate    # Crontab validieren
```

### Hauptmenü-Optionen

| Option | Beschreibung |
|--------|--------------|
| 📋 Jobs anzeigen | Zeigt alle Cronjobs in einer übersichtlichen Tabelle |
| ➕ Job hinzufügen | Erstellt einen neuen Cronjob mit Templates oder manuell |
| ✏️ Job bearbeiten/ausführen | Bearbeiten, Löschen oder sofortiges Ausführen |
| 🔍 Jobs durchsuchen | Suche nach Stichwörtern in allen Jobs |
| 📊 Job-Statistiken | Übersicht mit nächsten Ausführungszeiten |
| 📜 Job-Logs anzeigen | Zeigt Ausführungsprotokolle und Statistiken |
| 👁️ Job-Überwachung | Fehleranalyse und Monitoring-Konfiguration |
| 📧 E-Mail-Benachrichtigungen | SMTP-Konfiguration für Alarme |
| 📥 Jobs exportieren | Export als JSON, CSV, Crontab oder Markdown |
| 📤 Jobs importieren | Import aus JSON oder Crontab-Dateien |
| ✔️ Crontab validieren | Prüft Syntax und Konfiguration |
| 💾 Backup erstellen | Drei Modi: Benutzer, System, Komplett |
| 🔄 Bildschirm aktualisieren | Terminal neu zeichnen |

### Beispiele

#### Neuen Job mit Template erstellen
```bash
1. Wähle "➕ Job hinzufügen"
2. "Möchten Sie eine Vorlage verwenden?" → Ja
3. Wähle Kategorie: "💾 Backup-Scripts"
4. Wähle Template: "Home-Verzeichnis Backup"
5. Optional anpassen oder direkt übernehmen
6. Logging aktivieren? → Ja
```

#### Job sofort ausführen
```bash
1. Wähle "✏️ Job bearbeiten/ausführen"
2. Wähle den gewünschten Job
3. Wähle "▶️ Sofort ausführen"
4. Im Hintergrund ausführen? → Ja/Nein
5. Ausgabe wird angezeigt
```

#### Backup erstellen
```bash
1. Wähle "💾 Backup erstellen"
2. Wähle Backup-Typ:
   - Nur Benutzer-Crontab (einfaches Textfile)
   - Alle verfügbaren Crontabs (inkl. System)
   - Komplettes Backup (inkl. Logs & Config als tar.gz)
3. Backup wird in ~/.cron_manager/backups/ gespeichert
```

#### E-Mail-Benachrichtigungen einrichten
```bash
1. Wähle "📧 E-Mail-Benachrichtigungen"
2. "E-Mail-Einstellungen konfigurieren"
3. SMTP-Server: smtp.gmail.com
4. Port: 587
5. E-Mail und App-Passwort eingeben
6. "Test-E-Mail senden"
```

## 🗂️ Dateistruktur

```
cron-manager/
├── cron_manager.py         # Hauptscript
├── cron-manager-wrapper.sh # Wrapper für virtualenv (optional)
├── requirements.txt        # Python-Abhängigkeiten
├── README.md              # Diese Datei
└── LICENSE                # MIT-Lizenz

~/.cron_manager/           # Benutzerdaten (automatisch erstellt)
├── backups/               # Backup-Verzeichnis
│   ├── crontab_user_*.txt
│   └── cron_manager_complete_*.tar.gz
├── logs.db                # SQLite-Datenbank für Job-Logs
├── config.ini             # Konfigurationsdatei
└── wrappers/              # Wrapper-Scripts für Logging
    └── wrapper_*.sh       # Automatisch generierte Scripts
```

## ⚙️ Konfiguration

Die Konfigurationsdatei `~/.cron_manager/config.ini` wird automatisch erstellt:

```ini
[email]
enabled = false
smtp_server = smtp.gmail.com
smtp_port = 587
use_tls = true
sender = your-email@gmail.com
password = your-app-password
recipient = admin@example.com
notify_on_failure = true
notify_on_success = false

[monitoring]
enabled = true
check_interval = 300     # Prüfintervall in Sekunden
max_failures = 3         # Max. Fehler vor Benachrichtigung

[templates]
custom_scripts_path = ~/scripts
enable_custom_templates = true
```

## 🐧 Kompatibilität

Getestet und kompatibel mit:
- **Ubuntu** 20.04, 22.04, 24.04
- **Debian** 10, 11, 12
- **Linux Mint** 20, 21
- **Raspberry Pi OS** (Raspbian)
- Andere Debian-basierte Distributionen

## 🔧 Fehlerbehebung

### Problem: Root-Features funktionieren nicht in virtueller Umgebung

**Lösung:** Verwende das Wrapper-Script (siehe Installation Schritt 4)

### Problem: Import-Fehler bei Modulen

**Lösung 1:** Pakete in der aktuellen Umgebung installieren:
```bash
pip install rich questionary python-crontab
```

**Lösung 2:** Bei Root-Problemen systemweit installieren:
```bash
sudo pip install rich questionary python-crontab
```

### Problem: Keine System-Cronjobs sichtbar

**Prüfe:**
```bash
# Läuft Cron?
systemctl status cron

# Existieren die Verzeichnisse?
ls -la /etc/cron*

# Haben Sie Root-Rechte?
sudo ./cron-manager-wrapper.sh
```

### Problem: Nächste Ausführungen werden nicht angezeigt

**Lösung:** Die Funktion zeigt nur Jobs mit gültigen Zeitplänen. @reboot Jobs werden als "Bei Neustart" angezeigt.

## 📊 Job-Logging

### Automatisches Logging
Beim Erstellen eines Jobs kann automatisches Logging aktiviert werden. Das Tool erstellt dann ein Wrapper-Script, das:
- Den Original-Befehl ausführt
- stdout und stderr erfasst
- Exit-Code protokolliert
- Laufzeit misst
- Alles in der SQLite-Datenbank speichert

### Log-Analyse
- **Erfolgsrate**: Prozentsatz erfolgreicher Ausführungen
- **Fehler-Trends**: Häufigste Fehlerquellen
- **Performance**: Durchschnittliche Laufzeiten
- **Timeline**: Wann treten Fehler auf?
- **Nächste Ausführungen**: Zeigt die nächsten 10 geplanten Jobs

## 🚨 Fehlerbehandlung

### Überwachungsfunktionen
- Automatische Fehler-Erkennung
- Konfigurierbare Schwellwerte
- E-Mail-Alarme bei kritischen Fehlern
- Detaillierte Fehler-Reports als Markdown

## 💡 Tipps & Tricks

### Terminal-Größe
Für optimale Darstellung verwende ein Terminal mit mindestens 120 Zeichen Breite. Die Befehlsspalte zeigt bis zu 60 Zeichen.

### Alias erstellen
Füge zu deiner `.bashrc` hinzu:
```bash
alias cronmgr='/pfad/zu/cron-manager-wrapper.sh'
alias sudo-cronmgr='sudo /pfad/zu/cron-manager-wrapper.sh'
```

### Automatisches Backup
Erstelle einen Cronjob für regelmäßige Backups:
```bash
0 0 * * 0 /pfad/zu/cron-manager-wrapper.sh --backup
```

### Job-Templates anpassen
Die Templates können während der Erstellung angepasst werden. Eigene Script-Pfade können in der config.ini konfiguriert werden.

## 🔒 Sicherheit

- **Benutzer-Isolation**: Normale Benutzer können nur eigene Jobs verwalten
- **Root-Schutz**: System-Jobs nur mit Root-Rechten
- **Sichere Wrapper**: Job-Ausführung mit korrekten Berechtigungen
- **Passwort-Schutz**: E-Mail-Passwörter werden lokal gespeichert (App-Passwörter empfohlen)

## 🤝 Beitragen

Contributions sind willkommen! Bitte beachte:

1. Fork des Repositories erstellen
2. Feature-Branch erstellen (`git checkout -b feature/AmazingFeature`)
3. Änderungen committen (`git commit -m 'Add some AmazingFeature'`)
4. Branch pushen (`git push origin feature/AmazingFeature`)
5. Pull Request erstellen

## 📝 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe [LICENSE](LICENSE) für Details.

## 🙏 Danksagungen

- [Rich](https://github.com/Textualize/rich) - Für die Terminal-UI
- [Questionary](https://github.com/tmbo/questionary) - Für interaktive Prompts
- [Python-Crontab](https://gitlab.com/doctormo/python-crontab) - Für Crontab-Manipulation

## 📞 Support

Bei Fragen oder Problemen:
- 🐛 [Issue erstellen](https://github.com/DAI-SW/cron-manager/issues)
- 📧 E-Mail: support@example.com
- 📚 [Wiki](https://github.com/DAI-SW/cron-manager/wiki)

## 🗺️ Roadmap

- [ ] Web-Interface für Remote-Verwaltung
- [ ] Cron-Syntax-Validator mit Live-Vorschau
- [ ] Integration mit Systemd-Timern
- [ ] Docker-Container Support
- [ ] Job-Dependencies und Workflows
- [ ] Cloud-Backup-Integration (S3, Google Drive)
- [ ] Mobile App für Monitoring
- [ ] Webhook-Integration (Discord, Slack, Teams)
- [ ] Multi-Server Management
- [ ] Job-Performance-Graphen

## 📈 Changelog

### Version 1.0.0 (2025-08-14)
- Initiale Veröffentlichung
- Vollständige Cron-Verwaltung
- Job-Templates in 8 Kategorien
- Umfangreiches Logging-System
- E-Mail-Benachrichtigungen
- Backup-Funktionen
- Fehlerüberwachung
- Export/Import-Funktionen
- Command-Line-Argumente
- Wrapper-Script für virtualenv

---

<p align="center">
  Made with ❤️ for the Linux Community
</p>
