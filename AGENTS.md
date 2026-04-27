# AGENTS.md

## Product Goal

Build and maintain a **tool-style WeChat Mini Program backend** for used-car A2A collaboration.

This product is **not** a financial product and must remain safe for a **personal-subject Mini Program**.

Primary user-facing value:

- vehicle profile creation and browsing
- tamper-evident lifecycle records
- A2A inquiry and negotiation
- reputation leaderboard
- seller reporting and manual review

## Hard Constraints

Do not introduce or expose the following as active product capabilities:

- payment
- escrow
- loan transfer
- interest-rate discount
- financial recommendation
- investment / yield language
- guaranteed transaction wording

If such code exists historically, keep it disabled or out of the production entrypoint.

## Production Entrypoint

- Production app entry: `app.py`
- Historical experimental entrypoints should not be used for deployment.

## Deployment Target

- Tencent Cloud CloudBase / CloudRun
- WeChat Mini Program frontend
- CloudBase AI / Hunyuan via OpenAI-compatible API

## Engineering Preferences

- Keep the product in `APP_MODE=tool` by default
- Prefer small focused API surfaces over large all-in-one endpoints
- Preserve Chinese user-facing copy unless there is a reason to change it
- Favor boring deployment over clever architecture
- Treat Agent work as a supervised network: buyer Agent, seller Agent, and
  platform scheduler Agent should exchange state through the backend rather than
  relying on chat context alone
- Preserve explainability: matching, negotiation, and moderation decisions
  should leave reviewable traces for users and administrators

## Sync Rule

Before doing any analysis, edits, commits, or deployment work:

1. Run `scripts/ensure_latest.sh`
2. If the local branch is behind `origin/main`, fast-forward first
3. If the worktree has local uncommitted changes, do not auto-pull over them
4. If the branch has diverged, stop and resolve explicitly before continuing

This rule applies to:

- local work
- cloud agent work
- deployment preparation
- bugfix / review / refactor work

## Handoff Rule

`PROJECT_HANDOFF.md` is the canonical continuation document for any AI agent
that takes over this project.

Before every commit that changes code, docs, deployment configuration, tests, or
project direction:

1. Update `PROJECT_HANDOFF.md`
2. Record what changed
3. Record what was verified
4. Record current local / GitHub / CloudBase state when relevant
5. Record the next recommended task

Do not push work to GitHub without keeping `PROJECT_HANDOFF.md` current.

## Required Checks Before Shipping

1. `app.py` imports successfully
2. `/health` returns `healthy`
3. `/` returns `mode=tool`
4. Admin routes require `X-Admin-Token`
5. No production path exposes payment / escrow / loan flows
6. Working branch is synced with `origin/main` or divergence is explicitly handled

## Near-Term Priorities

1. Keep the SQLite-first CloudBase MVP stable without paid private networking
2. Run Qclaw / WorkBuddy / generic Agent MVP tests using `MVP_AGENT_TEST_PROMPTS.md`
3. Collect `/api/v1/agent/events` from external Agent testing
4. Add `scripts/online_smoke_test.py` for repeatable post-deploy checks
5. Improve Hermes-lite summaries for test blockers and next-round prompts
6. Consider CloudBase document database HTTP API only after free MVP usage shows
   the SQLite backup/restore workflow is insufficient

## Future Architecture Guardrail

The public repository is acceptable for early Agent installation, demos, and
integration testing. Before real commercial usage, split the system into:

- Public shell: `skill.md`, `openapi.json`, README, SDK examples, frontend shell,
  and non-sensitive request/response contracts
- Private Tencent Cloud core: matching/ranking algorithms, seller weighting,
  reputation scoring rules, negotiation strategy, risk controls, anti-abuse
  logic, admin workflows, databases, and logs

Public code should expose the protocol and entrypoints, not the proprietary
decision rules.
