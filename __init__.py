__all__ = ["__version__", "get_version", "__description__"]
__version__ = "2.0.0.post1"
__description__ = "Fast MicroPython CLI with a separately packaged board-management agent."
__author__ = "PlanX Lab Development Team"

def get_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
        installed_version = version("replx")
    except PackageNotFoundError:
        return __version__
    return installed_version if installed_version == __version__ else __version__