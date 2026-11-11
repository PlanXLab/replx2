import os
import re
import time
import urllib.request
import urllib.error
import json
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urljoin, urlparse

import typer
from rich.columns import Columns
from rich.prompt import Prompt
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text

from ..helpers import (
    OutputHelper, StoreManager,
    get_panel_box, CONSOLE_WIDTH
)
from ..connection import (
    _ensure_connected, _create_agent_client
)

from ..app import app
from replx.utils.device_info import normalize_core


SUPPORTED_FIRMWARE_DEVICES = {
    "ticle-lite",
    "ticle-sensor", 
}

FIRMWARE_REPO_OWNER = "PlanXLab"
FIRMWARE_REPO_NAME = "ticle_firmware"
FIRMWARE_REPO_BRANCH = "main"

_P4_C6_FIRMWARE_PAGE_URL = "https://micropython.org/download/ESP32_GENERIC_P4/"
_P4_C6_SECTION_TITLE = "Firmware (Support for external C6 WiFi/BLE)"
_P4_C6_FIRMWARE_FILENAME_RE = re.compile(
    r"ESP32_GENERIC_P4-C6_WIFI-(\d{8})-(v[^/]+)\.bin"
)


class FirmwareLookupError(RuntimeError):
    pass


class _P4C6FirmwarePageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_target_section = False
        self._heading_tag: Optional[str] = None
        self._heading_parts: list[str] = []
        self._build_type: Optional[str] = None
        self._link_href: Optional[str] = None
        self._link_parts: list[str] = []
        self.builds: dict[str, list[dict[str, str]]] = {
            "release": [],
            "preview": [],
        }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag == "h2":
            self._heading_tag = tag
            self._heading_parts = []
        elif tag == "h3" and self._in_target_section:
            self._heading_tag = tag
            self._heading_parts = []
        elif tag == "a" and self._in_target_section and self._build_type:
            href = dict(attrs).get("href")
            if href:
                self._link_href = href
                self._link_parts = []

    def handle_data(self, data: str) -> None:
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if self._link_href is not None:
            self._link_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self._heading_tag == "h2":
            heading = " ".join("".join(self._heading_parts).split())
            self._in_target_section = heading.casefold() == _P4_C6_SECTION_TITLE.casefold()
            self._build_type = None
            self._heading_tag = None
        elif tag == "h3" and self._heading_tag == "h3":
            heading = " ".join("".join(self._heading_parts).split()).casefold()
            self._build_type = {
                "releases": "release",
                "preview builds": "preview",
            }.get(heading)
            self._heading_tag = None
        elif tag == "a" and self._link_href is not None:
            self._record_build()
            self._link_href = None
            self._link_parts = []

    def _record_build(self) -> None:
        if self._build_type is None or self._link_href is None:
            return

        link = urlparse(self._link_href)
        if (link.scheme and link.scheme != "https") or (
            link.netloc and link.netloc.lower() != "micropython.org"
        ):
            return

        download_url = urljoin(_P4_C6_FIRMWARE_PAGE_URL, self._link_href)
        parsed_url = urlparse(download_url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.netloc.lower() != "micropython.org"
            or not parsed_url.path.startswith("/resources/firmware/")
        ):
            return

        filename = unquote(parsed_url.path.rsplit("/", 1)[-1])
        match = _P4_C6_FIRMWARE_FILENAME_RE.fullmatch(filename)
        if match is None:
            return

        build_date, version = match.groups()
        label = " ".join("".join(self._link_parts).split())
        self.builds[self._build_type].append({
            "version": version,
            "date": f"{build_date[:4]}-{build_date[4:6]}-{build_date[6:]}",
            "filename": filename,
            "download_url": download_url,
            "label": label,
        })

    def latest_builds(self) -> dict[str, dict[str, str]]:
        return {
            build_type: max(builds, key=lambda build: build["date"])
            for build_type, builds in self.builds.items()
            if builds
        }


def _get_p4_c6_firmware_builds() -> dict[str, dict[str, str]]:
    request = urllib.request.Request(
        _P4_C6_FIRMWARE_PAGE_URL,
        headers={"User-Agent": "replx"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            page = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise FirmwareLookupError(
            f"MicroPython firmware page returned HTTP {e.code}"
        ) from e
    except (urllib.error.URLError, TimeoutError) as e:
        reason = getattr(e, "reason", e)
        raise FirmwareLookupError(
            f"Could not reach the MicroPython firmware page: {reason}"
        ) from e
    except UnicodeDecodeError as e:
        raise FirmwareLookupError(
            "MicroPython firmware page was not valid UTF-8"
        ) from e

    parser = _P4C6FirmwarePageParser()
    parser.feed(page)
    parser.close()
    builds = parser.latest_builds()
    missing = [
        title
        for build_type, title in (
            ("release", "latest Release"),
            ("preview", "latest Preview build"),
        )
        if build_type not in builds
    ]
    if missing:
        raise FirmwareLookupError(
            f"Could not find the {' and '.join(missing)} in the C6 WiFi/BLE section "
            f"of {_P4_C6_FIRMWARE_PAGE_URL}"
        )
    return builds


def _get_firmware_local_dir(device: str) -> Path:
    return StoreManager.HOME_STORE / "firmware" / device


def _ensure_firmware_dir(device: str) -> Path:
    firmware_dir = _get_firmware_local_dir(device)
    firmware_dir.mkdir(parents=True, exist_ok=True)
    return firmware_dir


def _parse_version(version_str: str) -> tuple:
    try:
        match = re.fullmatch(
            r"v?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?",
            version_str.strip(),
        )
        if match is None:
            return (0, 0, 0, 0, ())

        numeric_parts = tuple(int(part) for part in match.group(1).split("."))
        numeric_parts += (0,) * max(0, 3 - len(numeric_parts))
        prerelease = match.group(2)
        if prerelease is None:
            return (*numeric_parts, 1, ())

        prerelease_parts = tuple(
            (0, int(part)) if part.isdigit() else (1, part.casefold())
            for part in prerelease.split(".")
        )
        return (*numeric_parts, 0, prerelease_parts)
    except (ValueError, AttributeError):
        return (0, 0, 0, 0, ())


def _get_remote_firmware_info(device: str) -> dict:
    api_url = f"https://api.github.com/repos/{FIRMWARE_REPO_OWNER}/{FIRMWARE_REPO_NAME}/releases/latest"
    
    headers = {"User-Agent": "replx"}
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            release_data = json.load(response)
            
        version = release_data.get('tag_name', '').lstrip('v')
        
        for asset in release_data.get('assets', []):
            asset_name = asset.get('name', '')
            if asset_name == f"{device}.uf2":
                return {
                    'version': version,
                    'download_url': asset.get('browser_download_url'),
                    'size': asset.get('size', 0)
                }
        
        download_url = f"https://github.com/{FIRMWARE_REPO_OWNER}/{FIRMWARE_REPO_NAME}/releases/download/v{version}/{device}.uf2"
        return {
            'version': version,
            'download_url': download_url,
            'size': 0 
        }
        
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise FirmwareLookupError(f"GitHub API returned HTTP {e.code}") from e
    except urllib.error.URLError as e:
        reason = getattr(e, 'reason', e)
        raise FirmwareLookupError(f"Could not reach firmware repository: {reason}") from e
    except json.JSONDecodeError as e:
        raise FirmwareLookupError("Firmware repository returned an invalid JSON response") from e
    except Exception as e:
        raise FirmwareLookupError(f"Failed to check firmware repository: {e}") from e


def _get_local_firmware_versions(device: str) -> list[tuple[str, Path]]:
    firmware_dir = _get_firmware_local_dir(device)
    if not firmware_dir.exists():
        return []
    
    versions = []
    pattern = re.compile(rf"^{re.escape(device)}_v(.+)\.uf2$")
    
    for f in firmware_dir.iterdir():
        if f.is_file():
            match = pattern.match(f.name)
            if match:
                version = match.group(1)
                versions.append((version, f))
    
    versions.sort(key=lambda x: _parse_version(x[0]), reverse=True)
    return versions


def _cleanup_old_firmware(device: str, keep_version: str):
    versions = _get_local_firmware_versions(device)
    for version, path in versions:
        if version != keep_version:
            try:
                path.unlink()
            except Exception:
                pass


def _download_firmware(device: str, version: str, url: str, target_path: Path, 
                       show_progress: bool = True) -> bool:
    
    try:
        headers = {"User-Agent": "replx"}
        req = urllib.request.Request(url, headers=headers)
        
        if show_progress:
            spinner = Spinner("dots", text=Text(f" Downloading {device} firmware v{version}...", style="bright_cyan"))
            with Live(spinner, console=OutputHelper._console, refresh_per_second=10, transient=True):
                with urllib.request.urlopen(req, timeout=60) as response:
                    content = response.read()
        else:
            with urllib.request.urlopen(req, timeout=60) as response:
                content = response.read()
        
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        temp_path = target_path.with_suffix('.tmp')
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        temp_path.replace(target_path)
        return True
        
    except urllib.error.HTTPError as e:
        if show_progress:
            OutputHelper.print_panel(
                f"Download failed: HTTP {e.code}\n\nURL: {url}",
                title="Download Error",
                border_style="error"
            )
        return False
    except Exception as e:
        if show_progress:
            OutputHelper.print_panel(
                f"Download failed: {str(e)}",
                title="Download Error",
                border_style="error"
            )
        return False


def _find_uf2_drive() -> Optional[Path]:
    import platform
    system = platform.system()
    
    if system == "Windows":
        import ctypes
        import string
        
        drives = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:")
            bitmask >>= 1
        
        for drive in drives:
            try:
                info_file = Path(drive) / "INFO_UF2.TXT"
                if info_file.exists():
                    return Path(drive)
            except Exception:
                continue
                
    elif system == "Darwin":
        volumes = Path("/Volumes")
        if volumes.exists():
            for vol in volumes.iterdir():
                try:
                    vol_name_upper = vol.name.upper()
                    if any(name in vol_name_upper for name in ["RPI", "RP2", "PICO", "BOOTLOADER"]):
                        info_file = vol / "INFO_UF2.TXT"
                        if info_file.exists():
                            return vol
                except (PermissionError, OSError):
                    continue
                        
    elif system == "Linux":
        user = os.getenv('USER', '')
        search_paths = [
            Path("/media"),
            Path("/mnt"),
            Path(f"/media/{user}") if user else None,
            Path(f"/run/media/{user}") if user else None,
        ]
        for base in search_paths:
            if base and base.exists():
                try:
                    for mount in base.iterdir():
                        if mount.is_dir():
                            try:
                                info_file = mount / "INFO_UF2.TXT"
                                if info_file.exists():
                                    return mount
                                mount_name_upper = mount.name.upper()
                                if any(name in mount_name_upper for name in ["RPI", "RP2", "PICO", "BOOTLOADER"]):
                                    if (mount / "INDEX.HTM").exists() or (mount / "INDEX.HTML").exists():
                                        return mount
                            except (PermissionError, OSError):
                                continue
                except (PermissionError, OSError):
                    continue
    
    return None


def _wait_for_uf2_drive(timeout: int = 30, live=None) -> Optional[Path]:
    start_time = time.time()
    while time.time() - start_time < timeout:
        drive = _find_uf2_drive()
        if drive:
            return drive
        time.sleep(0.5)
    
    return None


@app.command(rich_help_panel="Device Management")
def firmware(
    args: list[str] = typer.Argument(None, help="Firmware command: download or update"),
    force: bool = typer.Option(False, "--force", "-f", help="Force update even if already up to date"),
    image: Optional[Path] = typer.Option(None, "--file", help="ESP32-P4 merged MicroPython .bin image"),
    url: Optional[str] = typer.Option(None, "--url", help="Explicit HTTPS ESP32-P4 firmware image URL"),
    flash_port: Optional[str] = typer.Option(None, "--flash-port", help="ESP32-P4 bootloader port (does not require a working REPL)"),
    baud: int = typer.Option(460800, "--baud", help="ESP32-P4 flashing baud rate; use 115200 if unreliable"),
    erase: bool = typer.Option(False, "--erase", help="Erase entire ESP32-P4 flash, including files and settings"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm ESP32-P4 flash write without prompting"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        help_text = """\
Firmware management for ticle devices and ESP32-P4.

[bold cyan]Usage:[/bold cyan] replx firmware [yellow]SUBCOMMAND[/yellow] [[green]options[/green]]

[bold cyan]Subcommands:[/bold cyan]
  [yellow]download[/yellow]        Download firmware to local store
  [yellow]update[/yellow]          Download (if needed) and install firmware

[bold cyan]Options:[/bold cyan]
  [green]-f, --force[/green]     Force reinstall even if version matches
  [green]--file PATH[/green]       ESP32-P4 merged .bin image for update
  [green]--url HTTPS_URL[/green]   Explicit P4 image URL for download or update
  [green]--flash-port PORT[/green] P4 bootloader port; works without a REPL
  [green]--baud N[/green]          P4 flashing speed (default 460800)
  [green]--erase[/green]           P4 full erase, INCLUDING user files/settings
  [green]-y, --yes[/green]        Skip P4 flash write confirmation

[bold cyan]Examples:[/bold cyan]
  replx firmware download       [dim]Download firmware only[/dim]
  replx firmware update         [dim]Download and install[/dim]
  replx firmware update -f      [dim]Force reinstall[/dim]
  replx COM3 firmware download --url https://micropython.org/resources/firmware/IMAGE.bin
  replx COM3 firmware update --file .\\IMAGE.bin
  replx firmware update --flash-port COM3 --file .\\IMAGE.bin --yes

[bold cyan]UF2 Update Process (ticle):[/bold cyan]
  1. Download firmware (if newer version available)
  2. Enter UF2 bootloader mode
  3. Copy .uf2 file to bootloader drive
  4. Device restarts with new firmware
  5. Auto-reconnect to device

[bold cyan]Note:[/bold cyan]
  • UF2: ticle-lite, ticle-sensor; old versions auto-cleaned
  • ESP32P4C6: choose the latest Release or Preview from the official C6 WiFi/BLE builds
  • Other ESP32-P4: select an explicit merged .bin; esptool checks chip/revision
  • Back up files before updating. --erase deletes ALL flash contents.
  • C6 coprocessor firmware is separate and is not flashed through the P4 port."""
        OutputHelper.print_panel(help_text, title="firmware", border_style="help")
        OutputHelper._console.print()
        raise typer.Exit()
    
    if not args:
        OutputHelper.print_panel(
            "Subcommands: [bright_blue]download[/bright_blue]  [bright_blue]update[/bright_blue]\n\n"
            "  [bright_green]replx firmware download[/bright_green]  [dim]# Download only[/dim]\n"
            "  [bright_green]replx firmware update[/bright_green]    [dim]# Download and install[/dim]\n\n"
            "Use [bright_blue]replx firmware --help[/bright_blue] for details.",
            title="Firmware",
            border_style="help"
        )
        raise typer.Exit(1)
    
    cmd = args[0].lower()

    if cmd not in ("download", "update") or len(args) != 1:
        OutputHelper.print_panel(
            "Use firmware download or firmware update; see firmware --help.",
            title="Firmware Error", border_style="error",
        )
        raise typer.Exit(1)

    if image is not None or url is not None or flash_port is not None:
        _firmware_esp32p4(cmd, image, url, flash_port, baud, erase, yes, force=force)
        return
    status = _ensure_connected()
    if normalize_core(status.get('core', '')) == 'ESP32P4':
        _firmware_esp32p4(
            cmd, image, url, flash_port, baud, erase, yes, status=status, force=force
        )
        return
    if erase or yes or baud != 460800:
        OutputHelper.print_panel(
            "--erase, --yes and --baud apply only to ESP32-P4 firmware.",
            title="Firmware Error", border_style="error",
        )
        raise typer.Exit(1)
    
    if cmd == "download":
        _firmware_download()
    elif cmd == "update":
        _firmware_update(force=force)
    else:
        OutputHelper.print_panel(
            f"Unknown command: [red]{cmd}[/red]\n\n"
            "Use: [bright_blue]replx firmware download[/bright_blue] or [bright_blue]replx firmware update[/bright_blue]",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)


def _download_p4_image(url: str) -> Path:
    parsed = urlparse(url)
    name = unquote(parsed.path.rsplit('/', 1)[-1])
    if (parsed.scheme != 'https' or not parsed.netloc
            or not name.startswith('ESP32_GENERIC_P4-') or not name.endswith('.bin')
            or any(ch in name for ch in '/\\:')):
        raise ValueError("Use an HTTPS ESP32_GENERIC_P4-*.bin URL from the official P4 download page.")
    target = _ensure_firmware_dir('esp32p4') / name
    if (
        parsed.netloc.lower() == "micropython.org"
        and parsed.path.startswith("/resources/firmware/")
        and target.is_file()
        and target.stat().st_size > 0
    ):
        return target
    if not _download_firmware('esp32p4', name, url, target):
        raise RuntimeError("ESP32-P4 firmware download failed.")
    return target


def _is_p4_c6_device(status: dict) -> bool:
    return any(
        str(status.get(key) or "").upper().replace("-", "").replace("_", "")
        == "ESP32P4C6"
        for key in ("device", "core")
    )


def _get_p4_c6_firmware_version(image: Optional[Path], url: Optional[str]) -> Optional[str]:
    if url:
        filename = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    elif image:
        filename = image.name
    else:
        return None

    match = _P4_C6_FIRMWARE_FILENAME_RE.fullmatch(filename)
    return match.group(2) if match else None


def _same_firmware_version(current: str, target: str) -> bool:
    return (
        current.strip().removeprefix("v").casefold()
        == target.strip().removeprefix("v").casefold()
    )


def _select_p4_c6_firmware_url() -> str:
    builds = _get_p4_c6_firmware_builds()
    panels = []
    for build_type, title, choice, color in (
        ("release", "Latest Release", "1", "success"),
        ("preview", "Latest Preview Build", "2", "warning"),
    ):
        build = builds[build_type]
        content = Text()
        content.append(f"{build['version']}\n", style="bold")
        content.append(f"Build date: {build['date']}\n")
        content.append(build["filename"], style="dim")
        panels.append(Panel(
            content,
            title=f"{title} ({choice})",
            title_align="left",
            border_style=OutputHelper._resolve_category_color(color),
            box=get_panel_box(),
            expand=True,
        ))

    OutputHelper._console.print(Columns(panels, equal=True, expand=True))
    try:
        choice = Prompt.ask(
            "Select firmware (1=Release, 2=Preview, 0=Cancel)",
            choices=["1", "2", "0"],
            console=OutputHelper._console,
        )
    except EOFError as e:
        raise RuntimeError(
            "Firmware selection requires an interactive terminal; use --url to select an image."
        ) from e

    if choice == "0":
        OutputHelper.print_panel(
            "Firmware selection cancelled.",
            title="Firmware",
            border_style="warning",
        )
        raise typer.Exit()

    build_type = "release" if choice == "1" else "preview"
    return builds[build_type]["download_url"]


def _firmware_esp32p4(cmd: str, image: Optional[Path], url: Optional[str],
                      flash_port: Optional[str], baud: int, erase: bool, yes: bool,
                      status: Optional[dict] = None, force: bool = False) -> None:
    try:
        if image is not None and url is not None:
            raise ValueError("Specify either --file or --url, not both.")
        if cmd == 'download' and (image is not None or erase):
            raise ValueError("firmware download requires --url; --file and --erase are update options.")
        if baud <= 0:
            raise ValueError("--baud must be positive.")
        if not image and not url and status and _is_p4_c6_device(status):
            url = _select_p4_c6_firmware_url()
        if not image and not url:
            raise ValueError(
                "ESP32-P4 requires an explicitly selected firmware image: download --url HTTPS_URL "
                "or update --file IMAGE.bin. Choose C6_WIFI and the correct chip revision "
                "(PRE_REV3 only for early chips). See https://micropython.org/download/ESP32_GENERIC_P4/."
            )
        if cmd == 'update' and not flash_port:
            status = status or _ensure_connected()
            if normalize_core(status.get('core', '')) != 'ESP32P4':
                raise ValueError("This .bin update path supports ESP32-P4 only; RP2 uses UF2.")
        if cmd == 'update' and not force and status and _is_p4_c6_device(status):
            current_version = status.get('version', '')
            target_version = _get_p4_c6_firmware_version(image, url)
            if (
                current_version
                and target_version
                and _same_firmware_version(current_version, target_version)
            ):
                OutputHelper.print_panel(
                    f"Firmware is already up to date.\n\n"
                    f"  Device:   [bright_yellow]ESP32P4C6[/bright_yellow]\n"
                    f"  Current:  [bright_green]v{current_version.removeprefix('v')}[/bright_green]\n"
                    f"  Selected: {target_version}\n\n"
                    "Use [bright_blue]--force[/bright_blue] to reinstall anyway.",
                    title="No Update Needed",
                    border_style="success",
                )
                return
        path = _download_p4_image(url) if url else image
        if path is None or not path.is_file() or path.suffix.lower() != '.bin':
            raise ValueError("Select an existing merged MicroPython ESP32-P4 .bin image.")
        path = path.resolve()
        port = flash_port or (status or {}).get('port')
        if cmd == 'update' and not port:
            raise ValueError("No flash port. Specify --flash-port PORT.")
        with _create_agent_client() as client:
            stage_id = None
            try:
                stage = client.stage_firmware(str(path))
                stage_id = stage["stage_id"]
                inspection = client.firmware_info(stage_id)
                inspection_output = inspection.get("output", "")
                if cmd == 'download':
                    client.discard_firmware(stage_id)
                    stage_id = None
                    OutputHelper.print_panel(
                        f"Firmware image ready and inspected:\n{path}\n"
                        "Image inspection does not check the connected chip revision or C6 coprocessor firmware."
                        + (f"\n\n{inspection_output}" if inspection_output else ""),
                        title="Firmware Ready", border_style="success",
                    )
                    return
                if not yes and not typer.confirm(
                    f"Write {path.name} to ESP32-P4 on {port}? Back up files first."
                    + (" ALL flash contents will be erased." if erase else "")
                ):
                    raise typer.Exit(1)
                result = client.firmware_flash(
                    stage_id, port=port, baud=baud, erase=erase
                )
                stage_id = None
            finally:
                if stage_id:
                    try:
                        client.discard_firmware(stage_id)
                    except (OSError, RuntimeError, ValueError) as cleanup_error:
                        OutputHelper._console.print(
                            f"Could not remove staged firmware: {cleanup_error}",
                            style="yellow",
                        )

        OutputHelper.print_panel(
            "ESP32-P4 firmware written and verified by esptool.\n"
            "Reconnect the MicroPython REPL (the native USB port number may change).\n"
            "This does not update the separate C6 coprocessor firmware.",
            title="Firmware Written", border_style="success",
        )
    except typer.Exit:
        raise
    except (ValueError, RuntimeError, OSError) as exc:
        OutputHelper.print_panel(str(exc), title="Firmware Error", border_style="error")
        raise typer.Exit(1) from exc


def _firmware_download():
    status = _ensure_connected()
    
    device = status.get('device', '').lower()
    if not device:
        OutputHelper.print_panel(
            "Could not determine device type from connected board.",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    if device not in SUPPORTED_FIRMWARE_DEVICES:
        OutputHelper.print_panel(
            f"Device [yellow]{device}[/yellow] is not supported for firmware management.\n\n"
            f"Supported devices: {', '.join(sorted(SUPPORTED_FIRMWARE_DEVICES))}",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    current_version = status.get('version', 'unknown')
    
    console = OutputHelper.make_console()
    spinner = Spinner("dots", text=Text(" Checking for firmware updates...", style="bright_cyan"))
    
    try:
        with Live(spinner, console=console, refresh_per_second=10, transient=True):
            remote_info = _get_remote_firmware_info(device)
    except FirmwareLookupError as e:
        OutputHelper.print_panel(
            f"Failed to check firmware repository.\n\n{e}",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    if not remote_info:
        OutputHelper.print_panel(
            f"Could not find firmware for [yellow]{device}[/yellow] in remote repository.",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    remote_version = remote_info['version']
    download_url = remote_info['download_url']
    
    local_versions = _get_local_firmware_versions(device)
    local_latest = local_versions[0][0] if local_versions else None
    
    if local_latest and _parse_version(local_latest) >= _parse_version(remote_version):
        firmware_path = _get_firmware_local_dir(device) / f"{device}_v{local_latest}.uf2"
        OutputHelper.print_panel(
            f"Firmware is already up to date.\n\n"
            f"  Device:      [bright_yellow]{device}[/bright_yellow]\n"
            f"  Current:     [bright_cyan]v{current_version}[/bright_cyan]\n"
            f"  Local:       [bright_green]v{local_latest}[/bright_green]\n"
            f"  Remote:      v{remote_version}\n\n"
            f"  File: [dim]{firmware_path}[/dim]",
            title="Firmware Up to Date",
            border_style="success"
        )
        return
    
    firmware_dir = _ensure_firmware_dir(device)
    target_path = firmware_dir / f"{device}_v{remote_version}.uf2"
    
    if _download_firmware(device, remote_version, download_url, target_path):
        _cleanup_old_firmware(device, remote_version)
        
        OutputHelper.print_panel(
            f"Firmware downloaded successfully.\n\n"
            f"  Device:      [bright_yellow]{device}[/bright_yellow]\n"
            f"  Version:     [bright_green]v{remote_version}[/bright_green]\n"
            f"  Current:     [dim]v{current_version}[/dim]\n\n"
            "To install, run: [bright_blue]replx firmware update[/bright_blue]",
            title="Firmware Downloaded",
            border_style="success"
        )
    else:
        raise typer.Exit(1)


def _firmware_update(force: bool = False):
    status = _ensure_connected()
    
    device = status.get('device', '').lower()
    port = status.get('port', '')
    core = status.get('core', '')
    
    if not device:
        OutputHelper.print_panel(
            "Could not determine device type from connected board.",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    if device not in SUPPORTED_FIRMWARE_DEVICES:
        OutputHelper.print_panel(
            f"Device [yellow]{device}[/yellow] is not supported for firmware management.\n\n"
            f"Supported devices: {', '.join(sorted(SUPPORTED_FIRMWARE_DEVICES))}",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    if core and not core.startswith("RP2"):
        OutputHelper.print_panel(
            f"Device core [yellow]{core}[/yellow] does not support UF2 firmware updates.\n\n"
            "UF2 updates are only supported for RP2040/RP2350 devices.",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    current_version = status.get('version', 'unknown')
    
    spinner = Spinner("dots", text=Text(" Checking for firmware updates...", style="bright_cyan"))
    try:
        with Live(spinner, console=OutputHelper._console, refresh_per_second=10, transient=True):
            remote_info = _get_remote_firmware_info(device)
    except FirmwareLookupError as e:
        OutputHelper.print_panel(
            f"Failed to check firmware repository.\n\n{e}",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    if not remote_info:
        OutputHelper.print_panel(
            f"Could not find firmware for [yellow]{device}[/yellow] in remote repository.",
            title="Firmware Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    remote_version = remote_info['version']
    download_url = remote_info['download_url']
    
    local_versions = _get_local_firmware_versions(device)
    local_latest = local_versions[0][0] if local_versions else None
    firmware_path = None
    
    if local_latest and _parse_version(local_latest) >= _parse_version(remote_version):
        firmware_path = _get_firmware_local_dir(device) / f"{device}_v{local_latest}.uf2"
        target_version = local_latest
    else:
        firmware_dir = _ensure_firmware_dir(device)
        firmware_path = firmware_dir / f"{device}_v{remote_version}.uf2"
        
        if not _download_firmware(device, remote_version, download_url, firmware_path):
            raise typer.Exit(1)
        
        _cleanup_old_firmware(device, remote_version)
        target_version = remote_version
    
    if not force and _parse_version(current_version) >= _parse_version(target_version):
        OutputHelper.print_panel(
            f"Firmware is already up to date.\n\n"
            f"  Device:      [bright_yellow]{device}[/bright_yellow]\n"
            f"  Current:     [bright_green]v{current_version}[/bright_green]\n"
            f"  Available:   v{target_version}\n\n"
            "Use [bright_blue]--force[/bright_blue] to reinstall anyway.",
            title="No Update Needed",
            border_style="success"
        )
        return
    
    spinner = Spinner("dots", style="bright_cyan")
    
    def make_update_panel(step: str, progress: float = None, detail: str = None, use_spinner: bool = True, 
                          complete: bool = False, success: bool = True, final_version: str = None):
        from rich.table import Table
        from rich.console import Group
        
        info_text = Text()
        info_text.append(f"  Device:      ")
        info_text.append(f"{device}", style="bright_yellow")
        info_text.append(f"\n  Current:     ")
        info_text.append(f"v{current_version}", style="dim")
        info_text.append(f"\n  Target:      ")
        info_text.append(f"v{target_version}", style="bright_green")
        
        separator = Text("\n")
        
        if complete:
            status_display = Text()
            status_display.append("  ")
            if success:
                status_display.append("✓", style="bright_green")
                status_display.append(" Firmware update complete!")
                if final_version and final_version != current_version:
                    status_display.append(f"\n  New version: ")
                    status_display.append(f"v{final_version}", style="bright_green")
            else:
                status_display.append("!", style="yellow")
                status_display.append(" Firmware installed but auto-reconnect failed.")
                status_display.append(f"\n  Please reconnect: ")
                status_display.append(f"replx --port {port} setup", style="bright_blue")
            
            content = Group(info_text, separator, status_display)
            border_style = "data"
        elif progress is not None:
            bar_width = 50
            filled = int(bar_width * progress)
            bar_filled = "█" * filled
            bar_empty = "░" * (bar_width - filled)
            pct = int(progress * 100)
            
            progress_text = Text()
            progress_text.append(f"  [")
            progress_text.append(bar_filled, style="green")
            progress_text.append(bar_empty, style="dim")
            progress_text.append(f"] {pct}%")
            if detail:
                progress_text.append(f" {detail}", style="dim")
            
            content = Group(info_text, separator, progress_text)
            border_style = "data"
        elif use_spinner:
            step_table = Table.grid(padding=(0, 1))
            step_table.add_column(width=3)
            step_table.add_column()
            step_table.add_row(spinner, Text(step, style="default"))
            
            content = Group(info_text, separator, step_table)
            border_style = "data"
        else:
            step_text = Text()
            step_text.append(f"  ")
            step_text.append("●", style="bright_cyan")
            step_text.append(f" {step}")
            content = Group(info_text, separator, step_text)
            border_style = "data"
        
        return Panel(
            content,
            title="Firmware Update",
            title_align="left",
            border_style=OutputHelper._resolve_category_color(border_style),
            box=get_panel_box(),
            width=CONSOLE_WIDTH
        )
    
    reconnected = False
    new_version = None
    was_foreground = False
    
    from rich.text import Text as RichText
    with Live(RichText(""), console=OutputHelper._console, refresh_per_second=10, transient=False) as live:
        live.update(make_update_panel("Preparing device for firmware update..."))
        try:
            with _create_agent_client() as client:
                result = client.send_command('session_info', timeout=2.0)
                was_foreground = result.get('is_foreground', False)
        except Exception:
            was_foreground = False
        
        live.update(make_update_panel("Entering bootloader mode..."))
        try:
            with _create_agent_client() as client:
                client.send_command('exec', code='import machine; machine.bootloader()', timeout=1.0)
        except Exception:
            pass
        
        time.sleep(0.3)
        try:
            with _create_agent_client() as client:
                client.send_command('disconnect_port', port=port, timeout=2.0)
        except Exception:
            pass
        
        time.sleep(1.0)
        
        live.update(make_update_panel("Waiting for bootloader drive..."))
        uf2_drive = _wait_for_uf2_drive(timeout=15, live=live)
        
        if not uf2_drive:
            live.stop()
            OutputHelper.print_panel(
                "Bootloader drive not found.\n\n"
                "Please manually:\n"
                "  1. Hold BOOTSEL button and press RESET\n"
                "  2. Copy the UF2 file to the drive\n\n"
                f"  File: [dim]{firmware_path}[/dim]",
                title="Manual Installation Required",
                border_style="warning"
            )
            raise typer.Exit(1)
        
        import platform
        try:
            target_uf2 = uf2_drive / f"{device}.uf2"
            file_size = firmware_path.stat().st_size
            copied = 0
            chunk_size = 64 * 1024 
            
            with open(firmware_path, 'rb') as src, open(target_uf2, 'wb') as dst:
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    dst.write(chunk)
                    copied += len(chunk)
                    progress = copied / file_size
                    live.update(make_update_panel(
                        "Copying firmware...",
                        progress=progress,
                        detail=f"{OutputHelper.format_bytes(copied)} / {OutputHelper.format_bytes(file_size)}"
                    ))
                dst.flush()
                os.fsync(dst.fileno())
            
            if platform.system() == "Darwin":
                try:
                    os.sync()
                except (AttributeError, OSError):
                    pass
                time.sleep(1.5)
            elif platform.system() == "Linux":
                try:
                    os.sync()
                except (AttributeError, OSError):
                    pass
                time.sleep(1.0)
            else:
                time.sleep(1.0)
            
        except Exception as e:
            live.stop()
            OutputHelper.print_panel(
                f"Failed to copy firmware: {str(e)}\n\n"
                f"Please manually copy:\n"
                f"  From: [dim]{firmware_path}[/dim]\n"
                f"  To:   [dim]{uf2_drive}[/dim]",
                title="Copy Failed",
                border_style="error"
            )
            raise typer.Exit(1)
        
        live.update(make_update_panel("Waiting for device to restart..."))
        time.sleep(3.0)
        
        live.update(make_update_panel("Reconnecting..."))
        time.sleep(1.0)
        
        for attempt in range(20):
            try:
                time.sleep(0.5)
                with _create_agent_client() as client:
                    result = client.send_command(
                        'session_setup',
                        port=port,
                        core=core,
                        device=device,
                        as_foreground=was_foreground,
                        timeout=2.0
                    )
                    if result.get('connected'):
                        reconnected = True
                        new_version = result.get('version', 'unknown')
                        break
            except Exception:
                continue
        
        if not reconnected:
            try:
                _ensure_connected()
                with _create_agent_client() as client:
                    new_status = client.send_command('status', timeout=2.0)
                    new_version = new_status.get('version', 'unknown')
                reconnected = True
            except Exception:
                pass
        
        live.update(make_update_panel(
            "", complete=True, success=reconnected, final_version=new_version
        ))
