# Versioning, review and rollback for team skills

Read this when setting up how skills are versioned, released, pinned, reviewed and rolled back, or wiring skill checks into CI.

## 1. Why version skills at all

A skill is executable intent. Changing one line of a `SKILL.md` changes what every agent on the team does on the next session, with no build, no deploy and no visible diff in the code they are working on. Without versions, "the agent did something different this week" is undebuggable. Versioning gives you: a record of what changed, a way to know which revision each engineer runs, staged rollout, and rollback.

## 2. SemVer for skills

Put the version in frontmatter and keep a changelog beside `SKILL.md`:

```yaml
metadata:
  version: "2.3.1"
```

Treat the agent as the API consumer:

| Bump | Skill changes that qualify |
|---|---|
| Patch | Typos, clarified wording, fixed broken link, no change in what the agent does |
| Minor | New reference file, new supported case, new optional script, broader description (more triggering), new gotcha |
| Major | Renamed skill, removed or reordered required workflow, changed default tool/command, changed script arguments or output, narrower description (stops triggering where it used to), new required dependency or permission |
| Pre-release | `2.4.0-beta.1` for pilot groups |

Rules:

- Versions only move forward. Rollback means serving or pinning an older release, not reusing a number.
- A description change is never "just docs": it changes triggering. Minimum minor; major if scope shrinks.
- Changing a bundled script's interface is major even if `SKILL.md` text barely changes.

## 3. Changelog template

`CHANGELOG.md` in the skill folder (or one per repo with a section per skill):

```markdown
# Changelog: db-migrations

## 2.3.1 - 2026-10-20
### Fixed
- Backfill step now batches by primary key range (was OFFSET, slow on large tables).

## 2.3.0 - 2026-10-02
### Added
- references/online-index.md: lock-free index creation, loaded only for CREATE INDEX tasks.
### Changed
- Description now triggers on "deploy blocked on migration".

## 2.0.0 - 2026-08-11
### Breaking
- scripts/migrate.py replaces scripts/migrate.sh; arguments changed (--plan, --apply).
- Removed the manual rollback workflow; use scripts/migrate.py --rollback.
```

Write entries for humans reviewing an upgrade: what the agent will do differently.

## 4. Release flow (git-based distribution)

Shared skills repo layout that the skills CLI discovers:

```
team-skills/
  skills/
    db-migrations/
      SKILL.md
      CHANGELOG.md
      references/
      scripts/
    release-packages/
      SKILL.md
      ...
  .github/CODEOWNERS
  .github/workflows/skills-ci.yml
```

The skills CLI also discovers a root `SKILL.md`, `skills/<category>/<name>/SKILL.md`, harness folders such as `.claude/skills/` and `.agents/skills/`, and skills declared in `.claude-plugin/marketplace.json`. See https://github.com/vercel-labs/skills/blob/main/docs/creating-skills.md

Release steps:

1. PR changes the skill, bumps `metadata.version`, adds a changelog entry.
2. CI lints and runs trigger evals (below). CODEOWNERS approve.
3. Merge, then tag. With several skills in one repo, use per-skill tags: `db-migrations/v2.3.1`.
4. Announce the changelog entry where the team reads it.

Installing and upgrading:

```bash
# Install from the repo (default branch)
npx skills add your-org/team-skills --skill db-migrations -a claude-code codex cursor -y

# Install from an exact path in the repo; point the tree URL at a release tag
# instead of a branch when you need a fixed revision
npx skills add https://github.com/your-org/team-skills/tree/main/skills/db-migrations

npx skills list             # what is installed, and from where
npx skills update db-migrations   # installs the latest version; review the diff before committing
```

`skills experimental_sync` can install skills declared in `package.json` and records them in `skills-lock.json`; the CLI docs recommend pinning a Git ref there for reproducible remote content. It is experimental; check https://github.com/vercel-labs/skills/blob/main/docs/commands.md before relying on it.

For in-repo skills (`.claude/skills/`, `.agents/skills/` committed with the code), the repo's own history is the version history: the skill changes in the same PR as the code it describes, and rolls back with it. Still bump `metadata.version` so traces and bug reports can name the revision.

## 5. Rollback by distribution model

| Model | Rollback |
|---|---|
| In-repo skill | `git revert` the commit that changed the skill; merge |
| Shared git repo | Revert on the default branch and cut a new patch release (versions move forward), or tell consumers to reinstall from the previous tag's tree URL |
| Plugin marketplace you host in git | Revert the plugin and bump the marketplace/plugin version so clients see an update |
| Bifrost Skills Repository | Shift the served version to the previous one (UI **Versions** or the Shift served skill version API); `bifrost-all-skills` gets a patch bump automatically. See `bifrost-skills-repository.md` |

Rehearse rollback once per model before you need it. Verify with a fresh agent session, since running sessions keep the already-loaded skill.

## 6. Review checklist

Add to the PR template for the skills repo.

**Format and triggering**
- [ ] `name` matches folder, lowercase-hyphen, <= 64 chars.
- [ ] Description states what + when, <= 1024 chars, includes indirect phrasings, and a "Not for..." boundary if a sibling skill overlaps.
- [ ] Trigger eval run; pass rate did not drop on the validation set.
- [ ] `metadata.version` bumped per the SemVer table; changelog entry written.

**Context cost**
- [ ] Body <= 500 lines; detail moved to `references/` with explicit load conditions.
- [ ] No content the model already knows.
- [ ] References one level deep; all relative links resolve.

**Behavior**
- [ ] One default per decision, not a menu.
- [ ] Destructive or irreversible steps use plan -> validate -> confirm -> execute.
- [ ] Verify step present so the agent checks its own work.

**Security**
- [ ] No secrets, tokens, internal URLs that should not leak, or customer data in any file.
- [ ] Scripts: no `curl ... | sh`, no `sudo`, no `rm -rf` on broad paths, no `eval` of input, no reads of `~/.ssh`, `~/.aws`, `.netrc`, `.npmrc`, no `git push --force`.
- [ ] Every network call a script makes is documented in `SKILL.md` and goes to an expected host.
- [ ] Remote resources pinned (exact versions, commit SHAs or checksums), never "latest".
- [ ] Instructions do not tell the agent to disable safety prompts, skip confirmation, or widen permissions.
- [ ] `allowed-tools`, if set, is the minimum (for example `Bash(git:*) Read`), and reviewers know support varies by harness.
- [ ] Instructions do not include text that would override the user's or the harness's instructions (prompt injection through skills is real for third-party skills).

**Third-party skills**
- [ ] Every file read before install, not just `SKILL.md`.
- [ ] Installed from a pinned revision; upgrades go through the same review.
- [ ] Vendored or mirrored into the team source if the upstream could change or disappear.

## 7. CI

Minimal GitHub Actions workflow for a skills repo (copy `scripts/lint_skills.py` from this skill into the repo):

```yaml
name: skills-ci
on:
  pull_request:
    paths: ["skills/**", ".claude/skills/**", ".agents/skills/**"]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python3 scripts/lint_skills.py skills .claude/skills .agents/skills
      - name: Version bumped for changed skills
        run: |
          git fetch origin "${{ github.base_ref }}" --depth=1
          for d in $(git diff --name-only "origin/${{ github.base_ref }}" -- skills | cut -d/ -f2 | sort -u); do
            [ -f "skills/$d/SKILL.md" ] || continue
            if ! git diff "origin/${{ github.base_ref }}" -- "skills/$d/SKILL.md" | grep -q '^+  version:'; then
              echo "::error::skills/$d changed without a metadata.version bump"; exit 1
            fi
          done
```

Optional: also validate against the reference implementation (`skills-ref validate ./skills/<name>`, https://github.com/agentskills/agentskills/tree/main/skills-ref), and run the trigger eval from `writing-skills-that-trigger.md` nightly rather than per PR (it costs model calls).

`.github/CODEOWNERS`:

```
/skills/            @your-org/platform-eng
/skills/**/scripts/ @your-org/security
```

## 8. Knowing what everyone runs

- Ask engineers (or a startup script) to report `npx skills list` output, or check installed `metadata.version` values under the harness directories.
- Put the version in a line the agent can echo when asked ("This is db-migrations 2.3.1"), which makes bug reports precise.
- With a central registry, the served version is the answer for everyone who installs from it; see `bifrost-skills-repository.md`.
