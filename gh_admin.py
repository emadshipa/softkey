#!/usr/bin/env python3
"""
gh_admin.py - manage and publish the static license store on GitHub Pages.

The client (attendance_app / license_manager.py) fetches licenses.json and
verifies each key's embedded HMAC signature locally. This tool is the only
place that can generate valid signed keys or change key status/binding.

Commands:
  list [--file FILE]
  gen   --count N [--note TEXT] [--hwid HWID] [--file FILE]
  set-note KEY NOTE [--file FILE]
  bind   KEY HWID [--file FILE]
  unbind KEY [--file FILE]
  revoke KEY [--file FILE]
  reactivate KEY [--file FILE]
  delete KEY [--file FILE]
  push [--owner OWNER --repo REPO --branch BRANCH --file FILE --token TOKEN]

push publishes the local file to GitHub using the Contents API.
Token: --token or GH_TOKEN env var (needs repo write scope).
"""

import argparse
import base64
import hmac
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error

DEFAULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "licenses.json")
GH_B32_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_GH_PARTS = ["K9qR2vT8", "4mN7pX3w", "B6hJ5cL0", "eZ1sD8fA"]


def _gh_secret():
    return "ghpages::" + "::".join(_GH_PARTS)


def _b32_to_str(v, n_chars):
    out = []
    for _ in range(n_chars):
        out.append(GH_B32_ALPHABET[v & 31])
        v >>= 5
    return "".join(reversed(out))


def generate_gh_key():
    payload = os.urandom(10).hex().upper()
    payload_groups = "-".join(payload[i:i + 4] for i in range(0, 20, 4))
    digest = hmac.new(_gh_secret().encode(), payload_groups.encode(), hashlib.sha256).digest()
    sig = _b32_to_str(int.from_bytes(digest[:5], "big"), 8)
    return "%s-%s" % (payload_groups, sig)


def load_store(path):
    if not os.path.exists(path):
        return {"licenses": []}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def save_store(store, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def find(store, key):
    for lic in store.get("licenses", []):
        if lic.get("license_key") == key:
            return lic
    return None


def cmd_list(args):
    store = load_store(args.file)
    rows = store.get("licenses", [])
    if not rows:
        print("(no licenses)")
        return 0
    for lic in rows:
        print("%-34s %-9s hwid=%s note=%s" % (
            lic.get("license_key", ""), lic.get("status", ""),
            (lic.get("bound_hwid") or "-")[:12], lic.get("note", "")))
    print("\n%d license(s)" % len(rows))
    return 0


def cmd_gen(args):
    store = load_store(args.file)
    keys = []
    for _ in range(args.count):
        key = generate_gh_key()
        entry = {
            "license_key": key,
            "status": "active",
            "created_at": time.strftime("%Y-%m-%d"),
            "expires_at": None,
            "note": args.note or "",
            "bound_hwid": args.hwid or "",
            "activated_at": None,
        }
        store.setdefault("licenses", []).append(entry)
        keys.append(key)
    save_store(store, args.file)
    for k in keys:
        print(k)
    return 0


def cmd_update(args, op):
    store = load_store(args.file)
    lic = find(store, args.key)
    if lic is None:
        print("ERROR: key not found: %s" % args.key)
        return 1
    if op == "set-note":
        lic["note"] = args.note
    elif op == "bind":
        lic["bound_hwid"] = args.hwid
        lic["activated_at"] = lic.get("activated_at") or time.strftime("%Y-%m-%d")
    elif op == "unbind":
        lic["bound_hwid"] = ""
    elif op == "revoke":
        lic["status"] = "revoked"
    elif op == "reactivate":
        lic["status"] = "active"
    save_store(store, args.file)
    print("OK: %s -> %s" % (args.key, lic.get("status", "")))
    return 0


def cmd_delete(args):
    store = load_store(args.file)
    rows = store.get("licenses", [])
    kept = [r for r in rows if r.get("license_key") != args.key]
    if len(kept) == len(rows):
        print("ERROR: key not found: %s" % args.key)
        return 1
    store["licenses"] = kept
    save_store(store, args.file)
    print("OK: deleted %s" % args.key)
    return 0


def _gh_api(method, url, token, body=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "token %s" % token,
        "User-Agent": "gh-admin/1.0",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, None


def cmd_push(args):
    token = args.token or os.environ.get("GH_TOKEN", "")
    if not token:
        print("ERROR: no token. Pass --token or set GH_TOKEN.")
        return 1
    owner = args.owner
    repo = args.repo
    path = args.file
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    base = "https://api.github.com/repos/%s/%s/contents/%s" % (owner, repo, os.path.basename(path))
    status, existing = _gh_api("GET", base, token)
    body = {
        "message": "Update license store (%d keys)" % len(load_store(path).get("licenses", [])),
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": args.branch,
    }
    if status == 200 and existing and existing.get("sha"):
        body["sha"] = existing["sha"]
    elif status != 404:
        print("ERROR: cannot read current file on GitHub: %s" % status)
        return 1
    status, result = _gh_api("PUT", base, token, body)
    if status in (200, 201):
        print("OK: pushed to https://%s.github.io/%s/%s" % (owner, repo, os.path.basename(path)))
        print("OR raw: https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, args.branch, os.path.basename(path)))
        return 0
    print("ERROR: push failed (%s): %s" % (status, result))
    return 1


def main():
    parser = argparse.ArgumentParser(prog="gh_admin", description="Manage static license store for GitHub Pages")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list licenses")
    p.add_argument("--file", default=DEFAULT_FILE)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("gen", help="generate signed key(s)")
    p.add_argument("--count", type=int, default=1)
    p.add_argument("--note", default="")
    p.add_argument("--hwid", default="")
    p.add_argument("--file", default=DEFAULT_FILE)
    p.set_defaults(func=cmd_gen)

    for name, args in (("set-note", ["key", "note"]), ("bind", ["key", "hwid"]),
                       ("unbind", ["key"]), ("revoke", ["key"]), ("reactivate", ["key"])):
        p = sub.add_parser(name, help=name)
        p.add_argument("key")
        if args:
            for a in args[1:]:
                p.add_argument(a)
        p.add_argument("--file", default=DEFAULT_FILE)
        p.set_defaults(func=lambda a, n=name: cmd_update(a, n))

    p = sub.add_parser("delete", help="delete a license")
    p.add_argument("key")
    p.add_argument("--file", default=DEFAULT_FILE)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("push", help="publish licenses.json to GitHub")
    p.add_argument("--owner", default="emadshipa")
    p.add_argument("--repo", default="attendance-license-ghpages")
    p.add_argument("--branch", default="main")
    p.add_argument("--file", default=DEFAULT_FILE)
    p.add_argument("--token", default="")
    p.set_defaults(func=cmd_push)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()