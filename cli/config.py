import os
import socket
import sys
import json
import ipaddress
import re
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any

from replx.utils.constants import AGENT_HOST, DEFAULT_AGENT_PORT, MIN_AGENT_PORT, MAX_AGENT_PORT

_write_port_lock = threading.Lock()


@dataclass
class RuntimeState:
    version: str = "?"
    core: str = ""
    device: str = ""
    manufacturer: str = ""
    device_root_fs: str = "/"
    core_path: str = ""
    device_path: str = ""


STATE = RuntimeState()

class GlobalOptions:
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._port = None
        return cls._instance
    
    @property
    def port(self) -> Optional[str]:
        return self._port
    
    @port.setter
    def port(self, value: Optional[str]):
        self._port = value
    
    def set(self, port: str = None):
        self._port = port
    
    def get(self) -> Dict[str, Any]:
        return {
            'port': self._port,
        }
    
    def clear(self):
        self._port = None


GLOBAL_OPTIONS = GlobalOptions()

class ConfigManager:
   
    @staticmethod
    def find_env_file() -> Optional[str]:
        current = os.path.realpath(os.getcwd())
        root = os.path.abspath(os.sep)
        
        visited = set()
        while current not in visited:
            visited.add(current)
            env_path = os.path.join(current, ".vscode", ".replx")
            if os.path.exists(env_path):
                return env_path
            parent = os.path.dirname(current)
            if parent == current or parent == root:
                break
            current = parent
        return None
    
    @staticmethod
    def find_or_create_vscode_dir() -> str:
        current = os.path.realpath(os.getcwd())
        vscode_dir = os.path.join(current, ".vscode")
        os.makedirs(vscode_dir, exist_ok=True)
        return vscode_dir
    
    @staticmethod
    def read(env_path: str) -> dict:
        result = {
            'connections': {},
            'default': None,
            'theme': None,
        }
        
        if not os.path.exists(env_path):
            return result
        
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            current_section = None
            
            for line in content.splitlines():
                line = line.strip()
                
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1].strip()
                    if current_section.upper() != 'DEFAULT':
                        result['connections'][current_section] = {}
                    continue
                
                if '=' in line and current_section:
                    key, value = line.split('=', 1)
                    key = key.strip().upper()
                    value = value.strip()
                    
                    if current_section.upper() == 'DEFAULT':
                        if key == 'CONNECTION':
                            result['default'] = value
                        elif key == 'THEME':
                            result['theme'] = value
                    else:
                        conn = result['connections'][current_section]
                        if key == 'VERSION':
                            conn['version'] = value
                        elif key == 'CORE':
                            conn['core'] = value
                        elif key == 'DEVICE':
                            conn['device'] = value
                        elif key == 'MANUFACTURER':
                            conn['manufacturer'] = value
                        elif key == 'SERIAL_PORT':
                            conn['serial_port'] = value
            
            return result
        except Exception:
            return result
    
    @staticmethod
    def write(
        env_path: str,
        connections: dict,
        default: Optional[str] = None,
        theme: Optional[str] = None,
        preserve_agent_metadata: bool = True,
    ):
        lines = []

        for conn_key, conn_data in connections.items():
            lines.append(f'[{conn_key}]')
            if conn_data.get('version'):
                lines.append(f"VERSION={conn_data['version']}")
            if conn_data.get('core'):
                lines.append(f"CORE={conn_data['core']}")
            if conn_data.get('device'):
                lines.append(f"DEVICE={conn_data['device']}")
            if conn_data.get('manufacturer'):
                lines.append(f"MANUFACTURER={conn_data['manufacturer']}")
            if conn_data.get('serial_port'):
                lines.append(f"SERIAL_PORT={conn_data['serial_port']}")
            lines.append('')

        if default:
            lines.append('[DEFAULT]')
            if default:
                lines.append(f'CONNECTION={default}')
            lines.append('')

        if preserve_agent_metadata:
            metadata_entries = AgentPortManager._read_agent_config(env_path)
            metadata_lines: list[str] = []
            for key in sorted(metadata_entries):
                upper_key = str(key).upper()
                if upper_key in AgentPortManager._METADATA_KEYS and metadata_entries.get(key) is not None:
                    metadata_lines.append(f"{key}={metadata_entries[key]}")
            if metadata_lines:
                if lines and lines[-1] != '':
                    lines.append('')
                lines.extend(metadata_lines)

        os.makedirs(os.path.dirname(env_path), exist_ok=True)

        with open(env_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    
    @staticmethod
    def get_connection(env_path: str, connection: str) -> Optional[dict]:
        env_data = ConfigManager.read(env_path)
        if not connection:
            return None

        if connection in env_data.get('connections', {}):
            return env_data['connections'][connection]

        if sys.platform.startswith("win"):
            needle = str(connection).lower()
            for key, value in env_data.get('connections', {}).items():
                if isinstance(key, str) and key.lower() == needle:
                    return value

        return None
    
    @staticmethod
    def update_connection(env_path: str, connection: str, version: str = None,
                          core: str = None, device: str = None,
                          manufacturer: str = None,
                          serial_port: str = None,
                          agent_port: int = None,
                          theme: str = None,
                          theme_mode: str = None,
                          set_default: bool = False):

        def _resolve_os_serial_port_name(port: str) -> str:
            if not port:
                return port
            p = str(port).strip()
            if sys.platform.startswith("win") and re.fullmatch(r"(?i)com\d+", p):
                return p.upper()
            return p

        desired_key = _resolve_os_serial_port_name(connection)

        env_data = ConfigManager.read(env_path)
        
        existing_key = None
        for key in env_data.get('connections', {}):
            if key == desired_key:
                existing_key = key
                break

        if existing_key is None and sys.platform.startswith("win") and desired_key:
            needle = str(desired_key).lower()
            for key in env_data.get('connections', {}):
                if isinstance(key, str) and key.lower() == needle:
                    existing_key = key
                    break

        conn_key = None
        if existing_key:
            if sys.platform.startswith("win") and desired_key and existing_key != desired_key:
                conns = env_data.get('connections', {})
                if desired_key in conns and desired_key != existing_key:
                    merged = dict(conns[desired_key] or {})
                    for k, v in (conns[existing_key] or {}).items():
                        if k not in merged:
                            merged[k] = v
                    conns[desired_key] = merged
                    try:
                        del conns[existing_key]
                    except KeyError:
                        pass
                else:
                    conns[desired_key] = conns.pop(existing_key)

                if env_data.get('default') == existing_key:
                    env_data['default'] = desired_key

                conn_key = desired_key
            else:
                conn_key = existing_key
        else:
            conn_key = desired_key
            env_data.setdefault('connections', {})[conn_key] = {}
        
        conn = env_data['connections'][conn_key]
        
        if version is not None:
            conn['version'] = version
        if core is not None:
            conn['core'] = core
        if device is not None:
            conn['device'] = device
        if manufacturer is not None:
            conn['manufacturer'] = manufacturer
        if serial_port is not None:
            conn['serial_port'] = serial_port
        
        if set_default:
            env_data['default'] = conn_key

        if theme is not None:
            AgentPortManager._write_registered_theme(theme)
            AgentPortManager._write_registered_theme_mode(theme_mode)
        
        ConfigManager.write(env_path, env_data['connections'], env_data['default'])
    
    @staticmethod
    def get_default(env_path: str) -> Optional[str]:
        env_data = ConfigManager.read(env_path)
        return env_data.get('default')

    @staticmethod
    def get_theme(env_path: str | None = None) -> str:
        theme_mode = AgentPortManager._read_registered_theme_mode()
        if theme_mode:
            return theme_mode

        theme = AgentPortManager._read_registered_theme(legacy_env_path=env_path)
        return theme or 'dark'

    @staticmethod
    def set_theme(env_path: str | None, theme: str, theme_mode: str | None = None):
        AgentPortManager._write_registered_theme(theme)
        AgentPortManager._write_registered_theme_mode(theme_mode)


class AgentPortManager:

    _AGENT_IP_KEY = 'AGENT_IP'
    _AGENT_PORT_KEY = 'AGENT_PORT'
    _THEME_KEY = 'THEME'
    _THEME_MODE_KEY = 'THEME_MODE'
    _PANEL_BOX_KEY = 'PANEL_BOX'
    _PANEL_COLORS_KEY = 'PANEL_COLORS'
    _METADATA_KEYS = {
        _AGENT_IP_KEY,
        _AGENT_PORT_KEY,
        _THEME_KEY,
        _THEME_MODE_KEY,
        _PANEL_BOX_KEY,
        _PANEL_COLORS_KEY,
    }

    @staticmethod
    def _kill_agent_process_by_port(port: int) -> bool:
        try:
            import psutil
        except Exception:
            return False

        try:
            for conn in psutil.net_connections(kind='tcp'):
                if conn.laddr and conn.laddr.port == port and conn.pid:
                    try:
                        psutil.Process(conn.pid).kill()
                        return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
        except Exception:
            return False

        return False

    @staticmethod
    def _pick_primary_port(
        running_ports: list[int],
        preferred_port: Optional[int] = None,
        *,
        persist_config: bool = True,
    ) -> Optional[int]:
        if not running_ports:
            return None

        registered_port = AgentPortManager._read_registered_port(
            persist_config=persist_config
        )
        for candidate in (preferred_port, registered_port, DEFAULT_AGENT_PORT):
            if isinstance(candidate, int) and candidate in running_ports:
                return candidate

        return min(running_ports)

    _singleton_cache: Optional[int] = None
    _singleton_cache_miss: bool = False

    @staticmethod
    def _ensure_singleton_running_agent(
        preferred_port: Optional[int] = None,
        *,
        persist_config: bool = True,
    ) -> Optional[int]:
        from .agent.client import AgentClient

        # Process-level cache: ``_ensure_connected`` calls this twice in the same
        # CLI invocation. The set of running agents cannot change between those
        # back-to-back calls, so reuse the prior result.
        if AgentPortManager._singleton_cache is not None:
            return AgentPortManager._singleton_cache
        if AgentPortManager._singleton_cache_miss:
            return None

        # Fast path: if the preferred / registered / default port already responds
        # to a ping, skip the slow scan-and-cleanup phase. Stale agent processes
        # left from previous sessions can otherwise add ~0.3s per dead candidate
        # (TCP connect timeout) on every CLI invocation. Singleton enforcement and
        # zombie cleanup still happen on cold paths (setup / shutdown) where the
        # priority candidate is unreachable.
        registered_port = AgentPortManager._read_registered_port(
            persist_config=persist_config
        )
        agent_host = AgentPortManager._read_registered_ip(
            persist_config=persist_config
        )
        checked_ports = set()
        for candidate in (preferred_port, registered_port, DEFAULT_AGENT_PORT):
            if not isinstance(candidate, int) or candidate in checked_ports:
                continue
            checked_ports.add(candidate)
            if AgentClient.is_agent_running(port=candidate, host=agent_host):
                AgentPortManager._singleton_cache = candidate
                if persist_config and registered_port != candidate:
                    AgentPortManager._write_registered_port(candidate)
                return candidate

        running_ports = []
        for port in AgentPortManager._get_candidate_agent_ports(
            preferred_port=preferred_port,
            persist_config=persist_config,
        ):
            if port in checked_ports:
                continue
            checked_ports.add(port)
            if AgentClient.is_agent_running(port=port, host=agent_host):
                running_ports.append(port)

        if not running_ports:
            AgentPortManager._singleton_cache_miss = True
            return None

        primary_port = AgentPortManager._pick_primary_port(
            running_ports,
            preferred_port=preferred_port,
            persist_config=persist_config,
        )
        if primary_port is None:
            AgentPortManager._singleton_cache_miss = True
            return None

        if persist_config:
            AgentPortManager._write_registered_port(primary_port)
        AgentPortManager._singleton_cache = primary_port
        return primary_port

    @staticmethod
    def _candidate_agent_config_files(env_path: str | None = None) -> list[str]:
        paths: list[str] = []
        seen: set[str] = set()

        def _append(path: Optional[str]) -> None:
            if not path:
                return
            normalized = os.path.abspath(path)
            if normalized not in seen:
                seen.add(normalized)
                paths.append(normalized)

        if env_path:
            _append(env_path)

        workspace_env = ConfigManager.find_env_file()
        if workspace_env:
            _append(workspace_env)

        legacy_config = os.path.join(os.path.expanduser('~'), '.replx', 'config')
        legacy_dot_config = os.path.join(os.path.expanduser('~'), '.replx', '.config')
        _append(legacy_dot_config)
        _append(legacy_config)

        legacy_port_file = os.path.join(os.path.expanduser('~'), '.replx', '.agent_port')
        _append(legacy_port_file)

        return paths

    @staticmethod
    def _agent_config_file(env_path: str | None = None) -> str:
        if env_path:
            return os.path.abspath(env_path)
        workspace_env = ConfigManager.find_env_file()
        if workspace_env:
            return workspace_env
        vscode_dir = ConfigManager.find_or_create_vscode_dir()
        return os.path.join(vscode_dir, '.replx')

    @staticmethod
    def _legacy_agent_port_file() -> str:
        return os.path.join(os.path.expanduser('~'), '.replx', '.agent_port')

    @staticmethod
    def ensure_agent_config(env_path: str | None = None) -> str:
        path = AgentPortManager._agent_config_file(env_path)
        entries = AgentPortManager._read_agent_config(env_path=path)
        changed = not os.path.exists(path)

        agent_ip = entries.get(AgentPortManager._AGENT_IP_KEY)
        if not agent_ip:
            entries[AgentPortManager._AGENT_IP_KEY] = AGENT_HOST
            changed = True

        try:
            port = int(entries.get(AgentPortManager._AGENT_PORT_KEY, ''))
        except (ValueError, TypeError):
            port = None
        if port is None:
            legacy_path = AgentPortManager._legacy_agent_port_file()
            try:
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    port = int(f.read().strip())
            except (OSError, ValueError):
                port = None
        if port is None or not 1 <= port <= MAX_AGENT_PORT:
            port = DEFAULT_AGENT_PORT
        if entries.get(AgentPortManager._AGENT_PORT_KEY) != str(port):
            entries[AgentPortManager._AGENT_PORT_KEY] = str(port)
            changed = True

        if changed:
            AgentPortManager._write_agent_config(entries, env_path=path)
        return path

    @staticmethod
    def _read_agent_config(env_path: str | None = None) -> dict[str, str]:
        result: dict[str, str] = {}
        current_section: Optional[str] = None

        for path in reversed(AgentPortManager._candidate_agent_config_files(env_path)):
            if not os.path.exists(path):
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for raw_line in f:
                        line = raw_line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if line.startswith('[') and line.endswith(']'):
                            current_section = line[1:-1].strip()
                            continue
                        if '=' not in line:
                            continue
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if not key:
                            continue
                        upper_key = key.upper()
                        if upper_key in AgentPortManager._METADATA_KEYS:
                            result[upper_key] = value
            except OSError:
                continue

        for env_key in ('AGENT_IP', 'AGENT_PORT'):
            env_value = os.environ.get(env_key)
            if env_value is not None and str(env_value).strip():
                result[env_key] = str(env_value).strip()

        return result

    @staticmethod
    def _write_agent_config(entries: dict[str, str], env_path: str | None = None) -> None:
        path = AgentPortManager._agent_config_file(env_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        env_data = ConfigManager.read(path)
        ConfigManager.write(
            path,
            env_data.get('connections', {}),
            env_data.get('default'),
            preserve_agent_metadata=False,
        )

        metadata_entries = {str(key).upper(): str(value).strip() for key, value in entries.items() if key and str(value).strip()}
        metadata_entries = {
            key: value for key, value in metadata_entries.items() if key in AgentPortManager._METADATA_KEYS
        }

        if metadata_entries:
            with open(path, 'a', encoding='utf-8') as f:
                for key in sorted(metadata_entries):
                    f.write(f'{key}={metadata_entries[key]}\n')

    @staticmethod
    def _read_registered_ip(*, persist_config: bool = True) -> Optional[str]:
        if persist_config:
            path = AgentPortManager.ensure_agent_config()
            entries = AgentPortManager._read_agent_config(env_path=path)
        else:
            entries = AgentPortManager._read_agent_config()
        value = entries.get(AgentPortManager._AGENT_IP_KEY)
        if value is None or not str(value).strip():
            return AGENT_HOST
        return str(value).strip()

    @staticmethod
    def _write_registered_ip(host: str) -> None:
        normalized = str(host).strip()
        if not normalized:
            raise ValueError('Agent IP cannot be empty')
        entries = AgentPortManager._read_agent_config()
        entries[AgentPortManager._AGENT_IP_KEY] = normalized
        AgentPortManager._write_agent_config(entries)

    @staticmethod
    def _read_registered_port(*, persist_config: bool = True) -> Optional[int]:
        if persist_config:
            path = AgentPortManager.ensure_agent_config()
            config_entries = AgentPortManager._read_agent_config(env_path=path)
        else:
            config_entries = AgentPortManager._read_agent_config()
        value = config_entries.get(AgentPortManager._AGENT_PORT_KEY)

        if value is None:
            legacy_path = AgentPortManager._legacy_agent_port_file()
            if os.path.exists(legacy_path):
                try:
                    with open(legacy_path, 'r', encoding='utf-8') as f:
                        value = f.read().strip()
                except OSError:
                    value = None

                if value:
                    config_entries[AgentPortManager._AGENT_PORT_KEY] = value
                    if persist_config:
                        AgentPortManager._write_agent_config(config_entries)

        try:
            port = int(value) if value is not None else DEFAULT_AGENT_PORT
        except (ValueError, TypeError):
            return DEFAULT_AGENT_PORT

        if 1 <= port <= MAX_AGENT_PORT:
            return port
        return DEFAULT_AGENT_PORT

    @staticmethod
    def _write_registered_port(port: int) -> None:
        if not isinstance(port, int) or not (1 <= port <= MAX_AGENT_PORT):
            return

        entries = AgentPortManager._read_agent_config()
        entries[AgentPortManager._AGENT_PORT_KEY] = str(port)
        AgentPortManager._write_agent_config(entries)

    @staticmethod
    def _read_registered_theme(legacy_env_path: Optional[str] = None) -> Optional[str]:
        config_entries = AgentPortManager._read_agent_config()
        theme = config_entries.get(AgentPortManager._THEME_KEY)
        if theme:
            return theme

        if legacy_env_path:
            legacy_theme = ConfigManager.read(legacy_env_path).get('theme')
            if legacy_theme:
                config_entries[AgentPortManager._THEME_KEY] = legacy_theme
                AgentPortManager._write_agent_config(config_entries)
                return legacy_theme

        return None

    @staticmethod
    def _read_registered_theme_mode() -> Optional[str]:
        config_entries = AgentPortManager._read_agent_config()
        theme_mode = config_entries.get(AgentPortManager._THEME_MODE_KEY)
        if theme_mode:
            return theme_mode.strip() or None
        return None

    @staticmethod
    def _write_registered_theme(theme: Optional[str]) -> None:
        if theme is None:
            return

        normalized = str(theme).strip()
        if not normalized:
            return

        entries = AgentPortManager._read_agent_config()
        entries[AgentPortManager._THEME_KEY] = normalized
        AgentPortManager._write_agent_config(entries)

    @staticmethod
    def _write_registered_theme_mode(theme_mode: Optional[str]) -> None:
        entries = AgentPortManager._read_agent_config()

        if theme_mode is None:
            entries.pop(AgentPortManager._THEME_MODE_KEY, None)
            AgentPortManager._write_agent_config(entries)
            return

        normalized = str(theme_mode).strip()
        if not normalized:
            entries.pop(AgentPortManager._THEME_MODE_KEY, None)
            AgentPortManager._write_agent_config(entries)
            return

        entries[AgentPortManager._THEME_MODE_KEY] = normalized
        AgentPortManager._write_agent_config(entries)

    @staticmethod
    def read_panel_box() -> str:
        """Return the configured panel box style."""
        entries = AgentPortManager._read_agent_config()
        val = entries.get(AgentPortManager._PANEL_BOX_KEY, '').strip().lower()
        valid_styles = ('rounded', 'horizontals', 'square', 'heavy', 'double', 'minimal')
        return val if val in valid_styles else 'rounded'

    @staticmethod
    def write_panel_box(style: str) -> None:
        style = style.strip().lower()
        valid_styles = ('rounded', 'horizontals', 'square', 'heavy', 'double', 'minimal')
        if style not in valid_styles:
            raise ValueError(
                f"Invalid panel box style: {style!r}. Use one of: {', '.join(valid_styles)}."
            )
        entries = AgentPortManager._read_agent_config()
        entries[AgentPortManager._PANEL_BOX_KEY] = style
        AgentPortManager._write_agent_config(entries)

    @staticmethod
    def read_panel_colors() -> dict[str, str]:
        """Return category color overrides: {'help': '#ff8800', ...}"""
        entries = AgentPortManager._read_agent_config()
        raw = entries.get(AgentPortManager._PANEL_COLORS_KEY, '').strip()
        if not raw:
            return {}
        try:
            result = json.loads(raw)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def write_panel_colors(colors: dict[str, str]) -> None:
        entries = AgentPortManager._read_agent_config()
        if colors:
            entries[AgentPortManager._PANEL_COLORS_KEY] = json.dumps(colors, separators=(',', ':'))
        else:
            entries.pop(AgentPortManager._PANEL_COLORS_KEY, None)
        AgentPortManager._write_agent_config(entries)

    @staticmethod
    def _can_bind_port(port: Optional[int]) -> bool:
        if not isinstance(port, int) or not (1 <= port <= MAX_AGENT_PORT):
            return False

        host = AgentPortManager._read_registered_ip()
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            for family, socktype, proto, _canonname, address in addresses:
                with socket.socket(family, socktype, proto) as sock:
                    sock.bind(address)
                    return True
        except OSError:
            return False
        return False

    @staticmethod
    def _is_local_ip(host: str) -> bool:
        normalized = str(host or '').strip().split('%', 1)[0]
        if normalized.lower() == 'localhost':
            return True
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError:
            return False
        if address.is_loopback or address.is_unspecified:
            return True

        try:
            import psutil
            for interface_addresses in psutil.net_if_addrs().values():
                for interface_address in interface_addresses:
                    candidate = interface_address.address.split('%', 1)[0]
                    if candidate == normalized:
                        return True
        except Exception:
            pass
        return False

    @staticmethod
    def _normalize_connection_port(port: Optional[str]) -> str:
        if not port:
            return ""
        p = str(port).strip()
        if sys.platform.startswith("win"):
            return p.upper()
        return p

    @staticmethod
    def _discover_running_agent_ports() -> list[int]:
        try:
            import psutil
        except Exception:
            return []

        ports = set()
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
            except Exception:
                continue

            if not cmdline:
                continue

            cmd_lower = [str(part).lower() for part in cmdline]
            module_index = None
            for i in range(len(cmd_lower) - 1):
                if cmd_lower[i] == '-m' and cmd_lower[i + 1] == 'replx_agent':
                    module_index = i + 1
                    break

            if module_index is None:
                continue

            port = DEFAULT_AGENT_PORT
            if module_index + 1 < len(cmdline):
                maybe_port = str(cmdline[module_index + 1]).strip()
                if maybe_port.isdigit():
                    port = int(maybe_port)

            ports.add(port)

        return sorted(ports)

    @staticmethod
    def _get_candidate_agent_ports(
        env_path: str = None,
        preferred_port: int = None,
        *,
        persist_config: bool = True,
    ) -> list[int]:
        ports: list[int] = []

        def _add(port: Optional[int]) -> None:
            if isinstance(port, int) and port > 0 and port not in ports:
                ports.append(port)

        _add(preferred_port)
        _add(
            AgentPortManager._read_registered_port(
                persist_config=persist_config
            )
        )
        _add(DEFAULT_AGENT_PORT)

        for port in AgentPortManager._discover_running_agent_ports():
            _add(port)

        return ports
    
    @staticmethod
    def find_available_port(env_path: str = None) -> int:
        registered_port = AgentPortManager._read_registered_port()
        running_port = AgentPortManager._ensure_singleton_running_agent(preferred_port=registered_port)
        if running_port is not None:
            return running_port

        if not AgentPortManager._is_local_ip(AgentPortManager._read_registered_ip()):
            return registered_port or DEFAULT_AGENT_PORT

        if registered_port is not None and AgentPortManager._can_bind_port(registered_port):
            return registered_port

        for port in range(MIN_AGENT_PORT, MAX_AGENT_PORT + 1):
            if not AgentPortManager._can_bind_port(port):
                continue
            AgentPortManager._write_registered_port(port)
            return port

        fallback_port = registered_port or DEFAULT_AGENT_PORT
        AgentPortManager._write_registered_port(fallback_port)
        return fallback_port
    
    @staticmethod
    def find_running_agent(
        env_path: str = None,
        *,
        persist_config: bool = True,
    ) -> Optional[int]:
        return AgentPortManager._ensure_singleton_running_agent(
            persist_config=persist_config
        )

    @staticmethod
    def find_running_agents(
        env_path: str = None,
        *,
        persist_config: bool = True,
    ) -> list[int]:
        running_port = AgentPortManager._ensure_singleton_running_agent(
            persist_config=persist_config
        )
        if running_port is None:
            return []
        return [running_port]

    @staticmethod
    def find_agent_for_connection(
        port: str,
        env_path: str = None,
        preferred_port: int = None,
        client: Any = None,
    ) -> Optional[int]:
        from .agent.client import AgentClient

        target_port = AgentPortManager._normalize_connection_port(port)
        if not target_port:
            return None

        agent_port = AgentPortManager._ensure_singleton_running_agent(preferred_port=preferred_port)
        if agent_port is None:
            return None

        try:
            if client is None:
                with AgentClient(port=agent_port) as status_client:
                    session_info = status_client.send_command('session_info', timeout=1.0)
            else:
                session_info = client.send_command('session_info', timeout=1.0)
        except Exception:
            return None

        for conn in session_info.get('connections', []):
            conn_port = AgentPortManager._normalize_connection_port(conn.get('port'))
            if conn_port == target_port and conn.get('connected'):
                return agent_port

        return None


class ConnectionResolver:
    
    @staticmethod
    def resolve(global_port: str = None) -> Optional[dict]:
        env_path = ConfigManager.find_env_file()
        
        if global_port:
            return ConnectionResolver._resolve_serial(global_port, env_path)

        result = ConnectionResolver._resolve_from_session(env_path)
        if result:
            return result
        
        return ConnectionResolver._resolve_from_default(env_path)
    
    @staticmethod
    def _resolve_serial(port: str, env_path: str) -> dict:
        conn_key = port
        result = {
            'connection': port,
            'source': 'global',
            'agent_port': AgentPortManager.find_available_port(env_path),
        }
        
        if env_path:
            config = ConfigManager.get_connection(env_path, conn_key)
            if config:
                result['core'] = config.get('core')
                result['device'] = config.get('device')
        
        return result
    
    @staticmethod
    def _resolve_from_session(env_path: str = None) -> Optional[dict]:
        from .agent.client import AgentClient, get_cached_session_id

        ppid = get_cached_session_id()
        agent_port = AgentPortManager.find_running_agent(env_path)
        if agent_port is None:
            return None

        try:
            with AgentClient(port=agent_port) as client:
                session_info = client.send_command('session_info', timeout=1.0)

            sessions = session_info.get('sessions', [])
            if any('is_current' in session for session in sessions):
                current_sessions = [session for session in sessions if session.get('is_current')]
            else:
                current_sessions = [session for session in sessions if session.get('ppid') == ppid]

            for session in current_sessions:
                if session.get('foreground'):
                    fg_port = session['foreground']

                    for conn in session_info.get('connections', []):
                        if conn.get('port') == fg_port and conn.get('connected'):
                            return {
                                'connection': fg_port,
                                'agent_port': agent_port,
                                'core': conn.get('core'),
                                'device': conn.get('device'),
                                'source': 'session'
                            }
        except Exception:
            return None
        
        return None
    
    @staticmethod
    def _resolve_from_default(env_path: str) -> Optional[dict]:
        if not env_path:
            return None
        
        default_conn = ConfigManager.get_default(env_path)
        if not default_conn:
            return None
        
        config = ConfigManager.get_connection(env_path, default_conn)
        if not config:
            return None
        
        return {
            'connection': default_conn,
            'agent_port': AgentPortManager.find_available_port(env_path),
            'core': config.get('core'),
            'device': config.get('device'),
            'source': 'default'
        }

def _find_env_file() -> Optional[str]:
    return ConfigManager.find_env_file()

def _find_or_create_vscode_dir() -> str:
    return ConfigManager.find_or_create_vscode_dir()

def _read_env_ini(env_path: str) -> dict:
    return ConfigManager.read(env_path)

def _get_connection_config(env_path: str, connection: str) -> Optional[dict]:
    return ConfigManager.get_connection(env_path, connection)

def _update_connection_config(env_path: str, connection: str, **kwargs):
    return ConfigManager.update_connection(env_path, connection, **kwargs)

def _get_default_connection(env_path: str) -> Optional[str]:
    return ConfigManager.get_default(env_path)

def _get_theme_config(env_path: str | None = None) -> str:
    return ConfigManager.get_theme(env_path)

def _set_theme_config(env_path: str | None, theme: str, theme_mode: str | None = None):
    return ConfigManager.set_theme(env_path, theme, theme_mode)

def _find_available_agent_port(env_path: str) -> int:
    return AgentPortManager.find_available_port(env_path)

def _resolve_agent_port() -> int:
    return AgentPortManager.find_available_port()

def _get_registered_agent_port() -> Optional[int]:
    return AgentPortManager._read_registered_port()

def _find_running_agent_port(env_path: str) -> Optional[int]:
    return AgentPortManager.find_running_agent(env_path)

def _find_running_agent_ports(
    env_path: str = None,
    *,
    persist_config: bool = True,
) -> list[int]:
    return AgentPortManager.find_running_agents(
        env_path,
        persist_config=persist_config,
    )

def _find_agent_for_connection(
    port: str,
    env_path: str = None,
    preferred_port: int = None,
    client: Any = None,
) -> Optional[int]:
    return AgentPortManager.find_agent_for_connection(
        port,
        env_path,
        preferred_port,
        client=client,
    )

def _resolve_connection(global_port: str = None) -> Optional[dict]:
    return ConnectionResolver.resolve(global_port)

def _set_global_options(port: str = None):
    GLOBAL_OPTIONS.set(port)

def _get_global_options() -> dict:
    return GLOBAL_OPTIONS.get()
