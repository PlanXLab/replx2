
from importlib import import_module

from .protocol import AgentProtocol

__all__ = [
    'AgentProtocol',
    'AgentClient',
    'get_session_id',
    'get_cached_session_id',
    'clear_session_cache',
    'AgentServer',
    'agent_main',
]


def __getattr__(name):
    if name in {
        'AgentClient',
        'get_session_id',
        'get_cached_session_id',
        'clear_session_cache',
    }:
        return getattr(import_module('.client', __name__), name)

    if name == 'AgentServer':
        from .server import AgentServer

        return AgentServer
    if name == 'agent_main':
        from .server import main as agent_main

        return agent_main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
