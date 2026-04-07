"""Plugin discovery and loading for RetroSprite."""
from __future__ import annotations
import importlib.util
import json
import os
import sys
import traceback


DEFAULT_PLUGIN_DIR = os.path.join(os.path.expanduser("~"), ".retrosprite", "plugins")
DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".retrosprite", "plugins.json")


def discover_plugins(plugin_dir: str = DEFAULT_PLUGIN_DIR) -> list[str]:
    """Return list of .py file paths in plugin directory."""
    if not os.path.isdir(plugin_dir):
        return []
    return sorted(
        os.path.join(plugin_dir, f)
        for f in os.listdir(plugin_dir)
        if f.endswith(".py") and not f.startswith("_")
    )


def load_plugin(path: str, api) -> dict | None:
    """Import a plugin module, call register(api), return plugin info.

    Returns None if the plugin has no register() function or raises an error.
    """
    module_name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(
        f"retrosprite_plugin_{module_name}", path
    )
    if spec is None or spec.loader is None:
        return None
    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception:
        traceback.print_exc()
        return None

    register_fn = getattr(module, "register", None)
    if register_fn is None:
        return None

    try:
        register_fn(api)
    except Exception:
        traceback.print_exc()
        return None

    info = getattr(module, "PLUGIN_INFO", {"name": module_name})
    info.setdefault("name", module_name)
    info["_module"] = module
    info["_path"] = path
    return info


def load_all_plugins(api, plugin_dir: str = DEFAULT_PLUGIN_DIR,
                     config_path: str = DEFAULT_CONFIG_PATH) -> list[dict]:
    """Discover and load all plugins, respecting disabled list."""
    disabled = set()
    if os.path.exists(config_path):
        try:
            with open(config_path) as f:
                config = json.load(f)
            disabled = set(config.get("disabled", []))
        except (json.JSONDecodeError, IOError):
            pass

    results = []
    for path in discover_plugins(plugin_dir):
        filename = os.path.basename(path)
        if filename in disabled:
            continue
        info = load_plugin(path, api)
        if info is not None:
            results.append(info)
    return results


def unload_all_plugins(plugins: list[dict], api) -> None:
    """Call unregister() on all loaded plugins that support it."""
    for info in plugins:
        module = info.get("_module")
        if module is None:
            continue
        unregister_fn = getattr(module, "unregister", None)
        if unregister_fn is not None:
            try:
                unregister_fn(api)
            except Exception:
                traceback.print_exc()
