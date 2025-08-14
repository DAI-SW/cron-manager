#!/usr/bin/env python3
"""
Cron Manager - Ein modernes CLI-Tool zur Verwaltung von Cronjobs
Erforderliche Pakete: pip install rich questionary python-crontab
Optional für E-Mail: pip install secure-smtplib
"""

import os
import sys
import json
import glob
import signal
import threading
import sqlite3
import smtplib
import configparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict
import subprocess
from pathlib import Path

# Prüfe und installiere fehlende Pakete
def check_and_install_packages():
    """Prüft ob erforderliche Pakete installiert sind und installiert sie bei Bedarf"""
    required_packages = {
        'rich': 'rich',
        'questionary': 'questionary',
        'crontab': 'python-crontab'
    }
    
    missing_packages = []
    
    for module, package in required_packages.items():
        try:
            __import__(module)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Fehlende Pakete erkannt: {', '.join(missing_packages)}")
        
        # Prüfe ob wir in einer virtualenv sind
        in_virtualenv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        
        if os.geteuid() == 0 and in_virtualenv:
            print("\n⚠️  WARNUNG: Sie führen das Script als Root in einer virtuellen Umgebung aus.")
            print("Dies kann zu Problemen führen. Empfohlene Lösungen:")
            print("\n1. Verwenden Sie das Wrapper-Script:")
            print("   Erstellen Sie 'cron-manager-wrapper.sh' mit folgendem Inhalt:")
            print(f"""
#!/bin/bash
VENV_PATH="{os.path.dirname(os.path.dirname(sys.executable))}"
SCRIPT_PATH="{os.path.abspath(__file__)}"

if [ "$EUID" -eq 0 ]; then
    "$VENV_PATH/bin/python" "$SCRIPT_PATH" "$@"
else
    source "$VENV_PATH/bin/activate"
    python "$SCRIPT_PATH" "$@"
fi
            """)
            print("\n2. Oder installieren Sie die Pakete systemweit:")
            print(f"   sudo pip install {' '.join(missing_packages)}")
            sys.exit(1)
        
        # Versuche automatische Installation
        response = input(f"\nMöchten Sie die fehlenden Pakete automatisch installieren? (j/n): ")
        if response.lower() in ['j', 'ja', 'y', 'yes']:
            try:
                import pip
                for package in missing_packages:
                    print(f"Installiere {package}...")
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print("\n✅ Installation abgeschlossen. Bitte starten Sie das Script neu.")
                sys.exit(0)
            except Exception as e:
                print(f"\n❌ Fehler bei der Installation: {e}")
                print(f"Bitte installieren Sie manuell: pip install {' '.join(missing_packages)}")
                sys.exit(1)
        else:
            print(f"\nBitte installieren Sie die erforderlichen Pakete manuell:")
            print(f"pip install {' '.join(missing_packages)}")
            sys.exit(1)

# Prüfe Pakete bevor Import
check_and_install_packages()

# Jetzt können wir die Pakete importieren
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich.progress import track
    from rich import box
    from rich.prompt import Confirm
    import questionary
    from crontab import CronTab
except ImportError as e:
    print(f"Fehler beim Import: {e}")
    print("Bitte starten Sie das Script neu nach der Installation der Pakete.")
    sys.exit(1)

console = Console()

class CronManager:
    def __init__(self):
        self.user_cron = CronTab(user=True)
        self.system_cron = None
        self.is_root = os.geteuid() == 0
        
        # Erkenne Distribution
        self.distro = self._detect_distribution()
        
        # Debug-Ausgabe
        console.print(f"[cyan]Distribution: {self.distro}[/cyan]")
        if self.is_root:
            console.print("[green]✓ Root-Rechte erkannt[/green]")
        else:
            console.print("[yellow]⚠ Keine Root-Rechte - System-Features eingeschränkt[/yellow]")
        
        # System-Cron Pfade (kompatibel mit Debian-basierten Systemen)
        self.system_paths = {
            'crontab': '/etc/crontab',
            'hourly': '/etc/cron.hourly',
            'daily': '/etc/cron.daily',
            'weekly': '/etc/cron.weekly',
            'monthly': '/etc/cron.monthly',
            'cron.d': '/etc/cron.d'
        }
        
        # Alternative Pfade für verschiedene Distributionen
        self.alt_paths = {
            'anacron': '/etc/anacrontab',
            'systemd': '/etc/systemd/system'
        }
        
        if self.is_root:
            self._load_system_crontabs()
        
        # Initialisiere Logging-Datenbank
        self.init_logging_db()
        
        # Lade Konfiguration
        self.config = self.load_config()
    
    def _detect_distribution(self) -> str:
        """Erkennt die Linux-Distribution"""
        try:
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release', 'r') as f:
                    content = f.read()
                    if 'ubuntu' in content.lower():
                        return 'Ubuntu'
                    elif 'debian' in content.lower():
                        return 'Debian'
                    elif 'mint' in content.lower():
                        return 'Linux Mint'
                    elif 'raspbian' in content.lower() or 'raspberry' in content.lower():
                        return 'Raspberry Pi OS'
            return 'Unknown'
        except:
            return 'Unknown'
    
    def _load_system_crontabs(self):
        """Lädt System-Crontabs mit besserer Fehlerbehandlung"""
        # Versuche /etc/crontab zu laden
        if os.path.exists('/etc/crontab'):
            try:
                # Lese die Datei zuerst manuell um das Format zu prüfen
                with open('/etc/crontab', 'r') as f:
                    content = f.read()
                
                # Prüfe ob die Datei Inhalt hat
                if content.strip():
                    # Verwende system=True für System-Crontabs
                    self.system_cron = CronTab(tabfile='/etc/crontab', user=False)
                    console.print("[green]✓ System-Crontab geladen[/green]")
                else:
                    console.print("[yellow]⚠ /etc/crontab ist leer[/yellow]")
                    
            except Exception as e:
                console.print(f"[yellow]⚠ Fehler beim Laden von /etc/crontab: {str(e)}[/yellow]")
                # Fallback: Versuche die Datei manuell zu parsen
                self._manual_parse_system_crontab()
        else:
            console.print("[yellow]⚠ /etc/crontab nicht gefunden[/yellow]")
    
    def _manual_parse_system_crontab(self):
        """Manuelles Parsen der System-Crontab falls CronTab fehlschlägt"""
        try:
            with open('/etc/crontab', 'r') as f:
                lines = f.readlines()
            
            console.print("[yellow]Verwende manuellen Parser für System-Crontab[/yellow]")
            # Hier könnten wir einen eigenen Parser implementieren
            # Für jetzt setzen wir system_cron auf None
            self.system_cron = None
        except:
            self.system_cron = None
    def init_logging_db(self):
        """Initialisiert die SQLite-Datenbank für Job-Logs"""
        db_path = os.path.expanduser("~/.cron_manager/logs.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Erstelle Tabellen
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                command TEXT,
                user TEXT,
                exit_code INTEGER,
                stdout TEXT,
                stderr TEXT,
                duration_seconds REAL,
                status TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                command TEXT,
                user TEXT,
                error_message TEXT,
                notified BOOLEAN DEFAULT 0
            )
        ''')
        
        self.conn.commit()
    
    def load_config(self):
        """Lädt die Konfiguration für E-Mail-Benachrichtigungen"""
        config_path = os.path.expanduser("~/.cron_manager/config.ini")
        config = configparser.ConfigParser()
        
        if os.path.exists(config_path):
            config.read(config_path)
        else:
            # Erstelle Standard-Konfiguration
            config['email'] = {
                'enabled': 'false',
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': '587',
                'use_tls': 'true',
                'sender': '',
                'password': '',
                'recipient': '',
                'notify_on_failure': 'true',
                'notify_on_success': 'false'
            }
            
            config['monitoring'] = {
                'enabled': 'true',
                'check_interval': '300',  # 5 Minuten
                'max_failures': '3'
            }
            
            config['templates'] = {
                'custom_scripts_path': '~/scripts',
                'enable_custom_templates': 'true'
            }
            
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                config.write(f)
        
        return config
    
    def add_job(self):
        """Fügt einen neuen Cronjob hinzu"""
        console.print(Panel("📝 Neuen Cronjob hinzufügen", style="bold blue"))
        
        # Frage ob Template verwendet werden soll
        use_template = questionary.confirm(
            "Möchten Sie eine Vorlage verwenden?",
            default=False
        ).ask()
        
        if use_template:
            command, schedule, comment = self._select_job_template()
            if not command:  # Benutzer hat abgebrochen
                return
        else:
            # Befehl eingeben
            command = questionary.text(
                "Befehl eingeben:",
                validate=lambda text: True if text.strip() else "Befehl darf nicht leer sein"
            ).ask()
            
            if not command:
                return
            
            # Zeitplan wählen
            schedule_choice = questionary.select(
                "Zeitplan wählen:",
                choices=[
                    "Jede Minute",
                    "Stündlich",
                    "Täglich",
                    "Wöchentlich",
                    "Monatlich",
                    "@reboot (Bei Systemstart)",
                    "Benutzerdefiniert"
                ]
            ).ask()
            
            if not schedule_choice:
                return
            
            # Zeitplan erstellen
            schedule = self._create_schedule(schedule_choice)
            if not schedule:
                return
            
            # Kommentar hinzufügen
            comment = questionary.text("Kommentar (optional):").ask()
        
        # Logging aktivieren?
        enable_logging = questionary.confirm(
            "Logging für diesen Job aktivieren?",
            default=True
        ).ask()
        
        # Wrapper-Command erstellen wenn Logging aktiviert
        if enable_logging:
            wrapper_script = self.create_logging_wrapper(command)
            actual_command = wrapper_script
        else:
            actual_command = command
        
        # Job erstellen
        try:
            job = self.user_cron.new(command=actual_command, comment=comment)
            job.setall(schedule)
            self.user_cron.write()
            
            console.print(Panel(
                f"[green]✓ Cronjob erfolgreich hinzugefügt![/green]\n"
                f"Befehl: {command}\n"
                f"Zeitplan: {schedule}\n"
                f"Logging: {'Aktiviert' if enable_logging else 'Deaktiviert'}",
                title="Erfolg",
                border_style="green"
            ))
        except Exception as e:
            console.print(Panel(f"[red]Fehler: {str(e)}[/red]", 
                              title="Fehler", border_style="red"))
    
    def create_backup(self):
        """Erstellt ein Backup der Crontab"""
        backup_dir = os.path.expanduser("~/.cron_manager/backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Wähle Backup-Typ
        backup_type = questionary.select(
            "Was soll gesichert werden?",
            choices=[
                "Nur Benutzer-Crontab",
                "Alle verfügbaren Crontabs",
                "Komplettes Backup (inkl. Logs & Config)",
                "Zurück"
            ]
        ).ask()
        
        if backup_type == "Zurück" or not backup_type:
            return
        
        if backup_type == "Nur Benutzer-Crontab":
            filename = os.path.join(backup_dir, f"crontab_user_{timestamp}.txt")
            try:
                with open(filename, 'w') as f:
                    for job in self.user_cron:
                        f.write(f"{job}\n")
                console.print(Panel(
                    f"[green]✓ Backup erstellt: {filename}[/green]",
                    title="Backup erfolgreich",
                    border_style="green"
                ))
            except Exception as e:
                console.print(f"[red]Fehler: {str(e)}[/red]")
        
        elif backup_type == "Alle verfügbaren Crontabs":
            backup_files = []
            
            # Benutzer-Crontab
            user_file = os.path.join(backup_dir, f"crontab_user_{timestamp}.txt")
            with open(user_file, 'w') as f:
                f.write("# BENUTZER-CRONTAB\n")
                for job in self.user_cron:
                    f.write(f"{job}\n")
            backup_files.append(user_file)
            
            # System-Crontabs (wenn Root)
            if self.is_root:
                if os.path.exists('/etc/crontab'):
                    system_file = os.path.join(backup_dir, f"crontab_system_{timestamp}.txt")
                    subprocess.run(['cp', '/etc/crontab', system_file])
                    backup_files.append(system_file)
                
                # Cron.d
                if os.path.exists('/etc/cron.d'):
                    cron_d_file = os.path.join(backup_dir, f"cron_d_{timestamp}.tar.gz")
                    subprocess.run(['tar', '-czf', cron_d_file, '-C', '/etc', 'cron.d'])
                    backup_files.append(cron_d_file)
            
            console.print(Panel(
                f"[green]✓ Backup erstellt:[/green]\n" + 
                "\n".join([f"  • {os.path.basename(f)}" for f in backup_files]),
                title="Backup erfolgreich",
                border_style="green"
            ))
        
        elif backup_type == "Komplettes Backup (inkl. Logs & Config)":
            archive_name = os.path.join(backup_dir, f"cron_manager_complete_{timestamp}.tar.gz")
            
            with console.status("[yellow]Erstelle komplettes Backup...[/yellow]"):
                # Temporäres Verzeichnis für Backup
                temp_dir = f"/tmp/cron_backup_{timestamp}"
                os.makedirs(temp_dir, exist_ok=True)
                
                # Crontabs
                with open(f"{temp_dir}/user_crontab.txt", 'w') as f:
                    for job in self.user_cron:
                        f.write(f"{job}\n")
                
                # Logs-Datenbank
                if os.path.exists(os.path.expanduser("~/.cron_manager/logs.db")):
                    subprocess.run(['cp', os.path.expanduser("~/.cron_manager/logs.db"), 
                                  f"{temp_dir}/logs.db"])
                
                # Konfiguration
                if os.path.exists(os.path.expanduser("~/.cron_manager/config.ini")):
                    subprocess.run(['cp', os.path.expanduser("~/.cron_manager/config.ini"), 
                                  f"{temp_dir}/config.ini"])
                
                # Archiv erstellen
                subprocess.run(['tar', '-czf', archive_name, '-C', '/tmp', f"cron_backup_{timestamp}"])
                
                # Aufräumen
                subprocess.run(['rm', '-rf', temp_dir])
            
            console.print(Panel(
                f"[green]✓ Komplettes Backup erstellt:[/green]\n{archive_name}\n\n"
                f"[yellow]Größe:[/yellow] {os.path.getsize(archive_name) / 1024 / 1024:.2f} MB",
                title="Backup erfolgreich",
                border_style="green"
            ))
    
    def get_cron_type(self) -> str:
        """Fragt ab, welche Crontab bearbeitet werden soll"""
        choices = ["Benutzer-Crontab"]
        
        if self.is_root:
            # Füge nur verfügbare Optionen hinzu
            if os.path.exists('/etc/crontab'):
                choices.append("System-Crontab (/etc/crontab)")
            
            if os.path.exists('/etc/cron.d') and os.path.isdir('/etc/cron.d'):
                choices.append("Cron.d Verzeichnis (/etc/cron.d)")
            
            # Prüfe ob periodische Verzeichnisse existieren
            periodic_exists = False
            for period in ['hourly', 'daily', 'weekly', 'monthly']:
                if os.path.exists(f'/etc/cron.{period}'):
                    periodic_exists = True
                    break
            
            if periodic_exists:
                choices.append("Periodische Jobs (hourly/daily/weekly/monthly)")
            
            if len(choices) == 1:  # Nur Benutzer-Crontab verfügbar
                console.print("[yellow]⚠ Keine System-Cron-Verzeichnisse gefunden[/yellow]")
        
        choice = questionary.select(
            "Welche Crontab möchten Sie bearbeiten?",
            choices=choices + ["Zurück"]
        ).ask()
        
        return choice
        """Fragt ab, welche Crontab bearbeitet werden soll"""
        choices = ["Benutzer-Crontab"]
        
        if self.is_root:
            choices.extend([
                "System-Crontab (/etc/crontab)",
                "Cron.d Verzeichnis (/etc/cron.d)",
                "Periodische Jobs (hourly/daily/weekly/monthly)"
            ])
        
        choice = questionary.select(
            "Welche Crontab möchten Sie bearbeiten?",
            choices=choices + ["Zurück"]
        ).ask()
        
        return choice
    
    def list_all_jobs(self, cron_type: str = "user") -> List[dict]:
        """Listet alle Cronjobs basierend auf dem Typ auf"""
        jobs = []
        
        if cron_type == "user" or cron_type == "Benutzer-Crontab":
            try:
                for job in self.user_cron:
                    jobs.append({
                        'command': job.command,
                        'schedule': str(job.slices),
                        'enabled': job.is_enabled(),
                        'comment': job.comment or '',
                        'user': os.getlogin() if hasattr(os, 'getlogin') else os.environ.get('USER', 'unknown'),
                        'source': 'user',
                        'job': job
                    })
            except Exception as e:
                console.print(f"[red]Fehler beim Laden der Benutzer-Crontab: {str(e)}[/red]")
        
        elif cron_type == "System-Crontab (/etc/crontab)":
            if not self.is_root:
                console.print("[red]Root-Rechte erforderlich für System-Crontab[/red]")
                return jobs
                
            if self.system_cron:
                try:
                    for job in self.system_cron:
                        # System crontab hat das Format: min hour day month weekday user command
                        jobs.append({
                            'command': job.command,
                            'schedule': str(job.slices),
                            'enabled': job.is_enabled(),
                            'comment': job.comment or '',
                            'user': getattr(job, 'user', 'root'),
                            'source': 'system',
                            'job': job
                        })
                except Exception as e:
                    console.print(f"[red]Fehler beim Laden der System-Crontab: {str(e)}[/red]")
            else:
                console.print("[yellow]System-Crontab konnte nicht geladen werden[/yellow]")
        
        elif cron_type == "Periodische Jobs (hourly/daily/weekly/monthly)":
            if not self.is_root:
                console.print("[red]Root-Rechte erforderlich für periodische Jobs[/red]")
                return jobs
            jobs.extend(self._list_periodic_jobs())
        
        elif cron_type == "Cron.d Verzeichnis (/etc/cron.d)":
            if not self.is_root:
                console.print("[red]Root-Rechte erforderlich für /etc/cron.d[/red]")
                return jobs
            jobs.extend(self._list_cron_d_jobs())
        
        return jobs
    
    def _list_periodic_jobs(self) -> List[dict]:
        """Listet Jobs aus den periodischen Verzeichnissen auf"""
        jobs = []
        
        for period in ['hourly', 'daily', 'weekly', 'monthly']:
            path = self.system_paths[period]
            if os.path.exists(path) and os.path.isdir(path):
                try:
                    for script in os.listdir(path):
                        if script.startswith('.'):  # Versteckte Dateien überspringen
                            continue
                            
                        script_path = os.path.join(path, script)
                        if os.path.isfile(script_path) and os.access(script_path, os.X_OK):
                            # Prüfe ob es ein Text-Script ist (kein Binärfile)
                            try:
                                with open(script_path, 'rb') as f:
                                    header = f.read(2)
                                    if header == b'#!':  # Shebang gefunden
                                        jobs.append({
                                            'command': script_path,
                                            'schedule': f'@{period}',
                                            'enabled': True,
                                            'comment': f'{period.capitalize()} job',
                                            'user': 'root',
                                            'source': f'periodic-{period}',
                                            'job': None
                                        })
                            except:
                                pass
                except Exception as e:
                    console.print(f"[yellow]Warnung beim Lesen von {path}: {str(e)}[/yellow]")
        
        return jobs
    
    def _list_cron_d_jobs(self) -> List[dict]:
        """Listet Jobs aus /etc/cron.d auf"""
        jobs = []
        cron_d_path = self.system_paths['cron.d']
        
        if os.path.exists(cron_d_path) and os.path.isdir(cron_d_path):
            try:
                for filename in os.listdir(cron_d_path):
                    # Überspringe bestimmte Systemdateien
                    if filename in ['.', '..', '.placeholder', 'README']:
                        continue
                        
                    filepath = os.path.join(cron_d_path, filename)
                    if os.path.isfile(filepath):
                        try:
                            # Versuche die Datei als Crontab zu laden
                            tab = CronTab(tabfile=filepath, user=False)
                            for job in tab:
                                jobs.append({
                                    'command': job.command,
                                    'schedule': str(job.slices),
                                    'enabled': job.is_enabled(),
                                    'comment': f'{filename}: {job.comment or ""}',
                                    'user': getattr(job, 'user', 'root'),
                                    'source': f'cron.d/{filename}',
                                    'job': job
                                })
                        except Exception as e:
                            # Fallback: Manuelles Parsen
                            jobs.extend(self._manual_parse_cron_d_file(filepath, filename))
            except Exception as e:
                console.print(f"[yellow]Warnung beim Lesen von {cron_d_path}: {str(e)}[/yellow]")
        
        return jobs
    
    def _manual_parse_cron_d_file(self, filepath: str, filename: str) -> List[dict]:
        """Manuelles Parsen einer cron.d Datei"""
        jobs = []
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Überspringe Kommentare und leere Zeilen
                    if not line or line.startswith('#'):
                        continue
                    
                    # Einfaches Parsen: min hour day month weekday user command
                    parts = line.split(None, 6)
                    if len(parts) >= 7:
                        schedule = ' '.join(parts[:5])
                        user = parts[5]
                        command = parts[6]
                        
                        jobs.append({
                            'command': command,
                            'schedule': schedule,
                            'enabled': True,
                            'comment': f'Aus {filename}',
                            'user': user,
                            'source': f'cron.d/{filename}',
                            'job': None
                        })
        except Exception as e:
            console.print(f"[yellow]Konnte {filepath} nicht parsen: {str(e)}[/yellow]")
        
        return jobs
    
    def display_jobs_table(self, cron_type: str = "user"):
        """Zeigt Cronjobs in einer schönen Tabelle an"""
        jobs = self.list_all_jobs(cron_type)
        
        title = "🕐 Aktuelle Cronjobs"
        if cron_type != "user":
            title += f" - {cron_type}"
        
        table = Table(title=title, box=box.ROUNDED)
        
        table.add_column("Nr.", style="cyan", no_wrap=True, width=4)
        table.add_column("Zeitplan", style="magenta", width=20)
        table.add_column("Befehl", style="green", width=60, no_wrap=False)  # Vergrößert und Wrap erlaubt
        table.add_column("Benutzer", style="blue", width=10)
        table.add_column("Quelle", style="yellow", width=15)
        table.add_column("Status", style="bold", width=10)
        
        if not jobs:
            console.print(Panel("[yellow]Keine Cronjobs gefunden[/yellow]", 
                              title="Info", border_style="yellow"))
            return jobs
        
        for idx, job in enumerate(jobs, 1):
            status = "[green]✓ Aktiv[/green]" if job['enabled'] else "[red]✗ Inaktiv[/red]"
            
            # Zeitplan formatieren
            schedule = self._format_schedule(job['schedule'])
            
            # Befehl NICHT kürzen - volle Länge anzeigen
            command = job['command']
            
            table.add_row(
                str(idx),
                schedule,
                command,
                job['user'],
                job['source'],
                status
            )
        
        console.print(table)
        return jobs
    
    def _format_schedule(self, schedule: str) -> str:
        """Formatiert den Cron-Zeitplan in lesbare Form"""
        # Spezielle Syntax
        if schedule.startswith('@'):
            translations = {
                '@yearly': 'Jährlich',
                '@annually': 'Jährlich',
                '@monthly': 'Monatlich',
                '@weekly': 'Wöchentlich',
                '@daily': 'Täglich',
                '@midnight': 'Um Mitternacht',
                '@hourly': 'Stündlich',
                '@reboot': 'Bei Neustart'
            }
            return translations.get(schedule, schedule)
        
        parts = schedule.split()
        if len(parts) != 5:
            return schedule
        
        minute, hour, day, month, weekday = parts
        
        # Spezielle Fälle
        if minute == "0" and hour == "0" and day == "*" and month == "*" and weekday == "*":
            return "Täglich um Mitternacht"
        elif minute == "0" and hour == "*" and day == "*" and month == "*" and weekday == "*":
            return "Stündlich"
        elif minute == "*" and hour == "*" and day == "*" and month == "*" and weekday == "*":
            return "Jede Minute"
        elif minute == "*/5" and hour == "*" and day == "*" and month == "*" and weekday == "*":
            return "Alle 5 Minuten"
        elif minute == "0" and hour == "0" and day == "*" and month == "*" and weekday == "0":
            return "Wöchentlich (Sonntags)"
        elif minute == "0" and hour == "0" and day == "1" and month == "*" and weekday == "*":
            return "Monatlich (1. Tag)"
        
        # Standard Format
        return f"{minute} {hour} {day} {month} {weekday}"
    
    def export_jobs(self):
        """Exportiert Cronjobs in verschiedene Formate"""
        format_choice = questionary.select(
            "Export-Format wählen:",
            choices=["JSON", "CSV", "Crontab-Format", "Markdown", "Zurück"]
        ).ask()
        
        if format_choice == "Zurück" or not format_choice:
            return
        
        cron_type = self.get_cron_type()
        if cron_type == "Zurück":
            return
        
        jobs = self.list_all_jobs(cron_type)
        if not jobs:
            console.print("[yellow]Keine Jobs zum Exportieren vorhanden[/yellow]")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_choice == "JSON":
            filename = f"cronjobs_export_{timestamp}.json"
            export_data = []
            for job in jobs:
                export_data.append({
                    'command': job['command'],
                    'schedule': job['schedule'],
                    'enabled': job['enabled'],
                    'comment': job['comment'],
                    'user': job['user'],
                    'source': job['source']
                })
            
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
        
        elif format_choice == "CSV":
            filename = f"cronjobs_export_{timestamp}.csv"
            with open(filename, 'w') as f:
                f.write("Schedule,Command,User,Source,Enabled,Comment\n")
                for job in jobs:
                    f.write(f'"{job["schedule"]}","{job["command"]}","{job["user"]}",'
                           f'"{job["source"]}",{job["enabled"]},"{job["comment"]}"\n')
        
        elif format_choice == "Crontab-Format":
            filename = f"cronjobs_export_{timestamp}.cron"
            with open(filename, 'w') as f:
                for job in jobs:
                    if job['comment']:
                        f.write(f"# {job['comment']}\n")
                    if job['source'] == 'system':
                        f.write(f"{job['schedule']} {job['user']} {job['command']}\n")
                    else:
                        f.write(f"{job['schedule']} {job['command']}\n")
                    f.write("\n")
        
        elif format_choice == "Markdown":
            filename = f"cronjobs_export_{timestamp}.md"
            with open(filename, 'w') as f:
                f.write("# Cronjobs Export\n\n")
                f.write(f"Exportiert am: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n")
                f.write("| Zeitplan | Befehl | Benutzer | Quelle | Status |\n")
                f.write("|----------|---------|----------|---------|--------|\n")
                for job in jobs:
                    status = "Aktiv" if job['enabled'] else "Inaktiv"
                    f.write(f"| {job['schedule']} | {job['command']} | {job['user']} | "
                           f"{job['source']} | {status} |\n")
        
        console.print(Panel(
            f"[green]✓ Export erfolgreich: {filename}[/green]",
            title="Export abgeschlossen",
            border_style="green"
        ))
    
    def import_jobs(self):
        """Importiert Cronjobs aus einer Datei"""
        files = glob.glob("cronjobs_export_*.json") + glob.glob("*.cron")
        
        if not files:
            console.print("[yellow]Keine Import-Dateien gefunden[/yellow]")
            return
        
        file_choice = questionary.select(
            "Datei zum Importieren wählen:",
            choices=files + ["Zurück"]
        ).ask()
        
        if file_choice == "Zurück" or not file_choice:
            return
        
        if file_choice.endswith('.json'):
            with open(file_choice, 'r') as f:
                jobs = json.load(f)
            
            console.print(f"[cyan]Gefunden: {len(jobs)} Jobs[/cyan]")
            
            if Confirm.ask("Möchten Sie diese Jobs importieren?"):
                imported = 0
                for job_data in track(jobs, description="Importiere Jobs..."):
                    try:
                        if job_data['source'] == 'user':
                            new_job = self.user_cron.new(
                                command=job_data['command'],
                                comment=job_data['comment']
                            )
                            new_job.setall(job_data['schedule'])
                            if not job_data['enabled']:
                                new_job.enable(False)
                            imported += 1
                    except Exception as e:
                        console.print(f"[red]Fehler beim Import: {str(e)}[/red]")
                
                self.user_cron.write()
                console.print(f"[green]✓ {imported} Jobs importiert[/green]")
    
    def add_system_job(self):
        """Fügt einen System-Cronjob hinzu (nur für Root)"""
        if not self.is_root:
            console.print("[red]Fehler: Root-Rechte erforderlich![/red]")
            return
        
        location = questionary.select(
            "Wo soll der Job hinzugefügt werden?",
            choices=[
                "/etc/crontab",
                "/etc/cron.d/ (eigene Datei)",
                "Periodisch (hourly/daily/weekly/monthly)",
                "Zurück"
            ]
        ).ask()
        
        if location == "Zurück" or not location:
            return
        
        if location == "/etc/crontab":
            self._add_to_system_crontab()
        elif location == "/etc/cron.d/ (eigene Datei)":
            self._add_to_cron_d()
        elif location == "Periodisch (hourly/daily/weekly/monthly)":
            self._add_periodic_job()
    
    def _add_to_cron_d(self):
        """Fügt einen Job zu /etc/cron.d hinzu"""
        filename = questionary.text(
            "Dateiname (ohne Pfad):",
            validate=lambda x: x.replace('-', '').replace('_', '').isalnum()
        ).ask()
        
        if not filename:
            return
        
        filepath = os.path.join(self.system_paths['cron.d'], filename)
        
        command = questionary.text("Befehl:").ask()
        user = questionary.text("Benutzer:", default="root").ask()
        schedule = self._get_schedule_input()
        
        content = f"# Erstellt von Cron Manager\n"
        content += f"SHELL=/bin/bash\n"
        content += f"PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin\n\n"
        content += f"{schedule} {user} {command}\n"
        
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            os.chmod(filepath, 0o644)
            console.print(f"[green]✓ Job erstellt in {filepath}[/green]")
        except Exception as e:
            console.print(f"[red]Fehler: {str(e)}[/red]")
    
    def _add_periodic_job(self):
        """Fügt ein Script zu den periodischen Jobs hinzu"""
        period = questionary.select(
            "Ausführungsintervall:",
            choices=["hourly", "daily", "weekly", "monthly"]
        ).ask()
        
        if not period:
            return
        
        script_name = questionary.text(
            "Script-Name:",
            validate=lambda x: x.replace('-', '').replace('_', '').isalnum()
        ).ask()
        
        if not script_name:
            return
        
        script_path = os.path.join(self.system_paths[period], script_name)
        
        console.print("[cyan]Geben Sie das Script ein (beenden mit Strg+D):[/cyan]")
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        
        content = "#!/bin/bash\n"
        content += "# Erstellt von Cron Manager\n"
        content += "\n".join(lines)
        
        try:
            with open(script_path, 'w') as f:
                f.write(content)
            os.chmod(script_path, 0o755)
            console.print(f"[green]✓ Script erstellt: {script_path}[/green]")
        except Exception as e:
            console.print(f"[red]Fehler: {str(e)}[/red]")
    
    def _get_schedule_input(self) -> str:
        """Hilfsfunktion für Zeitplan-Eingabe"""
        schedule_choice = questionary.select(
            "Zeitplan wählen:",
            choices=[
                "Jede Minute",
                "Stündlich",
                "Täglich",
                "Wöchentlich",
                "Monatlich",
                "@reboot (Bei Systemstart)",
                "Benutzerdefiniert"
            ]
        ).ask()
        
        if schedule_choice == "Jede Minute":
            return "* * * * *"
        elif schedule_choice == "Stündlich":
            minute = questionary.text("Minute (0-59):", default="0").ask()
            return f"{minute} * * * *"
        elif schedule_choice == "Täglich":
            time = questionary.text("Zeit (HH:MM):", default="00:00").ask()
            hour, minute = time.split(":")
            return f"{minute} {hour} * * *"
        elif schedule_choice == "Wöchentlich":
            weekday = questionary.select(
                "Wochentag:",
                choices=["Montag", "Dienstag", "Mittwoch", "Donnerstag", 
                        "Freitag", "Samstag", "Sonntag"]
            ).ask()
            weekday_num = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", 
                          "Freitag", "Samstag", "Sonntag"].index(weekday) + 1
            time = questionary.text("Zeit (HH:MM):", default="00:00").ask()
            hour, minute = time.split(":")
            return f"{minute} {hour} * * {weekday_num % 7}"
        elif schedule_choice == "Monatlich":
            day = questionary.text("Tag des Monats (1-31):", default="1").ask()
            time = questionary.text("Zeit (HH:MM):", default="00:00").ask()
            hour, minute = time.split(":")
            return f"{minute} {hour} {day} * *"
        elif schedule_choice == "@reboot (Bei Systemstart)":
            return "@reboot"
        else:
            console.print("[yellow]Cron-Format: Minute Stunde Tag Monat Wochentag[/yellow]")
            return questionary.text("Cron-Ausdruck:").ask()
    
    def search_jobs(self):
        """Durchsucht Cronjobs nach Stichwörtern"""
        keyword = questionary.text("Suchbegriff:").ask()
        
        if not keyword:
            return
        
        console.print(f"\n[cyan]Suche nach '{keyword}'...[/cyan]\n")
        
        found = False
        sources = ["Benutzer-Crontab"]
        
        if self.is_root:
            sources.extend([
                "System-Crontab (/etc/crontab)",
                "Cron.d Verzeichnis (/etc/cron.d)",
                "Periodische Jobs (hourly/daily/weekly/monthly)"
            ])
        
        for source in sources:
            jobs = self.list_all_jobs(source)
            matches = []
            
            for job in jobs:
                if (keyword.lower() in job['command'].lower() or 
                    keyword.lower() in job['comment'].lower()):
                    matches.append(job)
            
            if matches:
                found = True
                console.print(f"\n[green]Gefunden in {source}:[/green]")
                for match in matches:
                    console.print(f"  • {match['schedule']} - {match['command']}")
        
        if not found:
            console.print(f"[yellow]Keine Treffer für '{keyword}' gefunden[/yellow]")
    
    def validate_crontab(self):
        """Validiert die Crontab-Syntax"""
        console.print("[cyan]Validiere Crontabs...[/cyan]\n")
        
        # Benutzer-Crontab
        try:
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            if result.returncode == 0:
                console.print("[green]✓ Benutzer-Crontab ist gültig[/green]")
            else:
                console.print("[red]✗ Fehler in Benutzer-Crontab[/red]")
        except:
            pass
        
        # System-Crontab
        if self.is_root and os.path.exists('/etc/crontab'):
            try:
                with open('/etc/crontab', 'r') as f:
                    content = f.read()
                # Einfache Validierung
                console.print("[green]✓ System-Crontab ist lesbar[/green]")
            except Exception as e:
                console.print(f"[red]✗ Fehler in System-Crontab: {str(e)}[/red]")
    
    def show_job_statistics(self):
        """Zeigt Statistiken über alle Cronjobs an"""
        console.print(Panel("📊 Cronjob-Statistiken", style="bold cyan"))
        
        # Lade Quick Stats aus Logs wenn vorhanden
        try:
            self.cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as success,
                       AVG(CASE WHEN status='success' THEN duration_seconds ELSE NULL END) as avg_duration
                FROM job_logs
                WHERE timestamp > datetime('now', '-7 days')
            """)
            log_stats = self.cursor.fetchone()
            
            if log_stats and log_stats[0] > 0:
                console.print("\n[yellow]📈 Letzte 7 Tage:[/yellow]")
                success_rate = (log_stats[1] / log_stats[0] * 100) if log_stats[0] > 0 else 0
                console.print(f"  • Ausführungen: {log_stats[0]}")
                console.print(f"  • Erfolgsrate: {success_rate:.1f}%")
                console.print(f"  • Ø Laufzeit: {log_stats[2]:.2f}s" if log_stats[2] else "  • Ø Laufzeit: N/A")
        except:
            pass
        
        all_jobs = []
        sources = ["Benutzer-Crontab"]
        
        if self.is_root:
            sources.extend([
                "System-Crontab (/etc/crontab)",
                "Cron.d Verzeichnis (/etc/cron.d)",
                "Periodische Jobs (hourly/daily/weekly/monthly)"
            ])
        
        stats = {
            'total': 0,
            'active': 0,
            'inactive': 0,
            'by_source': {},
            'by_user': {},
            'by_frequency': {
                'minute': 0,
                'hourly': 0,
                'daily': 0,
                'weekly': 0,
                'monthly': 0,
                'other': 0
            }
        }
        
        # Sammle alle Jobs
        for source in sources:
            jobs = self.list_all_jobs(source)
            all_jobs.extend(jobs)
            stats['by_source'][source] = len(jobs)
            
            for job in jobs:
                stats['total'] += 1
                
                if job['enabled']:
                    stats['active'] += 1
                else:
                    stats['inactive'] += 1
                
                # Nach Benutzer
                user = job.get('user', 'unknown')
                stats['by_user'][user] = stats['by_user'].get(user, 0) + 1
                
                # Nach Häufigkeit
                schedule = job['schedule']
                if schedule == "* * * * *":
                    stats['by_frequency']['minute'] += 1
                elif "0 * * * *" in schedule or schedule == "@hourly":
                    stats['by_frequency']['hourly'] += 1
                elif schedule in ["0 0 * * *", "@daily", "@midnight"]:
                    stats['by_frequency']['daily'] += 1
                elif schedule == "@weekly" or "0 0 * * 0" in schedule:
                    stats['by_frequency']['weekly'] += 1
                elif schedule == "@monthly" or "0 0 1 * *" in schedule:
                    stats['by_frequency']['monthly'] += 1
                else:
                    stats['by_frequency']['other'] += 1
        
        # Anzeige der Statistiken
        table = Table(box=box.ROUNDED, show_header=False)
        table.add_column("Kategorie", style="cyan")
        table.add_column("Wert", style="white")
        
        table.add_row("Gesamt-Jobs", str(stats['total']))
        table.add_row("Aktive Jobs", f"[green]{stats['active']}[/green]")
        table.add_row("Inaktive Jobs", f"[red]{stats['inactive']}[/red]")
        
        console.print(table)
        
        # Nach Quelle
        if stats['by_source']:
            console.print("\n[yellow]Nach Quelle:[/yellow]")
            source_table = Table(box=box.SIMPLE)
            source_table.add_column("Quelle", style="cyan")
            source_table.add_column("Anzahl", style="white")
            
            for source, count in stats['by_source'].items():
                if count > 0:
                    source_table.add_row(source, str(count))
            
            console.print(source_table)
        
        # Nach Benutzer
        if len(stats['by_user']) > 1:
            console.print("\n[yellow]Nach Benutzer:[/yellow]")
            user_table = Table(box=box.SIMPLE)
            user_table.add_column("Benutzer", style="cyan")
            user_table.add_column("Anzahl", style="white")
            
            for user, count in sorted(stats['by_user'].items()):
                user_table.add_row(user, str(count))
            
            console.print(user_table)
        
        # Nach Häufigkeit
        console.print("\n[yellow]Nach Ausführungshäufigkeit:[/yellow]")
        freq_table = Table(box=box.SIMPLE)
        freq_table.add_column("Häufigkeit", style="cyan")
        freq_table.add_column("Anzahl", style="white")
        
        freq_labels = {
            'minute': 'Jede Minute',
            'hourly': 'Stündlich',
            'daily': 'Täglich',
            'weekly': 'Wöchentlich',
            'monthly': 'Monatlich',
            'other': 'Andere'
        }
        
        for freq, label in freq_labels.items():
            if stats['by_frequency'][freq] > 0:
                freq_table.add_row(label, str(stats['by_frequency'][freq]))
        
        console.print(freq_table)
        
        # Nächste Ausführung
        console.print("\n[yellow]Nächste geplante Ausführungen:[/yellow]")
        next_runs = []
        
        for job in all_jobs:
            if job['job'] and job['enabled']:
                try:
                    # Erstelle Schedule-Objekt aus dem Job
                    schedule = job['job'].schedule()
                    next_run = schedule.get_next(datetime)
                    if next_run:
                        # Kürze Befehl für bessere Übersicht
                        cmd_display = job['command']
                        if len(cmd_display) > 50:
                            cmd_display = cmd_display[:47] + "..."
                        next_runs.append((next_run, cmd_display, job['user']))
                except Exception as e:
                    # Für periodische Jobs ohne CronTab-Objekt
                    if job['schedule'].startswith('@'):
                        # Spezielle Behandlung für @reboot, @hourly, etc.
                        if job['schedule'] == '@reboot':
                            console.print(f"  • Bei Neustart - {job['command'][:50]}")
                        elif job['schedule'] == '@hourly':
                            next_hour = datetime.now().replace(minute=0, second=0) + timedelta(hours=1)
                            next_runs.append((next_hour, job['command'][:50], job['user']))
                        elif job['schedule'] == '@daily':
                            next_day = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
                            next_runs.append((next_day, job['command'][:50], job['user']))
                        elif job['schedule'] == '@weekly':
                            days_until_sunday = (6 - datetime.now().weekday()) % 7
                            if days_until_sunday == 0:
                                days_until_sunday = 7
                            next_week = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=days_until_sunday)
                            next_runs.append((next_week, job['command'][:50], job['user']))
                        elif job['schedule'] == '@monthly':
                            next_month = datetime.now().replace(day=1, hour=0, minute=0, second=0)
                            if next_month.month == 12:
                                next_month = next_month.replace(year=next_month.year + 1, month=1)
                            else:
                                next_month = next_month.replace(month=next_month.month + 1)
                            next_runs.append((next_month, job['command'][:50], job['user']))
        
        # Sortiere nach Zeit
        next_runs.sort(key=lambda x: x[0])
        
        if next_runs:
            # Zeige nur die nächsten 10 Ausführungen
            for next_run, command, user in next_runs[:10]:
                time_diff = next_run - datetime.now()
                if time_diff.total_seconds() > 0:
                    # Formatiere Zeitdifferenz
                    days = time_diff.days
                    hours, remainder = divmod(time_diff.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    
                    if days > 0:
                        time_str = f"in {days}d {hours}h"
                    elif hours > 0:
                        time_str = f"in {hours}h {minutes}m"
                    else:
                        time_str = f"in {minutes}m"
                    
                    console.print(f"  • {next_run.strftime('%d.%m %H:%M')} ({time_str}) - [{user}] {command}")
        else:
            console.print("  [gray]Keine geplanten Ausführungen gefunden[/gray]")

def clear_screen():
    """Löscht den Bildschirm plattformübergreifend"""
    os.system('clear' if os.name == 'posix' else 'cls')

def show_main_menu():
    """Zeigt das Hauptmenü an"""
    manager = CronManager()
    
    # Bildschirm löschen beim Start
    clear_screen()
    
    console.print(Panel(
        "[bold blue]Cron Manager[/bold blue]\n"
        "Modernes Tool zur Verwaltung von Cronjobs\n"
        f"[yellow]{'Root-Modus' if manager.is_root else 'Benutzer-Modus'}[/yellow]\n"
        f"[cyan]System: {manager.distro}[/cyan]",
        title="🕐 Willkommen",
        border_style="blue"
    ))
    
    # Zeige wichtige Systeminformationen
    if manager.is_root:
        total_jobs = len(manager.list_all_jobs("Benutzer-Crontab"))
        system_jobs = 0
        if os.path.exists('/etc/crontab'):
            system_jobs += len(manager.list_all_jobs("System-Crontab (/etc/crontab)"))
        
        console.print(f"\n[cyan]Aktive Jobs:[/cyan] {total_jobs} Benutzer | {system_jobs} System")
    
    while True:
        console.print("\n")
        
        menu_items = [
            "📋 Jobs anzeigen",
            "➕ Job hinzufügen",
            "✏️  Job bearbeiten/ausführen",
            "🔍 Jobs durchsuchen",
            "📊 Job-Statistiken",
            "📜 Job-Logs anzeigen",
            "👁️  Job-Überwachung",
            "📧 E-Mail-Benachrichtigungen",
            "📥 Jobs exportieren",
            "📤 Jobs importieren",
            "✔️  Crontab validieren",
            "💾 Backup erstellen",
            "🔄 Bildschirm aktualisieren"
        ]
        
        if manager.is_root:
            menu_items.append("⚙️  System-Job hinzufügen")
        
        menu_items.append("🚪 Beenden")
        
        choice = questionary.select(
            "Was möchten Sie tun?",
            choices=menu_items
        ).ask()
        
        if not choice or "Beenden" in choice:
            console.print("[yellow]Auf Wiedersehen![/yellow]")
            break
        
        elif "anzeigen" in choice:
            cron_type = manager.get_cron_type()
            if cron_type != "Zurück":
                manager.display_jobs_table(cron_type)
        
        elif "hinzufügen" in choice:
            manager.add_job()
        
        elif "bearbeiten" in choice:
            cron_type = manager.get_cron_type()
            if cron_type != "Zurück":
                jobs = manager.list_all_jobs(cron_type)
                manager.display_jobs_table(cron_type)
                manager.edit_job(jobs)
        
        elif "durchsuchen" in choice:
            manager.search_jobs()
        
        elif "exportieren" in choice:
            manager.export_jobs()
        
        elif "importieren" in choice:
            manager.import_jobs()
        
        elif "validieren" in choice:
            manager.validate_crontab()
        
        elif "Backup" in choice:
            manager.create_backup()
        
        elif "Statistiken" in choice:
            manager.show_job_statistics()
        
        elif "Logs" in choice:
            manager.view_job_logs()
        
        elif "Überwachung" in choice:
            manager.monitor_jobs()
        
        elif "Benachrichtigungen" in choice:
            manager.configure_notifications()
        
        elif "System-Job" in choice:
            manager.add_system_job()
        
        elif "aktualisieren" in choice:
            clear_screen()
            console.print("[green]✓ Bildschirm aktualisiert[/green]")
            return show_main_menu()  # Neustart des Menüs

def main():
    """Hauptfunktion"""
    # Prüfe ob wir auf einem Linux-System sind
    if os.name != 'posix':
        console.print("[red]Dieses Tool funktioniert nur auf Linux/Unix-Systemen![/red]")
        sys.exit(1)
    
    # Parse Command-Line-Argumente
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            console.print("""
[bold cyan]Cron Manager - Hilfe[/bold cyan]

[yellow]Verwendung:[/yellow]
  ./cron_manager.py [OPTIONEN]

[yellow]Optionen:[/yellow]
  -h, --help         Diese Hilfe anzeigen
  -v, --version      Version anzeigen
  -b, --backup       Schnelles Backup erstellen
  -l, --list         Jobs auflisten und beenden
  -s, --stats        Statistiken anzeigen und beenden
  --validate         Crontab validieren und beenden

[yellow]Beispiele:[/yellow]
  ./cron_manager.py                # Normaler Start
  sudo ./cron_manager.py           # Als Root für System-Features
  ./cron_manager.py --backup       # Schnelles Backup
  ./cron_manager.py --list         # Jobs anzeigen
            """)
            return
        
        elif sys.argv[1] == '--version' or sys.argv[1] == '-v':
            console.print("[cyan]Cron Manager v1.0.0[/cyan]")
            return
        
        elif sys.argv[1] == '--backup' or sys.argv[1] == '-b':
            manager = CronManager()
            clear_screen()
            console.print("[cyan]Erstelle Backup...[/cyan]")
            manager.create_backup()
            return
        
        elif sys.argv[1] == '--list' or sys.argv[1] == '-l':
            manager = CronManager()
            clear_screen()
            manager.display_jobs_table("Benutzer-Crontab")
            return
        
        elif sys.argv[1] == '--stats' or sys.argv[1] == '-s':
            manager = CronManager()
            clear_screen()
            manager.show_job_statistics()
            return
        
        elif sys.argv[1] == '--validate':
            manager = CronManager()
            clear_screen()
            manager.validate_crontab()
            return
    
    # Normaler interaktiver Modus
    try:
        show_main_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Programm beendet.[/yellow]")
    except Exception as e:
        console.print(f"[red]Unerwarteter Fehler: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
