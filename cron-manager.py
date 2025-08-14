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
except ImportError:
    print("Bitte installiere die erforderlichen Pakete:")
    print("pip install rich questionary python-crontab")
    sys.exit(1)

console = Console()

class CronManager:
    def __init__(self):
        self.user_cron = CronTab(user=True)
        self.system_cron = None
        self.is_root = os.geteuid() == 0
        
        # System-Cron Pfade
        self.system_paths = {
            'crontab': '/etc/crontab',
            'hourly': '/etc/cron.hourly',
            'daily': '/etc/cron.daily',
            'weekly': '/etc/cron.weekly',
            'monthly': '/etc/cron.monthly',
            'cron.d': '/etc/cron.d'
        }
        
        if self.is_root:
            try:
                self.system_cron = CronTab(tabfile='/etc/crontab')
            except:
                console.print("[yellow]⚠ Warnung: Konnte /etc/crontab nicht laden[/yellow]")
        
        # Initialisiere Logging-Datenbank
        self.init_logging_db()
        
        # Lade Konfiguration
        self.config = self.load_config()
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
            
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                config.write(f)
        
        return config
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
            for job in self.user_cron:
                jobs.append({
                    'command': job.command,
                    'schedule': str(job.slices),
                    'enabled': job.is_enabled(),
                    'comment': job.comment or '',
                    'user': os.getlogin(),
                    'source': 'user',
                    'job': job
                })
        
        elif cron_type == "System-Crontab (/etc/crontab)" and self.system_cron:
            for job in self.system_cron:
                jobs.append({
                    'command': job.command,
                    'schedule': str(job.slices),
                    'enabled': job.is_enabled(),
                    'comment': job.comment or '',
                    'user': job.user or 'root',
                    'source': 'system',
                    'job': job
                })
        
        elif cron_type == "Periodische Jobs (hourly/daily/weekly/monthly)":
            jobs.extend(self._list_periodic_jobs())
        
        elif cron_type == "Cron.d Verzeichnis (/etc/cron.d)":
            jobs.extend(self._list_cron_d_jobs())
        
        return jobs
    
    def _list_periodic_jobs(self) -> List[dict]:
        """Listet Jobs aus den periodischen Verzeichnissen auf"""
        jobs = []
        
        for period in ['hourly', 'daily', 'weekly', 'monthly']:
            path = self.system_paths[period]
            if os.path.exists(path):
                for script in os.listdir(path):
                    script_path = os.path.join(path, script)
                    if os.path.isfile(script_path) and os.access(script_path, os.X_OK):
                        jobs.append({
                            'command': script_path,
                            'schedule': f'@{period}',
                            'enabled': True,
                            'comment': f'{period.capitalize()} job',
                            'user': 'root',
                            'source': f'periodic-{period}',
                            'job': None
                        })
        
        return jobs
    
    def _list_cron_d_jobs(self) -> List[dict]:
        """Listet Jobs aus /etc/cron.d auf"""
        jobs = []
        cron_d_path = self.system_paths['cron.d']
        
        if os.path.exists(cron_d_path):
            for filename in os.listdir(cron_d_path):
                filepath = os.path.join(cron_d_path, filename)
                if os.path.isfile(filepath):
                    try:
                        tab = CronTab(tabfile=filepath)
                        for job in tab:
                            jobs.append({
                                'command': job.command,
                                'schedule': str(job.slices),
                                'enabled': job.is_enabled(),
                                'comment': f'{filename}: {job.comment or ""}',
                                'user': job.user or 'root',
                                'source': f'cron.d/{filename}',
                                'job': job
                            })
                    except:
                        pass
        
        return jobs
    
    def display_jobs_table(self, cron_type: str = "user"):
        """Zeigt Cronjobs in einer schönen Tabelle an"""
        jobs = self.list_all_jobs(cron_type)
        
        title = "🕐 Aktuelle Cronjobs"
        if cron_type != "user":
            title += f" - {cron_type}"
        
        table = Table(title=title, box=box.ROUNDED)
        
        table.add_column("Nr.", style="cyan", no_wrap=True)
        table.add_column("Zeitplan", style="magenta")
        table.add_column("Befehl", style="green")
        table.add_column("Benutzer", style="blue")
        table.add_column("Quelle", style="yellow")
        table.add_column("Status", style="bold")
        
        if not jobs:
            console.print(Panel("[yellow]Keine Cronjobs gefunden[/yellow]", 
                              title="Info", border_style="yellow"))
            return jobs
        
        for idx, job in enumerate(jobs, 1):
            status = "[green]✓ Aktiv[/green]" if job['enabled'] else "[red]✗ Inaktiv[/red]"
            
            # Zeitplan formatieren
            schedule = self._format_schedule(job['schedule'])
            
            # Befehl kürzen wenn zu lang
            command = job['command']
            if len(command) > 40:
                command = command[:37] + "..."
            
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
        
        for job in all_jobs[:10]:  # Nur die ersten 10 für Übersichtlichkeit
            if job['job'] and job['enabled']:
                try:
                    schedule = job['job'].schedule()
                    next_run = schedule.get_next(datetime)
                    if next_run:
                        next_runs.append((next_run, job['command'][:50]))
                except:
                    pass
        
        next_runs.sort(key=lambda x: x[0])
        
        for next_run, command in next_runs[:5]:  # Top 5 nächste
            time_diff = next_run - datetime.now()
            if time_diff.total_seconds() > 0:
                console.print(f"  • {next_run.strftime('%H:%M')} - {command}")

def show_main_menu():
    """Zeigt das Hauptmenü an"""
    manager = CronManager()
    
    console.print(Panel(
        "[bold blue]Cron Manager[/bold blue]\n"
        "Modernes Tool zur Verwaltung von Cronjobs\n"
        f"[yellow]{'Root-Modus' if manager.is_root else 'Benutzer-Modus'}[/yellow]",
        title="Willkommen",
        border_style="blue"
    ))
    
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
            "💾 Backup erstellen"
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
            manager.backup_crontab()
        
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

def main():
    """Hauptfunktion"""
    # Prüfe ob wir auf einem Linux-System sind
    if os.name != 'posix':
        console.print("[red]Dieses Tool funktioniert nur auf Linux/Unix-Systemen![/red]")
        sys.exit(1)
    
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