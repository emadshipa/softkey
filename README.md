# SoftKey

Static license store for **Attendance Reporter** hosted on GitHub Pages — no
server needed (replaces the optional `hrkey.onrender.com` service). Includes a
browser admin panel with **login + employee database + permissions**.

- Panel: **https://emadshipa.github.io/softkey/**
- Store: `https://emadshipa.github.io/softkey/licenses.json`

## How it works

- New license keys carry an **embedded HMAC signature** (6th group). The client
  verifies the signature locally and reads status/binding from
  `licenses.json` published to GitHub.
- `licenses.json` is the only source of truth: `active`/`revoked` status and the
  `bound_hwid` of each key. A key that is not listed in the store is rejected.
- The signing secret ships inside the EXE, so this is **obfuscation**, not
  server-grade security. Only someone with this repo's write access can mint
  keys or change status.

## Files

| File | Purpose |
| ---- | ------- |
| `licenses.json` | The license store (managed via the web panel or `gh_admin.py`) |
| `users.json` | Employee accounts (PBKDF2-hashed passwords) + roles/permissions |
| `index.html` | Static web admin panel: login, licenses, employees |
| `gh_admin.py` | CLI tool: generate keys, bind/revoke, publish to GitHub |

## Web admin panel (no install, runs in the browser)

Open: **https://emadshipa.github.io/softkey/**

1. First time only: open **إعدادات الاتصال** on the login screen, enter a GitHub
   token (classic PAT with `public_repo` / `repo`) — needed to save anything.
2. Log in with an employee account. The seeded first account is:
   - username: `admin`
   - password: `Tigertopto@hr`  ← **change it after first login**
3. **التراخيص** tab: enter the signing secret once, then **تحميل التراخيص**,
   **توليد**, and **ربط/فك ربط/إلغاء/حذف/ملاحظة**. Press
   **حفظ التغييرات على GitHub** to publish.
4. **الموظفون** tab (needs `manage_users`): add employees, set role and
   per-task permissions, reset passwords, enable/disable or delete accounts.

### Permissions

`view`, `generate`, `bind`, `revoke`, `delete`, `note`, `manage_users`.
Role `admin` implies all permissions. Buttons are shown/hidden per permission.

### Security note (important)

GitHub Pages is static, so login and permissions are enforced **in the browser**
and there is no server-side database. The real write boundary is the **GitHub
token**: whoever holds it can change the repo. Keep the token only on trusted
admin machines. If you need real, enforced access control, use the optional
`attendance-license-server` (FastAPI) instead — it has a server-side users DB.

## Admin CLI (alternative to the panel)

```powershell
python gh_admin.py list
python gh_admin.py gen --count 2 --note "PC-1 PC-2"
python gh_admin.py bind XXXX-XXXX-XXXX-XXXX-XXXX-XXXX <hwid>
python gh_admin.py revoke XXXX-...
python gh_admin.py unbind XXXX-...
$env:GH_TOKEN = "ghp_..."   # or --token
python gh_admin.py push
```

## Client configuration

The current Attendance Reporter build **uses this store by default** (no
`onrender.com`):

```
https://emadshipa.github.io/softkey/licenses.json
```

Override per PC via `%APPDATA%\AttendanceReporter\settings.json`:

```json
{
  "license_store_url": "https://raw.githubusercontent.com/emadshipa/softkey/main/licenses.json",
  "license_mode": "static"
}
```

Mode selection: `license_mode` (default `static`). In `static` mode the store URL
is: explicit `license_store_url` → `LICENSE_STORE_URL` env → default above.

## Schemas

`licenses.json`:

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

`users.json`:

```json
{
  "users": [
    {
      "username": "admin",
      "name": "المدير العام",
      "role": "admin | user",
      "permissions": ["view", "generate", "bind", "revoke", "delete", "note", "manage_users"],
      "active": true,
      "password_hash": "pbkdf2$120000$<salt-b64>$<hash-b64>",
      "created_at": "2026-10-10"
    }
  ]
}
```
