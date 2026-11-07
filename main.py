"""
main.py - Primary Application Launcher for Friday AI
"""
import sys
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from config.settings import (
    get_github_token, get_groq_key, get_telegram_token, get_authorized_user_ids,
    save_env_values
)
from core.logger import logger
from tools.apps import load_known_apps

console = Console()


def run_configuration_wizard():
    """Interactive CLI wizard to configure API keys and Telegram settings."""
    console.print(Panel.fit(
        "[bold cyan]⚙️ FRIDAY AI CREDENTIAL & SETUP WIZARD[/bold cyan]\n"
        "[dim]Configure your free LLM API keys and Telegram credentials.[/dim]",
        border_style="cyan"
    ))

    gh_token = get_github_token()
    groq_key = get_groq_key()
    tg_token = get_telegram_token()
    user_ids = get_authorized_user_ids()

    current_gh = gh_token if gh_token else "[red]Not Configured[/red]"
    current_groq = groq_key if groq_key else "[red]Not Configured[/red]"
    current_tg = tg_token if tg_token else "[red]Not Configured[/red]"
    current_users = ",".join(map(str, user_ids)) if user_ids else "[yellow]All Users Allowed[/yellow]"

    table = Table(title="Current Configuration Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Status / Value", style="magenta")

    table.add_row("1. GitHub Models Token", current_gh)
    table.add_row("2. Groq API Key", current_groq)
    table.add_row("3. Telegram Bot Token", current_tg)
    table.add_row("4. Authorized Telegram User IDs", current_users)
    console.print(table)

    console.print("\n[bold yellow]Enter new values (press Enter to keep current setting):[/bold yellow]")

    gh_input = Prompt.ask("GitHub Models Token (Free from github.com/settings/tokens)", default=gh_token, password=True)
    groq_input = Prompt.ask("Groq API Key (Free from console.groq.com)", default=groq_key, password=True)
    tg_input = Prompt.ask("Telegram Bot Token (From @BotFather)", default=tg_token, password=True)
    users_input = Prompt.ask("Authorized Telegram User IDs (comma-separated)", default=",".join(map(str, user_ids)))

    save_env_values(
        github_token=gh_input.strip(),
        groq_key=groq_input.strip(),
        tg_token=tg_input.strip(),
        user_ids=users_input.strip()
    )

    console.print("\n[bold green]✅ Credentials saved successfully to .env file![/bold green]\n")
    from connectors.telegram_bot import start_telegram_in_background
    start_telegram_in_background()


def main():
    parser = argparse.ArgumentParser(description="Friday AI - Multi-Medium Assistant Launcher")
    parser.add_argument("--gui", "-g", action="store_true", help="Launch Friday Native Desktop Graph Canvas GUI App")
    parser.add_argument("--terminal", "-t", action="store_true", help="Launch directly in Terminal REPL mode")
    parser.add_argument("--dashboard", "-d", action="store_true", help="Launch Friday Local Web Dashboard in browser")
    parser.add_argument("--telegram", "-tg", action="store_true", help="Launch directly in Telegram Polling Bot Daemon")
    parser.add_argument("--config", "-c", action="store_true", help="Launch API credentials configuration wizard")

    args = parser.parse_args()

    # Pre-warm app index cache
    logger.info("Initializing Friday system components...")
    load_known_apps()

    if args.config:
        run_configuration_wizard()
    elif args.gui:
        from gui_app import launch_gui_app
        launch_gui_app()
    elif args.telegram:
        from connectors.telegram_bot import run_telegram_bot
        run_telegram_bot()
    elif args.terminal:
        from connectors.telegram_bot import start_telegram_in_background
        start_telegram_in_background()
        from dashboard.server import start_dashboard_in_background
        url = start_dashboard_in_background(open_browser=True)
        console.print(f"[bold green]🌐 Opening Friday Web Dashboard at {url}...[/bold green]")
        from connectors.terminal import run_terminal
        run_terminal()
    else:
        # Default behavior: Launch Friday Web Dashboard & automatically open in browser
        from connectors.telegram_bot import start_telegram_in_background
        start_telegram_in_background()
        from dashboard.server import start_dashboard_in_background
        url = start_dashboard_in_background(open_browser=True)
        console.print(Panel.fit(
            f"[bold green]🚀 FRIDAY AI IS ONLINE![/bold green]\n\n"
            f"🌐 [bold white]Web Dashboard:[/bold white] [bold cyan]{url}[/bold cyan] [dim](Automatically opened in browser)[/dim]\n"
            f"🤖 [bold white]Telegram Daemon:[/bold white] [dim]Active in background[/dim]\n\n"
            f"[dim]Press Ctrl+C to stop Friday AI.[/dim]",
            title="[bold blue]Friday System Control Center[/bold blue]",
            border_style="cyan"
        ))
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down Friday AI... Bye! 👋[/yellow]")



if __name__ == "__main__":
    main()
