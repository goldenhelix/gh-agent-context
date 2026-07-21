#!/usr/bin/env python3
"""Generate searchable Markdown indexes of the task/workflow examples that live
ON this VS Warehouse server, so an agent can grep one file instead of walking
the filesystem.

Sources indexed:
  * /opt/backend/tasks                                    -> built-in-tasks.md
  * /opt/server_templates/workspaces/*/Automation         -> server-templates.md

Run on the server (or any box with those paths):
    python3 server-index/generate-index.py

Re-run whenever the server image is upgraded. Output is committed so an off-server
clone still has something to search; the server-local files are the source of truth.
"""
import os
import sys
import glob

try:
    from ruamel.yaml import YAML

    _yaml = YAML(typ="safe")

    def load_yaml(path):
        with open(path) as f:
            return _yaml.load(f)
except Exception:  # pragma: no cover - fallback if ruamel missing
    import yaml as _pyyaml

    def load_yaml(path):
        with open(path) as f:
            return _pyyaml.safe_load(f)

BUILTIN_TASKS_DIR = "/opt/backend/tasks"
TEMPLATE_ROOTS = sorted(glob.glob("/opt/server_templates/workspaces/*/Automation"))
HERE = os.path.dirname(os.path.abspath(__file__))


def one_line(text):
    if not text:
        return ""
    return " ".join(str(text).split()).strip()


def summarize_params(doc):
    params = doc.get("parameters") or []
    names = []
    for p in params:
        if not isinstance(p, dict):
            continue
        n = p.get("name", "?")
        t = p.get("type", "?")
        opt = "?" if p.get("optional") else ""
        names.append(f"{n}:{t}{opt}")
    return ", ".join(names)


def summarize_stages(doc):
    stages = doc.get("stages") or []
    return " -> ".join(s.get("name", "?") for s in stages if isinstance(s, dict))


def scan_dir(root, kinds):
    """kinds: dict suffix -> ('task'|'workflow'|'plugin'|'application')."""
    rows = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in sorted(files):
            for suffix, kind in kinds.items():
                if fn.endswith(suffix):
                    full = os.path.join(dirpath, fn)
                    rel = os.path.relpath(full, root)
                    try:
                        doc = load_yaml(full) or {}
                    except Exception as e:
                        rows.append(
                            (kind, rel, full, "(unparseable: %s)" % e, "", "")
                        )
                        continue
                    name = one_line(doc.get("name", fn))
                    desc = one_line(doc.get("description", ""))
                    if kind == "task":
                        extra = summarize_params(doc)
                    elif kind == "workflow":
                        extra = summarize_stages(doc)
                    else:
                        extra = ""
                    rows.append((kind, rel, full, name, desc, extra))
    return rows


TASK_KINDS = {
    ".task.yaml": "task",
    ".workflow.yaml": "workflow",
    ".plugin.yaml": "plugin",
    ".application.yaml": "application",
}


def write_builtin():
    rows = scan_dir(BUILTIN_TASKS_DIR, {".task.yaml": "task"})
    out = [
        "# Built-in (system) tasks",
        "",
        "System tasks shipped with the server, available in **every** workspace under the",
        "`System/` task path (run them with `gautil client task-run System/<name>`).",
        f"Source on this server: `{BUILTIN_TASKS_DIR}/`. Regenerate with",
        "`server-index/generate-index.py`.",
        "",
        "| Task path | Name | Parameters | Description |",
        "|---|---|---|---|",
    ]
    for _kind, rel, _full, name, desc, extra in sorted(rows, key=lambda r: r[1]):
        base = rel[: -len(".task.yaml")]
        path = f"System/{base}"
        out.append(f"| `{path}` | {name} | {extra or '—'} | {desc} |")
    out.append("")
    out.append(f"_{len(rows)} built-in tasks indexed._")
    return "\n".join(out) + "\n"


def write_templates():
    out = [
        "# Server workspace templates (example tasks & workflows)",
        "",
        "Tasks, workflows, plugins, and applications shipped as **workspace templates** on",
        "this server. They are the best worked examples to copy from: each is a real,",
        "runnable definition. To use one, copy it into your workspace's `Automation/` tree",
        "(or read it in place with `Read`), then adapt.",
        "",
        "Source on this server:",
    ]
    for root in TEMPLATE_ROOTS:
        out.append(f"- `{root}/`")
    out.append("")
    out.append("Regenerate with `server-index/generate-index.py`.")
    out.append("")

    total = 0
    for root in TEMPLATE_ROOTS:
        rows = scan_dir(root, TASK_KINDS)
        total += len(rows)
        ws = root.split("/workspaces/")[-1].split("/")[0]
        out.append("")
        out.append(f"## Workspace template: `{ws}`")
        out.append("")
        out.append("| Kind | File | Name | Stages / Params | Description |")
        out.append("|---|---|---|---|---|")
        for kind, rel, full, name, desc, extra in sorted(
            rows, key=lambda r: (r[0], r[1])
        ):
            out.append(
                f"| {kind} | `{full}` | {name} | {extra or '—'} | {desc} |"
            )
    out.append("")
    out.append(f"_{total} template definitions indexed across {len(TEMPLATE_ROOTS)} workspace template(s)._")
    return "\n".join(out) + "\n"


def main():
    wrote = []
    if os.path.isdir(BUILTIN_TASKS_DIR):
        p = os.path.join(HERE, "built-in-tasks.md")
        with open(p, "w") as f:
            f.write(write_builtin())
        wrote.append(p)
    else:
        print(f"skip: {BUILTIN_TASKS_DIR} not present", file=sys.stderr)

    if TEMPLATE_ROOTS:
        p = os.path.join(HERE, "server-templates.md")
        with open(p, "w") as f:
            f.write(write_templates())
        wrote.append(p)
    else:
        print("skip: no /opt/server_templates workspace Automation dirs", file=sys.stderr)

    for p in wrote:
        print("wrote", p)


if __name__ == "__main__":
    main()
