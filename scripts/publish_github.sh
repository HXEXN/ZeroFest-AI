#!/usr/bin/env bash
# Publish the current ZeroFest source to an already-created GitHub repository.
# Usage: ./scripts/publish_github.sh https://github.com/HXEXN/ZeroFest-AI.git

set -euo pipefail

REPOSITORY_URL="${1:-${GITHUB_REPOSITORY_URL:-}}"
BRANCH_NAME="${GITHUB_BRANCH:-main}"

if [[ -z "$REPOSITORY_URL" ]]; then
  echo "Repository URL is required."
  echo "Usage: ./scripts/publish_github.sh https://github.com/HXEXN/ZeroFest-AI.git"
  exit 1
fi

if [[ ! "$REPOSITORY_URL" =~ ^(https://github\.com/|git@github\.com:)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?$ ]]; then
  echo "Repository URL must be a GitHub HTTPS or SSH repository URL."
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Run this script from the ZeroFest Git repository root."
  exit 1
fi

if [[ -z "$(git config user.name || true)" || -z "$(git config user.email || true)" ]]; then
  echo "Set git user.name and git user.email before publishing."
  exit 1
fi

git add \
  .gitignore \
  .github \
  .streamlit \
  README.md \
  agents app.py components config.py data docs models pages requirements.txt scripts services tests pytest.ini .env.example

if ! git diff --cached --quiet; then
  git commit -m "feat: add ZeroFest AI festival operations MVP"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REPOSITORY_URL"
else
  git remote add origin "$REPOSITORY_URL"
fi

git branch -M "$BRANCH_NAME"
git push -u origin "$BRANCH_NAME"

echo "Published ZeroFest to $REPOSITORY_URL"
