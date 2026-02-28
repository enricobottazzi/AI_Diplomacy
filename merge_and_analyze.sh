#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

usage() {
  cat <<EOF
Usage: $0 --merge SRC1,SRC2,...=DST [--merge SRC3,SRC4,...=DST2 ...]

Merge runs from multiple source experiments into new destination experiments
and run statistical analysis on each.

Examples:
  # Merge exp1+exp3 into exp5, merge exp2+exp4 into exp6
  $0 --merge exp1,exp3=exp5 --merge exp2,exp4=exp6

  # Merge three experiments into one
  $0 --merge exp1,exp3,exp7=exp10
EOF
  exit 1
}

MERGES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --merge)  MERGES+=("$2"); shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

if [[ ${#MERGES[@]} -eq 0 ]]; then
  echo "Error: at least one --merge is required."
  usage
fi

DEST_DIRS=()

for merge_spec in "${MERGES[@]}"; do
  sources="${merge_spec%%=*}"
  dest="${merge_spec##*=}"

  if [[ "$sources" == "$merge_spec" || -z "$dest" ]]; then
    echo "Error: invalid merge spec '$merge_spec'. Expected format: src1,src2=dst"
    exit 1
  fi

  IFS=',' read -ra SRC_NAMES <<< "$sources"

  rm -rf "results/$dest"
  mkdir -p "results/$dest/runs"
  mkdir -p "results/$dest/analysis/statistical_game_analysis"

  run_idx=0
  src_summary=""

  for src_name in "${SRC_NAMES[@]}"; do
    src_runs_dir="results/$src_name/runs"
    if [[ ! -d "$src_runs_dir" ]]; then
      echo "Error: $src_runs_dir does not exist"
      exit 1
    fi

    src_count=0
    for run_dir in "$src_runs_dir"/run_*; do
      [[ -d "$run_dir" ]] || continue
      ln -s "$(pwd)/$run_dir" "results/$dest/runs/run_$(printf '%05d' $run_idx)"
      run_idx=$((run_idx + 1))
      src_count=$((src_count + 1))
    done

    if [[ -n "$src_summary" ]]; then src_summary="$src_summary + "; fi
    src_summary="${src_summary}${src_name}(${src_count} runs)"
  done

  echo "✓ $dest: $run_idx runs symlinked from $src_summary"
  DEST_DIRS+=("$dest")
done

ANALYSIS_CMDS=""
for dest in "${DEST_DIRS[@]}"; do
  ANALYSIS_CMDS+="
print('═══ Statistical analysis: $dest ═══')
run_analysis(Path('results/$dest'), {})
print()
"
done

python3 -c "
from pathlib import Path
from experiment_runner.analysis.statistical_game_analysis import run as run_analysis
${ANALYSIS_CMDS}
print('Done!')
"
