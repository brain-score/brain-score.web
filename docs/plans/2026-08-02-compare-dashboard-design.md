# Compare Dashboard Design

## Goal

Turn Compare Benchmarks into a cohort-aware dashboard. A shared wayback date
must affect benchmark comparisons, summaries, and downloads in the same way.
Compare Models remains a current-data comparison tool.

## Filter semantics

The dashboard resolves filters in this order:

1. Make each benchmark available from its first version's start date while
   always using the latest version's definition and value.
2. Make that latest value available from the model's earliest numeric score
   timestamp for any version of the logical benchmark.
3. Remove models submitted after that cutoff.
4. Rebuild parent and domain aggregates from the remaining leaf scores.
5. Calculate each model's completedness across the active leaves represented by
   the two selected benchmark axes.

Completedness is the percentage of active leaves beneath the two selected
benchmark axes that have a finite score greater than zero. The two descendant
sets are combined without double-counting overlapping leaves. Engineering
benchmarks remain available for plots and model comparisons, but do not
contribute to completedness.

## Page structure

A cohort panel sits inside Compare Benchmarks. It contains the wayback date,
minimum model completedness, reset control, and live summaries for the cutoff
date, eligible models, active leaves beneath the selected axes, and median
completedness.

The Compare Benchmarks tab retains its searchable axis selectors and scatter
plot. It adds a compact cohort distribution. Correlation and paired-count
statistics remain in the chart's compact header rather than duplicate cards.

The Compare Models tab retains the model cards, trend, per-benchmark scatter,
difference chart, and domain distributions. Model cards add completedness.
The tab adds common coverage and benchmark win/tie summaries. It always uses
the latest unfiltered models, benchmark definitions, and complete historical
trends.

The first release keeps heavier suite analyses out of the main interaction
path. A later Suite Structure view can expose versioned, precomputed clustered
correlations, PCA axes, redundancy, and alternative aggregation results.

## Data and state

The server provides a compare-specific payload alongside the current template
context. Models are keyed by model ID so duplicate names cannot collide. Each
model includes its name, submission date, metadata, and score-version timeline.
Each benchmark includes its current identifier, logical benchmark type,
hierarchy, display name, domain, and leaf status.

A compare dashboard JavaScript module owns the benchmark filter state and
exposes a small subscription API. Pure functions resolve the historical
snapshot, calculate completedness, and derive the eligible benchmark cohort.
The model comparison consumes a separate latest-data snapshot from the same
normalized payload and does not subscribe to wayback changes.

The URL stores the benchmark cutoff date, active tab, selected model IDs, and
selected benchmark IDs. The cutoff date applies only to Compare Benchmarks.
The completedness threshold is session-local and starts at zero on every load.
The completedness denominator is recalculated when an axis or cutoff changes,
so parent-category coverage follows the benchmark set active at that date.
Restoring a URL runs through the same state paths as direct interaction.

## Empty and invalid states

Expected data limitations are shown in the relevant panel instead of leaving
an empty chart or raising an exception. These include no benchmarks at the
cutoff, no eligible models, a model that did not yet exist, fewer than three
paired observations for correlation, and a benchmark version without a valid
score. If filtering removes a selected model or benchmark, the dashboard
chooses a valid fallback when one exists and explains the change.

## Analysis guidance from meta-analysis v1-v4

The interactive dashboard initially uses descriptive analyses that remain
well-defined under arbitrary cohorts: completedness distributions, paired
coverage, Pearson and Spearman correlations, neural-versus-behavioral profiles,
and model score differences. Cross-benchmark comparisons should eventually
offer cohort percentiles because a shared zero-to-one score range does not make
heterogeneous benchmark measurements directly commensurable.

PCA, clustered correlation maps, redundancy estimates, and alternative model
rankings require stronger safeguards. The later meta-analyses show material
dependence on missing-value treatment, cohort coverage, architecture
deduplication, and benchmark vintage. Those analyses should therefore be
precomputed, versioned, and labeled with their cohort and methodology rather
than silently recomputed in the browser.

## Verification

Backend tests cover payload serialization and privacy. Browser-independent
JavaScript tests cover latest-version backcasting, score timestamp gates,
model submission gates, neural/behavioral-only completedness, zero and NaN
handling, and duplicate model names. View-level checks
cover URL restoration, removed selections, empty cohorts, and insufficient
paired data. Existing compare-page and trend endpoint tests must continue to
pass.

## Delivery constraints

Work takes place on a dedicated feature branch. Changes remain uncommitted
until explicitly requested. Any later commits use Conventional Commits,
contain one logical change, use imperative subjects no longer than 72
characters, and contain no authorship markers.
