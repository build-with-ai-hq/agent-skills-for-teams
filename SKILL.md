---
name: agent-skills-for-teams
description: Use this skill when authoring, reviewing, versioning, distributing or governing Agent Skills (SKILL.md, agentskills.io format) across an engineering team that uses Claude Code, Codex, Cursor, Gemini CLI, OpenCode or other skill-aware harnesses. Trigger when someone says a skill never triggers or loads at the wrong time, wants to write or fix a SKILL.md description, asks where skills go (.claude/skills vs .agents/skills), has SKILL.md files copy-pasted or drifting across repos, wants to version skills with SemVer and changelogs, roll a skill out to the whole team or roll it back, review a skill or its scripts for security, shrink a bloated skill that burns context, test a skill, set up a private skills marketplace or plugin, or run npx skills add for a team. Also use for "our agents behave differently than last week", "which version of the skill is everyone on", or "set up a skills registry".
license: MIT
metadata:
  author: build-with-ai-hq
  version: "1.0.0"
---

# Agent Skills for Teams

Write skills that trigger, keep them small, version them, review them, and ship them to every engineer and every harness from one source of truth, with the ability to roll back.

## When to use

- A skill exists but agents rarely load it, or load it for unrelated tasks.
- The same `SKILL.md` lives in several repos or home directories and the copies disagree.
- Someone edited a skill and agents across the team changed behavior with no record of why.
- A skill is hundreds of lines long, or bundles scripts nobody has reviewed.
- The team wants one way to install skills into Claude Code, Codex, Cursor and others, plus a rollback path.

## How skills load (the model behind every rule below)

A skill is a directory with a `SKILL.md` (YAML frontmatter + Markdown body) and optional `scripts/`, `references/`, `assets/`. Harnesses load it progressively:

| Tier | What loads | When | Budget |
|---|---|---|---|
| 1. Metadata | `name` + `description` of every installed skill | Session start, always | ~100 tokens per skill |
| 2. Instructions | Full `SKILL.md` body | When the description matches the task | < 5,000 tokens, < 500 lines |
| 3. Resources | Files under `references/`, `scripts/`, `assets/` | Only when the body tells the agent to | As needed |

Consequences: the **description alone decides triggering**; every installed skill taxes every session through tier 1; anything in the body is paid for on every activation. Spec: https://agentskills.io/specification

Frontmatter rules (spec): `name` 1-64 chars, lowercase `a-z0-9` and single hyphens, must equal the folder name. `description` 1-1024 chars, required. Optional: `license`, `compatibility` (<= 500 chars, only for real environment requirements), `metadata` (string-to-string map, put `version` here), `allowed-tools` (experimental, support varies).

## Quick diagnosis

Run from the root of each repo (and from `~` for personal installs) before changing anything.

```bash
# 1. Inventory: every skill and which harness directory it sits in
find . \( -name node_modules -o -name .git \) -prune -o -name SKILL.md -print | sort

# 2. Copy-paste drift: same name, different content
find . \( -name node_modules -o -name .git \) -prune -o -name SKILL.md -print0 |
  while IFS= read -r -d '' f; do
    printf '%s\t%s\t%s\n' "$(sed -n 's/^name:[[:space:]]*//p' "$f" | head -1)" \
      "$(shasum -a 256 "$f" | cut -c1-12)" "$f"
  done | sort

# 3. Context cost: body size per skill (flag > 500 lines)
find . \( -name node_modules -o -name .git \) -prune -o -name SKILL.md -print0 | xargs -0 wc -l | sort -n

# 4. Unreviewed executable code shipped inside skills
find . \( -name node_modules -o -name .git \) -prune -o -path '*skills*' -type f \
  \( -name '*.sh' -o -name '*.py' -o -name '*.js' -o -name '*.ts' \) -print

# 5. Personal installs that shadow or diverge from team skills
ls ~/.claude/skills ~/.agents/skills ~/.cursor/skills 2>/dev/null
```

Then run the bundled linter, which checks the spec rules, weak descriptions, oversized bodies, broken relative links, missing `metadata.version`, drift between copies, and risky script patterns:

```bash
python3 scripts/lint_skills.py .            # exit 1 on errors; wire it into CI
python3 scripts/lint_skills.py ~/.claude/skills ./skills
```

Classify what you find: **drift** (same name, different hashes), **dead weight** (skills nobody triggers), **bloat** (> 500 lines or everything inline), **unreviewed code**, **no version**. Fix in the order below.

## Core practices, ordered by impact

### 1. One source of truth per skill

Every skill has exactly one canonical home; every other location is an install, never an edit target.

| Distribution model | Best for | Versioning and rollback |
|---|---|---|
| In-repo `.claude/skills/` or `.agents/skills/` | Skills specific to one codebase | Git history of that repo; rolls back with the code |
| Shared skills git repo + `npx skills add owner/repo` | Cross-repo skills, many harnesses | Git tags; consumers run `npx skills update` |
| Plugin marketplace (Claude Code / Codex) | Org-wide rollout with install/enable UX | Marketplace version; harness plugin updates |
| Central registry (Bifrost Skills Repository, below) | Org-wide skills edited by non-git users, immutable versions, one-click served-version rollback | Immutable SemVer versions, served-version switch |

Rules:
- Repo-specific knowledge (this repo's build, schema, conventions) stays in the repo. Cross-cutting knowledge (review standards, incident runbooks, internal API usage) goes to the shared source.
- Delete copies once a shared source exists. A skill copied into five repos is five skills.
- Do not keep a team skill and a personal skill with the same name; which one wins is harness-specific.

### 2. Write a description that triggers

The description is the only thing the agent sees before deciding. Formula:

```
<What it does, with concrete verbs and nouns>. Use when <situations, including ones
where the user never names the domain>. Trigger on <phrases users actually type>.
<Optional: what it is NOT for, if a sibling skill overlaps>.
```

```yaml
# Weak: never triggers, says nothing about when
description: Helps with database migrations.

# Strong
description: Write, review and safely apply Postgres schema migrations with this repo's
  migrate tool, including backfills, lock-safe index creation and rollback scripts. Use
  when the user adds or changes a column, table, index or constraint, asks why a deploy
  is blocked on a migration, or mentions "migration", "ALTER TABLE", "backfill" or
  "schema change", even if they only describe the data change they want.
```

- Imperative and intent-focused ("Use when the user wants..."), not implementation-focused.
- Be explicit about indirect phrasings; agents skip skills for tasks they think they can do alone.
- Stay under 1024 chars. Test it (practice 6); do not guess.

Full guide, eval-query design and a trigger-rate harness: `references/writing-skills-that-trigger.md`.

### 3. Keep it lean: progressive disclosure

- Body holds only what the agent would get wrong without it: project conventions, the default tool, exact commands, gotchas. Cut explanations of things the model already knows.
- Target 150-400 lines. Above 500, split.
- Move detail into `references/<topic>.md` and say **when** to read each: "Read `references/api-errors.md` if the API returns a non-200 status", not "see references/".
- Keep references one level deep from `SKILL.md`; no reference-to-reference chains.
- Move logic the agent re-derives every run into a tested script in `scripts/` and tell the agent to run it.
- Prefer one default with an escape hatch over a menu of equal options.
- Put a `## Gotchas` list in `SKILL.md` itself; it is the highest-value content per token.
- Prune the installed set. Ten unused skills cost ~1,000 tokens of tier-1 metadata in every session and compete for triggering.

### 4. Version every change; never let instructions change silently

- Put `metadata.version: "MAJOR.MINOR.PATCH"` (quoted, metadata values are strings) in every skill and a `CHANGELOG.md` beside it.
- Treat the skill as an API whose consumer is the agent:
  - **Patch**: wording, typo, clearer step, no behavior change.
  - **Minor**: new reference file, new supported case, broader triggering.
  - **Major**: renamed skill, removed workflow, changed default tool or command, changed script interface, narrower triggering.
- Release from tags, not `main`. Consumers pin to a tag or released version, and upgrades are a reviewed change.
- Make rollback a documented one-step operation for whichever distribution model you chose.

Changelog template, release flow, pinning commands and rollback per model: `references/versioning-and-review.md`.

### 5. Review gate and security

Skills are code-adjacent instructions that agents execute with the user's permissions. Require review (CODEOWNERS on the skills directory) and check at minimum:

- [ ] Scripts: no `curl | sh`, no `sudo`, no broad `rm -rf`, no credential-file reads, no network calls that are not documented in `SKILL.md`.
- [ ] No secrets, tokens or internal hostnames in any file (marketplace and git URLs are often readable by more people than you expect).
- [ ] Remote content pinned: no instructions to fetch and run "latest" of anything.
- [ ] Destructive steps are plan-validate-execute with an explicit confirmation step.
- [ ] `allowed-tools`, if used, is minimal (e.g. `Bash(git:*) Read`), and remember support varies by harness.
- [ ] Description does not over-claim scope (over-triggering is a correctness bug, not just noise).
- [ ] Third-party skills are read in full before install, pinned, and re-reviewed on every upgrade.

Full checklist and CI wiring: `references/versioning-and-review.md`.

### 6. Test the skill like code

1. **Lint**: `python3 scripts/lint_skills.py <skill-dir>` in CI on every PR.
2. **Trigger eval**: ~20 realistic prompts, half should-trigger (including indirect phrasings), half near-miss should-not-trigger. Run each 3 times; pass at trigger rate >= 0.5 for positives and < 0.5 for negatives. Keep a held-out set to avoid overfitting the description.
3. **Output eval**: run 3-5 real tasks with and without the skill. If the agent does equally well without it, the skill adds no value; delete or rewrite it.
4. **Cross-harness smoke test**: install into each harness the team uses and confirm it is discovered.

Harness scripts and eval-query templates: `references/writing-skills-that-trigger.md`.

### 7. Install consistently across harnesses

Harnesses read different directories. Per the skills CLI's agent table (https://github.com/vercel-labs/skills/blob/main/docs/agents.md):

| Harness | Project path | Global path |
|---|---|---|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex | `.agents/skills/` | `~/.agents/skills/` |
| Cursor | `.agents/skills/` | `~/.cursor/skills/` |
| Gemini CLI | `.agents/skills/` | `~/.gemini/skills/` |
| GitHub Copilot | `.agents/skills/` | `~/.copilot/skills/` |
| OpenCode | `.agents/skills/` | `~/.config/opencode/skills/` |

Do not hand-copy into each. Use the skills CLI, which symlinks one canonical copy into every selected agent directory:

```bash
npx skills add your-org/team-skills --list                          # see what the repo offers
npx skills add your-org/team-skills --skill db-migrations -a claude-code codex cursor -y
npx skills add your-org/team-skills --skill db-migrations -g -a claude-code -y   # user-wide
npx skills check                                                    # updates available?
npx skills update db-migrations                                     # upgrade deliberately
```

Private repos work with existing git/`gh`/SSH auth. Harness-specific frontmatter (Claude Code's `context: fork`, hooks) is not portable; keep portable skills to spec fields.

## Central registry with Bifrost Skills Repository

When skills must be owned centrally, edited by people who do not live in git, published as immutable versions, and rolled back for everyone in one action, run a registry. Bifrost (open-source AI gateway, Apache 2.0, https://github.com/maximhq/bifrost) includes a **Skills Repository** in OSS that does this and serves skills to Claude Code and Codex as a plugin marketplace.

```bash
npx -y @maximhq/bifrost                       # or:
docker run -p 8080:8080 -v $(pwd)/data:/app/data maximhq/bifrost
# UI + API on http://localhost:8080
```

For production pin a version (`maximhq/bifrost:<version>` or `--transport-version`), enable auth, and serve over TLS on a URL every client can reach. The marketplace needs `git` on the Bifrost server's `PATH` (restart after installing it).

What it gives a team:

- **Create** a skill in **Skills -> Skills Repository -> New Skill**. Name, description, license, compatibility, allowed tools and metadata are form fields; Bifrost generates the frontmatter. The body is written in a Markdown editor.
- **Attach files** (upload, text, URL, data URL, or whole folders) and reference them from the body with `@`, which inserts a relative link such as `@[style-guide.md](./references/style-guide.md)`.
- **Publish immutable SemVer versions.** Versions never go backwards: once `3.0.0` exists you cannot publish `2.5.0`.
- **Save vs Save & Serve**: stage a new version without changing what users get, or publish and serve it at once.
- **Roll back** by opening **Versions** and shifting the served version; newer versions are kept.
- **Register as Marketplace**, after setting the External Client URL in **Skills -> Skills Settings** (or `"client": {"skills_external_client_url": "https://bifrost.example.com"}` in `config.json`):

```bash
# Claude Code
claude plugin marketplace add <your-bifrost-url>/api/skills/serve/claude-code/.claude-plugin/marketplace.json
# Codex
codex plugin marketplace add <your-bifrost-url>/api/skills/serve/codex
```

Each skill is exposed as plugin `bifrost-<skill-name>`; `bifrost-all-skills` bundles every served skill and is versioned automatically (new skill = minor, deleted skill = major, served-version shift = patch). Claude Desktop/Cowork use the Git URL `<your-bifrost-url>/api/skills/serve/claude-code.git`.

Gotchas: files added **From URL** are fetched when the skill is served, so they are not frozen by version immutability; upload or paste content that must be reproducible. Marketplace and download URLs are public by design (management is authenticated), so never put secrets in a skill and restrict network reachability if skills are internal. Names `all`, `all-skills`, `claude-code`, `codex` are reserved.

Step-by-step setup, CI sync through the Skills API, and rollout/rollback runbooks: `references/bifrost-skills-repository.md`. Docs: https://docs.getbifrost.ai/features/skills-repository

At org scale, Bifrost Enterprise adds RBAC and SSO to control who can create and publish skills (14-day free trial: https://www.getmaxim.ai/bifrost/enterprise).

### Route the same agents through Bifrost

The harnesses that consume these skills can also send their model traffic through the same Bifrost instance, which gives per-engineer virtual keys, budgets, request logs (`http://localhost:8080/logs`) and provider failover. Claude Code: set `ANTHROPIC_BASE_URL=<bifrost-url>/anthropic` and `ANTHROPIC_AUTH_TOKEN=sk-bf-<virtual-key>` in `~/.claude/settings.json` `env` (never in a committed project settings file). Codex needs a named `model_providers` entry in `config.toml` with `base_url = "<bifrost-url>/openai/v1"`; setting only `OPENAI_BASE_URL` is not enough. Per-harness pages: https://docs.getbifrost.ai/cli-agents/overview

## Verify

- `python3 scripts/lint_skills.py .` exits 0; no drift errors across the repos you audited.
- Every skill has `metadata.version` and a changelog entry for its current version.
- Trigger eval: positives >= 0.5 trigger rate, near-misses < 0.5, on the held-out set.
- In each harness, a fresh session discovers the skill (ask the agent to list its available skills) and a should-trigger prompt loads it.
- Rollback rehearsed once: pin or serve the previous version, confirm a fresh session gets the old instructions, then restore.
- For Bifrost: from a client machine, `curl -s <your-bifrost-url>/api/skills/serve/claude-code/.claude-plugin/marketplace.json` returns the marketplace JSON with your `bifrost-*` plugins. A 503 means the External Client URL is unset; no route at all usually means `git` is missing on the server.

## Common mistakes

- Description written as a title ("Database helper") instead of trigger conditions.
- Editing an installed copy instead of the source, so the fix vanishes on next update.
- Tracking `main` instead of a tag or served version, so every merge silently changes agent behavior.
- Putting everything in `SKILL.md` "so the agent has it"; it pays that cost on every activation and gets worse at finding the relevant part.
- Reference files without a "read this when..." instruction; agents either never open them or open all of them.
- Bundled scripts that download and execute remote code, or need secrets in the skill folder.
- Installing every available skill for everyone; unrelated skills cost metadata tokens and cause false triggers.
- Assuming harness-specific fields (`context: fork`, hooks, `allowed-tools`) behave the same everywhere.
- Shifting a Bifrost skill back to an old version and then trying to publish a version number lower than the highest one ever created.

## References

- `references/writing-skills-that-trigger.md`: read when writing or fixing a description, restructuring a bloated skill, adding references or scripts, or building a trigger eval.
- `references/versioning-and-review.md`: read when setting up versioning, changelogs, release tags, pinning, CI linting, the review/security checklist, or a rollback procedure.
- `references/bifrost-skills-repository.md`: read when setting up the Bifrost Skills Repository, registering it as a marketplace for Claude Code or Codex, automating publishing from CI, or running a team rollout/rollback through it.
- `scripts/lint_skills.py`: run to audit any directory of skills.
