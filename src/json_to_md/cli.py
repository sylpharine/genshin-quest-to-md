import argparse
import json
import sys

from . import config
from .filters import filter_doc
from .parser import json_to_doc
from .placeholders import normalize_gender
from .renderers.plugin import load_renderer, render_with_plugin
from .renderers.templates import render_with_templates
from .stream import render_stream


def parse_branch_choices(raw_list):
    choices = {}
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
        help="Name to replace #{NICKNAME}/Traveler/Traveller/玩家 and role 主角 (default: 旅行者)",
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

    config.set_unknown_role(args.unknown_role)
    config.set_traveler_name(args.traveler_name)
    config.set_traveler_gender(normalize_gender(args.traveler_gender))
    config.set_wanderer_name(args.wanderer_name)
    config.set_branch_config(
        not args.hide_branches,
        parse_branch_choices(args.branch_choice),
        args.branch_default if args.branch_default >= 1 else 1,
    )

    cli_filter_opts = {
        "filter_roles": args.filter_role,
        "exclude_roles": args.exclude_role,
        "filter_keywords": args.filter_keyword,
        "exclude_keywords": args.exclude_keyword,
        "filter_tasks": args.filter_task,
        "filter_ids": args.filter_id,
    }

    if args.format_file:
        renderer_spec, cfg = load_renderer(args.format_file)
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

        if args.stream:
            if renderer_spec != "templates":
                raise ValueError("Streaming only supports template rendering")
            if args.output:
                with open(args.output, "w", encoding="utf-8") as out_f:
                    render_stream(args.input, out_f, cfg, filter_opts)
            else:
                render_stream(args.input, sys.stdout, cfg, filter_opts)
            return

        with open(args.input, "r", encoding=args.encoding) as f:
            data = json.load(f)
        doc = json_to_doc(data)
        doc = filter_doc(doc, filter_opts)
        for key, value in filter_opts.items():
            if value:
                cfg["options"][key] = value
        if renderer_spec == "templates":
            md = render_with_templates(doc, cfg)
        else:
            md = render_with_plugin(doc, renderer_spec, cfg)
    else:
        if args.stream:
            if args.output:
                with open(args.output, "w", encoding="utf-8") as out_f:
                    render_stream(args.input, out_f, {"options": {}}, cli_filter_opts)
            else:
                render_stream(args.input, sys.stdout, {"options": {}}, cli_filter_opts)
            return
        with open(args.input, "r", encoding=args.encoding) as f:
            data = json.load(f)
        doc = json_to_doc(data)
        doc = filter_doc(doc, cli_filter_opts)
        md = render_with_templates(doc, {})

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
    else:
        print(md, end="")
