#!/usr/bin/env python3
"""Re-download the VS Warehouse OpenAPI specs from the running server so the static
copies in this folder match the exact version the server is on.

Auth: uses the same env + cookie mechanism the shipped server tasks use
(`/opt/backend/tasks/workflow_checkout.task.yaml`):
  1. GET  {GH_SERVER_URL}/auth/api/authenticationMethod  -> .sessionCookieName
  2. send Cookie: <sessionCookieName>=<GH_SESSION_KEY> on every request
  3. GET  {GH_SERVER_URL}/auth/api/me/openApiUrls         -> [{url, name}, ...]
  4. download each spec

By default only the **workspace-agnostic** specs are refreshed (the Auth API and the
current workspace's Workflow/Catalogs/Files/Lookup APIs), written to fixed filenames so
they line up with what this folder already ships:

  Auth API            -> openapi.json
  Workflow (mcp) API  -> workflow-api.json
  Catalogs API        -> catalogs-api.yaml
  Files API           -> files-api.yaml
  Lookup API          -> lookup-api.yaml

Run on the server (env is already set in the agent runtime):
    python3 vswarehouse/api/refresh-api-specs.py
    python3 vswarehouse/api/refresh-api-specs.py --all   # also dump every workspace's specs

Requires: curl (present in the server image). No third-party Python deps.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# name (from openApiUrls) -> local filename. Matched case-insensitively on a substring
# so it survives the "<Workspace> " prefix the server adds to per-workspace spec names.
NAME_TO_FILE = [
    ("auth api", "openapi.json"),
    ("workflow api", "workflow-api.json"),
    ("catalogs api", "catalogs-api.yaml"),
    ("files api", "files-api.yaml"),
    ("lookup api", "lookup-api.yaml"),
]


# The committed specs must not hard-code a real deployment. Scrub the live host and
# workspace id (which appear in each spec's `servers:` url) to neutral placeholders.
PLACEHOLDER_HOST = "example.varseq.com"
PLACEHOLDER_WORKSPACE = "my_workspace"


def env(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"error: {name} is not set (run this on the server / in the agent runtime)")
    return v


def scrub(body, host, workspace):
    if host:
        body = body.replace(host, PLACEHOLDER_HOST)
    if workspace:
        # only the workspace path segment (avoid clobbering unrelated substrings)
        body = body.replace(f"/w/{workspace}/", f"/w/{PLACEHOLDER_WORKSPACE}/")
    return body


def curl(url, cookie=None):
    # -f: fail (nonzero exit) on a 4xx/5xx response instead of returning the error body as
    # if it were a spec. -S: keep stderr on so a -f failure still reports something.
    cmd = ["curl", "-k", "-s", "-S", "-f", "-H", "accept: application/json"]
    if cookie:
        cmd += ["-H", f"Cookie: {cookie}"]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"error: curl failed for {url} (exit {out.returncode}): {out.stderr.strip()}")
    return out.stdout


def looks_like_spec(body, is_json):
    if is_json:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict) and "paths" in parsed
    return "\npaths:" in body or body.startswith("paths:")


def main():
    do_all = "--all" in sys.argv
    server = env("GH_SERVER_URL").rstrip("/")
    session_key = env("GH_SESSION_KEY")
    workspace = os.environ.get("GH_WORKSPACE_ID", "")
    # hostname (without scheme) as it appears in the specs' servers url, incl. an optional :port
    host = server.split("://", 1)[-1]

    auth = json.loads(curl(f"{server}/auth/api/authenticationMethod"))
    cookie_name = auth.get("sessionCookieName")
    if not cookie_name:
        sys.exit("error: could not resolve sessionCookieName from /auth/api/authenticationMethod")
    cookie = f"{cookie_name}={session_key}"

    specs = json.loads(curl(f"{server}/auth/api/me/openApiUrls", cookie))
    if not isinstance(specs, list):
        sys.exit(f"error: unexpected openApiUrls response: {specs}")

    written = []
    for spec in specs:
        url, name = spec.get("url", ""), spec.get("name", "")
        is_this_ws = ("/auth/" in url) or (workspace and f"/w/{workspace}/" in url)
        if not do_all and not is_this_ws:
            continue

        target = None
        low = name.lower()
        for needle, fname in NAME_TO_FILE:
            if needle in low:
                target = fname
                break
        if target is None:
            if do_all:
                # dump unknown/other-workspace specs under a derived name
                target = url.strip("/").replace("/", "_").replace(".json", "").replace(".yaml", "")
                target += ".yaml" if url.endswith(".yaml") else ".json"
            else:
                continue

        is_json = target.endswith(".json")
        raw = curl(f"{server}{url}", cookie)
        if not looks_like_spec(raw, is_json):
            print(f"warning: {name} ({url}) has no 'paths' key, refusing to overwrite {target}", file=sys.stderr)
            continue
        body = scrub(raw, host, workspace)
        # pretty-print JSON specs; leave YAML as-is
        if is_json:
            body = json.dumps(json.loads(body), indent=2) + "\n"
        path = os.path.join(HERE, target)
        with open(path, "w") as f:
            f.write(body)
        written.append((name, url, target))

    for name, url, target in written:
        print(f"wrote {target:22s}  <- {url}   ({name})")
    if not written:
        print("nothing written (no matching specs for this workspace; try --all)", file=sys.stderr)


if __name__ == "__main__":
    main()
