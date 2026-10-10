# attendance-license-ghpages

Static license store for **Attendance Reporter** hosted on GitHub Pages — no
server needed (replaces the optional `hrkey.onrender.com` service).

## How it works

- New license keys carry an **embedded HMAC signature** (6th group). The client
  verifies the signature locally and reads status/binding from
  `licenses.json` published to GitHub.
- `licenses.json` is the only source of truth: `active`/`revoked` status and the
  `bound_hwid` of each key.
- The signing secret ships inside the EXE, so this is **obfuscation**, not
  server-grade security. Only someone with this repo's write access can mint
  keys or change status.

## Files

| File | Purpose |
| ---- | ------- |
| `licenses.json` | The store (manually managed via `gh_admin.py`) |
| `gh_admin.py` | CLI tool: generate keys, bind/revoke, publish to GitHub |

## Admin workflow (run on the admin PC)

```powershell
# list current keys
python gh_admin.py list

# generate 2 keys for two PCs and install the printed keys on them
python gh_admin.py gen --count 2 --note "PC-1 PC-2"

# after each new PC shows its Hardware ID (from the activation dialog),
# bind its key to that hwid
python gh_admin.py bind XXXX-XXXX-XXXX-XXXX-XXXX-XXXX <hwid>

# publish everything to GitHub (repo write token -> GH_TOKEN or --token)
$env:GH_TOKEN = "ghp_..."
python gh_admin.py push

# revoke / reactivate / unbind a key
python gh_admin.py revoke XXXX-...
python gh_admin.py reactivate XXXX-...
python gh_admin.py unbind XXXX-...
```

The client will pick up the change on its next online check. A revoked key
stops working within one check; a key bound to another PC is rejected.

## Client configuration

On each attendance PC, set the store URL so the app uses the static mode
(instead of a server). Add this key to
`%APPDATA%\AttendanceReporter\settings.json`:

```json
{
  "license_store_url": "https://raw.githubusercontent.com/emadshipa/attendance-license-ghpages/main/licenses.json"
}
```

GitHub Pages URL alternative (if Pages is enabled on the repo branch):

```json
{
  "license_store_url": "https://emadshipa.github.io/attendance-license-ghpages/licenses.json"
}
```

When `license_store_url` is empty, the app keeps using the old
`license_server_url` (server mode) — so existing installs are unaffected.

## Store schema

```json
{
  "licenses": [
    {
      "license_key": "XXXX-XXXX-XXXX-XXXX-XXXX-XXXX",
      "status": "active | revoked",
      "created_at": "2026-10-10",
      "expires_at": null,
      "note": "PC-1",
      "bound_hwid": "",
      "activated_at": null
    }
  ]
}
```

- `status = active` → allowed.
- `status = revoked` → rejected even if previously activated locally.
- `bound_hwid` empty → any device (bind it the same day to keep control).
- `bound_hwid` set → only that exact Hardware ID may activate.