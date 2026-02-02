from typing import Any, Dict, List, Optional

from .. import config


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

    for node in nodes:
        prefix = indent_unit * indent_level
        if node["type"] == "branch":
            for idx, option in enumerate(node["options"], 1):
                if _tpl("branch_label"):
                    label = _tpl("branch_label").format(index=idx)
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
            if _tpl("black_screen"):
                lines.append(f"{prefix}{_tpl('black_screen').format(text=text)}")
            last_was_dialog = False
            continue

        if dialog_id and _tpl("dialog_id"):
            lines.append(f"{prefix}{_tpl('dialog_id').format(dialog_id=dialog_id)}")

        if last_was_dialog and role == last_role and indent_level == last_indent:
            if _tpl("dialog_cont"):
                lines.append(
                    f"{prefix}{_tpl('dialog_cont').format(text=text, role=role)}"
                )
        else:
            if _tpl("dialog_line"):
                lines.append(
                    f"{prefix}{_tpl('dialog_line').format(role=role, text=text)}"
                )
            last_role = role
            last_indent = indent_level
            last_was_dialog = True

    return lines


def render_with_templates(doc: Dict[str, Any], config_dict: Dict[str, Any]) -> str:
    templates = {**config.DEFAULT_TEMPLATES, **config_dict.get("templates", {})}
    options = config_dict.get("options", {})
    if "skip_fields" not in options:
        options = {**options, "skip_fields": ["story_id", "task_id", "dialog_id"]}
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

    lines: List[str] = []
    chapter_num = doc.get("chapter_num", "")
    chapter_title_value = doc.get("chapter_title", "")
    if chapter_title_value and _tpl("chapter_title"):
        chapter_title = _tpl("chapter_title").format(
            chapter_num=chapter_num,
            chapter_title=chapter_title_value,
        ).strip()
    else:
        chapter_title = f"# {chapter_num}".strip() if chapter_num else ""
    if chapter_title:
        lines.append(chapter_title)
    chapter_desc = doc.get("chapter_desc", "")
    if chapter_desc and _tpl("chapter_desc"):
        lines.append(_tpl("chapter_desc").format(chapter_desc=chapter_desc))

    for task in doc.get("tasks", []):
        story_id = task.get("story_id", "")
        task_id = task.get("task_id", "")
        if story_id and _tpl("story_id"):
            lines.append(_tpl("story_id").format(story_id=story_id))
        if task_id and _tpl("task_id"):
            lines.append(_tpl("task_id").format(task_id=task_id))
        title = task.get("title") or ""
        if title and _tpl("task_title"):
            lines.append("")
            lines.append(_tpl("task_title").format(task_title=title))
        desc = task.get("desc") or ""
        if desc and _tpl("task_desc"):
            lines.append(_tpl("task_desc").format(task_desc=desc))
        nodes = task.get("nodes") or []
        lines.extend(render_nodes_with_templates(nodes, templates, options, 0))

    return "\n".join([line for line in lines if line is not None]).strip() + "\n"
