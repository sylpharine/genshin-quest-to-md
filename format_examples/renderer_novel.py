def render(doc, options):
    lines = []
    chapter_num = doc.get("chapter_num", "")
    chapter_title = doc.get("chapter_title", "")
    if chapter_num or chapter_title:
        title = " ".join([p for p in [chapter_num, f"《{chapter_title}》"] if p])
        lines.append(title)
    if doc.get("chapter_desc"):
        lines.append(doc["chapter_desc"])

    branch_prefix = options.get("branch_prefix", "> ")
    branch_label = options.get("branch_label", "分支{index}")
    dialog_sep = options.get("dialog_sep", "\n")

    def render_nodes(nodes, indent=0):
        for node in nodes:
            if node["type"] == "branch":
                for idx, option in enumerate(node["options"], 1):
                    lines.append(f"{branch_prefix}{branch_label.format(index=idx)}")
                    render_nodes(option, indent + 1)
                continue
            if node.get("is_black_screen"):
                lines.append(f"*{node['text']}*")
                continue
            role = node.get("role", "")
            text = node.get("text", "")
            if role:
                lines.append(f"{role}：{text}")
            else:
                lines.append(text)

    for task in doc.get("tasks", []):
        if task.get("title"):
            lines.append("\n## " + task["title"])
        if task.get("desc"):
            lines.append(task["desc"])
        render_nodes(task.get("nodes", []))

    return dialog_sep.join(lines).strip() + "\n"
