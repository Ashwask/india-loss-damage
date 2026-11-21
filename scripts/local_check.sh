#!/bin/zsh
# Weekly source check from a computer in India.
#
# Several government sites refuse connections from GitHub's servers (for example
# ndmindia.mha.gov.in), so the scheduled GitHub workflow cannot see them. This script runs the
# same check from this machine and reports to the same GitHub issue. It never changes a figure.
#
# It works on a fresh copy of main in a cache folder, so it does not touch any working copy.
set -u
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
REPO="Ashwask/india-loss-damage"
WORK="$HOME/Library/Caches/india-loss-damage-source-check"
LOG="$HOME/Library/Logs/india-loss-damage-source-check.log"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
  rm -rf "$WORK" && mkdir -p "$WORK"
  if ! git clone -q --depth 1 "https://github.com/$REPO.git" "$WORK/repo"; then
    echo "clone failed; nothing checked"; exit 1
  fi
  cd "$WORK/repo" || exit 1
  export GITHUB_OUTPUT="$WORK/output.txt"; : > "$GITHUB_OUTPUT"
  python3 check_sources.py --report "$WORK/report.md" | sed -n '3p'
  if grep -q '^attention=true' "$GITHUB_OUTPUT"; then
    printf '\n_Run from a computer in India (local scheduled check)._\n' >> "$WORK/report.md"
    gh label create source-check --repo "$REPO" --description "A source document changed or disappeared" --color B8391F --force >/dev/null
    n=$(gh issue list --repo "$REPO" --label source-check --state open --json number --jq '.[0].number // empty')
    if [ -n "$n" ]; then
      gh issue comment "$n" --repo "$REPO" --body-file "$WORK/report.md"
    else
      gh issue create --repo "$REPO" --title "Source documents changed or gone: re-verify" --label source-check --body-file "$WORK/report.md"
    fi
  else
    echo "nothing changed or gone; no issue"
  fi
} >> "$LOG" 2>&1
