import importlib.util
from pathlib import Path
from typing import Any, Dict, Tuple

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime dependency check
    raise ImportError("PyYAML is required for YAML config files. Install with uv/pip.") from exc


def load_renderer(format_file: str) -> Tuple[str, Dict[str, Any]]:
    with open(format_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    renderer_spec = config.get("renderer")
    if not renderer_spec:
        return "templates", config
    return renderer_spec, config


def render_with_plugin(doc: Dict[str, Any], renderer_spec: str, config: Dict[str, Any]) -> str:
    if ":" not in renderer_spec:
        raise ValueError("renderer must be in 'path.py:function' format")
    path_str, func_name = renderer_spec.split(":", 1)
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"Renderer file not found: {path}")
    module_name = f"renderer_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load renderer module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, func_name, None)
    if func is None:
        raise AttributeError(f"Renderer function not found: {func_name}")
    return str(func(doc, config.get("options", {})))
