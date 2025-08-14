# cron-manager
Consolen Cronjob Managment Tool 

# 🕐 Cron Manager

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Unix-lightgrey.svg)](https://www.linux.org/)

Ein modernes, benutzerfreundliches CLI-Tool zur Verwaltung von Cronjobs unter Linux/Unix-Systemen. Mit einer eleganten Terminal-Oberfläche, umfangreichen Logging-Funktionen, E-Mail-Benachrichtigungen und Job-Überwachung.

![Cron Manager Demo](demo.png)

## ✨ Features

### 🎯 Kernfunktionen
- **Intuitive Benutzeroberfläche** - Moderne CLI mit Rich-Library für ansprechende Darstellung
- **Vollständige Cron-Verwaltung** - Erstellen, Bearbeiten, Löschen von User- und System-Cronjobs
- **Einfache Zeitplanung** - Vordefinierte Zeitpläne (stündlich, täglich, etc.) oder benutzerdefiniert
- **Sofort-Ausführung** - Jobs direkt aus dem Tool heraus testen
- **Mehrsprachige Unterstützung** - Deutsche Benutzeroberfläche

### 📊 Erweiterte Features
- **📜 Job-Logging** - Automatische Protokollierung aller Job-Ausführungen in SQLite-Datenbank
- **👁️ Fehler-Überwachung** - Automatische Erkennung und Benachrichtigung bei Job-Fehlern
- **📧 E-Mail-Benachrichtigungen** - SMTP-Integration für Alarme und Reports
- **📈 Statistiken & Reports** - Detaillierte Analysen und Fehler-Reports
- **💾 Backup & Export** - Sicherung und Migration von Cronjobs (JSON, CSV, Markdown)
- **🔍 Suchfunktion** - Durchsuchen aller Cronjobs nach Stichwörtern

### 🔐 System-Features (Root)
- Verwaltung von `/etc/crontab`
- Jobs in `/etc/cron.d/` erstellen
- Periodische Jobs (`hourly`, `daily`, `weekly`, `monthly`)
- Multi-User Job-Verwaltung

## 📋 Voraussetzungen

- Python 3.7 oder höher
- Linux/Unix-basiertes Betriebssystem
- Root-Rechte für System-Cronjobs (optional)

## 🚀 Installation

### 1. Repository klonen
```bash
git clone https://github.com/DAI-SW/cron-manager.git
cd cron-manager
```

### 2. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

Oder manuell:
```bash
pip install rich questionary python-crontab
```

### 3. Ausführbar machen
```bash
chmod +x cron_manager.py
```

## 📖 Verwendung

### Grundlegende Verwendung

```bash
# Als normaler Benutzer
./cron_manager.py

# Mit Root-Rechten für System-Cronjobs
sudo ./cron_manager.py
```

### Hauptmenü-Optionen

| Option | Beschreibung |
|--------|--------------|
| 📋 Jobs anzeigen | Zeigt alle Cronjobs in einer übersichtlichen Tabelle |
| ➕ Job hinzufügen | Erstellt einen neuen Cronjob mit Assistent |
| ✏️ Job bearbeiten/ausführen | Bearbeiten, Löschen oder sofortiges Ausführen |
| 📜 Job-Logs anzeigen | Zeigt Ausführungsprotokolle und Statistiken |
| 👁️ Job-Überwachung | Fehleranalyse und Monitoring-Konfiguration |
| 📧 E-Mail-Benachrichtigungen | SMTP-Konfiguration für Alarme |

### Beispiele

#### Neuen Job mit Logging erstellen
```bash
1. Wähle "➕ Job hinzufügen"
2. Gib den Befehl ein: /home/user/backup.sh
3. Wähle Zeitplan: "Täglich"
4. Zeit eingeben: 02:00
5. Logging aktivieren? → Ja
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
~/.cron_manager/
├── logs.db              # SQLite-Datenbank für Job-Logs
├── config.ini           # Konfigurationsdatei
└── wrappers/            # Wrapper-Scripts für Logging
    └── wrapper_*.sh     # Automatisch generierte Scripts
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
```

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

## 🚨 Fehlerbehandlung

### Überwachungsfunktionen
- Automatische Fehler-Erkennung
- Konfigurierbare Schwellwerte
- E-Mail-Alarme bei kritischen Fehlern
- Detaillierte Fehler-Reports

### Fehler-Report Beispiel
```markdown
# Cron Manager - Fehler-Report

Erstellt am: 15.08.2025 10:30:00
Zeitraum: Letzte 7 Tage

## Zusammenfassung
- Fehlgeschlagene Jobs: 3
- Gesamte Fehler: 12

## Fehler-Details
### /home/user/backup.sh
- Anzahl Fehler: 8
- Erster Fehler: 2025-08-10 02:00:01
- Letzter Fehler: 2025-08-14 02:00:02
- Fehlermeldungen:
  - Backup-Verzeichnis nicht gefunden
  - Speicherplatz nicht ausreichend
```

## 🔒 Sicherheit

- **Benutzer-Isolation**: Normale Benutzer können nur eigene Jobs verwalten
- **Root-Schutz**: System-Jobs nur mit Root-Rechten
- **Sichere Wrapper**: Job-Ausführung mit korrekten Berechtigungen
- **Passwort-Schutz**: E-Mail-Passwörter werden lokal verschlüsselt gespeichert

## 🤝 Beitragen

Contributions sind willkommen! Bitte beachten Sie:

1. Fork des Repositories erstellen
2. Feature-Branch erstellen (`git checkout -b feature/AmazingFeature`)
3. Änderungen committen (`git commit -m 'Add some AmazingFeature'`)
4. Branch pushen (`git push origin feature/AmazingFeature`)
5. Pull Request erstellen

## 📝 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert - siehe [LICENSE](LICENSE) für Details.

## 🙏 Danksagungen

- [Rich](https://github.com/Textualize/rich) - Für die wunderschöne Terminal-UI
- [Questionary](https://github.com/tmbo/questionary) - Für interaktive Prompts
- [Python-Crontab](https://gitlab.com/doctormo/python-crontab) - Für Crontab-Manipulation

## 📞 Support

Bei Fragen oder Problemen:
- 🐛 [Issue erstellen](https://github.com/DAI-SW/cron-manager/issues)
- 📧 E-Mail: support@example.com
- 📚 [Wiki](https://github.com/DAI-SW/cron-manager/wiki)

## 🗺️ Roadmap

- [ ] Web-Interface für Remote-Verwaltung
- [ ] Cron-Syntax-Validator mit Vorschau
- [ ] Integration mit Systemd-Timern
- [ ] Mehrsprachige Unterstützung (EN, ES, FR)
- [ ] Job-Dependencies und Workflows
- [ ] Cloud-Backup-Integration
- [ ] Mobile App für Monitoring

---

<p align="center">
  Made with ❤️ for the Linux Community
</p>
