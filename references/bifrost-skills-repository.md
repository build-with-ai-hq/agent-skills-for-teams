# Bifrost Skills Repository: central registry, marketplace, rollout and rollback

Read this when setting up Bifrost as the team's skills registry, registering it as a marketplace for Claude Code, Codex or Claude Desktop, automating skill publishing from CI, or rolling a skill forward or back for everyone.

Source of truth for every step here: https://docs.getbifrost.ai/features/skills-repository. If the UI or API differs from what is written below, follow the docs.

## What it is

Bifrost is an open-source (Apache 2.0) AI gateway (https://github.com/maximhq/bifrost). Its OSS **Skills Repository** stores Agent Skills (agentskills.io format) centrally and serves them to harnesses:

- A skill is a stable identity (its name). Every save creates an immutable SemVer version.
- Files belong to versions, so older installs stay reproducible.
- One version per skill is **served**; that is what marketplaces and downloads expose.
- Each skill is published as plugin `bifrost-<skill-name>`; `bifrost-all-skills` bundles every served skill.
- Management (create, edit, publish, shift) is authenticated. Marketplace and download URLs are public so CLI agents can fetch skills without dashboard credentials.

Use it instead of (or alongside) a git skills repo when: non-engineers author skills, you want one-click serve/rollback for the whole team without anyone running `npx skills update`, or you already run Bifrost for model traffic.

## 1. Run Bifrost

```bash
npx -y @maximhq/bifrost                       # or:
docker run -p 8080:8080 -v $(pwd)/data:/app/data maximhq/bifrost
# UI + API on http://localhost:8080
```

Production: pin a version (`maximhq/bifrost:<version>` or `npx -y @maximhq/bifrost --transport-version <version>`), enable dashboard/management auth, terminate TLS, and persist the data directory.

Marketplace prerequisites (both required):

1. `git` on the Bifrost server's `PATH`. Restart Bifrost after installing it. Without git, marketplace routes are not registered. If you run the container image, confirm git is available inside it (`docker exec <container> git --version`).
2. An **External Client URL**: the public base URL clients use to reach Bifrost. Set it in **Skills -> Skills Settings** and click **Save Changes**, or in `config.json`:

```json
{
  "client": {
    "skills_external_client_url": "https://bifrost.example.com"
  }
}
```

Helm: `bifrost.client.skillsExternalClientUrl`. The value accepts `env.BIFROST_SKILLS_URL`-style environment references and vault references. Bifrost never derives this URL from `Host` or forwarded headers. If it is unset or empty, **Register as Marketplace** is disabled and marketplace endpoints return 503.

For a single-machine trial `http://localhost:8080` works; for a team it must be reachable from every engineer's machine (internal DNS or VPN is fine).

Creating, editing, versioning and direct downloads work without git or the URL; only the marketplace needs them.

## 2. Create a skill

Dashboard: **Skills -> Skills Repository -> New Skill** (or **Create Skill** on the empty state).

Left sidebar: **Details**, **Metadata**, **Extra Frontmatter**, then the file tree.

| Field | Notes |
|---|---|
| Name | Lowercase letters, numbers, hyphens. Cannot be changed later; it becomes the plugin name `bifrost-<name>`. Reserved: `all-skills`, `all`, `claude-code`, `codex`. |
| Description | Same rules as the spec: what + when, <= 1024 chars. This is still what makes the skill trigger; see `writing-skills-that-trigger.md`. |
| License | Optional SPDX id, e.g. `MIT`. |
| Compatibility | Optional; intended harnesses. |
| Allowed tools | Optional, experimental frontmatter. |
| Metadata | Key-value pairs emitted under `metadata:`. |
| Extra Frontmatter | JSON for additional top-level keys (use sparingly; non-spec keys are harness-specific). |

Bifrost generates the YAML frontmatter from these fields. Click the **SKILL.md** node to write only the Markdown body (Edit/Preview tabs).

### Attach files

In the file tree use **Add file**, **Add Folder** or **Upload folder** (preserves structure). **Add file** sources:

| Source | Behavior | Use for |
|---|---|---|
| Upload | Stored file; replace by delete + re-upload | Scripts, binaries, large references |
| From text | Editable inline content | Short references, templates |
| From URL | **Fetched when the skill is served**; stays in sync with the remote | Only content you deliberately want live |
| From data URL | Inline base64 content | Small generated assets |

Governance gotcha: a version is immutable, but a **From URL** file is not frozen by it. If the remote changes, every install of that "immutable" version changes. For anything that must be reproducible or reviewed (scripts above all), upload or paste the content.

Reference files from the body by typing `@` in the editor and picking the file; Bifrost inserts a relative link:

```md
Before responding, read @[style-guide.md](./references/style-guide.md) for conventions.
```

Keep the same progressive-disclosure discipline as any skill: say *when* to read each file.

Storage: new versions copy only metadata and file paths; unchanged files are shared across versions, so versioning large skills does not multiply storage. Moving or renaming files costs nothing.

## 3. Publish versions

- First publish: **Create Skill**, choose the version in the dialog (e.g. `1.0.0`). It is served immediately.
- Later: open the skill -> **Add New Version**, edit, then:
  - **Save**: new immutable version, served version unchanged (stage it, test it, then serve).
  - **Save & Serve**: new version becomes what everyone installs.

SemVer: `MAJOR.MINOR.PATCH[-SUFFIX]`. Patch for safe fixes, minor for backward-compatible additions, major for removed workflows, renamed required files or surprising behavior, suffix for pre-releases like `1.2.0-beta.1`. Numeric versions cannot go backwards: once `3.0.0` exists, `2.5.0` is rejected, even if an older version is being served.

## 4. Roll forward and back

Open the skill -> **Versions** (searchable) -> pick a version -> shift to it. Shifting changes what marketplaces and downloads serve; it deletes nothing. The next new version must still be above the **highest created** version (if `3.0.0` exists and you serve `1.0.0`, the next is `3.0.1`, `3.1.0` or `4.0.0`).

Team runbook:

1. Publish the candidate with **Save** (not served).
2. Pilot: have one or two engineers test it (inspect the version in the dashboard, or install it locally from a downloaded copy).
3. **Shift** to the new version (or publish the next one with **Save & Serve**).
4. If agents misbehave: **Shift** back to the previous version. Record why in the skill's changelog.
5. Fix forward with a new patch version above the highest one, then serve it.

Clients pick up the change on their harness's next marketplace/plugin refresh; running agent sessions keep whatever skill they already loaded, so start a fresh session to verify.

## 5. Register Bifrost as a marketplace

Once the prerequisites are met and at least one skill exists, click **Register as Marketplace** in the Skills Repository header. It shows the commands for your URL.

Claude Code:

```bash
claude plugin marketplace add <your-bifrost-url>/api/skills/serve/claude-code/.claude-plugin/marketplace.json
```

Codex:

```bash
codex plugin marketplace add <your-bifrost-url>/api/skills/serve/codex
```

Claude Desktop / Cowork (personal marketplace):

1. **Register as Marketplace** -> **Claude Desktop / Cowork** copies `<your-bifrost-url>/api/skills/serve/claude-code.git`.
2. Claude Desktop -> **Customize** -> **Plugins** -> **Add** -> **Add marketplace**, paste the URL, **Sync**.
3. Open the `bifrost-skills` marketplace, install a skill, enable the plugin, start a new chat and pick it from `/`.

Organization-managed Claude Desktop marketplaces use Anthropic's GitHub integration and do not accept an arbitrary Bifrost Git URL.

Then install from the marketplace using each harness's plugin flow (in Claude Code, the `/plugin` menu; Codex has its CLI and desktop flows). Install either:

- `bifrost-<skill-name>`: one skill, e.g. `bifrost-review-migrations`.
- `bifrost-all-skills`: every currently served skill, laid out as `skills/<name>/SKILL.md` plus attached files.

For the exact install/update subcommands of each harness's plugin CLI, check that harness's docs; Bifrost's docs specify only the marketplace registration commands above.

Roll this out to the team by putting the registration command in onboarding (dotfiles, a setup script, or a repo `README`), not by copying skills around.

### How `bifrost-all-skills` is versioned

Bifrost bumps it automatically so harnesses see updates:

| Event | Bump |
|---|---|
| First skill published | `0.0.0` -> `1.0.0` |
| Skill added | Minor |
| Skill deleted | Major |
| Served skill gets patch / minor / major | Patch / Minor / Major |
| Served version shifted | Patch |

A manual patch/minor/major bump control exists in the dashboard (and API) to nudge a marketplace that has not refreshed.

Choosing between them: `bifrost-all-skills` is simplest for small teams with a curated set. Per-skill plugins are better once the repository grows, since every installed skill costs metadata tokens in every session and adds false-trigger risk.

## 6. Automate from git with the Skills API

Keep authoring in git (reviews, CODEOWNERS, CI lint) and let CI publish to Bifrost, so Bifrost becomes the distribution and rollback layer. Endpoints (exact shapes in the API reference):

| Action | Endpoint | Docs |
|---|---|---|
| List / find by name | `GET /api/skills?search=<name>` | https://docs.getbifrost.ai/api-reference/skills/list-skills |
| Create (first version, served) | `POST /api/skills` | https://docs.getbifrost.ai/api-reference/skills/create-skill |
| New version | `PUT /api/skills/{id}` with `"serve": true/false` | https://docs.getbifrost.ai/api-reference/skills/update-skill |
| Upload binary file first | returns `upload_id` | https://docs.getbifrost.ai/api-reference/skills/upload-skill-file |
| Get served or specific version | `?version=` | https://docs.getbifrost.ai/api-reference/skills/get-skill |
| Version history | `?search=` | https://docs.getbifrost.ai/api-reference/skills/list-skill-versions |
| Roll back / forward | `POST /api/skills/{id}/shift-version` `{"version": "1.4.2"}` | https://docs.getbifrost.ai/api-reference/skills/shift-served-skill-version |
| All-skills version / bump | | https://docs.getbifrost.ai/api-reference/skills/get-all-skills-version , https://docs.getbifrost.ai/api-reference/skills/bump-all-skills-version |

Authentication: management endpoints need management auth (the examples use basic auth with the admin credentials; a management API key can be sent as a bearer token instead). See https://docs.getbifrost.ai/api/procuring-api-keys

Create (request fields: `name`, `description`, `skill_md_body`, `version` required; `license`, `compatibility`, `metadata`, `extra_frontmatter`, `allowed_tools`, `files` optional; file `source_type` is one of `text`, `url`, `dataurl`, `upload`):

```bash
curl -sS -X POST "$BIFROST_URL/api/skills" \
  -u "$BIFROST_ADMIN_USER:$BIFROST_ADMIN_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "review-migrations",
    "description": "Review Postgres migrations for lock safety and rollback. Use when a PR adds or changes a migration, or the user asks if a schema change is safe to deploy.",
    "license": "MIT",
    "metadata": {"owner": "platform-team"},
    "skill_md_body": "# Review migrations\n\n1. Read references/locks.md when the migration alters a large table.\n",
    "version": "1.0.0",
    "files": [
      {"path": "references/locks.md", "source_type": "text", "mime_type": "text/markdown",
       "content": "# Lock levels\n..."}
    ]
  }'
```

Stage a new version without serving, then roll back if needed:

```bash
curl -sS -X PUT "$BIFROST_URL/api/skills/$SKILL_ID" \
  -u "$BIFROST_ADMIN_USER:$BIFROST_ADMIN_PASSWORD" -H "Content-Type: application/json" \
  -d '{"description": "...", "skill_md_body": "...", "version": "1.1.0", "serve": false}'

curl -sS -X POST "$BIFROST_URL/api/skills/$SKILL_ID/shift-version" \
  -u "$BIFROST_ADMIN_USER:$BIFROST_ADMIN_PASSWORD" -H "Content-Type: application/json" \
  -d '{"version": "1.0.0"}'
```

Note whether `files` in an update replaces or merges the previous file list is defined by the API reference; send the complete file list for each version from CI so every version is self-describing.

### CI sync script (Python)

Publishes every changed skill directory from git to Bifrost. It reads the version from `metadata.version`, sends text files inline, and stages without serving unless `SERVE=1`. Requires `pyyaml` and `requests`.

```python
#!/usr/bin/env python3
"""Sync skills/<name>/ directories from git to the Bifrost Skills Repository."""
import mimetypes, os, pathlib, sys
import requests, yaml

BASE = os.environ["BIFROST_URL"].rstrip("/")
AUTH = (os.environ["BIFROST_ADMIN_USER"], os.environ["BIFROST_ADMIN_PASSWORD"])
SERVE = os.environ.get("SERVE") == "1"
SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}

def load(skill_dir: pathlib.Path):
    text = (skill_dir / "SKILL.md").read_text()
    _, fm_raw, body = text.split("---", 2)
    fm = yaml.safe_load(fm_raw)
    files = []
    for p in sorted(skill_dir.rglob("*")):
        if p.is_file() and p.name != "SKILL.md":
            rel = p.relative_to(skill_dir).as_posix()
            mime = mimetypes.guess_type(p.name)[0] or "text/plain"
            # Text files inline; upload binaries via the upload endpoint and pass upload_id instead.
            files.append({"path": rel, "source_type": "text", "mime_type": mime,
                          "content": p.read_text()})
    payload = {
        "description": fm["description"],
        "license": fm.get("license"),
        "compatibility": fm.get("compatibility"),
        "metadata": {k: str(v) for k, v in (fm.get("metadata") or {}).items()},
        "allowed_tools": fm.get("allowed-tools"),
        "extra_frontmatter": {k: v for k, v in fm.items() if k not in SPEC_KEYS},
        "skill_md_body": body.lstrip("\n"),
        "version": str(fm["metadata"]["version"]),
        "files": files,
    }
    return fm["name"], payload

def find(name: str):
    r = requests.get(f"{BASE}/api/skills", params={"search": name, "limit": 100}, auth=AUTH, timeout=30)
    r.raise_for_status()
    return next((s for s in r.json().get("skills", []) if s["name"] == name), None)

def sync(skill_dir: pathlib.Path):
    name, payload = load(skill_dir)
    existing = find(name)
    if existing is None:
        r = requests.post(f"{BASE}/api/skills", json={"name": name, **payload}, auth=AUTH, timeout=60)
    elif existing.get("highest_version") == payload["version"]:
        print(f"{name}: {payload['version']} already published, skipping"); return
    else:
        r = requests.put(f"{BASE}/api/skills/{existing['id']}", json={**payload, "serve": SERVE},
                         auth=AUTH, timeout=60)
    if not r.ok:
        sys.exit(f"{name}: {r.status_code} {r.text}")
    print(f"{name}: published {payload['version']} (served={SERVE or existing is None})")

if __name__ == "__main__":
    for d in sys.argv[1:]:
        sync(pathlib.Path(d))
```

Run it after merge, for the directories changed in the merge: `python3 sync_skills.py skills/review-migrations`. Keep the version bump check from `versioning-and-review.md` in PR CI so a duplicate or lower version never reaches the publish step (Bifrost rejects it anyway).

## 7. Security and access

- Anyone who can reach the External Client URL can fetch served skills. Never put secrets, credentials or customer data in a skill; restrict network reachability if skill content is internal.
- Management actions require auth; in OSS, guard the admin credentials as you would any deploy credential.
- Review scripts before publishing (checklist in `versioning-and-review.md`); prefer **Save** + review + **Shift** over **Save & Serve** for skills with scripts.
- Avoid **From URL** files for scripts.

## 8. Route the same harnesses through Bifrost (optional)

The engineers consuming these skills can send model traffic through the same Bifrost, gaining per-person virtual keys, budgets, request logs and provider failover:

- Claude Code: `ANTHROPIC_BASE_URL=<bifrost-url>/anthropic`, `ANTHROPIC_AUTH_TOKEN=sk-bf-<virtual-key>` in `~/.claude/settings.json` `env` (never in a committed project settings file). https://docs.getbifrost.ai/cli-agents/claude-code
- Codex CLI: named `model_providers` entry in `~/.codex/config.toml` with `base_url = "<bifrost-url>/openai/v1"` and `env_key` holding the virtual key; `OPENAI_BASE_URL` alone is not enough. https://docs.getbifrost.ai/cli-agents/codex-cli
- Cursor and others: https://docs.getbifrost.ai/cli-agents/overview

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| **Register as Marketplace** disabled | External Client URL unset/empty, or git missing on the server. Set the URL, install git, restart. |
| Marketplace URL returns 503 | URL setting resolves empty (e.g. `env.` reference to an unset variable). |
| Marketplace routes 404 | git not on the server's `PATH` at startup; install and restart. |
| Clients fail to fetch | External Client URL not reachable from client machines (localhost, wrong DNS, TLS). |
| "Version must be greater" on publish | A higher version exists, even if an older one is served. Use the next version above `highest_version`. |
| Team still sees old behavior after shift | Harness has not refreshed the marketplace/plugin, or the session started before the change. Refresh and start a new session. |
| Skill installed but never triggers | Description problem, not a Bifrost problem; see `writing-skills-that-trigger.md`. |
| Name rejected | Reserved names `all`, `all-skills`, `claude-code`, `codex`, or invalid characters. |
