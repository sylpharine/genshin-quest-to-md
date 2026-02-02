def render(doc, options):
    lines = []
    skip_fields = set(options.get("skip_fields", []))
    indent_unit = options.get("indent_unit", "  ")
    cont_prefix = options.get("dialog_cont_prefix", "    ")

    chapter_num = doc.get("chapter_num", "")
    chapter_title = doc.get("chapter_title", "")
    if chapter_num or chapter_title:
        title = " ".join([p for p in [chapter_num, f"《{chapter_title}》"] if p])
        lines.append(title)
    if doc.get("chapter_desc") and "chapter_desc" not in skip_fields:
        lines.append(doc["chapter_desc"])

    branch_prefix = options.get("branch_prefix", "> ")
    branch_label = options.get("branch_label", "分支{index}")
    dialog_sep = options.get("dialog_sep", "\n")
    story_id_fmt = options.get("story_id_fmt", "StoryID: {story_id}")
    task_id_fmt = options.get("task_id_fmt", "TaskID: {task_id}")
    dialog_id_fmt = options.get("dialog_id_fmt", "DialogID: {dialog_id}")

    def render_nodes(nodes, indent=0):
        last_role = None
        last_indent = None
        last_was_dialog = False
        for node in nodes:
            prefix = indent_unit * indent
            if node["type"] == "branch":
                for idx, option in enumerate(node["options"], 1):
                    if "branch_label" not in skip_fields:
                        lines.append(f"{prefix}{branch_prefix}{branch_label.format(index=idx)}")
                    render_nodes(option, indent + 1)
                continue
            if node.get("is_black_screen"):
                if "black_screen" not in skip_fields:
                    lines.append(f"{prefix}*{node['text']}*")
                last_was_dialog = False
                continue
            role = node.get("role", "")
            text = node.get("text", "")
            dialog_id = node.get("id")
            if dialog_id and "dialog_id" not in skip_fields:
                lines.append(prefix + dialog_id_fmt.format(dialog_id=dialog_id))
            if last_was_dialog and role == last_role and indent == last_indent:
                lines.append(prefix + cont_prefix + text)
            else:
                if role:
                    lines.append(f"{prefix}{role}：{text}")
                else:
                    lines.append(prefix + text)
                last_role = role
                last_indent = indent
                last_was_dialog = True

    for task in doc.get("tasks", []):
        story_id = task.get("story_id")
        task_id = task.get("task_id")
        if story_id and "story_id" not in skip_fields:
            lines.append(story_id_fmt.format(story_id=story_id))
        if task_id and "task_id" not in skip_fields:
            lines.append(task_id_fmt.format(task_id=task_id))
        if task.get("title") and "task_title" not in skip_fields:
            lines.append("\n## " + task["title"])
        if task.get("desc") and "task_desc" not in skip_fields:
            lines.append(task["desc"])
        render_nodes(task.get("nodes", []))

    return dialog_sep.join(lines).strip() + "\n"
