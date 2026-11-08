"""
Step 1: Load and profile the BPI Challenge 2019 event log.

- Reads the raw XES file with pm4py (slow, only done once).
- Saves a parquet copy so later steps load in seconds.
- Prints basic counts: cases, events, activities, date range.
- Flags events with timestamps outside the year 2018.
- Saves a chart of events per month to charts/.
"""

import os

import matplotlib.pyplot as plt
import pandas as pd
import pm4py

XES_PATH = "data/BPI_Challenge_2019.xes"
PARQUET_PATH = "data/bpi2019_events.parquet"
CHART_PATH = "charts/01_events_per_month.png"

# Column names that pm4py uses
CASE_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIME_COL = "time:timestamp"
MATCHING_COL = "case:Item Category"

# Colors for the chart
COLOR_IN_2018 = "#2a78d6"   # blue
COLOR_OUTSIDE = "#eb6834"   # orange
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
SURFACE = "#fcfcfb"


# ---------------------------------------------------------------
# 1. Load the event log
# ---------------------------------------------------------------
print("Reading XES file (this can take several minutes)...")
df = pm4py.read_xes(XES_PATH)
print("Done.\n")

# Save a parquet copy for the next steps
df.to_parquet(PARQUET_PATH, index=False)
size_mb = os.path.getsize(PARQUET_PATH) / (1024 * 1024)
print(f"Saved parquet copy: {PARQUET_PATH} ({size_mb:.0f} MB)\n")


# ---------------------------------------------------------------
# 2. Basic profile
# ---------------------------------------------------------------
num_events = len(df)
num_cases = df[CASE_COL].nunique()
num_activities = df[ACTIVITY_COL].nunique()
first_time = df[TIME_COL].min()
last_time = df[TIME_COL].max()

print("=== Basic profile ===")
print(f"Events:      {num_events:,}")
print(f"Cases:       {num_cases:,}")
print(f"Activities:  {num_activities}")
print(f"Earliest:    {first_time}")
print(f"Latest:      {last_time}")
print(f"Average events per case: {num_events / num_cases:.1f}")
print()

print("=== Columns ===")
for column in df.columns:
    print(f"  {column}  ({df[column].dtype})")
print()

print("=== Events per activity ===")
activity_counts = df[ACTIVITY_COL].value_counts()
print(activity_counts.to_string())
print()

print("=== Cases per matching type (Item Category) ===")
# Each case has one matching type, so count each case once
case_types = df[[CASE_COL, MATCHING_COL]].drop_duplicates()
type_counts = case_types[MATCHING_COL].value_counts()
type_shares = type_counts / num_cases * 100
for matching_type in type_counts.index:
    count = type_counts[matching_type]
    share = type_shares[matching_type]
    print(f"  {matching_type:40s} {count:>8,}  ({share:.1f}%)")
print()


# ---------------------------------------------------------------
# 3. Flag timestamps outside 2018
# ---------------------------------------------------------------
start_2018 = pd.Timestamp("2018-01-01", tz="UTC")
start_2019 = pd.Timestamp("2019-01-01", tz="UTC")

is_before_2018 = df[TIME_COL] < start_2018
is_after_2018 = df[TIME_COL] >= start_2019
is_outside_2018 = is_before_2018 | is_after_2018

cases_outside = df.loc[is_outside_2018, CASE_COL].unique()

print("=== Timestamps outside 2018 ===")
print(f"Events before 2018:  {is_before_2018.sum():,}")
print(f"Events after 2018:   {is_after_2018.sum():,}")
print(f"Cases with at least one event outside 2018: {len(cases_outside):,} "
      f"({len(cases_outside) / num_cases * 100:.2f}% of cases)")
print()

print("Events outside 2018 by year:")
outside_years = df.loc[is_outside_2018, TIME_COL].dt.year.value_counts().sort_index()
print(outside_years.to_string())
print()

print("Example events outside 2018:")
examples = df.loc[is_outside_2018, [CASE_COL, ACTIVITY_COL, TIME_COL]].head(10)
print(examples.to_string(index=False))
print()


# ---------------------------------------------------------------
# 4. Chart: events per month
# ---------------------------------------------------------------
# Convert each timestamp to its month, e.g. 2018-03
months = df[TIME_COL].dt.tz_localize(None).dt.to_period("M")
events_per_month = months.value_counts().sort_index()

# Only months that actually have events are shown, as separate bars
labels = []
counts = []
colors = []
for month, count in events_per_month.items():
    labels.append(str(month))
    counts.append(count)
    if month.year == 2018:
        colors.append(COLOR_IN_2018)
    else:
        colors.append(COLOR_OUTSIDE)

fig, ax = plt.subplots(figsize=(max(10, len(labels) * 0.25), 5))
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)

ax.bar(range(len(labels)), counts, color=colors, width=0.8)
ax.set_yscale("log")

ax.set_xticks(range(len(labels)))
ax.set_xticklabels(labels, rotation=90, fontsize=7, color=TEXT_SECONDARY)
ax.tick_params(axis="y", colors=TEXT_SECONDARY)
ax.set_ylabel("Events (log scale)", color=TEXT_SECONDARY)
ax.set_title("Events per month (months with no events are not shown)",
             color=TEXT_PRIMARY, loc="left")

# Light horizontal grid, no box around the plot
ax.grid(axis="y", color="#e4e3df", linewidth=0.8)
ax.set_axisbelow(True)
for side in ["top", "right", "left"]:
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color("#c9c8c2")

# Legend
in_patch = plt.Rectangle((0, 0), 1, 1, color=COLOR_IN_2018)
out_patch = plt.Rectangle((0, 0), 1, 1, color=COLOR_OUTSIDE)
ax.legend([in_patch, out_patch], ["2018", "Outside 2018"],
          frameon=False, labelcolor=TEXT_SECONDARY)

fig.tight_layout()
fig.savefig(CHART_PATH, dpi=150)
print(f"Saved chart: {CHART_PATH}")
