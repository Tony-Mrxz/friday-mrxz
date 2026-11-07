"""
connectors/terminal.py - Rich Interactive Terminal Shell for Friday AI (CLI Mode)
"""
import sys
import os
import re
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.markdown import Markdown

from core.agent_loop import process_user_input, get_system_status_summary
from core.logger import logger

console = Console()


def show_status_banner():
    """Displays system status banner and diagnostics."""
    try:
        from tools.voice_input import is_voice_active
        status = get_system_status_summary()
        voice_status = "[bold green]Active[/bold green]" if is_voice_active() else "[bold red]Inactive[/bold red]"

        banner_text = (
            f"[bold cyan]🤖 FRIDAY AI — TERMINAL INTERACTIVE MODE[/bold cyan]\n\n"
            f"⚡ [bold white]LLM Provider:[/bold white] [green]{status['llm']}[/green]\n"
            f"💻 [bold white]Automation Engine:[/bold white] [green]{status['automation']}[/green]\n"
            f"💬 [bold white]Telegram Daemon:[/bold white] [green]{status['telegram']}[/green]\n"
            f"🎙️ [bold white]Voice Daemon:[/bold white] {voice_status}\n\n"
            f"[dim]Type your message to chat with Friday, or type 'status', 'voice', 'dashboard', 'config', 'help', 'exit'.[/dim]"
        )

        console.print(Panel(
            banner_text,
            title="[bold blue]System Diagnostic & Health[/bold blue]",
            border_style="cyan"
        ))
    except Exception as e:
        logger.error(f"Error building status banner: {e}")


def show_help_table():
    """Displays styled table of built-in CLI commands."""
    table = Table(title="Friday AI System CLI Commands")
    table.add_column("Command", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")

    table.add_row("status / health", "Show system health and diagnostics banner")
    table.add_row("restart / reload", "Restart Friday AI process instantly")
    table.add_row("dashboard / web", "Open local Web Dashboard in browser")
    table.add_row("config / settings", "Open API key & Telegram credentials wizard")
    table.add_row("telegram", "Start Telegram Polling Bot Daemon in background")
    table.add_row("voice", "Toggle wake word voice listener ('Friday') on/off")
    table.add_row("help / ?", "Display this help reference table")
    table.add_row("clear / cls", "Clear terminal screen")
    table.add_row("exit / quit", "Exit Friday CLI session")

    console.print(table)


def restart_friday_process():
    """Spawns a clean subprocess for restart and exits current instance."""
    console.print("[bold cyan]🔄 Restarting Friday AI system process...[/bold cyan]")
    subprocess.Popen([sys.executable, "main.py"] + sys.argv[1:])
    sys.exit(0)


def handle_voice_command_input(transcript: str):
    """Callback to process voice command transcript in terminal context."""
    if not transcript:
        return
    console.print(f"\n[bold green]🎙️ Voice Input Detected:[/bold green] {transcript}")
    response = process_user_input(transcript)
    console.print(f"[bold cyan]Friday:[/bold cyan] {response}")


def run_terminal():
    """Runs the rich interactive terminal REPL shell."""
    try:
        from connectors.telegram_bot import start_telegram_in_background
        start_telegram_in_background()
        from dashboard.server import start_dashboard_in_background
        start_dashboard_in_background(open_browser=True)
    except Exception as e:
        logger.error(f"Background services start error: {e}")

    show_status_banner()

    while True:
        try:
            user_input = Prompt.ask("\n[bold magenta]You[/bold magenta] ›")
            cmd = user_input.strip()
            if not cmd:
                continue

            cmd_lower = cmd.lower()

            if cmd_lower in ["exit", "quit", "q", "bye"]:
                try:
                    from tools.voice_input import stop_voice_daemon
                    stop_voice_daemon()
                except Exception:
                    pass
                console.print("[yellow]Shutting down Friday CLI session... Bye! 👋[/yellow]")
                break

            elif cmd_lower in ["status", "health", "/status", "/health"]:
                show_status_banner()
                continue

            elif cmd_lower in ["restart", "reload", "/restart", "/reload"]:
                restart_friday_process()
                break

            elif cmd_lower in ["help", "/help", "?"]:
                show_help_table()
                continue

            elif cmd_lower in ["clear", "cls"]:
                os.system("cls" if sys.platform == "win32" else "clear")
                continue

            elif cmd_lower in ["config", "settings", "/config"]:
                from main import run_configuration_wizard
                run_configuration_wizard()
                continue

            elif cmd_lower in ["dashboard", "web", "gui", "/dashboard"]:
                from dashboard.server import start_dashboard_in_background
                url = start_dashboard_in_background(open_browser=True)
                console.print(f"[bold green]🌐 Friday Web Dashboard opened on {url} in your browser![/bold green]")
                continue

            elif cmd_lower in ["voice", "/voice"]:
                from tools.voice_input import is_voice_active, start_voice_daemon, stop_voice_daemon
                if is_voice_active():
                    stop_voice_daemon()
                    console.print("[bold yellow]🎙️ Voice Daemon stopped.[/bold yellow]")
                else:
                    console.print("[cyan]🎙️ Starting Voice Daemon (listening for wake word 'Friday')...[/cyan]")
                    start_voice_daemon(callback=handle_voice_command_input)
                    console.print("[bold green]✅ Voice Daemon active! Say 'Friday' to talk.[/bold green]")
                continue

            elif cmd_lower in ["telegram", "/telegram"]:
                from connectors.telegram_bot import is_telegram_running, start_telegram_in_background
                if is_telegram_running():
                    console.print("[bold green]✅ Telegram Bot is already running in background![/bold green]")
                else:
                    console.print("[cyan]🤖 Starting Telegram Bot Daemon in background...[/cyan]")
                    if start_telegram_in_background():
                        console.print("[bold green]✅ Telegram Bot is now running in background![/bold green]")
                    else:
                        console.print("[bold yellow]⚠️ Telegram Bot token not configured. Use 'config' to set TELEGRAM_BOT_TOKEN.[/bold yellow]")
                continue

            # Process AI conversation or automation command
            response = process_user_input(cmd)
            screenshot_match = re.search(r"\[SCREENSHOT:(.*?)\]", response)
            if screenshot_match:
                img_path = Path(screenshot_match.group(1).strip())
                clean_text = re.sub(r"\[SCREENSHOT:.*?\]", "", response).strip()
                sent_tg = False
                if img_path.exists():
                    try:
                        from connectors.telegram_bot import send_photo_to_telegram
                        sent_tg = send_photo_to_telegram(str(img_path), caption=clean_text)
                    except Exception:
                        pass
                    try:
                        img_path.unlink()
                    except Exception:
                        pass
                if sent_tg:
                    console.print(f"[bold cyan]Friday:[/bold cyan] {clean_text} [bold green](Sent photo to your Telegram!)[/bold green]")
                else:
                    console.print(f"[bold cyan]Friday:[/bold cyan] {clean_text}")
                continue

            # Print styled response
            console.print(f"[bold cyan]Friday:[/bold cyan]")
            if "\n" in response or "```" in response or "#" in response or "**" in response:
                console.print(Markdown(response))
            else:
                console.print(f"  {response}")

        except KeyboardInterrupt:
            console.print("\n[yellow]Use 'exit' or 'quit' to close Friday CLI cleanly.[/yellow]")
            continue
        except Exception as err:
            logger.error(f"Error in terminal REPL: {err}", exc_info=True)
            console.print(f"[bold red]An unexpected error occurred: {err}[/bold red]")
            continue
