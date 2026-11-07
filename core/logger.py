"""
core/logger.py - Unified Rich Console and Logging Handler for Friday AI
"""
import sys
import logging
from rich.console import Console
from rich.logging import RichHandler
from config.settings import LOGS_DIR

# Set UTF-8 encoding for Windows standard output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()

# File Handler
log_file = LOGS_DIR / "friday.log"
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
file_handler.setFormatter(file_formatter)

# Rich Console Handler
rich_handler = RichHandler(console=console, rich_tracebacks=True, show_time=False, show_path=False)
rich_handler.setLevel(logging.INFO)

# Setup Logger
logger = logging.getLogger("Friday")
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(rich_handler)
