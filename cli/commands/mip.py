import os
import json
import time
import shutil
import hashlib
import threading
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Optional

import typer
from rich.live import Live

from ..helpers import (
    OutputHelper, StoreManager, CompilerHelper,
    get_panel_box, CONSOLE_WIDTH
)
from replx.utils.constants import HTTP_REQUEST_TIMEOUT
from ..config import STATE
from ..connection import (
    _ensure_connected, _create_agent_client
)
from ..app import app
from replx.utils.device_info import normalize_core


_MIP_INDEX_URL = "https://micropython.org/pi/v2"
_MIP_INDEX_TTL = 3600  # 1 hour

_MIP_MPY_ARCH_CODES = {
    1: "x86", 2: "x64", 3: "armv6", 4: "armv6m",
    5: "armv7m", 6: "armv7em", 7: "armv7emsp", 8: "armv7emdp",
    9: "xtensa", 10: "xtensawin", 11: "rv32imc", 12: "rv64imc",
}


def _mip_root() -> Path:
    root = StoreManager.HOME_STORE / "mip"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _mip_staging() -> Path:
    staging = StoreManager.HOME_STAGING / "mip"
    staging.mkdir(parents=True, exist_ok=True)
    return staging


def _load_mip_index(index_url: str) -> tuple[dict, bool]:
    """Returns (index_data, is_from_cache)."""
    cache_path = _mip_root() / "index_cache.json"
    now = time.time()

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if now - cached.get("_cached_at", 0) < _MIP_INDEX_TTL:
                return cached, True
        except Exception:
            pass

    try:
        req = urllib.request.Request(
            f"{index_url}/index.json",
            headers={"User-Agent": "replx"}
        )
        with urllib.request.urlopen(req, timeout=HTTP_REQUEST_TIMEOUT) as r:
            data = json.load(r)
        data["_cached_at"] = now
        tmp = str(cache_path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, str(cache_path))
        return data, False
    except Exception:
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f), True
            except Exception:
                pass
        raise


def _load_mip_meta() -> dict:
    p = _mip_root() / "mip_meta.json"
    if not p.exists():
        return {"packages": {}}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"packages": {}}


def _save_mip_meta(meta: dict):
    p = _mip_root() / "mip_meta.json"
    tmp = str(p) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    os.replace(tmp, str(p))


def _rewrite_github_url(spec: str, branch: str = "HEAD") -> str:
    """github:org/repo[/path] → https://raw.githubusercontent.com/org/repo/HEAD/[path]"""
    org, repo, path, ref = _parse_github_spec(spec, None if branch == "HEAD" else branch)
    base = f"https://raw.githubusercontent.com/{org}/{repo}/{ref or 'HEAD'}"
    return f"{base}/{path}" if path else base


def _parse_github_spec(spec: str, version: Optional[str] = None) -> tuple[str, str, str, str]:
    """Return (org, repo, path, ref) for github:org/repo[@ref][/path]."""
    if not spec.startswith("github:"):
        raise typer.BadParameter(f"Invalid github spec: {spec}")
    parts = spec[7:].split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise typer.BadParameter(f"Invalid github spec (expected github:org/repo): {spec}")
    org, repo = parts[0], parts[1]
    ref = version or ""
    if "@" in repo and not version:
        repo, ref = repo.rsplit("@", 1)
    if not repo or ref == "":
        if "@" in parts[1]:
            raise typer.BadParameter(f"Invalid github ref in spec: {spec}")
    path = "/".join(p for p in parts[2:] if p)
    return org, repo, path, ref


def _github_contents_api_url(org: str, repo: str, path: str = "", ref: str = "") -> str:
    encoded = "/".join(urllib.parse.quote(p, safe="") for p in path.split("/") if p)
    url = f"https://api.github.com/repos/{org}/{repo}/contents"
    if encoded:
        url = f"{url}/{encoded}"
    if ref:
        url = f"{url}?ref={urllib.parse.quote(ref, safe='')}"
    return url


def _fetch_github_contents(org: str, repo: str, path: str = "", ref: str = ""):
    api_url = _github_contents_api_url(org, repo, path, ref)
    try:
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "replx", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_REQUEST_TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise typer.BadParameter(f"HTTP {e.status}: {api_url}")
    except Exception as e:
        raise typer.BadParameter(f"GitHub API error for {api_url}: {e}")


def _fetch_json(url: str) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "replx"})
        with urllib.request.urlopen(req, timeout=HTTP_REQUEST_TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise typer.BadParameter(f"HTTP {e.status}: {url}")
    except Exception as e:
        raise typer.BadParameter(f"Failed to fetch {url}: {e}")


def _download_bytes(url: str) -> bytes:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "replx"})
        with urllib.request.urlopen(req, timeout=HTTP_REQUEST_TIMEOUT) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise typer.BadParameter(f"HTTP {e.status}: {url}")
    except Exception as e:
        raise typer.BadParameter(f"Download failed for {url}: {e}")


def _write_file(dest_path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    tmp = dest_path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest_path)


def _collect_github_source_path_files(
    target: str,
    version: Optional[str],
    staging_files_dir: Path,
) -> list[tuple[str, str]] | None:
    org, repo, source_path, ref = _parse_github_spec(target, version)
    if not source_path:
        return _collect_github_python_project_files(org, repo, ref, staging_files_dir)

    try:
        item = _fetch_github_contents(org, repo, source_path, ref)
    except typer.BadParameter as e:
        if "HTTP 404" in str(e):
            return None
        raise

    if isinstance(item, dict):
        if item.get("type") != "file" or not item.get("name", "").endswith((".py", ".mpy")):
            return None
        dest_rel = item["name"]
        local_path = str(staging_files_dir / dest_rel)
        _write_file(local_path, _download_bytes(item["download_url"]))
        return [(local_path, dest_rel)]

    if not isinstance(item, list):
        return None

    root_has_init = any(
        child.get("type") == "file" and child.get("name") == "__init__.py"
        for child in item
    )
    dest_root = source_path.rstrip("/").rsplit("/", 1)[-1] if root_has_init else ""
    return _collect_github_directory_files(
        org, repo, source_path, ref, staging_files_dir, source_path, dest_root
    )


def _collect_github_python_project_files(
    org: str,
    repo: str,
    ref: str,
    staging_files_dir: Path,
) -> list[tuple[str, str]] | None:
    try:
        root_items = _fetch_github_contents(org, repo, "", ref)
    except typer.BadParameter:
        return None
    if not isinstance(root_items, list):
        return None

    root_names = {item.get("name") for item in root_items}
    if "pyproject.toml" in root_names and "src" in root_names:
        src_items = _fetch_github_contents(org, repo, "src", ref)
        if isinstance(src_items, list):
            package_dirs = []
            for item in src_items:
                if item.get("type") != "dir":
                    continue
                package_path = item.get("path", "")
                package_items = _fetch_github_contents(org, repo, package_path, ref)
                if isinstance(package_items, list) and any(
                    child.get("type") == "file" and child.get("name") == "__init__.py"
                    for child in package_items
                ):
                    package_dirs.append(package_path)
            if len(package_dirs) == 1:
                package_path = package_dirs[0]
                package_name = package_path.rstrip("/").rsplit("/", 1)[-1]
                return _collect_github_directory_files(
                    org, repo, package_path, ref, staging_files_dir, package_path, package_name
                )

    return None


def _collect_github_directory_files(
    org: str,
    repo: str,
    current_path: str,
    ref: str,
    staging_files_dir: Path,
    source_root: str,
    dest_root: str = "",
) -> list[tuple[str, str]]:
    items = _fetch_github_contents(org, repo, current_path, ref)
    if not isinstance(items, list):
        return []

    result: list[tuple[str, str]] = []
    for item in sorted(items, key=lambda x: (x.get("type") != "dir", x.get("name", ""))):
        name = item.get("name", "")
        item_path = item.get("path", "")
        if item.get("type") == "dir":
            if name.startswith(".") or name == "__pycache__":
                continue
            result.extend(
                _collect_github_directory_files(
                    org, repo, item_path, ref, staging_files_dir, source_root, dest_root
                )
            )
            continue
        if item.get("type") != "file" or not name.endswith((".py", ".mpy")):
            continue
        rel = item_path[len(source_root):].lstrip("/") if source_root else item_path
        dest_rel = f"{dest_root}/{rel}" if dest_root else rel
        dest_rel = dest_rel.replace("\\", "/")
        local_path = str(staging_files_dir / dest_rel.replace("/", os.sep))
        _write_file(local_path, _download_bytes(item["download_url"]))
        result.append((local_path, dest_rel))
    return result


def _get_mpy_abi_from_state() -> str:
    """Derive the mpy ABI version number from the connected board's firmware version.

    Returns e.g. '6' for MicroPython 1.23+, or 'py' (source-only) if unknown.
    """
    version = STATE.version
    if not version or version == "?":
        return "py"
    try:
        parts = version.split(".")
        major, minor = int(parts[0]), int(parts[1])
        if (major, minor) >= (1, 23):
            return "6"
        if (major, minor) >= (1, 20):
            return "5"
    except Exception:
        pass
    return "py"


def _get_board_mpy_arch(client) -> tuple[str, str] | None:
    """Execute sys.implementation._mpy on the board to get (arch_name, abi_str).

    Returns e.g. ('armv7emsp', '6.3'), or None if unavailable.
    """
    try:
        result = client.send_command(
            'exec',
            code="import sys; print(getattr(sys.implementation, '_mpy', 0))"
        )
        out = ""
        if isinstance(result, dict):
            out = result.get("output", "") or result.get("result", "") or ""
        elif isinstance(result, str):
            out = result
        mpy_val = int(out.strip().splitlines()[-1])
        if not mpy_val:
            return None
        # _mpy encoding: low byte = MPY_VERSION, high byte = (arch<<2)|sub_version
        abi = mpy_val & 0xFF
        feature_byte = (mpy_val >> 8) & 0xFF
        arch_code = (feature_byte >> 2) & 0x3F
        sub_version = feature_byte & 0x3
        arch_name = _MIP_MPY_ARCH_CODES.get(arch_code)
        if not arch_name:
            return None
        abi_str = f"{abi}.{sub_version}" if sub_version else str(abi)
        return arch_name, abi_str
    except Exception:
        return None


def _collect_github_pages_files(
    org: str,
    repo: str,
    arch: str,
    abi_str: str,
    staging_files_dir: Path,
) -> list[tuple[str, str]] | None:
    suffixes = [abi_str]
    if "." in abi_str:
        suffixes.append(abi_str.split(".")[0])

    for suffix in suffixes:
        abi_dir = f"{arch}_{suffix}"
        api_url = (
            f"https://api.github.com/repos/{org}/{repo}/contents"
            f"/builds/latest/{abi_dir}?ref=gh-pages"
        )
        try:
            req = urllib.request.Request(
                api_url,
                headers={"User-Agent": "replx", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=HTTP_REQUEST_TIMEOUT) as r:
                items = json.load(r)
        except urllib.error.HTTPError as e:
            if e.status == 404:
                continue
            return None
        except Exception:
            return None

        mpy_items = [
            item for item in items
            if item.get("type") == "file" and item["name"].endswith(".mpy")
        ]
        if not mpy_items:
            continue

        result = []
        for item in sorted(mpy_items, key=lambda x: x["name"]):
            local_path = str(staging_files_dir / item["name"])
            _write_file(local_path, _download_bytes(item["download_url"]))
            result.append((local_path, item["name"]))
        return result

    return None


def _package_json_url(target: str, version: Optional[str], index_url: str, mpy_abi: str = "py") -> tuple[str, str]:
    if target.startswith("github:"):
        base = _rewrite_github_url(target, version or "HEAD")
        pkg_url = f"{base}/package.json"
        return pkg_url, base
    if target.startswith(("http://", "https://")):
        if target.endswith(".json"):
            return target, target.rpartition("/")[0]
        pkg_url = target.rstrip("/") + "/package.json"
        return pkg_url, target.rstrip("/")

    ver = version or "latest"
    pkg_url = f"{index_url}/package/{mpy_abi}/{target}/{ver}.json"
    return pkg_url, index_url


def _collect_install_files(
    target: str,
    version: Optional[str],
    index_url: str,
    staging_files_dir: Path,
    visited: Optional[set] = None,
    mpy_abi: str = "py",
) -> list[tuple[str, str]]:
    """Recursively collect (abs_local_path, dest_rel_path) for all package files.

    Processes both `hashes` (pre-compiled .mpy from CDN) and `urls` (.py source).
    When mpy_abi is 'py', only `urls` are available (source-only path).
    """
    if visited is None:
        visited = set()

    visit_key = f"{target}@{version or 'latest'}"
    if visit_key in visited:
        return []
    visited.add(visit_key)

    if target.startswith(("http://", "https://")) and target.endswith((".py", ".mpy")):
        filename = target.rsplit("/", 1)[-1]
        local_path = str(staging_files_dir / filename)
        _write_file(local_path, _download_bytes(target))
        return [(local_path, filename)]

    if target.startswith("github:"):
        _, _, github_path, _ = _parse_github_spec(target, version)
        if github_path.endswith((".py", ".mpy")):
            files = _collect_github_source_path_files(target, version, staging_files_dir)
            if files:
                return files

    pkg_json_url, base_url = _package_json_url(target, version, index_url, mpy_abi)
    try:
        pkg_json = _fetch_json(pkg_json_url)
    except typer.BadParameter as e:
        if target.startswith("github:") and "HTTP 404" in str(e):
            files = _collect_github_source_path_files(target, version, staging_files_dir)
            if files:
                return files
        raise

    result: list[tuple[str, str]] = []

    for dest_rel, short_hash in pkg_json.get("hashes", []):
        dest_rel = dest_rel.replace("\\", "/")
        file_url = f"{index_url}/file/{short_hash[:2]}/{short_hash}"
        local_path = str(staging_files_dir / dest_rel.replace("/", os.sep))
        _write_file(local_path, _download_bytes(file_url))
        result.append((local_path, dest_rel))

    for dest_rel, file_url in pkg_json.get("urls", []):
        dest_rel = dest_rel.replace("\\", "/")
        if not file_url.startswith(("http://", "https://")):
            file_url = f"{base_url}/{file_url}"
        local_path = str(staging_files_dir / dest_rel.replace("/", os.sep))
        _write_file(local_path, _download_bytes(file_url))
        result.append((local_path, dest_rel))

    for dep_name, dep_version in pkg_json.get("deps", []):
        sub = _collect_install_files(dep_name, dep_version or None, index_url, staging_files_dir, visited, mpy_abi)
        result.extend(sub)

    return result


def _ensure_remote_dirs(paths: set[str], client) -> None:
    all_paths: set[str] = set()
    for path in paths:
        parts = [p for p in path.replace("\\", "/").strip("/").split("/") if p]
        cur = ""
        for p in parts:
            cur = f"{cur}/{p}"
            all_paths.add(cur)
    for p in sorted(all_paths):
        try:
            client.send_command('mkdir', path=p)
        except Exception:
            pass


def _upload_file_with_progress(client, local_path: str, remote_path: str, progress_callback):
    return client.send_command_streaming(
        'put_from_local_streaming',
        progress_callback=progress_callback,
        local_path=local_path,
        remote_path=remote_path,
    )


@app.command(name="mip", rich_help_panel="Package Management")
def mip(
    args: list[str] = typer.Argument(None, help="Subcommand and arguments"),
    device: str = typer.Option("lib", "--device", "-d", help="Board target path (for install)"),
    index: str = typer.Option(_MIP_INDEX_URL, "--index", help="Package index URL"),
    no_compile: bool = typer.Option(False, "--no-compile", help="Skip .mpy compilation, upload .py as-is"),
    source: str = typer.Option(None, "--source", "-s", help="Base URL; filenames in ARGS are appended to it"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True),
):
    if show_help:
        help_text = """\
MicroPython community package manager (micropython.org/pi/v2).

[bold cyan]Usage:[/bold cyan] replx mip [yellow]SUBCOMMAND[/yellow] [args]

[bold cyan]Subcommands:[/bold cyan]
  [yellow]search[/yellow]  [dim][QUERY | github:org/repo][/dim]   Search packages by name or description
  [yellow]install[/yellow] [green]TARGET[@version][/green] [dim][OPTS][/dim]               Download, compile, and install to device

[bold cyan]Install Targets:[/bold cyan]
  [green]requests[/green]                     Install latest version by name
  [green]requests@0.10.0[/green]              Install specific version
  [green]github:org/repo[/green]              Install from GitHub repo root
  [green]github:org/repo/path[/green]         Install from GitHub repo sub-path
  [green]github:org/repo/path/foo.py[/green]  Install a single GitHub source file
  [green]github:org/repo/src/package[/green]  Install a GitHub source package directory

[bold cyan]Install Options:[/bold cyan]
  [bright_blue]--device PATH[/bright_blue]                Board target path [dim](default: lib → /lib/)[/dim]
  [bright_blue]--no-compile[/bright_blue]                 Skip .mpy compilation, upload .py directly
  [bright_blue]--index URL[/bright_blue]                  Custom package index
  [bright_blue]--source/-s URL[/bright_blue]              Base URL; remaining args are filenames appended to it

[bold cyan]Examples:[/bold cyan]
  replx mip search                                           [dim]List all packages[/dim]
  replx mip search mqtt                                      [dim]Search by name[/dim]
  replx mip search github:micropython/micropython-lib
  replx mip install requests                                 [dim]→ /lib/[/dim]
  replx mip install requests@0.10.0                          [dim]→ /lib/[/dim]
  replx mip install aioble                                   [dim]→ /lib/aioble/[/dim]
  replx mip install github:org/repo                          [dim]→ /lib/[/dim]
  replx mip install --device /lib/ext umqtt.simple
  replx mip install --no-compile logging                     [dim]→ /lib/logging.py[/dim]
  replx mip install --source https://host/path/ a.mpy b.mpy  [dim]→ /lib/[/dim]

[bold cyan]Note:[/bold cyan]
  • All downloads happen on PC — board WiFi is not required
  • .py files are compiled to .mpy using mpy-cross before upload
  • Dependencies (deps field) are installed automatically"""
        OutputHelper.print_panel(help_text, title="mip", border_style="help")
        OutputHelper._console.print()
        raise typer.Exit()

    if not args:
        OutputHelper.print_panel(
            "Subcommands: [bright_blue]search[/bright_blue]  [bright_blue]install[/bright_blue]\n\n"
            "  [bright_green]replx mip search[/bright_green]                [dim]# List all community packages[/dim]\n"
            "  [bright_green]replx mip install requests[/bright_green]      [dim]# Install to /lib/[/dim]\n"
            "  [bright_green]replx mip install github:org/repo[/bright_green]  [dim]# Install from GitHub[/dim]\n\n"
            "Use [bright_blue]replx mip --help[/bright_blue] for details.",
            title="MicroPython Package Manager",
            border_style="help",
        )
        raise typer.Exit(1)

    cmd = args[0].lower()
    cmd_args = args[1:] if len(args) > 1 else []

    if cmd == "search":
        _mip_search(cmd_args, index)
    elif cmd == "install":
        _mip_install(cmd_args, device, index, no_compile, source_base=source)
    else:
        OutputHelper.print_panel(
            f"Unknown subcommand: [red]{cmd}[/red]\n\n"
            "Available: [bright_blue]search[/bright_blue], [bright_blue]install[/bright_blue]",
            title="mip Error",
            border_style="error",
        )
        raise typer.Exit(1)


def _mip_search(args: list[str], index_url: str):
    query = args[0] if args else None

    if query and query.startswith("github:"):
        _mip_search_github(query)
        return

    try:
        index_data, from_cache = _load_mip_index(index_url)
    except Exception as e:
        OutputHelper.print_panel(
            f"Failed to load package index: [red]{e}[/red]",
            title="Search Error",
            border_style="error",
        )
        raise typer.Exit(1)

    packages = index_data.get("packages", [])

    if query:
        q = query.lower()
        packages = [
            p for p in packages
            if q in p.get("name", "").lower() or q in p.get("description", "").lower()
        ]

    if not packages:
        OutputHelper.print_panel(
            f"No packages found{f' for [yellow]{query}[/yellow]' if query else ''}.",
            title="Search Results",
            border_style="warning",
        )
        return

    def _category(path: str) -> str:
        if not path:
            return ""
        top = path.split("/")[0]
        if top == "python-stdlib":
            return "stdlib"
        if top == "python-ecosys":
            return "ecosys"
        if top == "micropython":
            return "upy"
        return top[:8]

    sorted_pkgs = sorted(packages, key=lambda x: x.get("name", "").lower())

    w_name = max(4, max(len(p.get("name", "")) for p in sorted_pkgs))
    w_ver  = max(3, max(len(p.get("version", "")) for p in sorted_pkgs))
    w_cat  = max(3, max(len(_category(p.get("path", ""))) for p in sorted_pkgs))

    lines = []
    lines.append(
        f"{'NAME'.ljust(w_name)}   {'VER'.ljust(w_ver)}   {'CAT'.ljust(w_cat)}   DESCRIPTION"
    )
    lines.append("─" * (80 - 4))

    for p in sorted_pkgs:
        name = p.get("name", "")
        ver  = p.get("version", "")
        cat  = _category(p.get("path", ""))
        desc = p.get("description", "") or ""
        if len(desc) > 45:
            desc = desc[:42] + "..."
        lines.append(
            f"[bright_cyan]{name.ljust(w_name)}[/bright_cyan]"
            f"   [dim]{ver.ljust(w_ver)}[/dim]"
            f"   [dim]{cat.ljust(w_cat)}[/dim]"
            f"   {desc}"
        )

    cache_note = " [dim][cached][/dim]" if from_cache else ""
    count_note = f"[dim]{len(sorted_pkgs)} package(s)[/dim]"
    title = f"Search: {query}  {count_note}{cache_note}" if query else f"MicroPython Packages  {count_note}{cache_note}"

    OutputHelper.print_panel("\n".join(lines), title=title, border_style="mode")


def _mip_search_github(spec: str):
    try:
        base = _rewrite_github_url(spec)
    except Exception as e:
        OutputHelper.print_panel(str(e), title="mip search Error", border_style="error")
        raise typer.Exit(1)

    pkg_json_url = f"{base}/package.json"
    try:
        pkg_json = _fetch_json(pkg_json_url)
    except typer.BadParameter:
        org, repo, sub_path, ref = _parse_github_spec(spec)
        _mip_search_github_contents(spec, org, repo, sub_path, ref)
        return

    urls = pkg_json.get("urls", [])
    deps = pkg_json.get("deps", [])

    lines = [f"[dim]Source:[/dim] {pkg_json_url}", ""]
    if urls:
        lines.append("[bold]Files:[/bold]")
        for dest, src in urls:
            lines.append(f"  [bright_cyan]{dest}[/bright_cyan]   [dim]{src}[/dim]")
    if deps:
        lines.append("")
        lines.append("[bold]Dependencies:[/bold]")
        for dep_name, dep_ver in deps:
            lines.append(f"  [bright_cyan]{dep_name}[/bright_cyan]   [dim]@{dep_ver}[/dim]")
    if not urls and not deps:
        lines.append("[dim]No files or dependencies listed.[/dim]")

    OutputHelper.print_panel("\n".join(lines), title=f"GitHub: {spec}", border_style="mode")


def _mip_search_github_contents(spec: str, org: str, repo: str, sub_path: str, ref: str = ""):
    try:
        items = _fetch_github_contents(org, repo, sub_path, ref)
    except typer.BadParameter as e:
        OutputHelper.print_panel(
            f"Repository not found or inaccessible: [red]{e}[/red]",
            title="GitHub Error",
            border_style="error",
        )
        raise typer.Exit(1)

    repo_ref = f"{repo}@{ref}" if ref else repo
    prefix = f"{org}/{repo_ref}" + (f"/{sub_path}" if sub_path else "")

    if isinstance(items, dict):
        name = items.get("name", "")
        if items.get("type") == "file" and name.endswith((".py", ".mpy")):
            lines = [
                "[dim]No package.json found — showing repository file[/dim]",
                "",
                f"[bold]File[/bold]   [dim]replx mip install github:{prefix}[/dim]",
                f"  [bright_cyan]{items.get('path', name)}[/bright_cyan]",
            ]
            OutputHelper.print_panel("\n".join(lines), title=f"GitHub: {spec}", border_style="data")
            return
        OutputHelper.print_panel(
            f"No installable Python source found at [yellow]{spec}[/yellow].",
            title=f"GitHub: {spec}",
            border_style="warning",
        )
        return

    dirs = sorted(item["name"] for item in items if item["type"] == "dir")
    py_files = sorted(item["path"] for item in items if item["type"] == "file" and item["name"].endswith(".py"))

    lines = [f"[dim]No package.json found — showing repository contents[/dim]", ""]

    package_dirs: list[str] = []
    root_names = {item.get("name") for item in items}
    if not sub_path and "pyproject.toml" in root_names and "src" in root_names:
        src_items = _fetch_github_contents(org, repo, "src", ref)
        if isinstance(src_items, list):
            for item in src_items:
                if item.get("type") != "dir":
                    continue
                package_path = item.get("path", "")
                package_items = _fetch_github_contents(org, repo, package_path, ref)
                if isinstance(package_items, list) and any(
                    child.get("type") == "file" and child.get("name") == "__init__.py"
                    for child in package_items
                ):
                    package_dirs.append(package_path)
    elif dirs:
        for d in dirs:
            package_path = f"{sub_path}/{d}" if sub_path else d
            try:
                package_items = _fetch_github_contents(org, repo, package_path, ref)
            except typer.BadParameter:
                continue
            if isinstance(package_items, list) and any(
                child.get("type") == "file" and child.get("name") == "__init__.py"
                for child in package_items
            ):
                package_dirs.append(package_path)

    if package_dirs:
        lines.append("[bold]Detected Python package[/bold]")
        if not sub_path and len(package_dirs) == 1:
            lines.append(f"  [bright_green]replx mip install github:{org}/{repo_ref}[/bright_green]")
        for package_path in package_dirs:
            lines.append(f"  [bright_cyan]{package_path}/[/bright_cyan]   [dim]replx mip install github:{org}/{repo_ref}/{package_path}[/dim]")
        lines.append("")

    if sub_path and py_files:
        lines.append(f"[bold]Install this source directory[/bold]   [dim]replx mip install github:{prefix}[/dim]")
        lines.append("")

    if dirs:
        lines.append(f"[bold]Subdirectories[/bold]   [dim]replx mip search github:{prefix}/SUBDIR[/dim]")
        for d in dirs:
            lines.append(f"  [bright_yellow]{d}/[/bright_yellow]")

    if py_files:
        if dirs:
            lines.append("")
        lines.append(f"[bold].py Files[/bold]   [dim]replx mip install github:{org}/{repo_ref}/PATH[/dim]")
        for fpath in py_files:
            lines.append(f"  [bright_cyan]{fpath}[/bright_cyan]")

    if not dirs and not py_files:
        lines.append("[dim]No Python files or subdirectories found.[/dim]")

    OutputHelper.print_panel("\n".join(lines), title=f"GitHub: {spec}", border_style="data")


def _mip_install_from_source(
    filenames: list[str],
    base_url: str,
    device_path: str,
    no_compile: bool,
) -> None:
    """Batch-install a list of filenames from a common base URL.

    Downloads all files silently, then uploads them to the board with a single
    Live progress panel showing [1/N], [2/N], ... [N/N] per file.
    """
    base = base_url.rstrip('/')
    total = len(filenames)

    slug = hashlib.md5(base.encode()).hexdigest()[:8]
    staging_dir = _mip_staging() / slug
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_files_dir = staging_dir / "files"
    staging_files_dir.mkdir(parents=True, exist_ok=True)

    # Download all files silently — no per-file "Fetching..." messages.
    file_pairs: list[tuple[str, str]] = []
    for filename in filenames:
        url = f"{base}/{filename}"
        local_path = str(staging_files_dir / filename)
        _write_file(local_path, _download_bytes(url))
        file_pairs.append((local_path, filename))

    device_base = device_path.strip("/")
    upload_specs: list[tuple[str, str]] = []
    for local_path, filename in file_pairs:
        if not no_compile and local_path.endswith(".py"):
            try:
                out_mpy = CompilerHelper.compile_to_staging(local_path, str(staging_files_dir))
                remote_path = f"/{device_base}/{os.path.splitext(filename)[0]}.mpy"
                upload_specs.append((out_mpy, remote_path.replace("//", "/")))
            except Exception as e:
                OutputHelper.print_panel(
                    f"Compilation failed for [yellow]{filename}[/yellow]: [red]{e}[/red]\n\n"
                    "Use [bright_blue]--no-compile[/bright_blue] to upload .py files directly.",
                    title="Compile Error",
                    border_style="error",
                )
                raise typer.Exit(1)
        else:
            remote_path = f"/{device_base}/{filename}"
            upload_specs.append((local_path, remote_path.replace("//", "/")))

    client = _create_agent_client()
    unique_dirs: set[str] = set()
    for _, remote_path in upload_specs:
        d = remote_path.rsplit("/", 1)[0]
        if d and d != "/":
            unique_dirs.add(d)
    _ensure_remote_dirs(unique_dirs, client)

    file_sizes = [os.path.getsize(lp) if os.path.exists(lp) else 0 for lp, _ in upload_specs]
    total_bytes = sum(file_sizes)

    progress_state = {"cumulative": 0, "current": 0}
    progress_lock = threading.Lock()

    def progress_callback(data):
        with progress_lock:
            if isinstance(data, dict):
                progress_state["current"] = data.get("current", 0)

    install_errors: list[str] = []
    _url_display = base_url
    if len(base_url) > 50:
        _cut = base_url[:48].rfind('/')
        _url_display = (base_url[:_cut + 1] + "...") if _cut > 10 else (base_url[:48] + "...")
    panel_title = f"{_url_display}  →  /{device_base}/"

    with Live(
        OutputHelper.create_progress_panel(
            0, max(total_bytes, 1),
            title=panel_title,
            message="Preparing...",
            counter_text=f"0B/{OutputHelper.format_bytes(total_bytes)}",
        ),
        console=OutputHelper._console,
        refresh_per_second=10,
    ) as live:
        for idx, (local_path, remote_path) in enumerate(upload_specs):
            filename = os.path.basename(local_path)
            file_size = file_sizes[idx]

            with progress_lock:
                progress_state["current"] = 0

            upload_result: list = [None]

            def do_upload(lp=local_path, rp=remote_path):
                try:
                    upload_result[0] = _upload_file_with_progress(client, lp, rp, progress_callback)
                except Exception as exc:
                    upload_result[0] = {"error": str(exc)}

            upload_thread = threading.Thread(target=do_upload, daemon=True)
            upload_thread.start()

            while upload_thread.is_alive():
                with progress_lock:
                    current = progress_state["current"]
                    cumulative = progress_state["cumulative"]
                total_sent = cumulative + current
                msg = f"[{idx + 1}/{total}] {filename} ({OutputHelper.format_bytes(file_size)})"
                counter = f"({OutputHelper.format_bytes(total_sent)}/{OutputHelper.format_bytes(total_bytes)})"
                live.update(
                    OutputHelper.create_progress_panel(
                        total_sent, max(total_bytes, 1),
                        title=panel_title,
                        message=msg,
                        counter_text=counter,
                    )
                )
                time.sleep(0.1)

            upload_thread.join()
            with progress_lock:
                progress_state["cumulative"] += file_size

            resp = upload_result[0]
            if resp and isinstance(resp, dict) and resp.get("error"):
                install_errors.append(f"{remote_path}: {resp['error']}")

        live.update(
            OutputHelper.create_progress_panel(
                total_bytes, max(total_bytes, 1),
                title=panel_title,
                message=f"Complete ({total} files)",
                counter_text=f"({OutputHelper.format_bytes(total_bytes)}/{OutputHelper.format_bytes(total_bytes)})",
            )
        )

    try:
        shutil.rmtree(staging_dir)
    except Exception:
        pass

    if install_errors:
        OutputHelper.print_panel(
            f"[yellow]{len(install_errors)}[/yellow] file(s) failed to upload:\n"
            + "\n".join(f"  [red]•[/red] {e}" for e in install_errors[:5])
            + (f"\n  [dim]... and {len(install_errors) - 5} more[/dim]" if len(install_errors) > 5 else ""),
            title="Install Warnings",
            border_style="warning",
        )

    file_list = "\n".join(
        f"  [bright_cyan]{os.path.basename(rp)}[/bright_cyan]  [dim]→  {rp}[/dim]"
        for _, rp in upload_specs
    )
    ext_note = ".py" if no_compile else ".mpy"
    OutputHelper.print_panel(
        f"{file_list}\n\n"
        f"[green]{total}[/green] file(s) "
        f"([cyan]{OutputHelper.format_bytes(total_bytes)}[/cyan]) "
        f"installed to [cyan]/{device_base}/[/cyan] as {ext_note}",
        title=f"Installed: {total} files from --source",
        border_style="success",
    )


def _mip_install(args: list[str], device_path: str, index_url: str, no_compile: bool,
                 source_base: Optional[str] = None):
    status = _ensure_connected()
    if normalize_core(status.get('core', '')) == 'EFR32MG':
        if not no_compile:
            OutputHelper._console.print(
                "[yellow]XBee3 legacy firmware: installing .py source only "
                "(equivalent to --no-compile). Package API compatibility "
                "must still be checked.[/yellow]"
            )
        no_compile = True

    if source_base is not None:
        if not args:
            OutputHelper.print_panel(
                "When using [bright_blue]--source[/bright_blue], provide one or more filenames.\n\n"
                "Example:\n"
                "  [bright_green]replx mip install --source https://host/path/ file1.mpy file2.mpy[/bright_green]",
                title="mip install Error",
                border_style="error",
            )
            raise typer.Exit(1)
        _mip_install_from_source(args, source_base, device_path, no_compile)
        return

    if not args:
        OutputHelper.print_panel(
            "Usage: [bright_green]replx mip install[/bright_green] [yellow]TARGET[@version][/yellow]\n\n"
            "Examples:\n"
            "  [bright_green]replx mip install requests[/bright_green]\n"
            "  [bright_green]replx mip install requests@0.10.0[/bright_green]\n"
            "  [bright_green]replx mip install github:org/repo[/bright_green]",
            title="mip install",
            border_style="help",
        )
        raise typer.Exit(1)

    target_spec = args[0]
    version: Optional[str] = None

    if (
        "@" in target_spec
        and not target_spec.startswith(("http://", "https://", "github:"))
    ):
        target_spec, version = target_spec.rsplit("@", 1)

    pkg_display = target_spec + (f"@{version}" if version else "")

    slug = hashlib.md5(f"{target_spec}{version or ''}".encode()).hexdigest()[:8]
    staging_dir = _mip_staging() / slug
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_files_dir = staging_dir / "files"
    staging_files_dir.mkdir(parents=True, exist_ok=True)

    mpy_abi = "py" if no_compile else _get_mpy_abi_from_state()
    abi_note = f"[dim] (mpy ABI {mpy_abi})[/dim]" if mpy_abi != "py" else ""
    OutputHelper._console.print(
        f"[dim]Fetching package manifest for [bright_cyan]{pkg_display}[/bright_cyan]{abi_note}...[/dim]"
    )
    try:
        files = _collect_install_files(target_spec, version, index_url, staging_files_dir, mpy_abi=mpy_abi)
    except Exception as e:
        _pkg_error = e
        files = None
        if not no_compile and target_spec.startswith("github:") and "404" in str(e):
            try:
                org, repo, sub_path, _ = _parse_github_spec(target_spec, version)
            except Exception:
                org = repo = sub_path = ""
            if org and repo and not sub_path:
                _client_tmp = _create_agent_client()
                arch_info = _get_board_mpy_arch(_client_tmp)
                if arch_info:
                    arch, abi_str = arch_info
                    OutputHelper._console.print(
                        f"[dim]No package.json — trying GitHub Pages CDN "
                        f"([bright_cyan]{arch}_{abi_str}[/bright_cyan])...[/dim]"
                    )
                    files = _collect_github_pages_files(org, repo, arch, abi_str, staging_files_dir)
                    if files:
                        pkg_display = f"{target_spec} [{arch}_{abi_str}]"

        if files is None:
            if target_spec.startswith("github:") and "404" in str(_pkg_error):
                try:
                    org, repo, _, _ = _parse_github_spec(target_spec, version)
                except Exception:
                    org, repo = "org", "repo"
                msg = (
                    f"Failed to fetch package: [red]{_pkg_error}[/red]\n\n"
                    f"No [yellow]package.json[/yellow] found at [dim]{target_spec}[/dim].\n"
                    f"  • Search the repo:  [bright_green]replx mip search github:{org}/{repo}[/bright_green]\n"
                    f"  • Install a file:   [bright_green]replx mip install github:{org}/{repo}/path/to/file.py[/bright_green]\n"
                    f"  • Direct .mpy URL:  [bright_green]replx mip install https://.../{repo}/builds/latest/ARCH_ABI/MODULE.mpy[/bright_green]"
                )
            else:
                msg = f"Failed to fetch package: [red]{_pkg_error}[/red]"
            OutputHelper.print_panel(msg, title="Install Error", border_style="error")
            raise typer.Exit(1)

    if not files:
        OutputHelper.print_panel(
            f"No files found in package [yellow]{pkg_display}[/yellow].\n\n"
            "The package manifest contains no [yellow]hashes[/yellow] or [yellow]urls[/yellow] entries.\n"
            "Try specifying a sub-path or a direct URL to a .py/.mpy file.",
            title="Install Error",
            border_style="warning",
        )
        raise typer.Exit(1)

    device_base = device_path.strip("/")
    upload_specs: list[tuple[str, str]] = [] 

    for local_path, dest_rel in files:
        dest_rel = dest_rel.replace("\\", "/")
        if not no_compile and local_path.endswith(".py"):
            try:
                out_mpy = CompilerHelper.compile_to_staging(
                    local_path, str(staging_files_dir)
                )
                remote_path = f"/{device_base}/{os.path.splitext(dest_rel)[0]}.mpy"
                upload_specs.append((out_mpy, remote_path.replace("//", "/")))
            except Exception as e:
                OutputHelper.print_panel(
                    f"Compilation failed for [yellow]{dest_rel}[/yellow]: [red]{e}[/red]\n\n"
                    "Use [bright_blue]--no-compile[/bright_blue] to upload .py files directly.",
                    title="Compile Error",
                    border_style="error",
                )
                raise typer.Exit(1)
        else:
            remote_path = f"/{device_base}/{dest_rel}"
            upload_specs.append((local_path, remote_path.replace("//", "/")))

    client = _create_agent_client()
    unique_dirs: set[str] = set()
    for _, remote_path in upload_specs:
        d = remote_path.rsplit("/", 1)[0]
        if d and d != "/":
            unique_dirs.add(d)
    _ensure_remote_dirs(unique_dirs, client)

    total_files = len(upload_specs)
    file_sizes = [
        os.path.getsize(lp) if os.path.exists(lp) else 0
        for lp, _ in upload_specs
    ]
    total_bytes = sum(file_sizes)

    progress_state = {"cumulative": 0, "current": 0}
    progress_lock = threading.Lock()

    def progress_callback(data):
        with progress_lock:
            if isinstance(data, dict):
                progress_state["current"] = data.get("current", 0)

    install_errors: list[str] = []

    with Live(
        OutputHelper.create_progress_panel(
            0, max(total_bytes, 1),
            title=f"Installing {pkg_display} → /{device_base}/",
            message="Preparing...",
            counter_text=f"0B/{OutputHelper.format_bytes(total_bytes)}",
        ),
        console=OutputHelper._console,
        refresh_per_second=10,
    ) as live:
        for idx, (local_path, remote_path) in enumerate(upload_specs):
            filename = os.path.basename(local_path)
            file_size = file_sizes[idx]

            with progress_lock:
                progress_state["current"] = 0

            upload_result: list = [None]

            def do_upload(lp=local_path, rp=remote_path):
                try:
                    upload_result[0] = _upload_file_with_progress(
                        client, lp, rp, progress_callback
                    )
                except Exception as exc:
                    upload_result[0] = {"error": str(exc)}

            upload_thread = threading.Thread(target=do_upload, daemon=True)
            upload_thread.start()

            while upload_thread.is_alive():
                with progress_lock:
                    current = progress_state["current"]
                    cumulative = progress_state["cumulative"]
                total_sent = cumulative + current
                msg = f"[{idx + 1}/{total_files}] {filename} ({OutputHelper.format_bytes(file_size)})"
                counter = f"({OutputHelper.format_bytes(total_sent)}/{OutputHelper.format_bytes(total_bytes)})"
                live.update(
                    OutputHelper.create_progress_panel(
                        total_sent, max(total_bytes, 1),
                        title=f"Installing {pkg_display} → /{device_base}/",
                        message=msg,
                        counter_text=counter,
                    )
                )
                time.sleep(0.1)

            upload_thread.join()

            with progress_lock:
                progress_state["cumulative"] += file_size

            resp = upload_result[0]
            if resp and isinstance(resp, dict) and resp.get("error"):
                install_errors.append(f"{remote_path}: {resp['error']}")

        live.update(
            OutputHelper.create_progress_panel(
                total_bytes, max(total_bytes, 1),
                title=f"Installing {pkg_display} → /{device_base}/",
                message="Complete",
                counter_text=f"({OutputHelper.format_bytes(total_bytes)}/{OutputHelper.format_bytes(total_bytes)})",
            )
        )

    try:
        shutil.rmtree(staging_dir)
    except Exception:
        pass

    if install_errors:
        OutputHelper.print_panel(
            f"[yellow]{len(install_errors)}[/yellow] file(s) failed to upload:\n"
            + "\n".join(f"  [red]•[/red] {e}" for e in install_errors[:5])
            + (f"\n  [dim]... and {len(install_errors) - 5} more[/dim]" if len(install_errors) > 5 else ""),
            title="Install Warnings",
            border_style="warning",
        )

    meta = _load_mip_meta()
    meta["packages"][target_spec] = {
        "version": version or "latest",
        "source": index_url if not target_spec.startswith("github:") else target_spec,
        "device_path": f"/{device_base}",
        "installed_at": int(time.time()),
        "files": [rp for _, rp in upload_specs],
    }
    _save_mip_meta(meta)

    ext_note = ".py" if no_compile else ".mpy"
    OutputHelper.print_panel(
        f"[green]{total_files}[/green] file(s) "
        f"([cyan]{OutputHelper.format_bytes(total_bytes)}[/cyan]) "
        f"installed to [cyan]/{device_base}/[/cyan] as {ext_note}",
        title=f"Installed: {pkg_display}",
        border_style="success",
    )

