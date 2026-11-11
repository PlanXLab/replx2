import os
import sys
import re
import json
import subprocess
from functools import lru_cache

from rich.console import Console
from rich.panel import Panel
from rich.theme import Theme

from ..config import AgentPortManager
from . import get_panel_box, CONSOLE_WIDTH, get_global_context


_THEME_ALIASES = {
    'dark': 'one-dark-pro',
    'light': 'atom-one-light',
    'white': 'atom-one-light',
    'one-dark-pro': 'one-dark-pro',
    'atom-one-light': 'atom-one-light',
    'github-dark': 'github-dark',
    'github-light': 'github-light',
}

_THEME_STYLES = {
    'one-dark-pro': {
        'blue': '#61afef', 'bright_blue': '#61afef',
        'cyan': '#56b6c2', 'bright_cyan': '#56b6c2',
        'green': '#98c379', 'bright_green': '#98c379',
        'yellow': '#e5c07b', 'bright_yellow': '#e5c07b',
        'magenta': '#c678dd', 'bright_magenta': '#c678dd',
        'red': '#e06c75', 'bright_red': '#e06c75',
        'white': '#abb2bf', 'bright_white': '#d7dae0',
        'dim': '#7f848e',
    },
    'atom-one-light': {
        'blue': '#005cc5', 'bright_blue': '#005cc5',
        'cyan': '#0184bc', 'bright_cyan': '#0184bc',
        'green': '#22863a', 'bright_green': '#22863a',
        'yellow': '#b08800', 'bright_yellow': '#b08800',
        'magenta': '#6f42c1', 'bright_magenta': '#6f42c1',
        'red': '#d73a49', 'bright_red': '#d73a49',
        'white': '#24292e', 'bright_white': '#24292e',
        'dim': '#6a737d',
    },
    'github-dark': {
        'blue': '#79c0ff', 'bright_blue': '#79c0ff',
        'cyan': '#39c5cf', 'bright_cyan': '#39c5cf',
        'green': '#7ee787', 'bright_green': '#7ee787',
        'yellow': '#d29922', 'bright_yellow': '#d29922',
        'magenta': '#d2a8ff', 'bright_magenta': '#d2a8ff',
        'red': '#ff7b72', 'bright_red': '#ff7b72',
        'white': '#c9d1d9', 'bright_white': '#f0f6fc',
        'dim': '#8b949e',
    },
    'github-light': {
        'blue': '#0969da', 'bright_blue': '#0969da',
        'cyan': '#1b7c83', 'bright_cyan': '#1b7c83',
        'green': '#1a7f37', 'bright_green': '#1a7f37',
        'yellow': '#9a6700', 'bright_yellow': '#9a6700',
        'magenta': '#8250df', 'bright_magenta': '#8250df',
        'red': '#cf222e', 'bright_red': '#cf222e',
        'white': '#1f2328', 'bright_white': '#1f2328',
        'dim': '#656d76',
    },
}

_VSCODE_AUTO_THEME = 'vscode-auto'

_SYNTAX_THEME_MAP = {
    'one-dark-pro': 'one-dark',
    'atom-one-light': 'default',
    'github-dark': 'dracula',
    'github-light': 'friendly',
}

_CATEGORY_COLOR_KEYS: dict[str, str] = {
    'help':    'blue',
    'success': 'green',
    'data':    'cyan',
    'mode':    'magenta',
    'warning': 'yellow',
    'neutral': 'dim',
    'error':   'red',
}

VALID_PANEL_CATEGORIES: tuple[str, ...] = tuple(_CATEGORY_COLOR_KEYS)

def _load_jsonc(path: str):
    if not path or not os.path.exists(path):
        return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = f.read()
    except Exception:
        return None

    try:
        return json.loads(raw)
    except Exception:
        pass

    try:
        no_block_comments = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
        no_line_comments = re.sub(r"(^|\s)//.*$", "", no_block_comments, flags=re.M)
        no_trailing_commas = re.sub(r",\s*([}\]])", r"\1", no_line_comments)
        return json.loads(no_trailing_commas)
    except Exception:
        return None


@lru_cache(maxsize=1)
def _get_portable_vscode_root_from_pshome() -> str | None:
    pshome = os.environ.get('PSHOME', '').strip()
    if not pshome:
        try:
            run_kwargs = {
                'capture_output': True,
                'text': True,
                'encoding': 'utf-8',
                'errors': 'replace',
                'timeout': 2,
                'check': False,
            }
            if sys.platform.startswith('win'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                run_kwargs['startupinfo'] = startupinfo
                run_kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            result = subprocess.run(
                ['pwsh', '-NoLogo', '-NoProfile', '-Command', '$PSHOME'],
                **run_kwargs,
            )
            pshome = result.stdout.strip()
        except Exception:
            return None

    if not pshome:
        return None
    vscode_root = os.path.dirname(os.path.dirname(os.path.dirname(pshome)))
    vscode_root = os.path.dirname(os.path.dirname(os.path.dirname(pshome)))
    return vscode_root


@lru_cache(maxsize=1)
def _get_vscode_theme_name_from_settings() -> str | None:
    vscode_root = _get_portable_vscode_root_from_pshome()
    if not vscode_root:
        return None

    settings_path = os.path.join(vscode_root, 'data', 'user-data', 'User', 'settings.json')
    data = _load_jsonc(settings_path)
    if not isinstance(data, dict):
        return None

    theme_name = data.get('workbench.colorTheme')
    if isinstance(theme_name, str):
        theme_name = theme_name.strip()
        if theme_name:
            return theme_name

    return None


def _normalize_hex_color(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None

    color = value.strip()
    if not color:
        return None

    if re.fullmatch(r"#[0-9a-fA-F]{8}", color):
        return color[:7]
    if re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        return color
    if re.fullmatch(r"#[0-9a-fA-F]{4}", color):
        return '#' + ''.join(ch * 2 for ch in color[1:4])
    if re.fullmatch(r"#[0-9a-fA-F]{3}", color):
        return '#' + ''.join(ch * 2 for ch in color[1:])
    if color.lower() in {'black', 'white', 'red', 'green', 'blue', 'yellow', 'magenta', 'cyan'}:
        return color.lower()

    return None


def _normalize_theme_scope(scope_value) -> list[str]:
    if isinstance(scope_value, str):
        return [part.strip().lower() for part in scope_value.split(',') if part.strip()]
    if isinstance(scope_value, list):
        scopes = []
        for item in scope_value:
            if isinstance(item, str):
                scopes.extend(part.strip().lower() for part in item.split(',') if part.strip())
        return scopes
    return []


def _get_token_color(token_colors, needles: list[str]) -> str | None:
    if not isinstance(token_colors, list):
        return None

    lowered_needles = [needle.lower() for needle in needles]
    for entry in token_colors:
        if not isinstance(entry, dict):
            continue
        scopes = _normalize_theme_scope(entry.get('scope'))
        if not scopes:
            continue
        if not any(any(needle in scope for scope in scopes) for needle in lowered_needles):
            continue
        settings = entry.get('settings')
        if not isinstance(settings, dict):
            continue
        foreground = _normalize_hex_color(settings.get('foreground'))
        if foreground:
            return foreground

    return None


def _get_color_from_keys(colors: dict, keys: list[str]) -> str | None:
    for key in keys:
        color = _normalize_hex_color(colors.get(key))
        if color:
            return color
    return None


def _map_vscode_theme_to_builtin(theme_name: str | None, ui_theme: str | None = None) -> str:
    label = (theme_name or '').strip().lower()
    ui = (ui_theme or '').strip().lower()

    if 'github' in label and 'light' in label:
        return 'github-light'
    if 'github' in label and 'dark' in label:
        return 'github-dark'
    if 'one dark' in label:
        return 'one-dark-pro'
    if 'atom' in label and 'one' in label and 'light' in label:
        return 'atom-one-light'
    if 'light' in label or 'white' in label:
        return 'atom-one-light'
    if 'dark' in label:
        return 'one-dark-pro'
    if ui in {'vs', 'hc-light'}:
        return 'atom-one-light'
    return 'one-dark-pro'


@lru_cache(maxsize=1)
def _get_vscode_theme_contributions() -> tuple[tuple[str, str, str | None, str], ...]:
    vscode_root = _get_portable_vscode_root_from_pshome()
    if not vscode_root:
        return ()

    extensions_root = os.path.join(vscode_root, 'data', 'extensions')
    if not os.path.isdir(extensions_root):
        return ()

    contributions: list[tuple[str, str, str | None, str]] = []
    try:
        extension_dirs = sorted(os.listdir(extensions_root))
    except Exception:
        return ()

    for directory_name in extension_dirs:
        extension_dir = os.path.join(extensions_root, directory_name)
        if not os.path.isdir(extension_dir):
            continue

        package_path = os.path.join(extension_dir, 'package.json')
        manifest = _load_jsonc(package_path)
        if not isinstance(manifest, dict):
            continue

        contributes = manifest.get('contributes')
        if not isinstance(contributes, dict):
            continue

        themes = contributes.get('themes')
        if not isinstance(themes, list):
            continue

        for theme in themes:
            if not isinstance(theme, dict):
                continue
            label = theme.get('label')
            relative_path = theme.get('path')
            if not isinstance(label, str) or not isinstance(relative_path, str):
                continue
            ui_theme = theme.get('uiTheme') if isinstance(theme.get('uiTheme'), str) else None
            theme_path = os.path.normpath(os.path.join(extension_dir, relative_path))
            contributions.append((label.strip().lower(), label.strip(), ui_theme, theme_path))

    return tuple(contributions)


def _find_vscode_theme_entry(theme_name: str) -> tuple[str, str | None, str] | None:
    needle = theme_name.strip().lower()
    if not needle:
        return None

    for label_key, label, ui_theme, theme_path in _get_vscode_theme_contributions():
        if label_key == needle:
            return label, ui_theme, theme_path

    return None


def _build_dynamic_vscode_styles(theme_name: str, ui_theme: str | None, theme_data: dict) -> dict[str, str]:
    base_theme = _map_vscode_theme_to_builtin(theme_name, ui_theme)
    styles = dict(_THEME_STYLES[base_theme])

    colors = theme_data.get('colors')
    if not isinstance(colors, dict):
        colors = {}
    token_colors = theme_data.get('tokenColors')

    extracted = {
        'blue': _get_color_from_keys(colors, ['terminal.ansiBlue', 'editorCursor.foreground', 'button.background', 'focusBorder']) or _get_token_color(token_colors, ['entity.name.function', 'keyword.other.special-method', 'support.function.any-method']),
        'cyan': _get_color_from_keys(colors, ['terminal.ansiCyan', 'textLink.foreground', 'badge.background']) or _get_token_color(token_colors, ['support.function', 'support.type', 'string.regexp', 'markup.link']),
        'green': _get_color_from_keys(colors, ['terminal.ansiGreen', 'terminal.ansiBrightGreen']) or _get_token_color(token_colors, ['string', 'markup.inserted']),
        'yellow': _get_color_from_keys(colors, ['terminal.ansiYellow', 'terminal.ansiBrightYellow']) or _get_token_color(token_colors, ['constant.numeric', 'constant', 'entity.name.type', 'storage.type']),
        'magenta': _get_color_from_keys(colors, ['terminal.ansiMagenta', 'terminal.ansiBrightMagenta']) or _get_token_color(token_colors, ['keyword', 'storage']),
        'red': _get_color_from_keys(colors, ['terminal.ansiRed', 'terminal.ansiBrightRed']) or _get_token_color(token_colors, ['variable', 'invalid', 'markup.deleted']),
        'white': _get_color_from_keys(colors, ['terminal.foreground', 'editor.foreground']),
        'bright_white': _get_color_from_keys(colors, ['terminal.ansiBrightWhite', 'terminal.foreground', 'editor.foreground']),
        'dim': _get_color_from_keys(colors, ['terminal.ansiBrightBlack', 'descriptionForeground', 'editorLineNumber.foreground']) or _get_token_color(token_colors, ['comment']),
    }

    for key, color in extracted.items():
        if color:
            styles[key] = color

    for key in ('blue', 'cyan', 'green', 'yellow', 'magenta', 'red'):
        bright_key = f'bright_{key}'
        if extracted.get(key):
            styles[bright_key] = extracted[key]

    if styles.get('white') and not extracted.get('bright_white'):
        styles['bright_white'] = styles['white']

    return styles


@lru_cache(maxsize=32)
def _resolve_dynamic_vscode_theme(theme_name: str) -> tuple[str, dict[str, str]] | None:
    entry = _find_vscode_theme_entry(theme_name)
    if entry:
        label, ui_theme, theme_path = entry
        theme_data = _load_jsonc(theme_path)
        if isinstance(theme_data, dict):
            return label, _build_dynamic_vscode_styles(label, ui_theme, theme_data)
        base_theme = _map_vscode_theme_to_builtin(label, ui_theme)
        return label, dict(_THEME_STYLES[base_theme])

    theme_name = theme_name.strip()
    if theme_name:
        base_theme = _map_vscode_theme_to_builtin(theme_name)
        return theme_name, dict(_THEME_STYLES[base_theme])

    return None


def _resolve_theme_config(name: str | None) -> tuple[str, str, dict[str, str]]:
    raw_name = (name or 'dark').strip() or 'dark'
    canonical = _normalize_theme_name(raw_name)
    if canonical in _THEME_STYLES:
        return canonical, canonical, dict(_THEME_STYLES[canonical])

    if raw_name.lower() == _VSCODE_AUTO_THEME:
        current_vscode_theme = _get_vscode_theme_name_from_settings()
        if current_vscode_theme:
            resolved = _resolve_dynamic_vscode_theme(current_vscode_theme)
            if resolved:
                display_name, styles = resolved
                return _VSCODE_AUTO_THEME, display_name, styles
        return _VSCODE_AUTO_THEME, 'one-dark-pro', dict(_THEME_STYLES['one-dark-pro'])

    raise ValueError(
        f"Unsupported theme '{name}'. Available: {', '.join(OutputHelper.available_themes())}"
    )


def _normalize_theme_name(name: str | None) -> str:
    key = (name or 'dark').strip().lower()
    return _THEME_ALIASES.get(key, key)


def _build_rich_theme(name: str) -> Theme:
    try:
        _, _, styles = _resolve_theme_config(name)
    except Exception:
        styles = _THEME_STYLES['one-dark-pro']
    return Theme(styles)


class OutputHelper:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    
    _theme_name = 'one-dark-pro'
    _theme_display_name = 'one-dark-pro'
    _theme_styles = dict(_THEME_STYLES[_theme_name])
    _console = Console(width=CONSOLE_WIDTH, legacy_windows=False, theme=Theme(_theme_styles))
    PANEL_WIDTH = None

    @staticmethod
    def make_console(width: int = CONSOLE_WIDTH, file=None, **kwargs) -> Console:
        kwargs.setdefault('legacy_windows', False)
        kwargs.setdefault('theme', Theme(dict(OutputHelper._theme_styles)))
        return Console(width=width, file=file, **kwargs)

    @staticmethod
    def available_themes() -> list[str]:
        return ['dark', 'white', 'one-dark-pro', 'atom-one-light', 'github-dark', 'github-light']

    @staticmethod
    def set_theme(theme_name: str | None) -> str:
        stored_name, display_name, styles = _resolve_theme_config(theme_name)
        OutputHelper._theme_name = stored_name
        OutputHelper._theme_display_name = display_name
        OutputHelper._theme_styles = styles
        OutputHelper._console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        return stored_name

    @staticmethod
    def get_theme() -> str:
        return OutputHelper._theme_name

    @staticmethod
    def get_theme_display_name() -> str:
        return OutputHelper._theme_display_name

    @staticmethod
    def get_syntax_theme() -> str:
        theme = OutputHelper._theme_name
        if theme in _SYNTAX_THEME_MAP:
            return _SYNTAX_THEME_MAP[theme]
        if theme == _VSCODE_AUTO_THEME:
            display = OutputHelper._theme_display_name.lower()
            if any(k in display for k in ('light', 'white', 'solarized light')):
                return 'friendly'
        return 'one-dark'

    @staticmethod
    def format_bytes(b: int) -> str:
        if b < 1024:
            return f"{b}B"
        elif b < 1024 * 1024:
            return f"{b/1024:.1f}KB"
        else:
            return f"{b/(1024*1024):.1f}MB"

    @staticmethod
    def normalize_remote_path(path: str) -> str:
        path = path.replace('\\', '/')
        if not path.startswith('/'):
            path = '/' + path
        return path

    @staticmethod
    def format_port(port: str) -> str:
        if port is None:
            return ""
        p = str(port).strip()
        return p.upper() if sys.platform.startswith("win") else p
    
    @staticmethod
    def _get_panel_width():
        if OutputHelper.PANEL_WIDTH is None:
            OutputHelper.PANEL_WIDTH = CONSOLE_WIDTH
        return OutputHelper.PANEL_WIDTH
    
    @staticmethod
    def print_panel(
        content: str,
        title: str = "",
        border_style: str = "data",
        *,
        height: int | None = None,
        **panel_kwargs,
    ):
        width = OutputHelper._get_panel_width()
        panel_kwargs["title_align"] = "left"

        # Resolve category → color key → theme hex, with per-category user override
        if border_style not in _CATEGORY_COLOR_KEYS:
            raise ValueError(
                f"Unknown panel category: {border_style!r}. "
                f"Valid: {', '.join(_CATEGORY_COLOR_KEYS)}"
            )
        color_key = _CATEGORY_COLOR_KEYS[border_style]
        panel_colors = AgentPortManager.read_panel_colors()
        if border_style in panel_colors:
            resolved_border = panel_colors[border_style]
        else:
            resolved_border = OutputHelper._theme_styles[color_key]

        panel = Panel(
            content,
            title=title,
            border_style=resolved_border,
            box=get_panel_box(),
            expand=True,
            width=width,
            height=height,
            **panel_kwargs,
        )

        OutputHelper._console.print(panel)

    @staticmethod
    def _resolve_category_color(category: str) -> str:
        """Resolve a panel category to its final hex/color string."""
        color_key = _CATEGORY_COLOR_KEYS[category]
        panel_colors = AgentPortManager.read_panel_colors()
        if category in panel_colors:
            return panel_colors[category]
        return OutputHelper._theme_styles[color_key]

    @staticmethod
    def create_progress_panel(current: int, total: int, title: str = "Progress", message: str = "", counter_text: str = None):
        pct = 0 if total == 0 else min(1.0, current / total)
        
        panel_width = OutputHelper._get_panel_width()
        bar_length = max(20, panel_width - 40) 
        
        block = min(bar_length, int(round(bar_length * pct)))
        bar = "█" * block + "░" * (bar_length - block)
        percent = int(pct * 100)
        
        if counter_text is None:
            counter_text = f"({current}/{total})"
        
        content_lines = []
        if message:
            content_lines.append(message)
        content_lines.append(f"[{bar}] {percent}% {counter_text}")
        
        width = OutputHelper._get_panel_width()
        return Panel("\n".join(content_lines), title=title, title_align="left",
                     border_style=OutputHelper._resolve_category_color('success'),
                     box=get_panel_box(), expand=True, width=width)

    @staticmethod
    def create_spinner_panel(message: str, title: str = "Processing", spinner_frames: list = None, frame_idx: int = 0):
        if spinner_frames is None:
            spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        
        spinner = spinner_frames[frame_idx % len(spinner_frames)]
        content = f"{spinner}  {message}"
        width = OutputHelper._get_panel_width()
        return Panel(content, title=title, title_align="left",
                     border_style=OutputHelper._resolve_category_color('warning'),
                     box=get_panel_box(), expand=True, width=width)
    
    @staticmethod
    def format_error_output(out, local_file):
        _core, _device, _version, _device_root_fs, _device_path = get_global_context()
        
        OutputHelper._console.print(f"\r[dim]{'-'*40}Traceback{'-'*40}[/dim]")
        for l in out[1:-2]:
            if "<stdin>" in l:
                full_path = os.path.abspath(os.path.join(os.getcwd(), local_file))
                l = l.replace("<stdin>", full_path, 1)
            print(l.strip())
            
        try:
            err_line_raw = out[-2].strip()
            
            if "<stdin>" in err_line_raw:
                full_path = os.path.abspath(os.path.join(os.getcwd(), local_file))
                err_line = err_line_raw.replace("<stdin>", full_path, 1)
            else:
                match = re.search(r'File "([^"]+)"', err_line_raw)
                if match:
                    device_src_path = os.path.join(_device_path, "src")
                    full_path = os.path.join(device_src_path, match.group(1))
                    escaped_filename = re.sub(r"([\\\\])", r"\\\1", full_path)
                    err_line = re.sub(r'File "([^"]+)"', rf'File "{escaped_filename}"', err_line_raw)
                else:
                    full_path = os.path.abspath(os.path.join(os.getcwd(), local_file))
                    err_line = err_line_raw
                    
            print(f" {err_line}")
            
            err_content = out[-1].strip()

            match = re.search(r"line (\d+)", err_line)
            if match:
                line = int(match.group(1))
                try:
                    with open(full_path, "r") as f:
                        lines = f.readlines()
                        print(f"  {lines[line - 1].rstrip()}")
                except (OSError, IndexError):
                    pass

        except IndexError:
            err_content = out[-1].strip()
        
        OutputHelper._console.print(f"[bright_magenta]{err_content}[/bright_magenta]")

    @staticmethod
    def handle_error(error: Exception, context: str = "Error") -> bool:
        error_msg = str(error)
        
        if 'is busy' in error_msg:
            repl_match = re.search(r'Connection (\S+) is busy.*REPL session is active', error_msg)
            if repl_match:
                port = repl_match.group(1)
                message = (
                    f"[bright_cyan]{port}[/bright_cyan] has an active REPL session in another terminal.\n\n"
                    "[dim]Exit REPL first with [bold]exit()[/bold] or [bold]Ctrl+D[/bold] in the other terminal.[/dim]\n\n"
                    "Run [bright_cyan]replx status[/bright_cyan] to check connection status."
                )
                OutputHelper.print_panel(
                    message,
                    title="REPL Active",
                    border_style="warning"
                )
                return True
            
            detached_match = re.search(r'Connection (\S+) is busy.*detached script is running', error_msg)
            if detached_match:
                port = detached_match.group(1)
                message = (
                    f"[bright_cyan]{port}[/bright_cyan] is running a background script.\n\n"
                    "[dim]Stop it first with [bold]replx reset[/bold] or [bold]replx run --stop[/bold].[/dim]\n\n"
                    "Run [bright_cyan]replx status[/bright_cyan] to check connection status."
                )
                OutputHelper.print_panel(
                    message,
                    title="Script Running",
                    border_style="warning"
                )
                return True
            
            match = re.search(r'Connection (\S+) is busy.*Another command \((\w+)\)', error_msg)
            if match:
                port = match.group(1)
                command = match.group(2)
                message = (
                    f"[bright_cyan]{port}[/bright_cyan] is currently executing "
                    f"[yellow]{command}[/yellow].\n\n"
                    "[dim]Wait for it to complete, or press [bold]Ctrl+C[/bold] in the other terminal to stop it.[/dim]\n\n"
                    "Run [bright_cyan]replx status[/bright_cyan] to check connection status."
                )
            else:
                message = (
                    f"{error_msg}\n\n"
                    "Run [bright_cyan]replx status[/bright_cyan] to check connection status."
                )
            OutputHelper.print_panel(
                message,
                title="Connection Busy",
                border_style="warning"
            )
            return True
        elif 'Not connected' in error_msg:
            OutputHelper.print_panel(
                "No active connection.\n\n"
                "Run [bright_blue]replx --port PORT setup[/bright_blue] first.",
                title="Not Connected",
                border_style="error"
            )
            return True
        
        return False
