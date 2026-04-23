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

## Required Checks Before Shipping

1. `app.py` imports successfully
2. `/health` returns `healthy`
3. `/` returns `mode=tool`
4. Admin routes require `X-Admin-Token`
5. No production path exposes payment / escrow / loan flows

## Near-Term Priorities

1. Wire CloudBase deployment config
2. Replace local SQLite with CloudBase SQL in production
3. Connect Mini Program frontend to `/api/v1/*`
4. Add lightweight API regression tests for the production endpoints

