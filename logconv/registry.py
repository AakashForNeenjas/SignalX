
import importlib
import os
from typing import Dict, List, Optional, Tuple
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

    def detect_for_path(self, path: str) -> Tuple[Optional[LogFormatPlugin], Optional[str]]:
        """
        Try to detect a plugin for the given path.
        Returns (plugin, reason) where plugin may be None.
        """
        if not path or not os.path.exists(path):
            return None, "File not found"

        # Try extension match first
        for plugin in self._plugins.values():
            try:
                if plugin.detect(path):
                    return plugin, None
            except Exception:
                continue

        # Optional content sniff: read small sample and retry detect() with sample
        sample = None
        try:
            with open(path, "rb") as f:
                sample = f.read(2048)
        except Exception:
            sample = None

        for plugin in self._plugins.values():
            try:
                if plugin.detect(path, sample=sample):
                    return plugin, None
            except Exception:
                continue

        return None, "No plugin matched by extension or sniff"


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
