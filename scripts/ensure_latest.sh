#!/usr/bin/env bash
set -euo pipefail

branch="$(git rev-parse --abbrev-ref HEAD)"

if [[ "$branch" == "HEAD" ]]; then
  echo "Detached HEAD detected. Stop and switch to a branch before working."
  exit 1
fi

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Not inside a git repository."
  exit 1
fi

echo "Fetching latest refs from origin..."
git fetch origin

local_head="$(git rev-parse HEAD)"
remote_ref="origin/${branch}"

if ! git show-ref --verify --quiet "refs/remotes/${remote_ref}"; then
  echo "Remote branch ${remote_ref} does not exist yet."
  exit 0
fi

remote_head="$(git rev-parse "${remote_ref}")"
base_head="$(git merge-base HEAD "${remote_ref}")"

if [[ "$local_head" == "$remote_head" ]]; then
  echo "Branch is already up to date with ${remote_ref}."
  exit 0
fi

if [[ "$local_head" == "$base_head" ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Local worktree has uncommitted changes and branch is behind ${remote_ref}."
    echo "Commit/stash changes first, then run this script again."
    exit 1
  fi

  echo "Local branch is behind ${remote_ref}. Running fast-forward pull..."
  git pull --ff-only origin "$branch"
  echo "Fast-forward complete."
  exit 0
fi

if [[ "$remote_head" == "$base_head" ]]; then
  echo "Local branch is ahead of ${remote_ref}. No pull needed."
  exit 0
fi

echo "Local branch and ${remote_ref} have diverged."
echo "Resolve the divergence explicitly before continuing."
exit 1
