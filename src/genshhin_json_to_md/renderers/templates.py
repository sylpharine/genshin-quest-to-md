from typing import Any, Dict, List, Optional, Set, Tuple

from .. import config


def format_template(template: str, key: str, **kwargs: Any) -> str:
    try:
        return template.format(**kwargs)
    except KeyError as exc:
        missing = exc.args[0] if exc.args else ""
        raise ValueError(
            f"Template '{key}' references missing field '{missing}'."
        ) from exc
    except (IndexError, ValueError) as exc:
        raise ValueError(f"Template '{key}' has invalid format: {exc}") from exc


def normalize_templates_config(
    config_dict: Dict[str, Any],
) -> Tuple[Dict[str, str], Dict[str, Any], Set[str]]:
    if config_dict is None:
        config_dict = {}
    if not isinstance(config_dict, dict):
        raise ValueError("Format config must be a mapping (YAML object).")
    raw_templates = config_dict.get("templates", {})
    if raw_templates is None:
        raw_templates = {}
    if not isinstance(raw_templates, dict):
        raise ValueError("templates must be a mapping (YAML object).")
    for key, value in raw_templates.items():
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValueError(f"templates.{key} must be a string or null.")

    options = config_dict.get("options", {})
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ValueError("options must be a mapping (YAML object).")
    if "skip_fields" not in options:
        options = {**options, "skip_fields": ["story_id", "task_id", "dialog_id"]}
    skip_fields = options.get("skip_fields", [])
    if not isinstance(skip_fields, list):
        raise ValueError("options.skip_fields must be a list.")
    if any(not isinstance(item, str) for item in skip_fields):
        raise ValueError("options.skip_fields must be a list of strings.")

    templates = {**config.DEFAULT_TEMPLATES, **raw_templates}

    required_templates = [
        "chapter_title",
        "chapter_desc",
        "story_id",
        "task_id",
        "task_title",
        "task_desc",
        "dialog_id",
        "dialog_line",
        "dialog_cont",
        "branch_label",
        "black_screen",
    ]
    missing = [
        key
        for key in required_templates
        if key not in templates and key not in skip_fields
    ]
    if missing:
        raise ValueError(
            "Missing template field(s): "
            + ", ".join(missing)
            + ". Add them to templates or list them in options.skip_fields."
        )

    return templates, options, set(skip_fields)


def render_nodes_with_templates(
    nodes: List[Dict[str, Any]],
    templates: Dict[str, str],
    options: Dict[str, Any],
    indent_level: int = 0,
) -> List[str]:
    lines: List[str] = []
    last_role = None
    last_was_dialog = False
    last_indent = None

    indent_unit = options.get("indent_unit", "  ")
    skip_fields = set(options.get("skip_fields", []))

    def _tpl(key: str) -> Optional[str]:
        tpl = templates.get(key)
        if tpl is None:
            return None
        if isinstance(tpl, str) and tpl == "":
            return None
        if key in skip_fields:
            return None
        return tpl

    def _fmt(key: str, **kwargs: Any) -> Optional[str]:
        tpl = _tpl(key)
        if tpl is None:
            return None
        return format_template(tpl, key, **kwargs)

    for node in nodes:
        prefix = indent_unit * indent_level
        if node["type"] == "branch":
            for idx, option in enumerate(node["options"], 1):
                label = _fmt("branch_label", index=idx)
                if label:
                    lines.append(f"{prefix}{label}")
                lines.extend(
                    render_nodes_with_templates(option, templates, options, indent_level + 1)
                )
            continue

        role = node.get("role", "")
        text = node.get("text", "")
        dialog_id = node.get("id", "")
        is_black = bool(node.get("is_black_screen", False))
        if is_black:
            black_line = _fmt("black_screen", text=text)
            if black_line:
                lines.append(f"{prefix}{black_line}")
            last_was_dialog = False
            continue

        if dialog_id:
            dialog_line = _fmt("dialog_id", dialog_id=dialog_id)
            if dialog_line:
                lines.append(f"{prefix}{dialog_line}")

        if last_was_dialog and role == last_role and indent_level == last_indent:
            dialog_cont = _fmt("dialog_cont", text=text, role=role)
            if dialog_cont:
                lines.append(f"{prefix}{dialog_cont}")
        else:
            dialog_line = _fmt("dialog_line", role=role, text=text)
            if dialog_line:
                lines.append(f"{prefix}{dialog_line}")
            last_role = role
            last_indent = indent_level
            last_was_dialog = True

    return lines


def render_with_templates(doc: Dict[str, Any], config_dict: Dict[str, Any]) -> str:
    templates, options, skip_fields = normalize_templates_config(config_dict)

    def _tpl(key: str) -> Optional[str]:
        tpl = templates.get(key)
        if tpl is None:
            return None
        if isinstance(tpl, str) and tpl == "":
            return None
        if key in skip_fields:
            return None
        return tpl

    def _fmt(key: str, **kwargs: Any) -> Optional[str]:
        tpl = _tpl(key)
        if tpl is None:
            return None
        return format_template(tpl, key, **kwargs)

    lines: List[str] = []
    chapter_num = doc.get("chapter_num", "")
    chapter_title_value = doc.get("chapter_title", "")
    chapter_title_line = None
    if chapter_title_value:
        chapter_title_line = _fmt(
            "chapter_title",
            chapter_num=chapter_num,
            chapter_title=chapter_title_value,
        )
    if chapter_title_line:
        lines.append(chapter_title_line.strip())
    elif chapter_num and _tpl("chapter_title"):
        lines.append(f"# {chapter_num}".strip())
    chapter_desc = doc.get("chapter_desc", "")
    if chapter_desc:
        chapter_desc_line = _fmt("chapter_desc", chapter_desc=chapter_desc)
        if chapter_desc_line:
            lines.append(chapter_desc_line)

    for task in doc.get("tasks", []):
        story_id = task.get("story_id", "")
        task_id = task.get("task_id", "")
        if story_id:
            story_line = _fmt("story_id", story_id=story_id)
            if story_line:
                lines.append(story_line)
        if task_id:
            task_line = _fmt("task_id", task_id=task_id)
            if task_line:
                lines.append(task_line)
        title = task.get("title") or ""
        if title and _tpl("task_title"):
            lines.append("")
            title_line = _fmt("task_title", task_title=title)
            if title_line:
                lines.append(title_line)
        desc = task.get("desc") or ""
        if desc:
            desc_line = _fmt("task_desc", task_desc=desc)
            if desc_line:
                lines.append(desc_line)
        nodes = task.get("nodes") or []
        lines.extend(render_nodes_with_templates(nodes, templates, options, 0))

    return "\n".join([line for line in lines if line is not None]).strip() + "\n"
