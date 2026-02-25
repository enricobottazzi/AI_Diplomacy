# Statistical Analysis Tools

This document provides an overview of all the statistical analysis tools included in the repository. The tools span the full pipeline from raw game data processing to publication-quality visualizations and rigorous cross-experiment statistical comparisons.

---

## Table of Contents

1. [Data Processing Pipeline](#1-data-processing-pipeline)
2. [Statistical Game Analysis](#2-statistical-game-analysis)
3. [Experiment Runner Analysis Plugins](#3-experiment-runner-analysis-plugins)
4. [Experiment Comparison](#4-experiment-comparison)
5. [LLM-Powered Game Moment Analysis](#5-llm-powered-game-moment-analysis)
6. [Cross-Game Visualization Suite](#6-cross-game-visualization-suite)
7. [Data Validation](#7-data-validation)
8. [Jupyter Notebooks](#8-jupyter-notebooks)
9. [Quick Reference](#9-quick-reference)

---

## 1. Data Processing Pipeline

The `analysis/` package contains a three-stage pipeline that transforms raw game logs into structured analytical datasets.

### Orchestrator — `analysis/make_all_analysis_data.py`

Runs all three pipeline stages in sequence, reading raw game logs and producing structured CSV datasets.

```bash
# Process a specific game
python -m analysis.make_all_analysis_data \
  --game_data_folder results \
  --analysis_folder results/analysis \
  --selected_game 20260224_161339

# Process all games in a folder
python -m analysis.make_all_analysis_data \
  --game_data_folder results \
  --analysis_folder results/analysis
```

**Output structure:**

```
analysis_folder/
├── orders_data/
│   └── {game_name}_orders_data.csv
├── conversations_data/
│   └── {game_name}_conversations_data.csv
└── phase_data/
    └── {game_name}_phase_data.csv
```

### Stage 1 — Orders Data (`analysis/p1_make_longform_orders_data.py`)

Creates detailed order-level data with one row per order given by every power in every phase.

**Metrics computed:**
- Order classification (Move, Hold, Support Move, Support Hold, Convoy, Build, Disband, Retreat)
- Unit locations and destinations
- Supply center flags
- Adjudication results (bounce, dislodged, void, etc.)
- Territory ownership and trespassing analysis
- Support relationships (was\_supported, supported\_by\_self, supported\_by\_other)
- Relationship matrices (5-level scale: Enemy to Ally)
- LLM reasoning text and order extraction success

### Stage 2 — Conversation Data (`analysis/p2_make_convo_data.py`)

Extracts pairwise conversation data between all power combinations per phase.

**Metrics computed:**
- Message counts per party
- Message streaks (max consecutive messages from one party)
- Conversation transcripts
- Each party's relationship rating of the other

### Stage 3 — Phase Data (`analysis/p3_make_phase_data.py`)

Creates power-phase level summaries (60+ columns) combining state, actions, and conversations.

**Metrics computed:**
- **State:** supply centers, influence, unit counts (armies vs. fleets)
- **Change metrics:** centers\_change, units\_change, armies\_change, fleet\_change, influence\_change
- **Command counts:** build, convoy, disband, hold, move, retreat, support hold, support move
- **Result counts:** bounce, cut, dislodged, void, pass
- **Territorial dynamics:** moves into own/others' territory, territories gained, SCs gained
- **Diplomatic metrics:** countries supported, countries attacked, was\_supported\_by
- **LLM quality:** invalid\_order\_count, valid\_order\_count, no\_moves\_extracted\_flag, order\_reasoning\_length
- **Qualitative:** goals, diary entries, conversation transcripts per counterpart

### Supporting Modules

| Module | Purpose |
|---|---|
| `analysis/analysis_helpers.py` | Data loading utilities for game folders and zip archives, country-to-model mapping |
| `analysis/schemas.py` | Constants (province lists, supply centers, country names) and regex patterns for order parsing |

---

## 2. Statistical Game Analysis

**File:** `analysis/statistical_game_analysis.py`

A standalone statistical analyzer that produces phase-level and game-level CSV outputs with comprehensive metrics.

```bash
# Analyze a single game folder
python -m analysis.statistical_game_analysis results/20260224_161339

# Batch analyze multiple games
python -m analysis.statistical_game_analysis results/ --multiple

# Specify output directory
python -m analysis.statistical_game_analysis results/20260224_161339 --output /path/to/output
```

**Key class:** `StatisticalGameAnalyzer`

**Phase-level metrics:**
- Supply centers owned, territories controlled, military units
- Order counts by type (move, hold, support, convoy, build, disband, retreat)
- Response success/failure rates by type
- Negotiation message counts
- Relationship values and relationship similarity between phases
- Game score (Diplobench-style)

**Game-level metrics:**
- Aggregated averages of all phase metrics per power
- Final standings
- Total response counts
- Sentiment analysis
- Failure tracking and validation

---

## 3. Experiment Runner Analysis Plugins

These modules are invoked automatically by `experiment_runner.py` after game runs complete. They conform to the plugin interface: `run(experiment_dir, ctx)`.

To re run it 

```bash
python analysis/statistical_game_analysis.py results/exp012/runs -m -o results/exp012/analysis/statistical_game_analysis
```

### Results Summary — `experiment_runner/analysis/summary.py`

Aggregates results across all runs in an experiment.

**Metrics computed:**
- Outcome category (Solo Win, Loss, Eliminated, Ongoing/Draw)
- Supply center counts at game end
- Diplobench-style scoring per power
- Mean/median score by power

**Outputs:**
- `analysis/aggregated_results.csv`
- `analysis/score_summary_by_power.csv`
- `analysis/results_summary.png` (supply center box-plot)

### Statistical Plots — `experiment_runner/analysis/statistical_game_analysis.py`

Wraps the core `StatisticalGameAnalyzer` and generates a comprehensive suite of PNG visualizations.

**Plot types:**
- Box-plots per metric by power
- Z-score heatmaps
- Phase-level aggregated line plots
- Per-game phase line plots
- Per-power relationship evolution charts (with jitter for collision avoidance)

**Output structure:**

```
analysis/statistical_game_analysis/
├── individual/
│   ├── run_XXXXX_game_analysis.csv
│   └── run_XXXXX_phase_analysis.csv
└── plots/
    ├── game/*.png
    ├── phase/*.png
    ├── phase_by_game/*
    └── relationships/*
```

### Critical State Extractor — `experiment_runner/analysis/critical_state.py`

Extracts the board state before and after a critical phase for each run in a critical-state analysis experiment.

**Outputs:** `analysis/critical_state/<run_name>_before.json`, `<run_name>_after.json`

---

## 4. Experiment Comparison

**File:** `experiment_runner/analysis/compare_stats.py`

Compares two completed experiments with rigorous statistical testing. Reports every metric whose confidence interval excludes zero.

```bash
# Compare two experiments
python experiment_runner.py --experiment_dir results/exp010 --compare_to results/exp009

# Show all metrics (not just significant) and adjust significance level
python experiment_runner.py --experiment_dir results/exp010 --compare_to results/exp009 \
  --showall --sig_level 0.10
```

**Statistical tests performed:**

| Test | Description |
|---|---|
| Welch's t-test | Frequentist comparison of means |
| Permutation test | Non-parametric p-value (9,999 resamples) |
| Bayesian t-test | Posterior mean difference, credible interval, P(B > A) |
| Cohen's d | Standardized effect size |
| Statistical power | Power analysis for d = 0.5 |
| Median difference | Bootstrap BCa confidence interval |
| Leave-one-out influence | Influence diagnostic summary |
| Skewness & kurtosis | Distribution shape diagnostics |
| BH correction | Benjamini-Hochberg multiple-comparison correction |

**Derived "maximum-ever" metrics:**
- `max_supply_centers_owned` — per-power max across phases
- `max_territories_controlled` — per-power max across phases
- `max_military_units` — per-power max across phases
- `max_game_score` — game-level max across powers

**Outputs:**
- `comparison_aggregated_vs_<tag>.csv` — aggregated across all powers
- `comparison_by_power_vs_<tag>.csv` — per-power breakdown
- `phase_overlay/*.png` — overlay phase plots from both experiments

---

## 5. LLM-Powered Game Moment Analysis

**File:** `analyze_game_moments.py`

Uses an LLM (default: Gemini 2.5 Flash) to analyze Diplomacy games and identify key strategic moments. Runs asynchronously with configurable concurrency.

```bash
# Analyze a single game
python analyze_game_moments.py results/20260223_121232

# Customize model, max phases, and concurrency
python analyze_game_moments.py results/folder \
  --model "openrouter-google/gemini-2.5-flash-preview" \
  --max-phases 10 \
  --max-concurrent 5
```

**Moment categories detected:**
- Betrayals
- Collaborations
- Playing-both-sides
- Brilliant strategies
- Strategic blunders

**Additional analysis:**
- Lie detection (intentional vs. unintentional) by comparing diary entries against sent messages
- Interest scoring (1–10 scale)
- Invalid move tracking by model

**Outputs:** Markdown report and JSON file in `game_moments/` directory.

---

## 6. Cross-Game Visualization Suite

**File:** `diplomacy_unified_analysis_final.py`

Generates AAAI publication-quality visualizations across all games in a results directory, using CSV data as the source of truth.

```bash
# Analyze games from the last 200 days
python diplomacy_unified_analysis_final.py 200

# Specify a custom results directory
python diplomacy_unified_analysis_final.py --results-dir results 30
```

**Chart types (14 total):**

| Chart | Description |
|---|---|
| Top Models | Success rate + order composition for top performers |
| Success Rates | Success rates across all models |
| Active Order % | Active vs. passive play breakdown |
| Order Distribution | Order type heatmap across models |
| Temporal Analysis | Performance over game decades |
| Power Distribution | Power assignment distribution |
| Physical Timeline | Real-world experiment date timeline |
| Phase/Game Counts | Data volume by model |
| Comparison Heatmap | Model-vs-model comparison matrix |
| Unit Control | Performance vs. unit count scaling |
| Success Over Time | Success rate evolution over calendar time |
| Model Evolution | Model improvement over time |
| Summary Report | Markdown analysis summary |

**Output:** `visualization_results/csv_only_enhanced_<timestamp>_<N>days/` containing PNGs and `ANALYSIS_SUMMARY.md`.

---

## 7. Data Validation

**File:** `analysis/validation.py`

Pydantic v2 schema validator for Diplomacy game logs in LMVS format. Ensures structural and semantic correctness of game data before analysis.

```bash
python -m analysis.validation path/to/lmvsgame.json
```

**Key classes:** `LMVSGame`, `Phase`, `PhaseState`, `ValidationConfig`

---

## 8. Jupyter Notebooks

| Notebook | Purpose |
|---|---|
| `benchmark_results.ipynb` | Interactive benchmark result analysis and visualizations |
| `support_explanation_ablations_csa.ipynb` | Ablation study analysis for support explanations and critical state analysis |

---

## 9. Quick Reference

| Tool | Location | Invocation |
|---|---|---|
| Data Pipeline | `analysis/make_all_analysis_data.py` | `python -m analysis.make_all_analysis_data --game_data_folder ... --analysis_folder ...` |
| Statistical Analyzer | `analysis/statistical_game_analysis.py` | `python -m analysis.statistical_game_analysis <path>` |
| Results Summary | `experiment_runner/analysis/summary.py` | Auto-invoked by `experiment_runner.py` |
| Statistical Plots | `experiment_runner/analysis/statistical_game_analysis.py` | Auto-invoked by `experiment_runner.py` |
| Critical State | `experiment_runner/analysis/critical_state.py` | Auto-invoked with `--critical_state_base_run` |
| Experiment Comparison | `experiment_runner/analysis/compare_stats.py` | `python experiment_runner.py --compare_to <exp_dir>` |
| Game Moments | `analyze_game_moments.py` | `python analyze_game_moments.py <results_folder>` |
| Visualization Suite | `diplomacy_unified_analysis_final.py` | `python diplomacy_unified_analysis_final.py <days>` |
| Data Validation | `analysis/validation.py` | `python -m analysis.validation <path>` |


How to update an experiment

```bash
#!/bin/bash
set -euo pipefail

# Source experiments and target
EXP_A="results/exp011"
EXP_B="results/exp013"
TARGET="results/exp014"

# 1. Create target directory structure
mkdir -p "${TARGET}/runs"

# 2. Copy runs from exp011 as run_00000 .. run_00004
for i in $(seq 0 4); do
    src=$(printf "%s/runs/run_%05d" "$EXP_A" "$i")
    dst=$(printf "%s/runs/run_%05d" "$TARGET" "$i")
    cp -r "$src" "$dst"
    echo "Copied $src -> $dst"
done

# 3. Copy runs from exp013 as run_00005 .. run_00009
for i in $(seq 0 4); do
    src=$(printf "%s/runs/run_%05d" "$EXP_B" "$i")
    dst_idx=$((i + 5))
    dst=$(printf "%s/runs/run_%05d" "$TARGET" "$dst_idx")
    cp -r "$src" "$dst"
    echo "Copied $src -> $dst"
done

echo ""
echo "=== ${TARGET}/runs now contains $(ls -d ${TARGET}/runs/run_* | wc -l | tr -d ' ') runs ==="
echo ""

mkdir -p results/exp014/analysis/statistical_game_analysis

# 4. Run the statistical game analysis (generates CSVs)
python analysis/statistical_game_analysis.py "${TARGET}/runs" \
    -m \
    -o "${TARGET}/analysis/statistical_game_analysis"

echo ""
echo "=== Statistical game analysis complete ==="
```