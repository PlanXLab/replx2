import os
from typing import Optional
import psutil

def _find_terminal_process() -> Optional[dict]:
    shell_names = {
        # Windows
        'powershell.exe', 'pwsh.exe', 'cmd.exe', 'bash.exe', 'zsh.exe', 'sh.exe', 'fish.exe',
        'windowsterminal.exe',
        # Linux / macOS (no .exe)
        'bash', 'zsh', 'sh', 'fish', 'tcsh', 'csh', 'ksh', 'dash', 'pwsh',
    }

    ide_names = {
        # Windows
        'code.exe',
        'conemu64.exe', 'conemu.exe',
        'pycharm.exe', 'pycharm64.exe', 'idea.exe', 'idea64.exe',
        # Linux / macOS (no .exe)
        'code', 'code-oss',
        'pycharm', 'pycharm64', 'idea', 'idea64',
    }

    try:
        parent_pid = os.getppid()
        if parent_pid and parent_pid > 0:
            parent = psutil.Process(parent_pid)
            pname = (parent.name() or '').lower()
            if pname in shell_names:
                return {
                    'pid': parent.pid,
                    'name': parent.name(),
                    'create_time': parent.create_time(),
                    'cwd': None,
                    'level': 0,
                }
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
        pass

    try:
        current = psutil.Process()
        best_ide = None

        for level in range(12):
            if current is None:
                break

            try:
                name = (current.name() or '').lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                break

            if name in shell_names:
                return {
                    'pid': current.pid,
                    'name': current.name(),
                    'create_time': current.create_time(),
                    'cwd': None,
                    'level': level,
                }

            if name in ide_names and best_ide is None:
                try:
                    best_ide = {
                        'pid': current.pid,
                        'name': current.name(),
                        'create_time': current.create_time(),
                        'cwd': None,
                        'level': level,
                    }
                except Exception:
                    best_ide = None

            try:
                if current.ppid() == 0:
                    break
            except Exception:
                break

            try:
                parent = current.parent()
            except Exception:
                parent = None

            if parent is None:
                break
            current = parent

        if best_ide is not None:
            return best_ide

    except Exception:
        pass

    return None

def _find_jupyter_kernel() -> Optional[dict]:
    try:
        current = psutil.Process()
        for level in range(10):
            if current is None:
                break

            cmdline = ' '.join(current.cmdline()).lower()

            if any(keyword in cmdline for keyword in ['jupyter', 'ipykernel', 'ipython']):
                return {
                    'pid': current.pid,
                    'name': current.name(),
                    'cmdline': cmdline,
                    'level': level
                }

            if current.ppid() == 0:
                break

            parent = current.parent()
            if parent is None:
                break
            current = parent

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass

    return None

def get_session_id() -> int:
    terminal = _find_terminal_process()
    if terminal:
        return terminal['pid']

    jupyter = _find_jupyter_kernel()
    if jupyter:
        return jupyter['pid']

    ppid = os.getppid()
    if ppid and ppid > 0:
        return ppid

    workspace_hash = abs(hash(os.getcwd())) % (10**8)
    return workspace_hash

_session_id_cache: Optional[int] = None

def get_cached_session_id() -> int:
    global _session_id_cache

    if _session_id_cache is None:
        _session_id_cache = get_session_id()

    return _session_id_cache

def clear_session_cache():
    global _session_id_cache
    _session_id_cache = None
