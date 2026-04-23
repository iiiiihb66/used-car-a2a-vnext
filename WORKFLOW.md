# Workflow

## Rule

Before starting any work locally or in the cloud, run:

```bash
./scripts/ensure_latest.sh
```

## What the script does

- fetches `origin`
- checks whether current branch is behind `origin/<branch>`
- fast-forwards automatically when safe
- refuses to pull over uncommitted changes
- stops on divergence

## Daily usage

### Start working

```bash
./scripts/ensure_latest.sh
```

### After local changes

```bash
git add .
git commit -m "your message"
git push
```

### After cloud agent changes

On your local machine:

```bash
./scripts/ensure_latest.sh
```

## Source of truth

GitHub is the source of truth.

- local changes sync to GitHub with `git push`
- cloud changes sync back to local with `git pull` or `./scripts/ensure_latest.sh`
