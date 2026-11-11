from .config import (
    RuntimeState, STATE, GLOBAL_OPTIONS,
    ConfigManager, AgentPortManager, ConnectionResolver,
)
from replx.utils.constants import DEFAULT_AGENT_PORT, MIN_AGENT_PORT, MAX_AGENT_PORT

__all__ = [
    'RuntimeState', 'STATE', 'GLOBAL_OPTIONS',
    'ConfigManager', 'AgentPortManager', 'ConnectionResolver',
    'DEFAULT_AGENT_PORT', 'MIN_AGENT_PORT', 'MAX_AGENT_PORT',
    'app', 'main'
]


def __getattr__(name):
    if name in {'app', 'main'}:
        from .app import app, main

        return {'app': app, 'main': main}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
