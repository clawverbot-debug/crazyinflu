#!/bin/sh
# One-time setup for each collaborator (run from the repo root): turns on the shared git hooks.
cd "$(git rev-parse --show-toplevel)" || exit 1
chmod +x .githooks/pre-commit .githooks/pre-push
git config core.hooksPath .githooks
echo "Hooks on: every commit and push now checks first whether there is something to git pull."
