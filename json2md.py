#!/usr/bin/env python3
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

UNKNOWN_ROLE = "Unknown"
TRAVELER_NAME = "旅行者"
TRAVELER_GENDER = "F"
WANDERER_NAME = "流浪者"
SHOW_BRANCHES = True
BRANCH_CHOICES = {}
BRANCH_DEFAULT = 1

DEFAULT_TEMPLATES = {
    "chapter_title": "# {chapter_num} 《{chapter_title}》",
    "chapter_desc": "{chapter_desc}",
    "story_id": "StoryID: {story_id}",
    "task_id": "TaskID: {task_id}",
    "task_title": "## {task_title}",
    "task_desc": "{task_desc}",
    "dialog_id": "DialogID: {dialog_id}",
    "dialog_line": "{role}：{text}",
    "dialog_cont": "    {text}",
    "branch_label": "【分支{index}】",
    "black_screen": "*{text}*",
}


def _sort_keys_numeric(keys):
    def key_fn(k):
        try:
            return (0, int(k))
        except Exception:
            return (1, str(k))
    return sorted(keys, key=key_fn)


def _safe_role(role: Optional[str]) -> str:
    if role is None:
        return UNKNOWN_ROLE
    role = role.strip()
    return role if role else UNKNOWN_ROLE


def _normalize_gender(value: str) -> str:
    if value is None:
        return "F"
    v = str(value).strip().lower()
    if v in ("m", "male", "man", "男", "他"):
        return "M"
    if v in ("f", "female", "woman", "女", "她"):
        return "F"
    if v.upper() in ("M", "F"):
        return v.upper()
    return "F"


def _replace_gender(text: str) -> str:
    if not text:
        return text

    def repl_mf(match: re.Match) -> str:
        male = match.group(1)
        female = match.group(2)
        return male if TRAVELER_GENDER == "M" else female

    def repl_fm(match: re.Match) -> str:
        female = match.group(1)
        male = match.group(2)
        return male if TRAVELER_GENDER == "M" else female

    text = re.sub(r"\{M#([^}]*)\}\{F#([^}]*)\}", repl_mf, text)
    text = re.sub(r"\{F#([^}]*)\}\{M#([^}]*)\}", repl_fm, text)
    return text


def _parse_branch_choices(raw_list: List[str]) -> Dict[str, int]:
    choices: Dict[str, int] = {}
    for item in raw_list:
        if not item:
            continue
        for part in item.split(","):
            part = part.strip()
            if not part or "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or not value:
                continue
            try:
                idx = int(value)
            except ValueError:
                continue
            choices[key] = idx
    return choices


def _select_branch_index(dialog_id: str, total: int) -> int:
    idx = BRANCH_CHOICES.get(str(dialog_id), BRANCH_DEFAULT)
    if idx < 1:
        idx = 1
    if idx > total:
        idx = total
    return idx


def _replace_traveler(text: str) -> str:
    if not text:
        return text
    if text.startswith("#") and (
        "{NICKNAME}" in text
        or "#{NICKNAME}" in text
        or "REALNAME[" in text
        or "{M#" in text
        or "{F#" in text
    ):
        text = text[1:]
    text = _replace_gender(text)
    text = re.sub(r"#\{REALNAME\[[^\]]*\]\}", WANDERER_NAME, text)
    text = re.sub(r"\{REALNAME\[[^\]]*\]\}", WANDERER_NAME, text)
    for token in ("#{NICKNAME}", "{NICKNAME}", "Traveler", "Traveller", "玩家"):
        text = text.replace(token, TRAVELER_NAME)
    return text


def _next_after_echo(items: Dict[str, Any], next_id: Any) -> Optional[Any]:
    next_dialog = items.get(str(next_id))
    if not next_dialog or next_dialog.get("type") != "SingleDialog":
        return None
    next_entries = next_dialog.get("text") or []
    if not next_entries:
        return None
    next_ids = []
    for entry in next_entries:
        nid = entry.get("next")
        if nid is not None and nid not in next_ids:
            next_ids.append(nid)
    if len(next_ids) == 1:
        return next_ids[0]
    return None


def _build_dialog_nodes(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = task.get("items") or {}
    init_dialog = task.get("initDialog")
    if init_dialog is None:
        return []

    def _walk(items: Dict[str, Any], dialog_id: Any, path: set) -> List[Dict[str, Any]]:
        if dialog_id is None:
            return []

        current = str(dialog_id)
        if current == "finish" or current in path:
            return []

        dialog = items.get(current)
        if not dialog:
            return []

        path.add(current)

        role = _replace_traveler(_safe_role(dialog.get("role", "")))
        text_entries = dialog.get("text") or []
        is_black_screen = bool(dialog.get("isBlackScreen", False))
        dialog_entries: List[Tuple[str, Any]] = []
        for entry in text_entries:
            text = _replace_traveler(entry.get("text", ""))
            dialog_entries.append((text, entry.get("next")))

        if not dialog_entries:
            return []

        dialog_type = dialog.get("type", "")
        is_multi = dialog_type == "MultiDialog"
        unique_next = []
        for _, next_id in dialog_entries:
            if next_id is None:
                continue
            if next_id not in unique_next:
                unique_next.append(next_id)
        branching = is_multi or len(unique_next) > 1

        def _is_echo(next_id: Any, role_name: str, text_value: str) -> bool:
            if next_id is None:
                return False
            next_dialog = items.get(str(next_id))
            if not next_dialog or next_dialog.get("type") != "SingleDialog":
                return False
            next_role = _replace_traveler(_safe_role(next_dialog.get("role", "")))
            if next_role != role_name:
                return False
            next_entries = next_dialog.get("text") or []
            if not next_entries:
                return False
            next_text = _replace_traveler(next_entries[0].get("text", ""))
            return next_text == text_value

        def _dialog_node(text_value: str) -> Dict[str, Any]:
            return {
                "type": "dialog",
                "id": current,
                "role": role,
                "text": text_value,
                "is_black_screen": is_black_screen,
            }

        if not SHOW_BRANCHES and is_multi:
            choice_index = _select_branch_index(current, len(dialog_entries))
            text, next_id = dialog_entries[choice_index - 1]
            nodes: List[Dict[str, Any]] = []
            if _is_echo(next_id, role, text):
                next_after = _next_after_echo(items, next_id)
                if next_after is not None:
                    nodes.append(_dialog_node(text))
                    nodes.extend(_walk(items, next_after, path))
                    return nodes
            nodes.append(_dialog_node(text))
            if next_id is not None:
                nodes.extend(_walk(items, next_id, path))
            return nodes

        if not SHOW_BRANCHES and not is_multi:
            branching = False

        if branching and is_multi and len(unique_next) == 1:
            options = []
            for text, _ in dialog_entries:
                options.append([_dialog_node(text)])
            common = _walk(items, unique_next[0], path)
            return [{"type": "branch", "id": current, "options": options}] + common

        if branching and is_multi:
            echo_next_ids = []
            for text, next_id in dialog_entries:
                if not _is_echo(next_id, role, text):
                    echo_next_ids = []
                    break
                next_after = _next_after_echo(items, next_id)
                if next_after is None:
                    echo_next_ids = []
                    break
                echo_next_ids.append(next_after)
            if echo_next_ids and all(nid == echo_next_ids[0] for nid in echo_next_ids):
                options = []
                for text, _ in dialog_entries:
                    options.append([_dialog_node(text)])
                common = _walk(items, echo_next_ids[0], path)
                return [{"type": "branch", "id": current, "options": options}] + common

        if branching:
            options = []
            for text, next_id in dialog_entries:
                option_nodes: List[Dict[str, Any]] = []
                if not (is_multi and _is_echo(next_id, role, text)):
                    option_nodes.append(_dialog_node(text))
                if next_id is not None:
                    option_nodes.extend(_walk(items, next_id, set(path)))
                options.append(option_nodes)
            return [{"type": "branch", "id": current, "options": options}]

        nodes = [_dialog_node(text) for text, _ in dialog_entries]
        next_id = unique_next[0] if unique_next else None
        if next_id is not None:
            nodes.extend(_walk(items, next_id, path))
        return nodes

    return _walk(items, init_dialog, set())


def _render_nodes_with_templates(
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
                    _render_nodes_with_templates(
                        option, templates, options, indent_level + 1
                    )
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


def _render_with_templates(doc: Dict[str, Any], config: Dict[str, Any]) -> str:
    templates = {**DEFAULT_TEMPLATES, **config.get("templates", {})}
    options = config.get("options", {})
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
        lines.extend(_render_nodes_with_templates(nodes, templates, options, 0))

    return "\n".join([line for line in lines if line is not None]).strip() + "\n"


def _load_renderer(format_file: str) -> Tuple[str, Dict[str, Any]]:
    with open(format_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    renderer_spec = config.get("renderer")
    if not renderer_spec:
        return "templates", config
    return renderer_spec, config


def _render_with_plugin(doc: Dict[str, Any], renderer_spec: str, config: Dict[str, Any]) -> str:
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


def _stream_find_object(file_obj, key: str, decoder: json.JSONDecoder) -> Tuple[Optional[Dict[str, Any]], str]:
    buffer = ""
    while True:
        chunk = file_obj.read(65536)
        if not chunk:
            return None, buffer
        buffer += chunk
        key_idx = buffer.find(f"\"{key}\"")
        if key_idx == -1:
            if len(buffer) > 200000:
                buffer = buffer[-200000:]
            continue
        colon_idx = buffer.find(":", key_idx)
        if colon_idx == -1:
            continue
        start = colon_idx + 1
        while start < len(buffer) and buffer[start].isspace():
            start += 1
        try:
            obj, end = decoder.raw_decode(buffer, start)
            remaining = buffer[end:]
            return obj, remaining
        except json.JSONDecodeError:
            continue


def _stream_story_entries(file_obj, buffer: str, decoder: json.JSONDecoder):
    in_story = False
    while True:
        if not in_story:
            idx = buffer.find("\"storyList\"")
            if idx == -1:
                chunk = file_obj.read(65536)
                if not chunk:
                    return
                buffer += chunk
                if len(buffer) > 200000:
                    buffer = buffer[-200000:]
                continue
            brace_idx = buffer.find("{", idx)
            if brace_idx == -1:
                chunk = file_obj.read(65536)
                if not chunk:
                    return
                buffer += chunk
                continue
            buffer = buffer[brace_idx + 1 :]
            in_story = True

        while True:
            buffer = buffer.lstrip()
            if not buffer:
                chunk = file_obj.read(65536)
                if not chunk:
                    return
                buffer += chunk
                continue
            if buffer[0] == "}":
                return
            if buffer[0] == ",":
                buffer = buffer[1:]
                continue
            try:
                key, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                chunk = file_obj.read(65536)
                if not chunk:
                    return
                buffer += chunk
                continue
            buffer = buffer[end:]
            buffer = buffer.lstrip()
            if buffer.startswith(":"):
                buffer = buffer[1:]
            buffer = buffer.lstrip()
            while True:
                try:
                    value, end = decoder.raw_decode(buffer)
                    buffer = buffer[end:]
                    yield key, value
                    break
                except json.JSONDecodeError:
                    chunk = file_obj.read(65536)
                    if not chunk:
                        return
                    buffer += chunk


def _render_stream(
    input_path: str,
    output_handle,
    config: Dict[str, Any],
    filter_opts: Dict[str, Any],
) -> None:
    templates = {**DEFAULT_TEMPLATES, **config.get("templates", {})}
    options = config.get("options", {})
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

    decoder = json.JSONDecoder()
    with open(input_path, "r", encoding="utf-8") as f:
        info, buffer = _stream_find_object(f, "info", decoder)
        if info is None:
            return
        chapter_num = _replace_traveler(info.get("chapterNum", "") or "")
        chapter_title = _replace_traveler(info.get("chapterTitle", "") or "")
        if chapter_title:
            title_line = _tpl("chapter_title")
            if title_line:
                output_handle.write(
                    title_line.format(
                        chapter_num=chapter_num, chapter_title=chapter_title
                    ).strip()
                    + "\n"
                )
        elif chapter_num:
            output_handle.write(f"# {chapter_num}\n")

        chapter_desc_written = False
        for _, story in _stream_story_entries(f, buffer, decoder):
            if not isinstance(story, dict):
                continue
            if not chapter_desc_written:
                desc = (story.get("info") or {}).get("description") or ""
                desc = _replace_traveler(desc)
                if desc and _tpl("chapter_desc"):
                    output_handle.write(_tpl("chapter_desc").format(chapter_desc=desc) + "\n")
                chapter_desc_written = True

            story_id = story.get("id")
            story_steps = story.get("story") or {}
            for step_key in _sort_keys_numeric(story_steps.keys()):
                step = story_steps.get(step_key, {})
                task_id = step.get("id", step_key)
                title = _replace_traveler(step.get("title") or "")
                step_desc = step.get("stepDescription")
                step_desc = _replace_traveler(step_desc) if step_desc else ""

                task_data_list = step.get("taskData") or []
                nodes: List[Dict[str, Any]] = []
                for task in task_data_list:
                    if task.get("taskType") != "resultDialogue":
                        continue
                    nodes.extend(_build_dialog_nodes(task))

                temp_doc = {
                    "chapter_num": chapter_num,
                    "chapter_title": chapter_title,
                    "chapter_desc": "",
                    "tasks": [
                        {
                            "story_id": story_id,
                            "task_id": task_id,
                            "title": title,
                            "desc": step_desc,
                            "nodes": nodes,
                        }
                    ],
                }
                filtered = _filter_doc(temp_doc, filter_opts)
                if not filtered.get("tasks"):
                    continue
                task = filtered["tasks"][0]

                if task.get("story_id") and _tpl("story_id"):
                    output_handle.write(
                        _tpl("story_id").format(story_id=task["story_id"]) + "\n"
                    )
                if task.get("task_id") and _tpl("task_id"):
                    output_handle.write(
                        _tpl("task_id").format(task_id=task["task_id"]) + "\n"
                    )

                if task.get("title") and _tpl("task_title"):
                    output_handle.write("\n")
                    output_handle.write(
                        _tpl("task_title").format(task_title=task["title"]) + "\n"
                    )
                if task.get("desc") and _tpl("task_desc"):
                    output_handle.write(
                        _tpl("task_desc").format(task_desc=task["desc"]) + "\n"
                    )
                if task.get("nodes"):
                    lines = _render_nodes_with_templates(
                        task["nodes"], templates, options, 0
                    )
                    if lines:
                        output_handle.write("\n".join(lines) + "\n")


def _match_any(text: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    for kw in keywords:
        if kw and kw in text:
            return True
    return False


def _filter_doc(doc: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
    role_include = options.get("filter_roles", []) or []
    role_exclude = options.get("exclude_roles", []) or []
    keyword_include = options.get("filter_keywords", []) or []
    keyword_exclude = options.get("exclude_keywords", []) or []
    task_filters = options.get("filter_tasks", []) or []
    id_filters = options.get("filter_ids", []) or []

    def task_match(title: str) -> bool:
        if not task_filters:
            return True
        return _match_any(title, task_filters)

    def _parse_id_range(value: str) -> Optional[Tuple[str, str, int, int]]:
        if not value or "-" not in value:
            return None
        parts = value.split("-", 1)
        if len(parts) != 2:
            return None
        start = parts[0].strip()
        end = parts[1].strip()
        if not start or not end:
            return None
        try:
            return start, end, int(start), int(end)
        except ValueError:
            return None

    def _id_match(target: Any) -> bool:
        if not id_filters:
            return True
        if target is None:
            return False
        target_str = str(target)
        try:
            target_int = int(target_str)
        except ValueError:
            target_int = None
        for fid in id_filters:
            if fid is None:
                continue
            fid_str = str(fid).strip()
            if not fid_str:
                continue
            range_pair = _parse_id_range(fid_str)
            if range_pair:
                start_str, end_str, start_int, end_int = range_pair
                if (
                    len(start_str) == len(end_str)
                    and len(target_str) >= len(start_str)
                ):
                    prefix_val = target_str[: len(start_str)]
                    try:
                        prefix_int = int(prefix_val)
                    except ValueError:
                        prefix_int = None
                    if prefix_int is not None and start_int <= prefix_int <= end_int:
                        return True
                if target_int is not None and start_int <= target_int <= end_int:
                    return True
                continue
            if target_str.startswith(fid_str):
                return True
        return False

    def node_match(node: Dict[str, Any], task_id_match: bool) -> bool:
        if node["type"] == "branch":
            return True
        text = node.get("text", "") or ""
        role = node.get("role", "") or ""
        node_id = node.get("id")
        if id_filters and not task_id_match and not _id_match(node_id):
            return False
        if role_exclude and role in role_exclude:
            return False
        if role_include and role not in role_include:
            return False
        if keyword_exclude and _match_any(text, keyword_exclude):
            return False
        if keyword_include and not _match_any(text, keyword_include):
            return False
        return True

    def filter_nodes(nodes: List[Dict[str, Any]], task_id_match: bool) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for node in nodes:
            if node["type"] == "branch":
                options_nodes = []
                for option in node.get("options", []):
                    option_filtered = filter_nodes(option, task_id_match)
                    if option_filtered:
                        options_nodes.append(option_filtered)
                if options_nodes:
                    filtered.append(
                        {
                            "type": "branch",
                            "id": node.get("id"),
                            "options": options_nodes,
                        }
                    )
                continue
            if node_match(node, task_id_match):
                filtered.append(node)
        return filtered

    filtered_tasks = []
    for task in doc.get("tasks", []):
        title = task.get("title") or ""
        if not task_match(title):
            continue
        story_id = task.get("story_id")
        task_id = task.get("task_id")
        task_id_match = _id_match(story_id) or _id_match(task_id)
        nodes = filter_nodes(task.get("nodes", []), task_id_match)
        if not nodes:
            continue
        filtered_tasks.append(
            {
                "story_id": story_id,
                "task_id": task_id,
                "title": task.get("title"),
                "desc": task.get("desc"),
                "nodes": nodes,
            }
        )

    return {
        "chapter_num": doc.get("chapter_num", ""),
        "chapter_title": doc.get("chapter_title", ""),
        "chapter_desc": doc.get("chapter_desc", ""),
        "tasks": filtered_tasks,
    }


def json_to_doc(data: Dict[str, Any]) -> Dict[str, Any]:
    root = data.get("data", {})
    info = root.get("info", {})
    chapter_num = _replace_traveler(info.get("chapterNum", "") or "")
    chapter_title = _replace_traveler(info.get("chapterTitle", "") or "")
    chapter_desc = ""

    story_list = root.get("storyList") or {}
    story_keys = _sort_keys_numeric(story_list.keys())

    # Try to pick the first story description as chapter description.
    if story_keys:
        first_story = story_list.get(story_keys[0], {})
        chapter_desc = _replace_traveler(
            (first_story.get("info") or {}).get("description") or ""
        )

    doc: Dict[str, Any] = {
        "chapter_num": chapter_num,
        "chapter_title": chapter_title,
        "chapter_desc": chapter_desc,
        "tasks": [],
    }

    for story_key in story_keys:
        story = story_list.get(story_key, {})
        story_id = story.get("id", story_key)
        story_steps = story.get("story") or {}
        for step_key in _sort_keys_numeric(story_steps.keys()):
            step = story_steps.get(step_key, {})
            task_id = step.get("id", step_key)
            title = _replace_traveler(step.get("title") or "")
            step_desc = step.get("stepDescription")
            step_desc = _replace_traveler(step_desc) if step_desc else ""

            task_data_list = step.get("taskData") or []
            nodes: List[Dict[str, Any]] = []
            for task in task_data_list:
                if task.get("taskType") != "resultDialogue":
                    continue
                nodes.extend(_build_dialog_nodes(task))

            doc["tasks"].append(
                {
                    "story_id": story_id,
                    "task_id": task_id,
                    "title": title,
                    "desc": step_desc,
                    "nodes": nodes,
                }
            )

    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert quest JSON to markdown.")
    parser.add_argument("input", help="Input JSON file path")
    parser.add_argument("-o", "--output", help="Output markdown file path; default: stdout")
    parser.add_argument("--encoding", default="utf-8", help="File encoding (default: utf-8)")
    parser.add_argument(
        "--unknown-role",
        default="Unknown",
        help="Role name to use when role is empty (default: Unknown)",
    )
    parser.add_argument(
        "--traveler-name",
        default="旅行者",
        help="Name to replace #{NICKNAME}/Traveler/Traveller/玩家 (default: 旅行者)",
    )
    parser.add_argument(
        "--traveler-gender",
        default="F",
        help="Gender for {M#}{F#} placeholders: M or F (default: F)",
    )
    parser.add_argument(
        "--wanderer-name",
        default="流浪者",
        help="Name to replace #{REALNAME[...]} placeholders (default: 流浪者)",
    )
    parser.add_argument(
        "--hide-branches",
        action="store_true",
        help="Hide branches and select one path (default: show all branches)",
    )
    parser.add_argument(
        "--branch-choice",
        action="append",
        default=[],
        help="Branch choice mapping like 402231309-player=2 (repeatable, comma-separated)",
    )
    parser.add_argument(
        "--branch-default",
        type=int,
        default=1,
        help="Default branch index when branches are hidden (default: 1)",
    )
    parser.add_argument(
        "--format-file",
        help="Path to JSON format config file (templates or renderer plugin)",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream parse large JSON (templates only)",
    )
    parser.add_argument(
        "--filter-role",
        action="append",
        default=[],
        help="Only include dialog lines from specific role (repeatable)",
    )
    parser.add_argument(
        "--exclude-role",
        action="append",
        default=[],
        help="Exclude dialog lines from specific role (repeatable)",
    )
    parser.add_argument(
        "--filter-keyword",
        action="append",
        default=[],
        help="Only include dialog lines containing keyword (repeatable)",
    )
    parser.add_argument(
        "--exclude-keyword",
        action="append",
        default=[],
        help="Exclude dialog lines containing keyword (repeatable)",
    )
    parser.add_argument(
        "--filter-task",
        action="append",
        default=[],
        help="Only include tasks whose title contains keyword (repeatable)",
    )
    parser.add_argument(
        "--filter-id",
        action="append",
        default=[],
        help="Only include content matching ID prefix (repeatable)",
    )
    args = parser.parse_args()

    global UNKNOWN_ROLE
    UNKNOWN_ROLE = args.unknown_role
    global TRAVELER_NAME
    TRAVELER_NAME = args.traveler_name
    global TRAVELER_GENDER
    TRAVELER_GENDER = _normalize_gender(args.traveler_gender)
    global WANDERER_NAME
    WANDERER_NAME = args.wanderer_name
    global SHOW_BRANCHES
    SHOW_BRANCHES = not args.hide_branches
    global BRANCH_CHOICES
    BRANCH_CHOICES = _parse_branch_choices(args.branch_choice)
    global BRANCH_DEFAULT
    BRANCH_DEFAULT = args.branch_default if args.branch_default >= 1 else 1

    with open(args.input, "r", encoding=args.encoding) as f:
        data = json.load(f)

    doc = json_to_doc(data)
    cli_filter_opts = {
        "filter_roles": args.filter_role,
        "exclude_roles": args.exclude_role,
        "filter_keywords": args.filter_keyword,
        "exclude_keywords": args.exclude_keyword,
        "filter_tasks": args.filter_task,
        "filter_ids": args.filter_id,
    }
    if args.format_file:
        renderer_spec, cfg = _load_renderer(args.format_file)
        if "options" not in cfg:
            cfg["options"] = {}
        filter_opts = {
            "filter_roles": cfg["options"].get("filter_roles", []),
            "exclude_roles": cfg["options"].get("exclude_roles", []),
            "filter_keywords": cfg["options"].get("filter_keywords", []),
            "exclude_keywords": cfg["options"].get("exclude_keywords", []),
            "filter_tasks": cfg["options"].get("filter_tasks", []),
            "filter_ids": cfg["options"].get("filter_ids", []),
        }
        for key, value in cli_filter_opts.items():
            if value:
                filter_opts[key] = value
        doc = _filter_doc(doc, filter_opts)
        for key, value in filter_opts.items():
            if value:
                cfg["options"][key] = value
        if args.stream:
            if renderer_spec != "templates":
                raise ValueError("Streaming only supports template rendering")
            if args.output:
                with open(args.output, "w", encoding="utf-8") as out_f:
                    _render_stream(args.input, out_f, cfg, filter_opts)
            else:
                _render_stream(args.input, sys.stdout, cfg, filter_opts)
            return
        if renderer_spec == "templates":
            md = _render_with_templates(doc, cfg)
        else:
            md = _render_with_plugin(doc, renderer_spec, cfg)
    else:
        if args.stream:
            if args.output:
                with open(args.output, "w", encoding="utf-8") as out_f:
                    _render_stream(args.input, out_f, {"options": {}}, cli_filter_opts)
            else:
                _render_stream(args.input, sys.stdout, {"options": {}}, cli_filter_opts)
            return
        doc = _filter_doc(doc, cli_filter_opts)
        md = _render_with_templates(doc, {})

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        print(md, end="")


if __name__ == "__main__":
    main()
