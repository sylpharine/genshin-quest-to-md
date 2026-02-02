#!/usr/bin/env python3
import argparse
import json
import re
from typing import Any, Dict, List, Optional

UNKNOWN_ROLE = "Unknown"
TRAVELER_NAME = "旅行者"
TRAVELER_GENDER = "F"


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


def _replace_traveler(text: str) -> str:
    if not text:
        return text
    if text.startswith("#") and (
        "{NICKNAME}" in text
        or "#{NICKNAME}" in text
        or "{M#" in text
        or "{F#" in text
    ):
        text = text[1:]
    text = _replace_gender(text)
    for token in ("#{NICKNAME}", "{NICKNAME}", "Traveler", "玩家"):
        text = text.replace(token, TRAVELER_NAME)
    return text


def _walk_dialog(
    items: Dict[str, Any],
    dialog_id: Any,
    indent_level: int,
    path: set,
) -> List[Dict[str, Any]]:
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
    dialog_entries = []
    for entry in text_entries:
        text = _replace_traveler(entry.get("text", ""))
        dialog_entries.append((text, entry.get("next"), is_black_screen))

    if not dialog_entries:
        return []

    dialog_type = dialog.get("type", "")
    is_multi = dialog_type == "MultiDialog"
    unique_next = []
    for _, next_id, _ in dialog_entries:
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

    output: List[Dict[str, Any]] = []
    if branching and is_multi and len(unique_next) == 1:
        for idx, (text, _, _) in enumerate(dialog_entries, 1):
            output.append({"type": "label", "indent": indent_level, "text": f"【分支{idx}】"})
            output.append(
                {
                    "type": "dialog",
                    "indent": indent_level + 1,
                    "role": role,
                    "text": text,
                    "is_black_screen": is_black_screen,
                }
            )
        next_id = unique_next[0]
        output.extend(_walk_dialog(items, next_id, indent_level, path))
        return output

    if branching and is_multi:
        echo_next_ids = []
        for text, next_id, _ in dialog_entries:
            if not _is_echo(next_id, role, text):
                echo_next_ids = []
                break
            next_dialog = items.get(str(next_id))
            next_entries = next_dialog.get("text") or []
            next_ids = []
            for entry in next_entries:
                nid = entry.get("next")
                if nid is not None and nid not in next_ids:
                    next_ids.append(nid)
            if len(next_ids) != 1:
                echo_next_ids = []
                break
            echo_next_ids.append(next_ids[0])

        if echo_next_ids and all(nid == echo_next_ids[0] for nid in echo_next_ids):
            for idx, (text, _, _) in enumerate(dialog_entries, 1):
                output.append({"type": "label", "indent": indent_level, "text": f"【分支{idx}】"})
                output.append(
                    {
                        "type": "dialog",
                        "indent": indent_level + 1,
                        "role": role,
                        "text": text,
                        "is_black_screen": is_black_screen,
                    }
                )
            output.extend(_walk_dialog(items, echo_next_ids[0], indent_level, path))
            return output

    if branching:
        for idx, (text, next_id, _) in enumerate(dialog_entries, 1):
            output.append({"type": "label", "indent": indent_level, "text": f"【分支{idx}】"})
            if not (is_multi and _is_echo(next_id, role, text)):
                output.append(
                    {
                        "type": "dialog",
                        "indent": indent_level + 1,
                        "role": role,
                        "text": text,
                        "is_black_screen": is_black_screen,
                    }
                )
            if next_id is not None:
                output.extend(_walk_dialog(items, next_id, indent_level + 1, set(path)))
        return output

    for text, _, _ in dialog_entries:
        output.append(
            {
                "type": "dialog",
                "indent": indent_level,
                "role": role,
                "text": text,
                "is_black_screen": is_black_screen,
            }
        )

    next_id = unique_next[0] if unique_next else None
    if next_id is None:
        return output
    output.extend(_walk_dialog(items, next_id, indent_level, path))
    return output


def _extract_dialogue_lines(task: Dict[str, Any]) -> List[str]:
    items = task.get("items") or {}
    init_dialog = task.get("initDialog")
    if init_dialog is None:
        return []
    entries = _walk_dialog(items, init_dialog, 0, set())

    lines: List[str] = []
    last_role = None
    last_indent = None
    last_was_dialog = False

    for entry in entries:
        indent = entry["indent"]
        prefix = "  " * indent
        if entry["type"] == "label":
            lines.append(f"{prefix}{entry['text']}")
            last_was_dialog = False
            continue
        role = entry["role"]
        text = entry["text"]
        is_black_screen = bool(entry.get("is_black_screen", False))
        if is_black_screen:
            lines.append(f"{prefix}*{text}*")
            last_was_dialog = False
            continue
        if last_was_dialog and role == last_role and indent == last_indent:
            lines.append(f"{prefix}    {text}")
        else:
            lines.append(f"{prefix}{role}：{text}")
            last_role = role
            last_indent = indent
            last_was_dialog = True

    return lines


def json_to_md(data: Dict[str, Any]) -> str:
    root = data.get("data", {})
    info = root.get("info", {})
    chapter_num = _replace_traveler(info.get("chapterNum", "") or "")
    chapter_title = _replace_traveler(info.get("chapterTitle", "") or "")
    chapter_line = " ".join([part for part in [chapter_num, chapter_title] if part]).strip()
    if chapter_title:
        chapter_line = chapter_line.replace(chapter_title, f"《{chapter_title}》")

    story_list = root.get("storyList") or {}
    story_keys = _sort_keys_numeric(story_list.keys())

    # Try to pick the first story description as chapter description.
    chapter_desc = ""
    if story_keys:
        first_story = story_list.get(story_keys[0], {})
        chapter_desc = _replace_traveler(
            (first_story.get("info") or {}).get("description") or ""
        )

    md_lines: List[str] = []
    if chapter_line:
        md_lines.append(f"# {chapter_line}")
    if chapter_desc:
        md_lines.append(chapter_desc)

    for story_key in story_keys:
        story = story_list.get(story_key, {})
        story_steps = story.get("story") or {}
        for step_key in _sort_keys_numeric(story_steps.keys()):
            step = story_steps.get(step_key, {})
            title = _replace_traveler(step.get("title") or "")
            if title:
                md_lines.append("")
                md_lines.append(f"## {title}")
            step_desc = step.get("stepDescription")
            if step_desc:
                md_lines.append(_replace_traveler(step_desc))

            task_data_list = step.get("taskData") or []
            for task in task_data_list:
                if task.get("taskType") != "resultDialogue":
                    continue
                lines = _extract_dialogue_lines(task)
                md_lines.extend(lines)

    return "\n".join(md_lines).strip() + "\n"


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
        help="Name to replace #{NICKNAME}/Traveler/玩家 (default: 旅行者)",
    )
    parser.add_argument(
        "--traveler-gender",
        default="F",
        help="Gender for {M#}{F#} placeholders: M or F (default: F)",
    )
    args = parser.parse_args()

    global UNKNOWN_ROLE
    UNKNOWN_ROLE = args.unknown_role
    global TRAVELER_NAME
    TRAVELER_NAME = args.traveler_name
    global TRAVELER_GENDER
    TRAVELER_GENDER = _normalize_gender(args.traveler_gender)

    with open(args.input, "r", encoding=args.encoding) as f:
        data = json.load(f)

    md = json_to_md(data)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        print(md, end="")


if __name__ == "__main__":
    main()
