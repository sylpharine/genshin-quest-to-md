from typing import Any, Dict, List, Optional, Tuple


def match_any(text: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    for kw in keywords:
        if kw and kw in text:
            return True
    return False


def filter_doc(doc: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
    def ensure_list(key: str) -> List[Any]:
        value = options.get(key, [])
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        raise ValueError(f"Filter option '{key}' must be a list.")

    role_include = ensure_list("filter_roles")
    role_exclude = ensure_list("exclude_roles")
    keyword_include = ensure_list("filter_keywords")
    keyword_exclude = ensure_list("exclude_keywords")
    task_filters = ensure_list("filter_tasks")
    id_filters = ensure_list("filter_ids")

    def task_match(title: str) -> bool:
        if not task_filters:
            return True
        return match_any(title, task_filters)

    def parse_id_range(value: str) -> Optional[Tuple[str, str, int, int]]:
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

    def id_match(target: Any) -> bool:
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
            range_pair = parse_id_range(fid_str)
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
        if id_filters and not task_id_match and not id_match(node_id):
            return False
        if role_exclude and role in role_exclude:
            return False
        if role_include and role not in role_include:
            return False
        if keyword_exclude and match_any(text, keyword_exclude):
            return False
        if keyword_include and not match_any(text, keyword_include):
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
        task_id_match = id_match(story_id) or id_match(task_id)
        nodes = filter_nodes(task.get("nodes", []), task_id_match)
        if not nodes:
            continue
        filtered_tasks.append(
            {
                "story_id": story_id,
                "story_title": task.get("story_title"),
                "story_desc": task.get("story_desc"),
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
