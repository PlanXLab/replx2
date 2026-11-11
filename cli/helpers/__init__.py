from rich.box import DOUBLE, HEAVY, HORIZONTALS, MINIMAL, ROUNDED, SQUARE

CONSOLE_WIDTH = 100

_panel_box_cache: str | None = None


def get_panel_box():
    global _panel_box_cache
    if _panel_box_cache is None:
        try:
            from replx.cli.config import AgentPortManager
            _panel_box_cache = AgentPortManager.read_panel_box()
        except Exception:
            _panel_box_cache = 'rounded'
    box_styles = {
        'rounded': ROUNDED,
        'horizontals': HORIZONTALS,
        'square': SQUARE,
        'heavy': HEAVY,
        'double': DOUBLE,
        'minimal': MINIMAL,
    }
    return box_styles.get(_panel_box_cache, ROUNDED)


def invalidate_panel_box_cache():
    global _panel_box_cache
    _panel_box_cache = None


import threading
_core = ""
_device = ""
_version = "?"
_device_root_fs = "/"
_device_path = ""
_global_context_lock = threading.Lock()


def set_global_context(core: str, device: str, version: str, device_root_fs: str, device_path: str):
    global _core, _device, _version, _device_root_fs, _device_path
    with _global_context_lock:
        _core = core
        _device = device
        _version = version
        _device_root_fs = device_root_fs
        _device_path = device_path


def get_global_context():
    with _global_context_lock:
        return _core, _device, _version, _device_root_fs, _device_path


from .output import OutputHelper, VALID_PANEL_CATEGORIES
from replx.utils import (
    SUPPORT_CORE_DEVICE_TYPES, CORE_ROOT_FS, DEFAULT_ROOT_FS,
    get_root_fs_for_core, parse_device_banner,
)

__all__ = [
    'CONSOLE_WIDTH', 'get_panel_box', 'invalidate_panel_box_cache',
    'set_global_context', 'get_global_context',
    'OutputHelper', 'VALID_PANEL_CATEGORIES',
    'DeviceScanner',
    'parse_device_banner', 'get_root_fs_for_core',
    'SUPPORT_CORE_DEVICE_TYPES', 'CORE_ROOT_FS', 'DEFAULT_ROOT_FS',
    'EnvironmentManager',
    'StoreManager',
    'CompilerHelper',
    'InstallHelper', 'SearchHelper', 'RegistryHelper',
    'UpdateChecker',
]


_LAZY_ATTRS = {
    'DeviceScanner': ('.scanner', 'DeviceScanner'),
    'EnvironmentManager': ('.environment', 'EnvironmentManager'),
    'StoreManager': ('.store', 'StoreManager'),
    'CompilerHelper': ('.compiler', 'CompilerHelper'),
    'InstallHelper': ('.registry', 'InstallHelper'),
    'SearchHelper': ('.registry', 'SearchHelper'),
    'RegistryHelper': ('.registry', 'RegistryHelper'),
    'UpdateChecker': ('.updater', 'UpdateChecker'),
}


def __getattr__(name):
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module = import_module(target[0], __name__)
    value = getattr(module, target[1])
    globals()[name] = value
    return value
