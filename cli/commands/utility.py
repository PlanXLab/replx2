import os
import ipaddress
import re
import time
import threading
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner

from replx import __version__
from replx.utils.constants import AGENT_BIND_ALL_HOST, AGENT_HOST, DEFAULT_AGENT_PORT
from replx.terminal import IS_WINDOWS
from ..agent.client import AgentClient, get_cached_session_id
from ..helpers import (
    OutputHelper,
    get_panel_box, CONSOLE_WIDTH, set_global_context
)
from ..config import (
    STATE, DEFAULT_AGENT_PORT, AgentPortManager,
    _resolve_connection, _get_global_options,
    _find_env_file, _find_running_agent_ports,
)
from ..connection import (
    _ensure_connected, _create_agent_client,
    _get_current_agent_port
)
from ..app import app


def _port_sort_key(port: str) -> tuple:
    if port is None:
        return ("", -1)
    p = str(port).strip()
    m = re.search(r"(\d+)$", p)
    if m:
        return (p[: m.start()].lower(), int(m.group(1)))
    return (p.lower(), 0)


def _sorted_unique_ports(ports: list[str | None]) -> list[str]:
    seen = set()
    out: list[str] = []
    for p in ports:
        if not p:
            continue
        s = str(p).strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    out.sort(key=_port_sort_key)
    return out


def _get_connection_info_for_port(connections: dict, port: Optional[str]) -> dict:
    if not port or not connections:
        return {}

    if port in connections:
        return connections.get(port, {}) or {}

    if IS_WINDOWS:
        upper = port.upper()
        if upper in connections:
            return connections.get(upper, {}) or {}
        lower = port.lower()
        if lower in connections:
            return connections.get(lower, {}) or {}

        lower_key = lower
        for key, value in connections.items():
            if isinstance(key, str) and key.lower() == lower_key:
                return value or {}

    return {}


@app.command(name="version", hidden=True)
def version_cmd(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = Console(width=CONSOLE_WIDTH)
        help_text = """\
Show replx version information.

[bold cyan]Usage:[/bold cyan]
  replx version
  replx -v                [dim]# Short alias[/dim]

[bold cyan]Examples:[/bold cyan]
  replx version           [dim]# Show version[/dim]
  replx -v                [dim]# Same as above[/dim]"""
        OutputHelper.print_panel(help_text, title="version", border_style="help")
        console.print()
        raise typer.Exit()
    
    OutputHelper.print_panel(
        f"replx [green]{__version__}[/green]",
        title="Version",
        border_style="data"
    )


_AGENT_HELP_TEXT = """\
Manage the replx agent service and client connections.

[bold cyan]Usage:[/bold cyan]
  replx agent [yellow]SUBCOMMAND[/yellow] ...

[bold cyan]Subcommands:[/bold cyan]
  [green]status[/green]                 Show all client IP/SID sessions and assigned boards.
  [green]start[/green]                  Start or restart the agent on this computer.
  [green]connect[/green]                Save a remote agent endpoint to this workspace.
  [green]disconnect[/green]             Remove a client's sessions from the configured agent.
  [green]stop[/green]                   Stop the configured agent and release its boards.

[bold cyan]Start:[/bold cyan]
  replx agent start [[green]--host IP[/green]] [[green]--port PORT[/green]]
  --host IP   Local interface address to bind. By default, the agent uses its
              configured local address; with a token, it listens on all interfaces.
  --port PORT TCP listening port. Defaults to the configured port or 49153.

[bold cyan]Connect:[/bold cyan]
  replx agent connect [yellow]IP[/yellow] [[green]--port PORT[/green]]
  Verify the remote agent and save its endpoint to this workspace.
  --port PORT Defaults to 49153.

[bold cyan]Disconnect:[/bold cyan]
  replx agent disconnect [yellow]IP[/yellow]
  Remove sessions for this client IP and release its assigned boards.

[bold cyan]Examples:[/bold cyan]
  replx agent status
  replx agent start
  replx agent start --host 192.168.1.20 --port 50000
  replx agent connect <agent-IP>
  replx agent connect <agent-IP> --port 50000
  replx agent disconnect <client-IP>
  replx agent stop
  replx com4 ls -r             [dim]# Start the local agent on demand[/dim]

[bold cyan]Notes:[/bold cyan]
  [bold]Remote connection:[/bold]
  Set [yellow]REPLX_AGENT_TOKEN[/yellow] to the same secret on the agent and every
  remote client before starting the agent. The variable name is exactly
  REPLX_AGENT_TOKEN (not REPL_AGENT_TOKEN). Restart the agent after changing it.
  Without a token, the listener is loopback-only. TCP is unencrypted; use a
  trusted LAN/VPN, allow the agent port through the firewall, and never expose
  an unauthenticated listener. Remote clients can control connected boards.

  [bold]Endpoint settings:[/bold]
  The endpoint is stored in .vscode/.replx as AGENT_IP and AGENT_PORT.
  The default endpoint is 127.0.0.1:49153. Use --port when the agent listens
  on a non-default port. --host must be an IP address assigned to this computer."""


def _print_agent_help() -> None:
    OutputHelper.print_panel(_AGENT_HELP_TEXT, title="agent", border_style="help")
    Console(width=CONSOLE_WIDTH).print()


agent_app = typer.Typer(
    help="Manage the replx agent service and client connections.",
    add_completion=False,
    context_settings={"help_option_names": []},
    invoke_without_command=True,
)


@agent_app.callback()
def agent_callback(
    ctx: typer.Context,
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help or ctx.invoked_subcommand is None:
        _print_agent_help()
        raise typer.Exit()


@agent_app.command("status")
def agent_status(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        _print_agent_help()
        raise typer.Exit()

    host = AgentPortManager._read_registered_ip()
    port = _get_current_agent_port()
    try:
        AgentClient._get_auth_token(host)
    except RuntimeError as exc:
        OutputHelper.print_panel(str(exc), title="Agent Authentication Required", border_style="error")
        raise typer.Exit(1)
    if not AgentClient.is_agent_running(port=port, host=host):
        OutputHelper.print_panel(
            f"No responsive agent at [bright_blue]{host}:{port}[/bright_blue].",
            title="Agent Status",
            border_style="neutral"
        )
        raise typer.Exit()

    try:
        with AgentClient(port=port, host=host) as client:
            info = client.send_command('session_info', timeout=1.5)
    except Exception as exc:
        OutputHelper.print_panel(
            f"Could not query agent at {host}:{port}: {exc}",
            title="Agent Status Error",
            border_style="error"
        )
        raise typer.Exit(1)

    connection_by_port = {
        connection.get('port'): connection
        for connection in info.get('connections', [])
        if connection.get('port')
    }

    def session_sort_key(session):
        client_ip = str(session.get('client_ip') or '?')
        sid = session.get('sid', session.get('ppid', '?'))
        try:
            sid_key = (0, int(sid))
        except (TypeError, ValueError):
            sid_key = (1, str(sid).casefold())
        return client_ip.casefold(), sid_key

    sessions = sorted(info.get('sessions', []), key=session_sort_key)
    board_lines = []
    if not sessions:
        board_lines.append("  No client sessions connected to this agent.")
    for session in sessions:
        client_ip = session.get('client_ip') or '?'
        sid = session.get('sid', session.get('ppid', '?'))
        board_lines.append(f"[bright_cyan]{client_ip} / SID {sid}[/bright_cyan]")

        foreground = session.get('foreground')
        assigned = _sorted_unique_ports(
            ([foreground] if foreground else [])
            + list(session.get('backgrounds', []))
        )
        if not assigned:
            board_lines.append("  No boards assigned to this session.")
            continue

        for board_port in assigned:
            connection = _get_connection_info_for_port(connection_by_port, board_port)
            device = connection.get('device') or connection.get('core') or 'Unknown board'
            version = connection.get('version', '?')
            core = connection.get('core', '?')
            is_busy = connection.get('busy', False)
            status = "[red]busy[/red]" if is_busy else "[green]idle[/green]"
            marker = "[green]󱓥[/green]" if board_port == foreground else " "
            manufacturer = connection.get('manufacturer', '')
            board_lines.append(
                f"  {marker} {OutputHelper.format_port(board_port)}  {status}  "
                f"{version}  [bright_green]{core}[/bright_green]  "
                f"[bright_yellow]{device}[/bright_yellow]  [dim]{manufacturer}[/dim]"
            )
        board_lines.append("")

    OutputHelper.print_panel(
        f"Endpoint: [bright_green]{host}:{port}[/bright_green]\n"
        "Client sessions and assigned boards:\n" + "\n".join(board_lines).rstrip(),
        title="Agent Status",
        border_style="success"
    )


@agent_app.command("start")
def agent_start(
    port: Optional[int] = typer.Option(None, "--port", min=1, max=65535, help="TCP port to listen on."),
    host: Optional[str] = typer.Option(
        None,
        "--host",
        help="Local IP to bind; defaults to all interfaces with REPLX_AGENT_TOKEN, otherwise loopback.",
    ),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        _print_agent_help()
        raise typer.Exit()

    configured_host = AgentPortManager._read_registered_ip()
    selected_host = host or (
        configured_host if AgentPortManager._is_local_ip(configured_host) else AGENT_HOST
    )
    try:
        selected_host = ipaddress.ip_address(selected_host.strip()).compressed
    except ValueError:
        OutputHelper.print_panel(
            f"Invalid bind IP: {selected_host}",
            title="Agent Start Failed",
            border_style="error"
        )
        raise typer.Exit(1)
    if (
        host is None
        and ipaddress.ip_address(selected_host).is_loopback
        and AgentClient._get_auth_token(AGENT_HOST)
    ):
        selected_host = AGENT_BIND_ALL_HOST
    try:
        AgentClient._get_auth_token(selected_host)
    except RuntimeError as exc:
        OutputHelper.print_panel(str(exc), title="Agent Authentication Required", border_style="error")
        raise typer.Exit(1)
    if not AgentPortManager._is_local_ip(selected_host):
        OutputHelper.print_panel(
            f"{selected_host} is not assigned to this computer.",
            title="Agent Start Failed",
            border_style="error"
        )
        raise typer.Exit(1)

    selected_port = port or _get_current_agent_port()
    current_port = _get_current_agent_port()
    endpoints = {(configured_host, current_port), (selected_host, selected_port)}
    for endpoint_host, endpoint_port in endpoints:
        if not AgentPortManager._is_local_ip(endpoint_host):
            continue
        probe_host = AgentClient._probe_host(endpoint_host)
        if AgentClient.is_agent_running(port=endpoint_port, host=probe_host):
            if not AgentClient.stop_agent(port=endpoint_port, host=probe_host):
                OutputHelper.print_panel(
                    f"Could not stop the running agent at {probe_host}:{endpoint_port}.",
                    title="Agent Start Failed",
                    border_style="error"
                )
                raise typer.Exit(1)

    try:
        started = AgentClient.start_agent(port=selected_port, host=selected_host)
        AgentPortManager._write_registered_ip(AgentClient._probe_host(selected_host))
        AgentPortManager._write_registered_port(selected_port)
        AgentPortManager._singleton_cache = selected_port
        AgentPortManager._singleton_cache_miss = False
    except Exception as exc:
        OutputHelper.print_panel(
            f"Could not start agent at {selected_host}:{selected_port}: {exc}",
            title="Agent Start Failed",
            border_style="error"
        )
        raise typer.Exit(1)
    message = (
        f"replx agent started at [bright_green]{selected_host}:{selected_port}[/bright_green]"
        if started
        else f"replx agent is already running at [bright_green]{selected_host}:{selected_port}[/bright_green]"
    )
    bind_address = ipaddress.ip_address(selected_host)
    if bind_address.is_unspecified:
        message += (
            "\nListening on all interfaces. Remote clients must provide the same "
            "REPLX_AGENT_TOKEN."
        )
    elif bind_address.is_loopback:
        message += (
            "\nThis endpoint accepts local connections only. For remote access, restart with "
            "REPLX_AGENT_TOKEN set on the agent and client."
        )
    OutputHelper.print_panel(
        message,
        title="Agent Started" if started else "Agent Status",
        border_style="success" if started else "neutral"
    )


@agent_app.command("connect")
def agent_connect(
    ip: Optional[str] = typer.Argument(None, metavar="IP", help="IP address of the agent to connect to."),
    port: Optional[int] = typer.Option(None, "--port", min=1, max=65535, help="Agent TCP port."),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True),
):
    if show_help:
        _print_agent_help()
        raise typer.Exit()

    if not ip:
        OutputHelper.print_panel(
            "Missing agent IP.\nUsage: replx agent connect IP [--port PORT]\n"
            "Run 'replx agent --help' for the remote setup steps.",
            title="Agent Connect Failed",
            border_style="error"
        )
        raise typer.Exit(2)

    try:
        selected_ip = ipaddress.ip_address(ip.strip()).compressed
    except ValueError:
        OutputHelper.print_panel(f"Invalid agent IP: {ip}", title="Agent Connect Failed", border_style="error")
        raise typer.Exit(1)

    try:
        AgentClient._get_auth_token(selected_ip)
    except RuntimeError as exc:
        OutputHelper.print_panel(str(exc), title="Agent Authentication Required", border_style="error")
        raise typer.Exit(1)

    selected_port = port or DEFAULT_AGENT_PORT
    if not AgentClient.is_agent_running(port=selected_port, host=selected_ip):
        OutputHelper.print_panel(
            f"Could not verify a replx agent at {selected_ip}:{selected_port}. "
            "Check that the agent is listening on its LAN IP or all interfaces at this port, "
            "both computers "
            "use the same REPLX_AGENT_TOKEN, and the port is allowed through the firewall. "
            "Workspace settings were not changed.",
            title="Agent Connect Failed",
            border_style="error"
        )
        raise typer.Exit(1)

    AgentPortManager._write_registered_ip(selected_ip)
    AgentPortManager._write_registered_port(selected_port)
    AgentPortManager._singleton_cache = selected_port
    AgentPortManager._singleton_cache_miss = False
    OutputHelper.print_panel(
        f"Connected to [bright_green]{selected_ip}:{selected_port}[/bright_green]",
        title="Agent Connected",
        border_style="success"
    )


@agent_app.command("disconnect")
def agent_disconnect(
    ip: Optional[str] = typer.Argument(None, metavar="IP", help="Client IP whose sessions should be disconnected."),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True),
):
    if show_help:
        _print_agent_help()
        raise typer.Exit()

    if not ip:
        OutputHelper.print_panel(
            "Missing client IP.\nUsage: replx agent disconnect IP\n"
            "Run 'replx agent --help' for all agent commands.",
            title="Agent Disconnect Failed",
            border_style="error"
        )
        raise typer.Exit(2)

    try:
        client_ip = ipaddress.ip_address(ip.strip()).compressed
        host = AgentPortManager._read_registered_ip()
        port = _get_current_agent_port()
        with AgentClient(port=port, host=host) as client:
            result = client.send_command("client_disconnect", ip=client_ip, timeout=3.0)
    except Exception as exc:
        OutputHelper.print_panel(
            f"Could not disconnect client {ip}: {exc}",
            title="Agent Disconnect Failed",
            border_style="error"
        )
        raise typer.Exit(1)

    released_ports = result.get("released_ports", [])
    detail = f"Removed {result.get('sessions_disconnected', 0)} session(s) for {client_ip}."
    if released_ports:
        detail += "\nReleased boards: " + ", ".join(released_ports)
    OutputHelper.print_panel(detail, title="Client Disconnected", border_style="success")


@agent_app.command("stop")
def agent_stop(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        _print_agent_help()
        raise typer.Exit()

    _stop_agent()


app.add_typer(agent_app, name="agent")


def _get_session_list_data(*, include_connections_without_sessions: bool = False):
    env_path = _find_env_file()
    running_agent_ports = _find_running_agent_ports(env_path)
    if not running_agent_ports:
        return None, None, "no_server"

    current_ppid = get_cached_session_id()
    session_map = {}
    connections = {}
    query_errors = []

    def _merge_session(agent_session: dict) -> None:
        ppid = agent_session.get('ppid')
        if ppid is None:
            return
        sid = agent_session.get('sid', ppid)
        client_ip = agent_session.get('client_ip', '127.0.0.1')
        session_id = agent_session.get('session_key') or f'{client_ip}/{sid}'

        entry = session_map.setdefault(session_id, {
            'ppid': ppid,
            'sid': sid,
            'client_ip': client_ip,
            'is_current': bool(agent_session.get('is_current', ppid == current_ppid)),
            'foreground': None,
            'backgrounds': [],
            'default_port': None,
        })
        if agent_session.get('is_current'):
            entry['is_current'] = True

        fg_port = agent_session.get('foreground')
        if fg_port:
            if entry['foreground'] is None:
                entry['foreground'] = fg_port
            elif entry['foreground'] != fg_port and fg_port not in entry['backgrounds']:
                entry['backgrounds'].append(fg_port)

        for bg_port in agent_session.get('backgrounds', []):
            if not bg_port:
                continue
            if bg_port == entry['foreground']:
                continue
            if bg_port not in entry['backgrounds']:
                entry['backgrounds'].append(bg_port)

        default_port = agent_session.get('default_port')
        if default_port and not entry['default_port']:
            entry['default_port'] = default_port

    def _merge_connection(agent_port: int, conn: dict) -> None:
        port = conn.get('port')
        if not port:
            return

        existing = connections.get(port)
        merged = {
            'version': conn.get('version', '?'),
            'core': conn.get('core', '?'),
            'device': conn.get('device', '?'),
            'manufacturer': conn.get('manufacturer', ''),
            'busy': conn.get('busy', False),
            'agent_port': agent_port,
        }

        if existing and existing.get('busy') and not merged.get('busy'):
            merged['busy'] = True

        connections[port] = merged

    try:
        for agent_port in running_agent_ports:
            try:
                with AgentClient(port=agent_port) as client:
                    session_info = client.send_command('session_info', timeout=1.5)
            except Exception as e:
                query_errors.append(f"{agent_port}: {e}")
                continue

            for session in session_info.get('sessions', []):
                _merge_session(session)

            for conn in session_info.get('connections', []):
                _merge_connection(agent_port, conn)
    except Exception as e:
        return None, current_ppid, f"query_failed:{e}"

    if connections:
        referenced_ports = set()
        for sess in session_map.values():
            fg = sess.get('foreground')
            if fg:
                referenced_ports.add(fg)
            for bg in sess.get('backgrounds', []):
                referenced_ports.add(bg)
        unassigned_ports = [
            p for p, c in connections.items()
            if p not in referenced_ports and c.get('connected', True)
        ]
        if unassigned_ports:
            target_sess = next(
                (session for session in session_map.values() if session.get('is_current')),
                None,
            )
            if target_sess is None:
                target_sess = {
                    'ppid': current_ppid,
                    'sid': current_ppid,
                    'client_ip': None,
                    'is_current': True,
                    'foreground': None,
                    'backgrounds': [],
                    'last_access': 0,
                }
                session_map[('current', current_ppid)] = target_sess
            for p in unassigned_ports:
                if not target_sess.get('foreground'):
                    target_sess['foreground'] = p
                elif p != target_sess.get('foreground') and p not in target_sess['backgrounds']:
                    target_sess['backgrounds'].append(p)

    has_unassigned_connections = include_connections_without_sessions and bool(connections)

    if not session_map and query_errors and not has_unassigned_connections:
        return None, current_ppid, f"query_failed:{'; '.join(query_errors)}"

    sessions = []
    for session in session_map.values():
        session['backgrounds'] = _sorted_unique_ports(session.get('backgrounds', []))
        session['is_current'] = session.get('is_current', session.get('ppid') == current_ppid)
        sessions.append(session)
    
    if not sessions:
        if has_unassigned_connections:
            return {
                'sessions': [],
                'connections': connections,
                'current_session_empty': True,
            }, current_ppid, None
        return None, current_ppid, "no_sessions"
    
    total_connections = 0
    for sess in sessions:
        if sess.get('foreground'):
            total_connections += 1
        total_connections += len(sess.get('backgrounds', []))
    
    if total_connections == 0:
        if has_unassigned_connections:
            return {
                'sessions': sessions,
                'connections': connections,
                'current_session_empty': True,
            }, current_ppid, None
        return None, current_ppid, "no_sessions"
    
    current_session = None
    for sess in sessions:
        if sess.get('is_current'):
            current_session = sess
            break
    
    current_session_empty = (
        current_session is None or 
        (not current_session.get('foreground') and not current_session.get('backgrounds'))
    )
    
    return {
        'sessions': sessions,
        'connections': connections,
        'current_session_empty': current_session_empty
    }, current_ppid, None


def _handle_session_list_error(error: Optional[str], *, no_server_title: str, no_server_message: str,
                               no_sessions_title: str, no_sessions_message: str) -> bool:
    if error == "no_server":
        OutputHelper.print_panel(
            no_server_message,
            title=no_server_title,
            border_style="neutral"
        )
        return True

    if error == "no_sessions":
        OutputHelper.print_panel(
            no_sessions_message,
            title=no_sessions_title,
            border_style="neutral"
        )
        return True

    if error and error.startswith("query_failed:"):
        detail = error.split(":", 1)[1].strip() or "Unknown error"
        OutputHelper.print_panel(
            f"Failed to query agent sessions.\n\n{detail}",
            title="Session Error",
            border_style="error"
        )
        return True

    return False


def _num_to_bracket(n: int) -> str:
    return f"[{n}]".rjust(4)


def _print_session_list_interactive(sessions_data, current_ppid):
    sessions = sessions_data['sessions']
    connections = sessions_data['connections']
    
    color_map = ["yellow", "green", "blue"]
    
    sessions_sorted = sorted(sessions, key=lambda s: (not s.get('is_current'), s.get('ppid', 0)))
    
    current_fg = None
    for sess in sessions:
        if sess.get('is_current') and sess.get('foreground'):
            current_fg = sess['foreground']
            break
    
    all_ports = list(connections.keys())
    all_versions = [c.get('version', '?') for c in connections.values()]
    all_cores = [c.get('core', '?') for c in connections.values()]
    all_devices = [c.get('device', '?') for c in connections.values()]
    
    PORT_W = max((len(p) for p in all_ports), default=4)
    STATUS_W = 4
    VER_W = max((len(v) for v in all_versions), default=6)
    CORE_W = max((len(c) for c in all_cores), default=6)
    DEV_W = max((len(d) for d in all_devices), default=6)
    
    content_lines = []
    selectable_map = {}
    select_num = 1
    row_idx = 0
    
    numbered_ports = set()
    if current_fg:
        numbered_ports.add(current_fg)
    
    def make_row(selector, port, version, core, device, manufacturer, color, dimmed=False):
        if dimmed:
            return f"{selector:>4}  {port:>{PORT_W}}  {version:<{VER_W}}  {core:<{CORE_W}}  {device:<{DEV_W}}  {manufacturer}"
        else:
            return f"{selector:>4}  [{color}]{port:>{PORT_W}}[/{color}]  {version:<{VER_W}}  {core:<{CORE_W}}  [{color}]{device:<{DEV_W}}[/{color}]  [dim]{manufacturer}[/dim]"
    
    for sess in sessions_sorted:
        ppid = sess.get('ppid')
        is_current = sess.get('is_current', False)
        fg_port = sess.get('foreground')
        bg_ports = sess.get('backgrounds', [])
        
        if is_current:
            content_lines.append(f"[bold bright_cyan]\\[SID: {ppid}][/bold bright_cyan]")
        else:
            content_lines.append(f"[dim]SID: {ppid}[/dim]")
        
        ordered_ports = _sorted_unique_ports(([fg_port] if fg_port else []) + list(bg_ports or []))

        if ordered_ports:
            conn_info = _get_connection_info_for_port(connections, fg_port)
            for p in ordered_ports:
                is_fg = bool(fg_port and p == fg_port)
                conn_info = _get_connection_info_for_port(connections, p)
                version = conn_info.get('version', '?')
                core = conn_info.get('core', '?')
                device = conn_info.get('device', '?')
                manufacturer = conn_info.get('manufacturer', '')
                is_busy = conn_info.get('busy', False)
                status = 'busy' if is_busy else 'idle'
                status_color = 'red' if is_busy else 'green'

                color = color_map[row_idx % len(color_map)]
                row_idx += 1

                p_disp = OutputHelper.format_port(p)

                if is_current and is_fg:
                    selector = f"[{color}] 󱓥  [/{color}]"
                    line = f"{selector}  [{color}]{p_disp:>{PORT_W}}[/{color}]  [{status_color}]{status:<{STATUS_W}}[/{status_color}]  {version:<{VER_W}}  {core:<{CORE_W}}  [{color}]{device:<{DEV_W}}[/{color}]  [dim]{manufacturer}[/dim]"
                    content_lines.append(line)
                elif p not in numbered_ports:
                    bracket = _num_to_bracket(select_num)
                    selectable_map[select_num] = p
                    numbered_ports.add(p)
                    select_num += 1
                    selector = f"[bright_cyan]{bracket}[/bright_cyan]"
                    icon = "󱓥" if is_fg else " "
                    line = f"{selector}  [{color}]{p_disp:>{PORT_W}}[/{color}]  [{status_color}]{status:<{STATUS_W}}[/{status_color}]  {version:<{VER_W}}  {core:<{CORE_W}}  [{color}]{device:<{DEV_W}}[/{color}]  [dim]{manufacturer}[/dim]"
                    if icon and is_fg and is_current:
                        pass
                    content_lines.append(line)
                else:
                    selector = "[dim] 󰌹  [/dim]"
                    line = f"{selector}  [dim]{p_disp:>{PORT_W}}  {status:<{STATUS_W}}  {version:<{VER_W}}  {core:<{CORE_W}}  {device:<{DEV_W}}  {manufacturer}[/dim]"
                    content_lines.append(line)
        
        content_lines.append("")
    
    content_lines.append("[dim] 󱓥 foreground, 󰌹 duplicate[/dim]")
    
    OutputHelper.print_panel(
        "\n".join(content_lines),
        title="Sessions",
        border_style="data"
    )
    
    if not selectable_map:
        return None, None
    
    console = Console(width=CONSOLE_WIDTH)
    max_num = max(selectable_map.keys())
    prompt = f"\n[bright_cyan]\\[1-{max_num}] switch, \\[Enter] quit: [/bright_cyan]"
    
    while True:
        try:
            choice = console.input(prompt)
            choice = choice.strip().lower()
            
            if choice == 'q' or choice == '':
                return None, None
            
            try:
                num = int(choice)
                if num in selectable_map:
                    return selectable_map[num], None
                else:
                    console.print(f"[red]Invalid selection: {num}[/red]")
            except ValueError:
                console.print(f"[red]Invalid input: {choice}[/red]")
        except KeyboardInterrupt:
            console.print()
            return None, None


def _print_session_list_status(sessions_data, current_ppid):
    from rich.table import Table
    from rich.console import Console
    from io import StringIO
    from rich.text import Text
    from rich.panel import Panel
    from ..helpers import CONSOLE_WIDTH
    from ..helpers.output import get_panel_box
    
    sessions = sessions_data['sessions']
    connections = sessions_data['connections']
    
    all_defaults = set()
    for sess in sessions:
        if sess.get('default_port'):
            all_defaults.add(sess['default_port'])

    def _port_key(p: str) -> str:
        if not p:
            return ""
        s = str(p).strip()
        return s.lower() if IS_WINDOWS else s

    all_defaults_keyed = {_port_key(p) for p in all_defaults}
    
    sessions_sorted = sorted(sessions, key=lambda s: (not s.get('is_current'), s.get('ppid', 0)))
    
    COLUMN_PADDING = 2
    
    string_io = StringIO()
    temp_console = Console(file=string_io, force_terminal=True, width=300)
    
    def get_conn_marker(is_foreground, is_current):
        if not is_foreground:
            return ""
        return "[green]󱓥[/green]" if is_current else "[dim]󱓥[/dim]"
    
    def get_default_marker(port, is_current):
        is_default = _port_key(port) in all_defaults_keyed
        if not is_default:
            return ""
        return "[bright_yellow]󰷌[/bright_yellow]" if is_current else "[dim]󰷌[/dim]"
    
    for sess in sessions_sorted:
        ppid = sess.get('ppid')
        is_current = sess.get('is_current', False)
        fg_port = sess.get('foreground')
        bg_ports = sess.get('backgrounds', [])
        
        if is_current:
            temp_console.print(f"[bold bright_cyan]\\[SID: {ppid}][/bold bright_cyan]")
        else:
            temp_console.print(f"[dim]SID: {ppid}[/dim]")
        
        session_table = Table(show_header=False, box=None, padding=(0, COLUMN_PADDING), collapse_padding=True, expand=False)
        session_table.add_column("conn", no_wrap=True)
        session_table.add_column("port", no_wrap=True, justify="right")
        session_table.add_column("default", no_wrap=True)
        session_table.add_column("status", no_wrap=True)
        session_table.add_column("version", no_wrap=True)
        session_table.add_column("core", no_wrap=True)
        session_table.add_column("device", no_wrap=True)
        session_table.add_column("manufacturer", no_wrap=True, overflow="ignore")
        
        has_connections = False
        
        ordered_ports = _sorted_unique_ports(([fg_port] if fg_port else []) + list(bg_ports or []))

        for p in ordered_ports:
            has_connections = True
            is_fg = bool(fg_port and p == fg_port)
            conn_info = _get_connection_info_for_port(connections, p)
            version = conn_info.get('version', '?')
            core = conn_info.get('core', '?')
            device = conn_info.get('device', '?')
            manufacturer = conn_info.get('manufacturer', '')
            is_busy = conn_info.get('busy', False)
            if is_current:
                status_text = Text("busy", style="red") if is_busy else Text("idle", style="green")
                version_text = Text(version)
                core_text = Text(core, style="bright_green")
                device_text = Text(device, style="bright_yellow")
                manufacturer_text = Text(manufacturer, style="dim")
                port_text = Text(OutputHelper.format_port(p), style="bright_cyan")
            else:
                status_text = Text("busy", style="dim red") if is_busy else Text("idle", style="dim green")
                version_text = Text(version, style="dim")
                core_text = Text(core, style="dim")
                device_text = Text(device, style="dim")
                manufacturer_text = Text(manufacturer, style="dim")
                port_text = Text(OutputHelper.format_port(p), style="dim")

            session_table.add_row(
                get_conn_marker(is_fg, is_current),
                port_text,
                get_default_marker(p, is_current),
                status_text,
                version_text,
                core_text,
                device_text,
                manufacturer_text
            )
        
        if has_connections:
            temp_console.print(session_table)
        
        temp_console.print()
    
    temp_console.print("[dim] 󱓥 foreground  󰷌 default[/dim]")
    
    output_text = string_io.getvalue().rstrip()
    text_content = Text.from_ansi(output_text)
    text_content.no_wrap = True
    
    OutputHelper.print_panel(
        text_content,
        title="Sessions",
        title_align="left",
        border_style="data"
    )


@app.command(rich_help_panel="Connection & Session")
def status(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = Console(width=CONSOLE_WIDTH)
        help_text = """\
Show all active sessions and their board connections.

Displays a table of all terminal sessions with their connected boards.

[bold cyan]Usage:[/bold cyan]
  replx status

[bold cyan]What you'll see:[/bold cyan]
  [bold]Columns:[/bold]
    • [yellow]Session[/yellow]  - Terminal session identifier (current in [bright_white]brackets[/bright_white])
    • [yellow]FG[/yellow]       - Foreground connection (primary board)
    • [yellow]BG[/yellow]       - Background connections (secondary boards)
    • [yellow]Default[/yellow]  - Workspace default (󰷌 marked)

  [bold]Status icons:[/bold]
    󱓥  Serial connection (COM port)

[bold cyan]Example output:[/bold cyan]
    Session      FG           BG         Default
    [1234]       󱓥 COM19     COM3       󰷌 COM19
     5678        󱓥 COM3

[bold cyan]Understanding sessions:[/bold cyan]
  • Each terminal window has its own session
  • Sessions can connect to multiple boards
  • FG (foreground) is used by default for commands
  • BG (background) boards are available for switching

[bold cyan]Note:[/bold cyan]
  This command ignores -p/--port option.

[bold cyan]Related:[/bold cyan]
  replx fg COM3         [dim]# Switch FG to different board[/dim]
    replx close            [dim]# Release current FG connection[/dim]"""
        OutputHelper.print_panel(help_text, title="status", border_style="help")
        console.print()
        raise typer.Exit()
    
    sessions_data, current_ppid, error = _get_session_list_data()

    if _handle_session_list_error(
        error,
        no_server_title="No Connections",
        no_server_message=(
            "Agent is not running. No active connections.\n\n"
            "Start by running a command like:\n"
            "  [bright_green]replx ls[/bright_green]\n"
            "  [bright_green]replx exec \"print('hello')\"[/bright_green]"
        ),
        no_sessions_title="No Connections",
        no_sessions_message=(
            "No active connections.\n\n"
            "Connect to a board with:\n"
            "  [bright_green]replx ls[/bright_green]\n"
            "  [bright_green]replx --port COM19 setup[/bright_green]"
        ),
    ):
        raise typer.Exit()
    
    _print_session_list_status(sessions_data, current_ppid)


@app.command(rich_help_panel="Connection & Session")
def fg(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = Console(width=CONSOLE_WIDTH)
        help_text = """\
Switch foreground connection to another board.

When you have multiple boards connected, use this to switch between them.

[bold cyan]Usage:[/bold cyan]
  replx fg                    [dim]# Interactive: select from list[/dim]
  replx [cyan]PORT[/cyan] fg               [dim]# Direct: switch to PORT[/dim]

[bold cyan]Examples:[/bold cyan]
  replx fg                    [dim]# Show menu to pick a board[/dim]
  replx COM19 fg              [dim]# Switch to COM19[/dim]
  replx COM3 fg               [dim]# Switch to COM3[/dim]

[bold cyan]What happens:[/bold cyan]
  • The specified board becomes the foreground connection
  • All subsequent commands (ls, run, cat, etc.) use this board
  • Previous foreground moves to background (still connected)
  • If board isn't connected yet, it will be connected

[bold cyan]Interactive mode (no arguments):[/bold cyan]
  • Shows list of all connected boards
  • Use arrow keys to select
  • Press Enter to switch

[bold cyan]Related:[/bold cyan]
  replx status                [dim]# See all active connections[/dim]"""
        OutputHelper.print_panel(help_text, title="fg", border_style="help")
        console.print()
        raise typer.Exit()
    
    global_opts = _get_global_options()
    port = global_opts.get('port')
    
    if port:
        # reuse the same connect-if-needed flow every other explicit-port command
        # uses (starts the agent, connects as fg/bg as appropriate); it never
        # touches the default port, only `setup` does.
        _ensure_connected()

        switch_target = port
        target_agent_port = _get_current_agent_port()

        sessions_data, _current_ppid, _error = _get_session_list_data()
        if sessions_data and not _error:
            needle = str(switch_target).strip().lower() if IS_WINDOWS else str(switch_target).strip()
            for key, conn_info in sessions_data.get('connections', {}).items():
                if not isinstance(key, str):
                    continue
                key_cmp = key.strip().lower() if IS_WINDOWS else key.strip()
                if key_cmp == needle:
                    switch_target = key
                    target_agent_port = conn_info.get('agent_port', target_agent_port)
                    break

        try:
            with AgentClient(port=target_agent_port) as client:
                result = client.send_command('session_switch_fg', port=switch_target, timeout=3.0)

            if result and result.get('success'):
                OutputHelper.print_panel(
                    f"Switched foreground to [bright_green]{OutputHelper.format_port(switch_target)}[/bright_green]",
                    title="Foreground Switched",
                    border_style="success"
                )
            else:
                OutputHelper.print_panel(
                    f"Failed to switch foreground: {(result or {}).get('error', 'No response from agent')}",
                    title="Error",
                    title_align="left",
                    border_style="error"
                )
        except Exception as e:
            OutputHelper.print_panel(
                f"Failed to switch foreground: {str(e)}",
                title="Error",
                title_align="left",
                border_style="error"
            )
        return
    
    sessions_data, current_ppid, error = _get_session_list_data()

    if _handle_session_list_error(
        error,
        no_server_title="No Connections",
        no_server_message="Agent is not running. No active connections.",
        no_sessions_title="No Connections",
        no_sessions_message="No active connections.",
    ):
        raise typer.Exit()
    
    selected_port, action = _print_session_list_interactive(sessions_data, current_ppid)
    
    if selected_port:
        target_agent_port = sessions_data.get('connections', {}).get(selected_port, {}).get('agent_port', _get_current_agent_port())
        try:
            with AgentClient(port=target_agent_port) as client:
                result = client.send_command('session_switch_fg', port=selected_port, timeout=3.0)
            
            if result and result.get('success'):
                OutputHelper.print_panel(
                    f"Switched foreground to [bright_green]{OutputHelper.format_port(selected_port)}[/bright_green]",
                    title="Foreground Switched",
                    border_style="success"
                )
            else:
                OutputHelper.print_panel(
                    f"Failed to switch foreground: {(result or {}).get('error', 'No response from agent')}",
                    title="Error",
                    title_align="left",
                    border_style="error"
                )
        except Exception as e:
            OutputHelper.print_panel(
                f"Failed to switch foreground: {str(e)}",
                title="Error",
                title_align="left",
                border_style="error"
            )


@app.command(rich_help_panel="Connection & Session")
def whoami(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = Console(width=CONSOLE_WIDTH)
        help_text = """\
Show which board your commands are currently talking to.

Quickly check your active foreground connection.

[bold cyan]Usage:[/bold cyan]
  replx whoami

[bold cyan]Output shows:[/bold cyan]
  • Serial port
  • MicroPython version
  • Chip type (RP2350, ESP32, etc.)
  • Device name
  • Manufacturer

[bold cyan]Example output:[/bold cyan]
  COM19  1.29.0  RP2350  ticle  Raspberry Pi

[bold cyan]Note:[/bold cyan]
  This command ignores -p/--port option.
  It always shows the current session's foreground.

[bold cyan]Related:[/bold cyan]
  replx status            [dim]# See all active connections[/dim]"""
        OutputHelper.print_panel(help_text, title="whoami", border_style="help")
        console.print()
        raise typer.Exit()
    
    sessions_data, current_ppid, error = _get_session_list_data()

    if _handle_session_list_error(
        error,
        no_server_title="No Connection",
        no_server_message="Not connected.",
        no_sessions_title="No Connection",
        no_sessions_message="Not connected.",
    ):
        raise typer.Exit()
    
    current_session = None
    for sess in sessions_data['sessions']:
        if sess.get('is_current'):
            current_session = sess
            break
    
    if not current_session or not current_session.get('foreground'):
        OutputHelper.print_panel(
            "No foreground connection in current session.",
            title="No Foreground",
            border_style="neutral"
        )
        raise typer.Exit()
    
    fg_port = current_session['foreground']
    conn_info = sessions_data['connections'].get(fg_port, {})
    
    version = conn_info.get('version', '?')
    core = conn_info.get('core', '?')
    device = conn_info.get('device', '?')
    manufacturer = conn_info.get('manufacturer', '')
    
    OutputHelper.print_panel(
        f"[green]󱓥[/green]  [bright_cyan]{OutputHelper.format_port(fg_port)}[/bright_cyan]  {version}  [bright_green]{core}[/bright_green]  [bright_yellow]{device}[/bright_yellow]  [dim]{manufacturer}[/dim]",
        title="Foreground",
        border_style="success"
    )


@app.command(
    rich_help_panel="Connection & Session",
    help="Close the foreground serial connection, or use PORT close for a specific board. The agent remains running; use 'replx agent stop' to stop it.",
)
def close(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        help_text = """\
Close the current foreground board connection without stopping the replx agent.

[bold cyan]Usage:[/bold cyan]
  replx close                  [dim]# Close the current foreground board[/dim]
  replx --port [yellow]PORT[/yellow] close     [dim]# Close a selected board[/dim]
  replx [yellow]PORT[/yellow] close            [dim]# Shortcut for --port PORT[/dim]

[bold cyan]Examples:[/bold cyan]
  replx close
  replx COM3 close
  replx --port COM3 close

[bold cyan]Notes:[/bold cyan]
  Without --port, closes this client's current foreground connection.
  With --port, closes that board connection for this client.
  The agent remains running. Use [yellow]replx agent stop[/yellow] to stop the agent."""
        OutputHelper.print_panel(help_text, title="close", border_style="help")
        Console(width=CONSOLE_WIDTH).print()
        raise typer.Exit()

    global_opts = _get_global_options()
    port = global_opts.get('port')
    target_agent_port = _get_current_agent_port()
    sessions_data = None
    
    if not port:
        sessions_data, current_ppid, error = _get_session_list_data()

        if _handle_session_list_error(
            error,
            no_server_title="No Connection",
            no_server_message="Not connected to any device.",
            no_sessions_title="No Connection",
            no_sessions_message="Not connected to any device.",
        ):
            raise typer.Exit()

        if not sessions_data:
            OutputHelper.print_panel(
                "Not connected to any device.",
                title="No Connection",
                border_style="neutral"
            )
            raise typer.Exit()
        
        for sess in sessions_data['sessions']:
            if sess.get('is_current') and sess.get('foreground'):
                port = sess['foreground']
                break
    elif not sessions_data:
        sessions_data, _current_ppid, _error = _get_session_list_data()
    
    if not port:
        OutputHelper.print_panel(
                "No foreground connection to close.",
            title="No Connection",
            border_style="neutral"
        )
        raise typer.Exit()

    if sessions_data:
        target_agent_port = sessions_data.get('connections', {}).get(port, {}).get('agent_port', target_agent_port)
    
    try:
        with AgentClient(port=target_agent_port) as client:
            result = client.send_command('session_disconnect', port=port, timeout=3.0)
        
        if result.get('freed_port'):
            OutputHelper.print_panel(
                f"Closed [bright_blue]{OutputHelper.format_port(port)}[/bright_blue]",
                title="Connection Closed",
                border_style="success"
            )
        else:
            OutputHelper.print_panel(
                f"Failed to close connection: {result.get('error', 'Unknown error')}",
                title="Error",
                title_align="left",
                border_style="error"
            )
    except Exception as e:
        OutputHelper.print_panel(
            f"Failed to close connection: {str(e)}",
            title="Error",
            title_align="left",
            border_style="error"
        )


def _stop_agent():
    env_path = _find_env_file()
    agent_ports = _find_running_agent_ports(env_path, persist_config=False)
    agent_host = AgentPortManager._read_registered_ip(persist_config=False)
    current_agent_port = AgentPortManager._read_registered_port(
        persist_config=False
    )

    try:
        AgentClient._get_auth_token(agent_host)
    except RuntimeError as exc:
        OutputHelper.print_panel(str(exc), title="Agent Authentication Required", border_style="error")
        raise typer.Exit(1)

    if current_agent_port not in agent_ports and AgentClient.is_agent_running(
        port=current_agent_port, host=agent_host
    ):
        agent_ports.insert(0, current_agent_port)

    try:
        stopped_ports = []
        killed_ports = []
        failed_ports = []

        for agent_port in agent_ports:
            was_running = AgentClient.is_agent_running(port=agent_port, host=agent_host)
            stopped = AgentClient.stop_agent(port=agent_port, host=agent_host) if was_running else False

            if stopped:
                stopped_ports.append(agent_port)
                continue

            killed = (
                AgentPortManager._kill_agent_process_by_port(agent_port)
                if AgentPortManager._is_local_ip(agent_host)
                else False
            )
            if killed:
                killed_ports.append(agent_port)
            elif was_running:
                failed_ports.append(agent_port)

        if stopped_ports or killed_ports:
            total = len(stopped_ports) + len(killed_ports)
            detail = f"Stopped {total} replx agent(s)."
            if failed_ports:
                detail += f"\n[dim]Failed ports: {', '.join(str(p) for p in failed_ports)}[/dim]"
            OutputHelper.print_panel(
                f"Stopped agent at {agent_host}; its board connections were released.\n{detail}\n"
                "[dim]Run a device command to start a local agent, or use 'replx agent connect IP'.[/dim]",
                title="Agent Stopped",
                border_style="success"
            )
        elif not agent_ports:
            OutputHelper.print_panel(
                f"Agent at {agent_host}:{current_agent_port} is already stopped.\n"
                "[dim]Run a device command to start a local agent, or use 'replx agent connect IP'.[/dim]",
                title="Agent Already Stopped",
                border_style="neutral"
            )
        else:
            OutputHelper.print_panel(
                "Failed to stop agent cleanly.\n"
                f"[dim]Ports still active at {agent_host}: {', '.join(str(p) for p in failed_ports)}[/dim]",
                title="Agent Stop Failed",
                border_style="error"
            )
    except Exception as e:
        OutputHelper.print_panel(
            f"Failed to stop agent: {str(e)}",
            title="Agent Stop Failed",
            border_style="error"
        )


@app.command(rich_help_panel="Device Management")
def format(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = Console(width=CONSOLE_WIDTH)
        help_text = """\
Format (erase) the filesystem on the connected device.

[bold yellow]⚠ WARNING: This deletes ALL files on the device![/bold yellow]

[bold cyan]Usage:[/bold cyan]
  replx format

[bold cyan]What happens:[/bold cyan]
  • All files are deleted (boot.py, main.py, /lib, everything)
  • Filesystem is reformatted to empty state
  • Device may reset automatically after format

[bold cyan]When to use:[/bold cyan]
  • To start fresh with a clean device
  • If filesystem is corrupted
  • Before selling/giving away a device
  • To free up all storage space

[bold cyan]Before formatting:[/bold cyan]
  Back up any important files:
  replx get /*.py ./backup
  replx get /lib ./backup

[bold cyan]After formatting:[/bold cyan]
  • Device has empty filesystem
    • Reinstall libraries: [green]replx pkg update core.all[/green]
    • Install device libs: [green]replx pkg update device.all[/green]
  • Or use [green]replx init[/green] instead (format + install)

[bold cyan]Related:[/bold cyan]
  replx init              [dim]# Format AND install libraries[/dim]"""
        OutputHelper.print_panel(help_text, title="format", border_style="help")
        console.print()
        raise typer.Exit()
    
    _ensure_connected()
    
    global _is_stop_spinner

    _is_stop_spinner = False
    frame_idx = [0]
    
    def _spinner_task(live):
        try:
            while not _is_stop_spinner:
                live.update(OutputHelper.create_spinner_panel(
                    f"Formatting file system on {STATE.device}...",
                    title="Format File System",
                    frame_idx=frame_idx[0]
                ))
                frame_idx[0] += 1
                time.sleep(0.1)
        except Exception:
            pass
    
    ret = None
    error = None
    
    try:
        with Live(OutputHelper.create_spinner_panel(
            f"Formatting file system on {STATE.device}...",
            title="Format File System",
            frame_idx=0
        ), console=OutputHelper._console, refresh_per_second=10) as live:
            spinner_thread = threading.Thread(target=_spinner_task, args=(live,), daemon=True)
            spinner_thread.start()
            
            try:
                client = _create_agent_client()
                result = client.send_command('format')
                ret = result.get('formatted', True) if result else None
            except Exception as e:
                error = e
            finally:
                _is_stop_spinner = True
                spinner_thread.join(timeout=1.0)
    
    except KeyboardInterrupt:
        _is_stop_spinner = True
        OutputHelper.print_panel(
            "Format operation cancelled by user.",
            title="Format Cancelled",
            border_style="error"
        )
        return False
    
    if error:
        OutputHelper.print_panel(
            f"Format failed: [red]{error}[/red]",
            title="Format Failed",
            border_style="error"
        )
        return False
    
    if ret:
        if STATE.core == 'EFR32MG':
            try:
                time.sleep(1.0)
                
                client = _create_agent_client()
                global_opts = _get_global_options()
                client.send_command('connect', port=global_opts.get('port'))
            except Exception:
                pass
        
        OutputHelper.print_panel(
            f"File system on [bright_yellow]{STATE.device}[/bright_yellow] has been formatted successfully.",
            title="Format Complete",
            border_style="success"
        )
    else:
        OutputHelper.print_panel(
            f"Device [red]{STATE.device}[/red] does not support formatting.",
            title="Format Failed",
            border_style="error"
        )
    return ret


@app.command(rich_help_panel="Device Management")
def init(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = Console(width=CONSOLE_WIDTH)
        help_text = """\
Completely reset device: format filesystem and install all libraries.

[bold cyan]Usage:[/bold cyan]
  replx init

[bold cyan]What happens:[/bold cyan]
  1. [yellow]Format:[/yellow] Erases entire filesystem
  2. [yellow]Install:[/yellow] Installs core libraries for your chip
  3. [yellow]Install:[/yellow] Installs device-specific libraries

[bold cyan]When to use:[/bold cyan]
  • First-time setup of a new device
  • Resetting device to known working state
  • After MicroPython firmware update
  • When libraries are corrupted

[bold cyan]Before init:[/bold cyan]
  Back up any custom code:
  replx get /*.py ./backup

[bold cyan]After init:[/bold cyan]
  • Device has fresh libraries installed
  • Ready for your code: [green]replx put main.py /[/green]
  • Or set up workspace: [green]replx setup[/green]

[bold cyan]Equivalent to:[/bold cyan]
  replx pkg download          [dim]# Download libraries (if needed)[/dim]
  replx format                [dim]# Erase device storage[/dim]
  replx pkg update core.all   [dim]# Install all core libs[/dim]
  replx pkg update device.all [dim]# Install all device libs[/dim]

[bold cyan]Related:[/bold cyan]
  replx format                [dim]# Just erase (no install)[/dim]
  replx pkg update core.all   [dim]# Just install core (no format)[/dim]
  replx pkg update device.all [dim]# Just install device (no format)[/dim]"""
        OutputHelper.print_panel(help_text, title="init", border_style="help")
        console.print()
        raise typer.Exit()
    
    _ensure_connected()
    
    _pkg_client = _create_agent_client()
    try:
        store_status = _pkg_client.send_command('pkg_store_status', timeout=30.0)
    except Exception:
        store_status = {}
    store_status = store_status or {}
    
    if not store_status.get('meta'):
        OutputHelper.print_panel(
            "[red]Local store is not ready.[/red]\n\n"
            "The package registry is missing. Please run:\n"
            "  [cyan]replx pkg download[/cyan]\n\n"
            "This will download the required libraries to local store.",
            title="Initialization Failed",
            border_style="error"
        )
        raise typer.Exit(1)
    
    if not store_status.get('core_src'):
        OutputHelper.print_panel(
            f"[red]Core library for '{STATE.core}' not found.[/red]\n\n"
            "The core library is required for initialization. Please run:\n"
            "  [cyan]replx pkg download[/cyan]\n\n"
            "This will download the required libraries to local store.",
            title="Initialization Failed",
            border_style="error"
        )
        raise typer.Exit(1)
    
    console = Console(width=CONSOLE_WIDTH)
    
    def make_format_panel(message: str, title: str = "Formatting") -> Panel:
        spinner = Spinner("dots", text=f" {message}")
        return Panel(spinner, title=title, title_align="left", border_style=OutputHelper._resolve_category_color('data'),
                     box=get_panel_box(), width=CONSOLE_WIDTH)
    
    try:
        with Live(make_format_panel("Formatting file system..."), 
                  console=console, refresh_per_second=10) as live:
            client = _create_agent_client()
            result = client.send_command('format')
            format_result = result.get('formatted', True) if result else None
            
            if not format_result:
                live.stop()
                OutputHelper.print_panel(
                    "Initialization failed: Format operation was unsuccessful.",
                    title="Initialization Failed",
                    border_style="error"
                )
                return False
            
            live.update(make_format_panel("Reconnecting to device..."))
            
            global_opts = _get_global_options()
            explicit_port = global_opts.get('port')
            
            conn = _resolve_connection(explicit_port)
            if not conn:
                raise RuntimeError("No connection configuration found")
            
            agent_port = conn.get('agent_port', DEFAULT_AGENT_PORT)
            port = conn['connection']
            core = conn.get('core') or STATE.core
            device = conn.get('device') or STATE.device
            
            client = AgentClient(port=agent_port)
            
            needs_reconnect = (core == "EFR32MG")
            
            if needs_reconnect:
                was_foreground = True
                try:
                    session_info = client.send_command('session_info', timeout=1.0)
                    current_ppid = get_cached_session_id()
                    for sess in session_info.get('sessions', []):
                        if sess.get('ppid') == current_ppid:
                            fg_port = sess.get('foreground')
                            if fg_port:
                                was_foreground = (fg_port == port)
                            else:
                                bg_ports = sess.get('backgrounds', [])
                                was_foreground = not (port and port in bg_ports)
                            break
                except Exception:
                    pass
                try:
                    client.send_command('disconnect_port', port=port)
                except Exception:
                    pass
                
                time.sleep(3.0)
                
                live.update(make_format_panel("Reconnecting..."))
                if not AgentClient.is_agent_running(port=agent_port):
                    AgentClient.start_agent(port=agent_port)
                    time.sleep(0.5)
                
                live.update(make_format_panel("Verifying connection..."))
                last_error = None
                for attempt in range(3):
                    try:
                        client = AgentClient(port=agent_port, device_port=port if port else None)
                        resp = client.send_command('session_setup', port=port,
                                                   core=core, device=device, as_foreground=was_foreground)
                        if resp.get('connected'):
                            STATE.core = resp.get('core', core)
                            STATE.device = resp.get('device', device)
                            STATE.device_root_fs = resp.get('device_root_fs', STATE.device_root_fs)
                            set_global_context(STATE.core, STATE.device, STATE.version, STATE.device_root_fs, STATE.device_path)
                            break
                        last_error = RuntimeError(f"Reconnect failed: {resp}")
                    except Exception as e:
                        last_error = e
                    
                    if attempt < 2:
                        time.sleep(2.0)
                else:
                    raise last_error or RuntimeError("Reconnect failed after 3 attempts")
            
            live.update(Panel(
                f"[green]\u2713[/green] File system on [bright_yellow]{STATE.device}[/bright_yellow] formatted successfully.",
                title="Format Complete", title_align="left", border_style=OutputHelper._resolve_category_color('success'),
                box=get_panel_box(), width=CONSOLE_WIDTH
            ))
    
    except Exception as e:
        OutputHelper.print_panel(
            f"Format failed: [red]{e}[/red]",
            title="Format Failed",
            border_style="error"
        )
        return False
    
    install_stats = {}
    
    try:
        specs_to_install = ["core.all"]

        from .package import _install_spec_internal
        
        if store_status.get('device_src'):
            specs_to_install.append("device.all")
        
        from rich.panel import Panel as RichPanel
        initial_panel = RichPanel(
            "Preparing installation...",
            title="Installing", title_align="left", border_style=OutputHelper._resolve_category_color('data'),
            box=get_panel_box(), width=CONSOLE_WIDTH
        )
        
        with Live(initial_panel, console=console, refresh_per_second=10) as live:
            for spec_item in specs_to_install:
                result = _install_spec_internal(spec_item, live=live, update_callback=lambda p: live.update(p))
                if result:
                    install_stats[spec_item] = result
            
            summary_parts = []
            for spec_key in ["core.all", "device.all"]:
                if spec_key in install_stats:
                    stats = install_stats[spec_key]
                    summary_parts.append(f"🔧 {spec_key} {stats['files']} file(s) {OutputHelper.format_bytes(stats['bytes'])}")
            
            summary_line = "    ".join(summary_parts)
            live.update(RichPanel(
                summary_line,
                title="Installation Complete", title_align="left", border_style=OutputHelper._resolve_category_color('success'),
                box=get_panel_box(), width=CONSOLE_WIDTH
            ))
        
    except Exception as e:
        OutputHelper.print_panel(
            f"Initialization failed during install: [red]{e}[/red]",
            title="Initialization Failed",
            border_style="error"
        )
        return False
    
    OutputHelper.print_panel(
        f"Device [bright_yellow]{STATE.device}[/bright_yellow] has been initialized successfully.\n"
        "The device is now ready to use.",
        title="Complete",
        border_style="success"
    )
    return True
