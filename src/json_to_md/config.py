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
    "story_title": "## {story_title}",
    "story_desc": "{story_desc}",
    "task_id": "TaskID: {task_id}",
    "task_title": "### {task_title}",
    "task_desc": "{task_desc}",
    "dialog_id": "DialogID: {dialog_id}",
    "dialog_line": "{role}：{text}",
    "dialog_cont": "    {text}",
    "branch_label": "【分支{index}】",
    "black_screen": "**_{text}_**",
}


def set_unknown_role(value: str) -> None:
    global UNKNOWN_ROLE
    UNKNOWN_ROLE = value


def set_traveler_name(value: str) -> None:
    global TRAVELER_NAME
    TRAVELER_NAME = value


def set_traveler_gender(value: str) -> None:
    global TRAVELER_GENDER
    TRAVELER_GENDER = value


def set_wanderer_name(value: str) -> None:
    global WANDERER_NAME
    WANDERER_NAME = value


def set_branch_config(show_branches: bool, choices: dict, default_index: int) -> None:
    global SHOW_BRANCHES, BRANCH_CHOICES, BRANCH_DEFAULT
    SHOW_BRANCHES = show_branches
    BRANCH_CHOICES = choices
    BRANCH_DEFAULT = default_index
