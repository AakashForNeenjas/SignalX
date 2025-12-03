
import importlib
from typing import Dict, List, Optional
from .model import LogFormatPlugin


class FormatRegistry:
    """Simple registry to hold available log format plugins."""

    def __init__(self):
        self._plugins: Dict[str, LogFormatPlugin] = {}

    def register(self, plugin: LogFormatPlugin):
        key = plugin.name.lower()
        self._plugins[key] = plugin

    def get(self, name: str) -> Optional[LogFormatPlugin]:
        return self._plugins.get(name.lower())

    def all(self) -> List[LogFormatPlugin]:
        return list(self._plugins.values())

    def detect_for_path(self, path: str) -> Optional[LogFormatPlugin]:
        for plugin in self._plugins.values():
            try:
                if plugin.detect(path):
                    return plugin
            except Exception:
                continue
        return None


def load_builtin_plugins() -> FormatRegistry:
    """Load built-in plugins defined in logconv.plugins package."""
    registry = FormatRegistry()
    module_names = [
        "logconv.plugins.trc",
        "logconv.plugins.asc",
        "logconv.plugins.blf",
        "logconv.plugins.csv_plugin",
        "logconv.plugins.logtxt",
        "logconv.plugins.mdf",
        "logconv.plugins.pcap",
        "logconv.plugins.mat",
        "logconv.plugins.dat",
    ]
    for mod_name in module_names:
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "plugin"):
                registry.register(mod.plugin)
        except Exception:
            # Fail-soft: registry will skip broken plugins
            continue
    return registry
