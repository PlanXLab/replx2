import os
import sys
import re
import time
import json
import urllib.request

from .store import StoreManager


class UpdateChecker:
    
    UPDATE_TIMESTAMP_FILE = StoreManager.HOME_STORE / "update_check"
    UPDATE_INTERVAL = int(os.environ.get("REPLX_UPDATE_INTERVAL_SEC", str(60 * 60 * 24)))
    ENV_NO_UPDATE = "REPLX_NO_UPDATE_CHECK"
    
    @staticmethod
    def is_interactive_tty() -> bool:
        try:
            return sys.stdin.isatty() and sys.stdout.isatty()
        except Exception:
            return False
    
    @staticmethod
    def check_for_updates(current_version: str, *, force: bool = False):
        if os.environ.get(UpdateChecker.ENV_NO_UPDATE, "").strip():
            return
        if not force and not UpdateChecker.is_interactive_tty():
            return
        
        StoreManager.ensure_home_store()
        p = UpdateChecker.UPDATE_TIMESTAMP_FILE
        try:
            should_check = (not p.exists()) or (time.time() - p.stat().st_mtime) >= UpdateChecker.UPDATE_INTERVAL
        except Exception:
            should_check = True
        
        if not should_check:
            return
        
        def _vt(v: str) -> tuple:
            parts = re.findall(r"\d+", str(v))
            return tuple(int(p) for p in parts) or (0,)

        def _is_newer(latest: str, current: str) -> bool:
            return _vt(latest) > _vt(current)

        try:
            with urllib.request.urlopen("https://pypi.org/pypi/replx/json", timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest_version = data["info"]["version"]

            if _is_newer(latest_version, current_version):
                if UpdateChecker.is_interactive_tty():
                    from .output import OutputHelper
                    OutputHelper._console.print(f"\n[bright_yellow]New version available: {latest_version}[/bright_yellow]")
                    OutputHelper._console.print("Run: [bright_blue]pip install --upgrade replx[/bright_blue]\n")
        except Exception:
            pass
        finally:
            try:
                StoreManager.ensure_home_store()
                UpdateChecker.UPDATE_TIMESTAMP_FILE.touch()
            except Exception:
                pass
