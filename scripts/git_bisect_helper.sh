#!/usr/bin/env bash
# Read-only helper: inspect history, then run a real bisect session manually.
# Usage:
#   git bisect start
#   git bisect bad <bad-commit>
#   git bisect good <good-commit>
#   git bisect run python3 manage.py test
#   git bisect reset
set -euo pipefail
git log --oneline --decorate --graph -20
