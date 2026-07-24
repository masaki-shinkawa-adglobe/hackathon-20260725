#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --repo OWNER/REPO [--issue NUMBER]" >&2
  exit 2
}

repo=""
issue=""
while (($#)); do
  case "$1" in
    --repo)
      (($# >= 2)) || usage
      repo="$2"
      shift 2
      ;;
    --issue)
      (($# >= 2)) || usage
      issue="$2"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

[[ -n "$repo" ]] || usage

decorate='
  def label_names: [.labels[].name];
  def priority_labels:
    [label_names[] | select(startswith("priority:"))];
  def priority_rank:
    if (label_names | index("priority:critical")) then 0
    elif (label_names | index("priority:high")) then 1
    elif (label_names | index("priority:medium")) then 2
    elif (label_names | index("priority:low")) then 3
    else 4
    end;
  map(. + {
    labelNames: label_names,
    priorityLabels: priority_labels,
    priorityRank: priority_rank,
    hasPriorityConflict: ((priority_labels | length) > 1)
  })
  | sort_by(.priorityRank, .number)
'

if [[ -n "$issue" ]]; then
  gh issue view "$issue" \
    --repo "$repo" \
    --json number,title,body,url,state,labels,createdAt \
    | jq "[.] | $decorate"
  exit
fi

gh issue list \
  --repo "$repo" \
  --state open \
  --limit 100 \
  --json number,title,body,url,state,labels,createdAt \
  | jq '
      map(select(
        ([.labels[].name] | any(
          . == "duplicate"
          or . == "wontfix"
          or . == "blocked"
          or . == "status:in-progress"
          or . == "status:review"
          or . == "status:blocked"
        )) | not
      ))
    ' \
  | jq "$decorate"
