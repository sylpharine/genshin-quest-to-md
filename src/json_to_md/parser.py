from typing import Any, Dict, List, Optional, Tuple

from . import config
from .placeholders import replace_traveler, safe_role


def sort_keys_numeric(keys):
    def key_fn(k):
        try:
            return (0, int(k))
        except Exception:
            return (1, str(k))
    return sorted(keys, key=key_fn)


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


def _select_branch_index(dialog_id: str, total: int) -> int:
    idx = config.BRANCH_CHOICES.get(str(dialog_id), config.BRANCH_DEFAULT)
    if idx < 1:
        idx = 1
    if idx > total:
        idx = total
    return idx


def build_dialog_nodes(task: Dict[str, Any]) -> List[Dict[str, Any]]:
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

        role = replace_traveler(safe_role(dialog.get("role", "")))
        text_entries = dialog.get("text") or []
        is_black_screen = bool(dialog.get("isBlackScreen", False))
        dialog_entries: List[Tuple[str, Any]] = []
        for entry in text_entries:
            text = replace_traveler(entry.get("text", ""))
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
            next_role = replace_traveler(safe_role(next_dialog.get("role", "")))
            if next_role != role_name:
                return False
            next_entries = next_dialog.get("text") or []
            if not next_entries:
                return False
            next_text = replace_traveler(next_entries[0].get("text", ""))
            return next_text == text_value

        def _dialog_node(text_value: str) -> Dict[str, Any]:
            return {
                "type": "dialog",
                "id": current,
                "role": role,
                "text": text_value,
                "is_black_screen": is_black_screen,
            }

        if not config.SHOW_BRANCHES and is_multi:
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

        if not config.SHOW_BRANCHES and not is_multi:
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


def json_to_doc(data: Dict[str, Any]) -> Dict[str, Any]:
    root = data.get("data", {})
    info = root.get("info", {})
    chapter_num = replace_traveler(info.get("chapterNum", "") or "")
    chapter_title = replace_traveler(info.get("chapterTitle", "") or "")
    chapter_desc = replace_traveler(
        info.get("chapterDesc")
        or info.get("description")
        or ""
    )

    story_list = root.get("storyList") or {}
    story_keys = sort_keys_numeric(story_list.keys())

    doc: Dict[str, Any] = {
        "chapter_num": chapter_num,
        "chapter_title": chapter_title,
        "chapter_desc": chapter_desc,
        "tasks": [],
    }

    for story_key in story_keys:
        story = story_list.get(story_key, {})
        story_id = story.get("id", story_key)
        story_info = story.get("info") or {}
        story_title = replace_traveler(story_info.get("title") or "")
        story_desc = replace_traveler(story_info.get("description") or "")
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

            doc["tasks"].append(
                {
                    "story_id": story_id,
                    "story_title": story_title,
                    "story_desc": story_desc,
                    "task_id": task_id,
                    "title": title,
                    "desc": step_desc,
                    "nodes": nodes,
                }
            )

    return doc
