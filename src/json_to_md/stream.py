import json
from typing import Any, Dict, List, Optional, Tuple

from .filters import filter_doc
from .parser import build_dialog_nodes, sort_keys_numeric
from .placeholders import replace_traveler
from .renderers.templates import (
    format_template,
    normalize_templates_config,
    render_nodes_with_templates,
)


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


def render_stream(
    input_path: str,
    output_handle,
    config_dict: Dict[str, Any],
    filter_opts: Dict[str, Any],
) -> None:
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

    decoder = json.JSONDecoder()
    with open(input_path, "r", encoding="utf-8") as f:
        info, buffer = _stream_find_object(f, "info", decoder)
        if info is None:
            return
        chapter_num = replace_traveler(info.get("chapterNum", "") or "")
        chapter_title = replace_traveler(info.get("chapterTitle", "") or "")
        chapter_desc = replace_traveler(
            info.get("chapterDesc")
            or info.get("description")
            or ""
        )
        if chapter_title:
            title_line = _fmt(
                "chapter_title",
                chapter_num=chapter_num,
                chapter_title=chapter_title,
            )
            if title_line:
                output_handle.write(title_line.strip() + "\n")
        elif chapter_num and _tpl("chapter_title"):
            output_handle.write(f"# {chapter_num}\n")

        if chapter_desc:
            desc_line = _fmt("chapter_desc", chapter_desc=chapter_desc)
            if desc_line:
                output_handle.write(desc_line + "\n")

        for _, story in _stream_story_entries(f, buffer, decoder):
            if not isinstance(story, dict):
                continue

            story_id = story.get("id")
            story_info = story.get("info") or {}
            story_title = replace_traveler(story_info.get("title") or "")
            story_desc = replace_traveler(story_info.get("description") or "")
            story_emitted = False
            story_steps = story.get("story") or {}
            for step_key in sort_keys_numeric(story_steps.keys()):
                step = story_steps.get(step_key, {})
                task_id = step.get("id", step_key)
                title = replace_traveler(step.get("title") or "")
                step_desc = step.get("stepDescription")
                step_desc = replace_traveler(step_desc) if step_desc else ""

                task_data_list = step.get("taskData") or []
                nodes: List[Dict[str, Any]] = []
                for task in task_data_list:
                    if task.get("taskType") != "resultDialogue":
                        continue
                    nodes.extend(build_dialog_nodes(task))

                temp_doc = {
                    "chapter_num": chapter_num,
                    "chapter_title": chapter_title,
                    "chapter_desc": "",
                    "tasks": [
                        {
                            "story_id": story_id,
                            "story_title": story_title,
                            "story_desc": story_desc,
                            "task_id": task_id,
                            "title": title,
                            "desc": step_desc,
                            "nodes": nodes,
                        }
                    ],
                }
                filtered = filter_doc(temp_doc, filter_opts)
                if not filtered.get("tasks"):
                    continue
                task = filtered["tasks"][0]

                if not story_emitted:
                    if task.get("story_id"):
                        story_line = _fmt("story_id", story_id=task["story_id"])
                        if story_line:
                            output_handle.write(story_line + "\n")
                    if task.get("story_title") and _tpl("story_title"):
                        title_line = _fmt("story_title", story_title=task["story_title"])
                        if title_line:
                            output_handle.write("\n" + title_line + "\n")
                    if task.get("story_desc"):
                        desc_line = _fmt("story_desc", story_desc=task["story_desc"])
                        if desc_line:
                            output_handle.write(desc_line + "\n")
                    story_emitted = True
                if task.get("task_id"):
                    task_line = _fmt("task_id", task_id=task["task_id"])
                    if task_line:
                        output_handle.write(task_line + "\n")

                if task.get("title") and _tpl("task_title"):
                    output_handle.write("\n")
                    title_line = _fmt("task_title", task_title=task["title"])
                    if title_line:
                        output_handle.write(title_line + "\n")
                if task.get("desc"):
                    desc_line = _fmt("task_desc", task_desc=task["desc"])
                    if desc_line:
                        output_handle.write(desc_line + "\n")
                if task.get("nodes"):
                    lines = render_nodes_with_templates(
                        task["nodes"], templates, options, 0
                    )
                    if lines:
                        output_handle.write("\n".join(lines) + "\n")
