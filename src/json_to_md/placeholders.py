import re
from . import config


def safe_role(role):
    if role is None:
        return config.UNKNOWN_ROLE
    role = str(role).strip()
    return role if role else config.UNKNOWN_ROLE


def normalize_gender(value: str) -> str:
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


def replace_gender(text: str) -> str:
    if not text:
        return text

    def repl_mf(match: re.Match) -> str:
        male = match.group(1)
        female = match.group(2)
        return male if config.TRAVELER_GENDER == "M" else female

    def repl_fm(match: re.Match) -> str:
        female = match.group(1)
        male = match.group(2)
        return male if config.TRAVELER_GENDER == "M" else female

    text = re.sub(r"\{M#([^}]*)\}\{F#([^}]*)\}", repl_mf, text)
    text = re.sub(r"\{F#([^}]*)\}\{M#([^}]*)\}", repl_fm, text)
    return text


def replace_traveler(text: str) -> str:
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
    text = replace_gender(text)
    text = re.sub(r"#\{REALNAME\[[^\]]*\]\}", config.WANDERER_NAME, text)
    text = re.sub(r"\{REALNAME\[[^\]]*\]\}", config.WANDERER_NAME, text)
    for token in ("#{NICKNAME}", "{NICKNAME}", "Traveler", "Traveller", "玩家"):
        text = text.replace(token, config.TRAVELER_NAME)
    return text


def replace_role_name(role: str) -> str:
    role = safe_role(role)
    role = replace_traveler(role)
    if role == "主角":
        return config.TRAVELER_NAME
    return role
