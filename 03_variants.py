"""
Step 3: Variant analysis and a directly-follows map of the top variants.

- A variant is one distinct sequence of activities. Cases that go through
  exactly the same steps in the same order share a variant.
- Prints how many variants there are and how concentrated they are.
- Shows the top 10 variants and which matching types they belong to.
- Draws a directly-follows graph (DFG) for the cases in the top 10 variants.

Cases with any event before 2018 are excluded, same as Step 2.
Needs Graphviz installed (brew install graphviz) for the DFG picture.
"""

import matplotlib.pyplot as plt
import pandas as pd
import pm4py

PARQUET_PATH = "data/bpi2019_events.parquet"
COVERAGE_CHART = "charts/03_variant_coverage.png"
DFG_CHART = "charts/03_dfg_top10_variants.png"
TOP_K = 10

# Column names that pm4py uses
CASE_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIME_COL = "time:timestamp"
MATCHING_COL = "case:Item Category"

# Colors for the chart
SERIES_1 = "#2a78d6"   # blue
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
AXIS = "#c9c8c2"
SURFACE = "#fcfcfb"


# ---------------------------------------------------------------
# 1. Load data and exclude cases with dates before 2018
# ---------------------------------------------------------------
df = pd.read_parquet(PARQUET_PATH)

start_2018 = pd.Timestamp("2018-01-01", tz="UTC")
early_cases = df.loc[df[TIME_COL] < start_2018, CASE_COL].unique()
df = df[~df[CASE_COL].isin(early_cases)]

num_cases = df[CASE_COL].nunique()
print(f"Cases analysed: {num_cases:,}\n")


# ---------------------------------------------------------------
# 2. Count variants
# ---------------------------------------------------------------
# pm4py returns a dictionary: {(activity1, activity2, ...): number of cases}
variants = pm4py.get_variants(df)

# Turn it into a table, most common variant first
variant_table = pd.DataFrame({
    "variant": list(variants.keys()),
    "cases": list(variants.values()),
})
variant_table = variant_table.sort_values("cases", ascending=False).reset_index(drop=True)
variant_table["rank"] = variant_table.index + 1
variant_table["% of cases"] = variant_table["cases"] / num_cases * 100
variant_table["cumulative %"] = variant_table["% of cases"].cumsum()
variant_table["steps"] = variant_table["variant"].apply(len)

num_variants = len(variant_table)
singletons = variant_table[variant_table["cases"] == 1]

print("=== Variant overview ===")
print(f"Distinct variants:              {num_variants:,}")
print(f"Variants that occur only once:  {len(singletons):,} "
      f"({len(singletons) / num_variants * 100:.1f}% of variants, "
      f"{len(singletons) / num_cases * 100:.1f}% of cases)")

for target in [50, 80, 90]:
    needed = (variant_table["cumulative %"] < target).sum() + 1
    print(f"Variants needed to cover {target}% of cases: {needed:,}")
print()


# ---------------------------------------------------------------
# 3. Top variants and their matching types
# ---------------------------------------------------------------
top = variant_table.head(TOP_K)

print(f"=== Top {TOP_K} variants ===")
for _, row in top.iterrows():
    print(f"#{row['rank']}: {row['cases']:,} cases ({row['% of cases']:.1f}%, "
          f"cumulative {row['cumulative %']:.1f}%), {row['steps']} steps")

    # Which matching types do the cases in this variant have?
    variant_cases = pm4py.filter_variants(df, [row["variant"]])
    type_counts = variant_cases.groupby(CASE_COL)[MATCHING_COL].first().value_counts()
    type_text = ", ".join(f"{name}: {count:,}" for name, count in type_counts.items())
    print(f"    Matching types: {type_text}")

    print("    " + " -> ".join(row["variant"]))
    print()


# ---------------------------------------------------------------
# 4. Chart: cumulative case coverage by variant rank
# ---------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9, 5.5))
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)

ax.plot(variant_table["rank"], variant_table["cumulative %"],
        color=SERIES_1, linewidth=2)
ax.set_xscale("log")
ax.set_ylim(0, 100)

# Mark where the top K variants end
top_k_coverage = top["cumulative %"].iloc[-1]
ax.plot([TOP_K], [top_k_coverage], marker="o", markersize=8, color=SERIES_1,
        markeredgecolor=SURFACE, markeredgewidth=2)
ax.annotate(f"Top {TOP_K} variants cover {top_k_coverage:.1f}% of cases",
            xy=(TOP_K, top_k_coverage), xytext=(TOP_K * 3, top_k_coverage - 12),
            fontsize=9, color=TEXT_PRIMARY,
            arrowprops={"arrowstyle": "-", "color": TEXT_SECONDARY})

ax.set_xlabel("Variant rank (1 = most common, log scale)", color=TEXT_SECONDARY)
ax.set_ylabel("Cumulative % of cases", color=TEXT_SECONDARY)
ax.set_title(f"How many variants does it take to cover the cases?\n"
             f"{num_variants:,} variants in total for {num_cases:,} cases",
             color=TEXT_PRIMARY, loc="left", fontsize=11)

ax.grid(color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
for side in ["top", "right"]:
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(AXIS)
ax.spines["left"].set_color(AXIS)
ax.tick_params(colors=TEXT_SECONDARY)

fig.tight_layout()
fig.savefig(COVERAGE_CHART, dpi=150)
plt.close(fig)
print(f"Saved chart: {COVERAGE_CHART}")


# ---------------------------------------------------------------
# 5. Directly-follows graph of the top variants
# ---------------------------------------------------------------
# Keep only the cases that follow one of the top K variants
top_df = pm4py.filter_variants_top_k(df, TOP_K)
top_case_count = top_df[CASE_COL].nunique()
print(f"Cases in the top {TOP_K} variants: {top_case_count:,}")

# dfg = {(activity A, activity B): how often A is directly followed by B}
dfg, start_activities, end_activities = pm4py.discover_dfg(top_df)

print("\n=== Directly-follows pairs in the top variants (most frequent first) ===")
for (source, target), count in sorted(dfg.items(), key=lambda item: item[1], reverse=True):
    print(f"  {source} -> {target}: {count:,}")
print()

# rankdir="TB" draws the map top to bottom, which stays readable on a page
pm4py.save_vis_dfg(dfg, start_activities, end_activities, DFG_CHART, rankdir="TB")
print(f"Saved chart: {DFG_CHART}")
