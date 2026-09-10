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


def _parse_scalar(s):
    s = s.strip()
    if not s or s in ("null", "None", "~"):
        return None
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if s in ("true", "True", "yes", "Yes"):
        return True
    if s in ("false", "False", "no", "No"):
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _stdlib_load_yaml(path):
    """Extract name, description, parameters[].{name,type,optional,list} and
    stages[].name using only the stdlib, for boxes with neither ruamel.yaml nor
    PyYAML installed. Not a general YAML parser."""
    result = {}
    section = None
    item = None
    item_indent = None

    def flush():
        if item is not None:
            result.setdefault(section, []).append(item)

    with open(path) as f:
        lines = f.readlines()

    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()

        if indent == 0:
            flush()
            item = None
            section = None
            key, sep, rest = content.partition(":")
            if not sep:
                continue
            key = key.strip()
            rest = rest.strip()
            if key in ("name", "description") and rest:
                result[key] = _parse_scalar(rest)
            elif key in ("parameters", "stages"):
                section = key
                result.setdefault(section, [])
            continue

        if section is None:
            continue

        if content.startswith("- "):
            flush()
            item = {}
            item_indent = indent
            content = content[2:]
            if ":" in content:
                k, _, v = content.partition(":")
                item[k.strip()] = _parse_scalar(v.strip())
            continue

        if item is not None and indent == item_indent + 2 and ":" in content:
            k, _, v = content.partition(":")
            item[k.strip()] = _parse_scalar(v.strip())

    flush()
    return result


try:
    from ruamel.yaml import YAML

    _yaml = YAML(typ="safe")

    def load_yaml(path):
        with open(path) as f:
            return _yaml.load(f)
except Exception:  # pragma: no cover - fallback if ruamel missing
    try:
        import yaml as _pyyaml

        def load_yaml(path):
            with open(path) as f:
                return _pyyaml.safe_load(f)
    except Exception:  # pragma: no cover - neither ruamel.yaml nor PyYAML installed
        load_yaml = _stdlib_load_yaml

BUILTIN_TASKS_DIR = "/opt/backend/tasks"
TEMPLATE_ROOTS = sorted(glob.glob("/opt/server_templates/workspaces/*/Automation"))
HERE = os.path.dirname(os.path.abspath(__file__))


def one_line(text):
    if not text:
        return ""
    return " ".join(str(text).split()).strip().replace("|", "\\|")


def summarize_params(doc):
    params = doc.get("parameters") or []
    names = []
    for p in params:
        if not isinstance(p, dict):
            continue
        n = p.get("name", "?")
        t = p.get("type", "?")
        arr = "[]" if p.get("list") else ""
        opt = "?" if p.get("optional") else ""
        names.append(f"{n}:{t}{arr}{opt}")
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
        "runnable definition.",
        "",
        "Source on this server:",
    ]
    for root in TEMPLATE_ROOTS:
        out.append(f"- `{root}/`")
    out.append("")
    out.append(
        "Each template's `Automation/` tree has `Workflows/` (tasks and workflows),"
    )
    out.append(
        "`Applications/`, and `Plugins/` subfolders; that folder name is what the"
    )
    out.append("server discovers each definition as.")
    out.append("")
    out.append(
        "`core` is copied into every new workspace's `Automation/` tree by default"
    )
    out.append(
        "when the workspace is created (`ghadmin workspace-create`, opt out with"
    )
    out.append(
        "`--no-core`), so its Applications and Plugins are already present there,"
    )
    out.append(
        "not something you need to copy in yourself. `example` and `test` are"
    )
    out.append("opt-in template folders you copy from explicitly.")
    out.append("")
    out.append(
        "Application and plugin *definitions themselves* (like VSAgent's) live in"
    )
    out.append(
        "the versioned application/plugin registry, not in a workspace template;"
    )
    out.append(
        "they're installed into a workspace with the built-in `System/application_checkout`"
    )
    out.append("and `System/plugin_checkout` tasks.")
    out.append("")
    out.append(
        "Since this tree changes with each release, don't rely on a stale mirror of"
    )
    out.append("it here. Enumerate what's actually on the server:")
    out.append("")
    out.append("```sh")
    out.append("ls -R /opt/server_templates/workspaces/*/Automation")
    out.append("gautil client task-list                 # includes the built-in System/ tasks")
    out.append("gautil client task-list --path=<prefix>")
    out.append("```")
    out.append("")
    out.append(
        "Read a definition in place (`Read /opt/server_templates/workspaces/<template>/Automation/...`)"
    )
    out.append(
        "to see its parameters and description before copying it into your own"
    )
    out.append("workspace's `Automation/` tree and adapting it.")
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
