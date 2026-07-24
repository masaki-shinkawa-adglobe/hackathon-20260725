#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --repo OWNER/REPO" >&2
  exit 2
}

repo=""
while (($#)); do
  case "$1" in
    --repo)
      (($# >= 2)) || usage
      repo="$2"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

[[ -n "$repo" ]] || usage

existing="$(gh label list --repo "$repo" --limit 200 --json name --jq '.[].name')"

ensure_label() {
  local name="$1"
  local color="$2"
  local description="$3"

  if grep -Fqx "$name" <<<"$existing"; then
    return
  fi

  gh label create "$name" \
    --repo "$repo" \
    --color "$color" \
    --description "$description"
  existing+=$'\n'"$name"
}

ensure_label "priority:critical" "B60205" "Immediate action; highest delivery priority"
ensure_label "priority:high" "D93F0B" "High delivery priority"
ensure_label "priority:medium" "FBCA04" "Normal delivery priority"
ensure_label "priority:low" "0E8A16" "Low delivery priority"
ensure_label "status:in-progress" "1D76DB" "Autonomous implementation or revision is active"
ensure_label "status:review" "5319E7" "Pull request is awaiting autonomous review"
ensure_label "status:blocked" "000000" "Autonomous delivery cannot currently continue"
