import os
import sys
import threading
from typing import Optional

import typer

from .agent.client import AgentClient, get_cached_session_id
from .helpers import OutputHelper, set_global_context
from .config import (
    STATE,
    _find_env_file, _find_or_create_vscode_dir,
    _find_available_agent_port,
    _update_connection_config, _get_default_connection,
    _find_agent_for_connection,
    _resolve_connection,
    _get_global_options,
    AgentPortManager,
)

def _print_connect_info(
    port: str,
    version: str,
    core: str,
    device: str,
    manufacturer: str = "",
    *,
    auto: bool = False,
):
    port_disp = OutputHelper.format_port(port)
    OutputHelper.print_panel(
        f"[bright_green]{port_disp}[/bright_green]  {version}  {core}  [bright_green]{device}[/bright_green]  [dim]{manufacturer}[/dim]",
        title="Auto-connected" if auto else "Connected",
        border_style="neutral"
    )


def _is_transport_connection_error(e: Exception) -> bool:
    """Return True if the error indicates a physical board disconnect / serial port failure."""
    msg = str(e).lower()
    return any(kw in msg for kw in (
        'failed to create connection',
        'failed to open serial',
        'transporterror',
        'transport error',
        'cannot configure port',
        'i/o operation',
        'connection lost',
        'connection removed',
        'disconnectederror',
    ))


def _handle_connection_error(e: Exception, port: str = None, stop_agent: bool = False, agent_port: int = None):
    conn_info = OutputHelper.format_port(port) if port else "unknown"
    
    error_detail = str(e)
    if error_detail:
        error_msg = (
            f"Connection failure on configured device ([bright_blue]{conn_info}[/bright_blue]).\n\n"
            f"[yellow]Error details:[/yellow] {error_detail}\n\n"
            "Please check:\n"
            "  • Device is powered on and connected\n"
            "  • Serial cable is properly attached\n"
            "  • Port is not in use by another program (PuTTY, Arduino IDE, etc.)\n\n"
            "[dim]Run 'replx --port PORT setup' to reconfigure if needed.[/dim]"
        )
    else:
        error_msg = (
            f"Connection failure on configured device ([bright_blue]{conn_info}[/bright_blue]).\n\n"
            "Please check:\n"
            "  • Device is powered on and connected\n"
            "  • Serial cable is properly attached\n"
            "  • Port is not in use by another program (PuTTY, Arduino IDE, etc.)\n\n"
            "[dim]Run 'replx --port PORT setup' to reconfigure if needed.[/dim]"
        )
    
    OutputHelper.print_panel(
        error_msg,
        title="Connection Error",
        border_style="error"
    )


def _ensure_connected(
    ctx: typer.Context = None,
    client: Optional[AgentClient] = None,
) -> dict:
    global_opts = _get_global_options()
    explicit_port = global_opts.get('port')

    env_path = _find_env_file()
    default_conn = _get_default_connection(env_path) if env_path else None

    agent_port = _find_available_agent_port(env_path)

    global _cached_agent_port
    with _agent_port_cache_lock:
        if _cached_agent_port is None:
            _cached_agent_port = agent_port

    if client is not None and client.agent_port != agent_port:
        client.disconnect()
        client.agent_port = agent_port

    target_port = explicit_port or default_conn
    if target_port:
        running_agent_port = _find_agent_for_connection(
            target_port,
            env_path,
            preferred_port=agent_port,
            client=client,
        )
        if running_agent_port is not None:
            agent_port = running_agent_port
            with _agent_port_cache_lock:
                _cached_agent_port = agent_port
            if client is not None and client.agent_port != agent_port:
                client.disconnect()
                client.agent_port = agent_port
    
    agent_running = (
        client.ping()
        if client is not None
        else AgentClient.is_agent_running(port=agent_port)
    )
    if not agent_running:
        if client is not None:
            client.disconnect()

        if not explicit_port:
            if not default_conn:
                OutputHelper.print_panel(
                    "No default connection configured.\n\n"
                    "Run [bright_blue]replx --port PORT setup[/bright_blue] first.\n\n"
                    "Examples:\n"
                    "  [bright_green]replx --port COM3 setup[/bright_green]\n"
                    "  [bright_green]replx --port /dev/ttyACM0 setup[/bright_green]",
                    title="Setup Required",
                    border_style="error"
                )
                raise typer.Exit(1)
            
            conn = _resolve_connection(default_conn)
        else:
            conn = _resolve_connection(explicit_port)
        
        if not conn:
            OutputHelper.print_panel(
                "No connection configuration found.\n\n"
                "Run [bright_blue]replx --port PORT setup[/bright_blue] first.",
                title="Setup Required",
                border_style="error"
            )
            raise typer.Exit(1)
        
        try:
            AgentClient.start_agent(port=agent_port)
            AgentPortManager._singleton_cache = agent_port
            AgentPortManager._singleton_cache_miss = False

            if default_conn:
                with AgentClient(port=agent_port) as client:
                    client.send_command('set_default', port=default_conn, timeout=1.0)
        except Exception as e:
            OutputHelper.print_panel(f"Failed to start agent: {str(e)}", title="Agent Error", title_align="left", border_style="error")
            raise typer.Exit(1)
        
        try:
            port_arg = conn['connection']
            
            with AgentClient(port=agent_port) as client:
                result = client.send_command(
                    'session_setup',
                    port=port_arg,
                    core=conn.get('core') or "RP2350",
                    device=conn.get('device'),
                    as_foreground=True,
                    set_default=False,
                    local_default=default_conn,
                )
            
            if result.get('switched_from'):
                OutputHelper.print_panel(
                    f"Auto-disconnected [yellow]{result['switched_from']}[/yellow] (same board)",
                    title="Connection Switched",
                    border_style="neutral"
                )
            
            STATE.core = result.get('core', conn.get('core', ''))
            STATE.device = result.get('device', conn.get('device', 'unknown'))
            STATE.version = result.get('version', '?')
            STATE.manufacturer = result.get('manufacturer', '')
            STATE.device_root_fs = result.get('device_root_fs', '/')
            
            _print_connect_info(
                conn['connection'],
                STATE.version,
                STATE.core,
                STATE.device,
                STATE.manufacturer,
                auto=not bool(explicit_port),
            )
            
        except Exception as e:
            _handle_connection_error(e, port=port_arg, stop_agent=True, agent_port=agent_port)
            raise typer.Exit(1)
        
        if conn['source'] == 'global':
            if not env_path:
                vscode_dir = _find_or_create_vscode_dir()
                env_path = os.path.join(vscode_dir, '.replx')
            # Only `setup` may set the workspace default; a plain connect-on-demand
            # (e.g. `replx PORT ls` with no default configured yet) must only
            # register this port as the session's fg, never persist it as default.
            _update_connection_config(
                env_path, conn['connection'],
                version=STATE.version, core=STATE.core, device=STATE.device,
                manufacturer=STATE.manufacturer,
                set_default=False
            )
        
        set_global_context(STATE.core, STATE.device, STATE.version, STATE.device_root_fs, STATE.device_path)
        
        with AgentClient(port=agent_port, device_port=explicit_port) as client:
            status = client.send_command('status')
        return status
    
    try:
        if client is None:
            with AgentClient(port=agent_port) as status_client:
                status = status_client.send_command('status')
                session_info = status_client.send_command('session_info', timeout=1.0)
        else:
            status = client.send_command('status')
            session_info = client.send_command('session_info', timeout=1.0)

        def _port_norm(p: Optional[str]) -> str:
            if not p:
                return ""
            if sys.platform.startswith("win"):
                return p.upper()
            return p
        
        current_ppid = get_cached_session_id()
        current_fg = None
        current_bgs = []
        
        sessions = session_info.get('sessions', [])
        if any('is_current' in session for session in sessions):
            current_sessions = [session for session in sessions if session.get('is_current')]
        else:
            current_sessions = [session for session in sessions if session.get('ppid') == current_ppid]

        for session in current_sessions:
            if session.get('ppid') is not None:
                current_fg = session.get('foreground')
                current_bgs = session.get('backgrounds', [])
                break
        
        if not current_fg:
            if not explicit_port:
                if not default_conn:
                    OutputHelper.print_panel(
                        "No active foreground connection and no default configured.\n\n"
                        "Run [bright_blue]replx --port PORT setup[/bright_blue] first,\n"
                        "or specify a port with [bright_blue]--port PORT[/bright_blue].",
                        title="No Connection",
                        border_style="error"
                    )
                    raise typer.Exit(1)
                
                fg_conn = _resolve_connection(default_conn)
                if not fg_conn:
                    OutputHelper.print_panel(
                        "No connection available.\n\n"
                        "Run [bright_blue]replx --port PORT setup[/bright_blue] first.",
                        title="Setup Required",
                        border_style="error"
                    )
                    raise typer.Exit(1)
                
                port_arg = fg_conn['connection']
                
                with AgentClient(port=agent_port) as client:
                    result = client.send_command(
                        'session_setup',
                        port=port_arg,
                        core=fg_conn.get('core') or "RP2350",
                        device=fg_conn.get('device'),
                        as_foreground=True,
                        set_default=False,
                        local_default=default_conn,
                    )
                
                if result.get('switched_from'):
                    OutputHelper.print_panel(
                        f"Auto-disconnected [yellow]{result['switched_from']}[/yellow] (same board)",
                        title="Connection Switched",
                        border_style="neutral"
                    )
                
                _print_connect_info(
                    fg_conn['connection'],
                    result.get('version', '?'),
                    result.get('core', fg_conn.get('core', '?')),
                    result.get('device', fg_conn.get('device', '?')),
                    result.get('manufacturer', ''),
                    auto=True,
                )
                
                status = result
                status['connected'] = True
                current_fg = fg_conn['connection']
            else:
                fg_conn = _resolve_connection(explicit_port)
                if not fg_conn:
                    OutputHelper.print_panel(
                        "No connection configuration found.\n\n"
                        "Run [bright_blue]replx --port PORT setup[/bright_blue] first.",
                        title="Setup Required",
                        border_style="error"
                    )
                    raise typer.Exit(1)
                
                port_arg = fg_conn['connection']
                
                with AgentClient(port=agent_port) as client:
                    result = client.send_command(
                        'session_setup',
                        port=port_arg,
                        core=fg_conn.get('core') or "RP2350",
                        device=fg_conn.get('device'),
                        as_foreground=True,
                        set_default=False,
                        local_default=default_conn,
                    )
                
                if result.get('switched_from'):
                    OutputHelper.print_panel(
                        f"Auto-disconnected [yellow]{result['switched_from']}[/yellow] (same board)",
                        title="Connection Switched",
                        border_style="neutral"
                    )
                
                if fg_conn.get('source') == 'global':
                    if not env_path:
                        vscode_dir = _find_or_create_vscode_dir()
                        env_path = os.path.join(vscode_dir, '.replx')
                    _update_connection_config(
                        env_path, fg_conn['connection'],
                        version=result.get('version', fg_conn.get('version')),
                        core=result.get('core', fg_conn.get('core')),
                        device=result.get('device', fg_conn.get('device')),
                        manufacturer=result.get('manufacturer', fg_conn.get('manufacturer')),
                        set_default=False
                    )
                
                _print_connect_info(
                    fg_conn['connection'],
                    result.get('version', '?'),
                    result.get('core', fg_conn.get('core', '?')),
                    result.get('device', fg_conn.get('device', '?')),
                    result.get('manufacturer', ''),
                )
                
                status = result
                status['connected'] = True
                current_fg = fg_conn['connection']
                
                STATE.core = status.get('core', STATE.core)
                STATE.device = status.get('device', STATE.device)
                STATE.version = status.get('version', STATE.version)
                set_global_context(STATE.core, STATE.device, STATE.version, STATE.device_root_fs, STATE.device_path)
                
                return status

        if not explicit_port:
            STATE.core = status.get('core', STATE.core)
            STATE.device = status.get('device', STATE.device)
            STATE.version = status.get('version', STATE.version)
            STATE.device_root_fs = status.get('device_root_fs', STATE.device_root_fs)
            set_global_context(STATE.core, STATE.device, STATE.version, STATE.device_root_fs, STATE.device_path)
            
            return status
        
        if explicit_port:
            explicit_conn = _resolve_connection(explicit_port)
            if explicit_conn:
                explicit_key = explicit_conn['connection']
                if _port_norm(explicit_key) != _port_norm(current_fg) and _port_norm(explicit_key) not in [_port_norm(bg) for bg in current_bgs]:
                    port_arg = explicit_conn['connection']
                    
                    try:
                        with AgentClient(port=agent_port) as client:
                            bg_result = client.send_command(
                                'session_setup',
                                port=port_arg,
                                core=explicit_conn.get('core') or "RP2350",
                                device=explicit_conn.get('device'),
                                as_foreground=False,  # bg로 추가
                                set_default=False,
                            )

                        if bg_result and not bg_result.get('existing', False):
                            _print_connect_info(
                                port_arg,
                                bg_result.get('version', explicit_conn.get('version', '?')),
                                bg_result.get('core', explicit_conn.get('core', '?')),
                                bg_result.get('device', explicit_conn.get('device', '?')),
                                bg_result.get('manufacturer', explicit_conn.get('manufacturer', '')),
                            )
                        
                        if bg_result.get('switched_from'):
                            OutputHelper.print_panel(
                                f"Auto-disconnected [yellow]{bg_result['switched_from']}[/yellow] (same board)",
                                title="Connection Switched",
                                border_style="neutral"
                            )
                        
                        if not env_path:
                            vscode_dir = _find_or_create_vscode_dir()
                            env_path = os.path.join(vscode_dir, '.replx')
                        _update_connection_config(
                            env_path, explicit_conn['connection'],
                            version=bg_result.get('version', explicit_conn.get('version')),
                            core=bg_result.get('core', explicit_conn.get('core')),
                            device=bg_result.get('device', explicit_conn.get('device')),
                            manufacturer=bg_result.get('manufacturer', explicit_conn.get('manufacturer')),
                            set_default=False
                        )
                    except Exception as e:
                        _handle_connection_error(e, port=port_arg)
                        raise typer.Exit(1)
        
        if explicit_port:
            if client is None:
                with AgentClient(port=agent_port, device_port=explicit_port) as status_client:
                    status = status_client.send_command('status')
            else:
                status = client.send_command('status', port=explicit_port)
        
        STATE.core = status.get('core', STATE.core)
        STATE.device = status.get('device', STATE.device)
        STATE.version = status.get('version', STATE.version)
        STATE.device_root_fs = status.get('device_root_fs', STATE.device_root_fs)
        set_global_context(STATE.core, STATE.device, STATE.version, STATE.device_root_fs, STATE.device_path)
        
        return status
        
    except typer.Exit:
        raise
    except Exception as e:
        if _is_transport_connection_error(e):
            OutputHelper.print_panel(
                "Board connection lost.\n\n"
                f"[yellow]Error:[/yellow] {str(e)}\n\n"
                "Please check the board is powered and connected, then try again.\n\n"
                "[dim]The next command will reconnect automatically.[/dim]",
                title="Connection Lost",
                border_style="error"
            )
        else:
            OutputHelper.print_panel(f"Agent error: {str(e)}", title="Error", border_style="error")
        raise typer.Exit(1)


_cached_agent_port: Optional[int] = None
_agent_port_cache_lock = threading.Lock()


def _get_current_agent_port() -> int:
    global _cached_agent_port
    if _cached_agent_port is not None:
        return _cached_agent_port
    with _agent_port_cache_lock:
        if _cached_agent_port is None:
            env_path = _find_env_file()
            _cached_agent_port = _find_available_agent_port(env_path)
    return _cached_agent_port


def _get_device_port() -> Optional[str]:
    global_opts = _get_global_options()
    if global_opts.get('port'):
        return global_opts.get('port')
    return None


def _create_agent_client(*, include_device_port: bool = True) -> AgentClient:
    device_port = _get_device_port() if include_device_port else None
    return AgentClient(port=_get_current_agent_port(), device_port=device_port)


__all__ = [
    '_handle_connection_error',
    '_ensure_connected',
    '_get_current_agent_port',
    '_get_device_port',
    '_create_agent_client',
]
