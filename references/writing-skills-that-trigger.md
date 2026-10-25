# Writing skills that trigger (and stay small)

Read this when writing a new skill, fixing one that never loads or loads at the wrong time, restructuring a bloated skill, or building a trigger eval.

## 1. Decide whether it should be a skill at all

A skill earns its place when the agent would get the task wrong, slow or inconsistent without it. Good candidates:

- Project conventions the model cannot infer (this repo's migration tool, test layout, release steps).
- Internal APIs, schemas, runbooks, incident procedures.
- Fragile sequences that must run exactly (deploy, data backfill).
- Repeated corrections you keep typing into chats.

Bad candidates: general knowledge ("how to write good Python"), one-off tasks, anything a linter or formatter already enforces. Those belong in a linter config, a repo `CLAUDE.md`/`AGENTS.md`, or nowhere.

Scope like a function: one coherent unit of work. Too narrow and several skills load for one task with conflicting instructions; too broad and the description cannot trigger precisely.

## 2. Source material beats generation

Do not ask a model to "write a skill about X" from nothing; you get generic advice. Build from:

- A real task you completed with an agent: the steps that worked, every correction you made, the input/output formats.
- Runbooks, internal docs, code review comments, incident postmortems, the diffs of recurring fixes.

Every correction you had to make to an agent is a candidate gotcha.

## 3. The description

The harness shows the agent only `name` + `description` for every installed skill. The description carries the entire triggering decision.

Rules:

1. **What + when.** One sentence of concrete capability, then the situations.
2. **Imperative, intent-focused.** "Use when the user wants to..." rather than "This skill uses a Python script to...".
3. **Cover indirect phrasings.** List symptoms and goals, not just domain keywords: "deploy is stuck", "column is missing in prod", "even if they don't say migration".
4. **Name the near-misses** when a sibling skill overlaps: "Not for Excel formula edits; use spreadsheet-editing."
5. **Under 1024 characters.** Descriptions grow during tuning; re-check.
6. **No marketing.** Adjectives do not trigger anything.

Template:

```yaml
description: <Verb> <object> <with specifics>, including <2-4 concrete sub-tasks>. Use when
  <user goal 1>, <user goal 2>, <symptom the user reports>, or mentions "<phrase>",
  "<phrase>" or "<phrase>", even if they do not name <domain>. Not for <adjacent task>.
```

Before/after:

```yaml
# Before: describes a tool, not a trigger
description: Internal release helper.

# After
description: Cut, tag and publish a release of this monorepo's packages with the
  release script, including changelog generation, version bumps and npm publish
  with provenance. Use when the user wants to release, ship, publish or bump a
  package version, asks why a release CI job failed, or says "cut a release" or
  "tag v1.x". Not for deploying the web app; use deploy-web.
```

Note: agents tend to skip skills for tasks they believe are simple. A perfect description will not trigger on "read this file". Triggering matters most where the skill carries knowledge the model lacks.

## 4. The body

Structure that works for most skills:

```markdown
# <Title>
One line: what the agent achieves.

## When to use            (short; the description already did the heavy lifting)
## Steps / workflow       (numbered; exact commands for fragile parts)
## Defaults               (the one tool/approach to use, with an escape hatch)
## Gotchas                (environment facts that defy reasonable assumptions)
## Verify                 (how the agent checks its own work)
## References             (each file + when to read it)
```

Calibrate control to fragility:

- **Freedom** where several approaches are valid; explain *why* so the agent can adapt.
- **Prescriptive** where order and exactness matter: "Run exactly `python scripts/migrate.py --verify --backup`. Do not add flags."

Write procedures, not answers. "Read `references/schema.md`, join on `_id` foreign keys, aggregate as requested" generalizes; "join orders to customers on customer_id" solves one task.

Cut every line where the answer to "would the agent get this wrong without it?" is no.

## 5. Progressive disclosure in practice

| Content | Where |
|---|---|
| Steps run on every activation, gotchas, defaults | `SKILL.md` body |
| Long API references, schemas, error catalogs, per-provider details | `references/<topic>.md` |
| Logic the agent would otherwise rewrite each run | `scripts/<name>.py` (tested, documented deps) |
| Templates, example configs, lookup tables | `assets/` |

Rules:

- Link every reference with a load condition: "Read `references/errors.md` when the API returns 4xx/5xx."
- One level deep: `SKILL.md` -> `references/x.md`. No chains.
- Keep each reference focused; the agent loads whole files.
- Relative paths from the skill root (`references/x.md`, `scripts/run.py`), never absolute or `~` paths.
- Scripts: self-contained or dependencies stated at the top, clear error messages, non-zero exit codes on failure, no interactive prompts (agents cannot answer them), `--help` output.

Size targets: body 150-400 lines (hard ceiling 500 lines / ~5,000 tokens); each reference under ~300 lines.

## 6. Portable vs harness-specific frontmatter

Portable (agentskills.io spec): `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` (experimental).

Harness-specific fields exist (for example Claude Code supports `context: fork` and hooks; most other harnesses do not, per the skills CLI compatibility table: https://github.com/vercel-labs/skills/blob/main/docs/agents.md). If a team uses several harnesses, keep shared skills to spec fields and put harness-only behavior in a separate, clearly named skill.

`metadata` is a string-to-string map: quote versions (`version: "1.2.0"`). Use namespaced keys for your own data (`acme-owner: platform-team`).

## 7. Trigger evals

Build ~20 queries in a JSON file:

```json
[
  {"query": "prod deploy is stuck on 'waiting for migration lock' again, can you look", "should_trigger": true},
  {"query": "add a nullable archived_at column to invoices and backfill it from status", "should_trigger": true},
  {"query": "write a SQL query for last month's revenue by region", "should_trigger": false},
  {"query": "our ORM model for invoices is missing a type hint, fix it", "should_trigger": false}
]
```

- 8-10 should-trigger: vary formality, typos, length, and how directly the domain is named. The valuable ones describe the need without naming the skill's domain.
- 8-10 should-not-trigger **near-misses**: share keywords but need something else. "What's the weather" tests nothing.
- Include realistic context: file paths, ticket numbers, casual phrasing.
- Split ~60/40 into `train.json` and `validation.json`, with positives and negatives in both. Tune only on train; pick the description with the best validation score.

Runner (adapted from https://agentskills.io/skill-creation/optimizing-descriptions; replace `check_triggered` with your harness's way of reporting skill loads, and verify the JSON shape your CLI version emits):

```bash
#!/usr/bin/env bash
set -euo pipefail
QUERIES="${1:?usage: $0 queries.json}"; SKILL="${2:?skill name}"; RUNS="${RUNS:-3}"

check_triggered() {
  claude -p "$1" --output-format json 2>/dev/null |
    jq -e --arg s "$SKILL" 'any(.messages[].content[]?; .type=="tool_use" and .name=="Skill" and .input.skill==$s)' >/dev/null
}

n=$(jq length "$QUERIES")
for i in $(seq 0 $((n-1))); do
  q=$(jq -r ".[$i].query" "$QUERIES"); want=$(jq -r ".[$i].should_trigger" "$QUERIES"); hits=0
  for _ in $(seq 1 "$RUNS"); do check_triggered "$q" && hits=$((hits+1)) || true; done
  jq -n --arg q "$q" --argjson want "$want" --argjson h "$hits" --argjson r "$RUNS" \
    '{query:$q, should_trigger:$want, rate:($h/$r), pass:(if $want then ($h/$r)>=0.5 else ($h/$r)<0.5 end)}'
done | jq -s '{pass_rate: ((map(select(.pass))|length)/length), results: .}'
```

Iterate (usually <= 5 rounds):

- Positives failing -> description too narrow; add the *category* of situation, not the literal failing words.
- Negatives triggering -> too broad; add a "Not for..." boundary.
- Stuck -> rewrite the description structure, do not keep appending.
- Recheck the 1024-char limit each round.

## 8. Output evals

Triggering is half the job. For 3-5 representative tasks, run the agent with and without the skill and compare: correctness, steps wasted, commands used, whether it followed the defaults. Read the traces, not just results. Common findings:

- Agent tries several approaches -> instructions too vague or offer a menu; pick a default.
- Agent follows irrelevant steps -> content that does not apply to this task; move it to a reference with a load condition.
- Agent rewrites the same helper every run -> bundle it in `scripts/`.
- No difference with and without -> the skill adds nothing; delete it.

## 9. Bloat triage for an existing skill

1. `wc -l SKILL.md` and estimate tokens (`wc -c` / 4).
2. Mark each section: *every run* / *some runs* / *agent already knows*.
3. Delete *agent already knows*.
4. Move *some runs* into `references/` with explicit load conditions.
5. Replace long procedural prose with a script where the procedure is deterministic.
6. Re-run trigger and output evals; ship as a minor version (patch if behavior is unchanged).
