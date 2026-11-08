"""
Step 2: Compare item matching types (Item Category).

For each matching type we compare:
- Throughput time: first "Create Purchase Order Item" to last "Clear Invoice".
- Rework: price/quantity changes, and activities that happen more than once.
- Invoice before goods receipt: first invoice recorded before first goods receipt.
- Hypothesis test: do changed or invoice-first items take longer, and do they
  account for most of the rework?

Cases with any event before 2018 are excluded (likely bad dates).
Cases that run into January 2019 are kept.
"""

import matplotlib.pyplot as plt
import pandas as pd

PARQUET_PATH = "data/bpi2019_events.parquet"

# Column names that pm4py uses
CASE_COL = "case:concept:name"
ACTIVITY_COL = "concept:name"
TIME_COL = "time:timestamp"
MATCHING_COL = "case:Item Category"
RESOURCE_COL = "org:resource"   # who did the step; automated jobs are named "batch_..."

# Activities used in the measures
CREATE_PO = "Create Purchase Order Item"
CLEAR_INVOICE = "Clear Invoice"
RECORD_INVOICE = "Record Invoice Receipt"
RECORD_GR = "Record Goods Receipt"
CHANGE_PRICE = "Change Price"
CHANGE_QUANTITY = "Change Quantity"

# Activities that can legitimately repeat (partial deliveries, instalments)
NORMAL_REPEATS = [
    "Record Goods Receipt",
    "Record Invoice Receipt",
    "Vendor creates invoice",
    "Clear Invoice",
    "Record Service Entry Sheet",
    "Remove Payment Block",
    # Approval workflow step, not a correction to the order. It is reported
    # separately below as "% repeated approval change".
    "Change Approval for Purchase Order",
]
CHANGE_APPROVAL = "Change Approval for Purchase Order"
REMOVE_PAYMENT_BLOCK = "Remove Payment Block"
DELETE_PO_ITEM = "Delete Purchase Order Item"

# Order of matching types in tables and charts (largest first)
TYPE_ORDER = [
    "3-way match, invoice before GR",
    "3-way match, invoice after GR",
    "Consignment",
    "2-way match",
]

# Colors for the charts
SERIES_1 = "#2a78d6"   # blue
SERIES_2 = "#eb6834"   # orange
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
early_events = df[df[TIME_COL] < start_2018]
early_cases = early_events[CASE_COL].unique()

cases_before = df[CASE_COL].nunique()
df = df[~df[CASE_COL].isin(early_cases)]
cases_after = df[CASE_COL].nunique()

print("=== Filtering ===")
print(f"Cases before filtering:         {cases_before:,}")
print(f"Cases with an event before 2018: {len(early_cases):,} (excluded)")
print(f"Cases kept:                     {cases_after:,}")
print()


# ---------------------------------------------------------------
# 2. Build one row per case
# ---------------------------------------------------------------
# Matching type of each case
cases = df.groupby(CASE_COL)[MATCHING_COL].first().to_frame("matching_type")

# How often each activity happens in each case (rows = cases, columns = activities)
activity_counts = df.groupby([CASE_COL, ACTIVITY_COL]).size().unstack(fill_value=0)


def first_time_of(activity):
    """Earliest timestamp of an activity in each case."""
    rows = df[df[ACTIVITY_COL] == activity]
    return rows.groupby(CASE_COL)[TIME_COL].min()


def last_time_of(activity):
    """Latest timestamp of an activity in each case."""
    rows = df[df[ACTIVITY_COL] == activity]
    return rows.groupby(CASE_COL)[TIME_COL].max()


# --- Throughput time ---
cases["po_created"] = first_time_of(CREATE_PO)
cases["last_clear"] = last_time_of(CLEAR_INVOICE)
duration = cases["last_clear"] - cases["po_created"]
cases["throughput_days"] = duration.dt.total_seconds() / (60 * 60 * 24)

# --- Price / quantity changes ---
cases["n_price_qty_changes"] = activity_counts[CHANGE_PRICE] + activity_counts[CHANGE_QUANTITY]
cases["has_price_qty_change"] = cases["n_price_qty_changes"] > 0

# --- Repeated activities ---
cases["has_any_repeat"] = (activity_counts > 1).any(axis=1)
unusual_counts = activity_counts.drop(columns=NORMAL_REPEATS)
cases["has_unusual_repeat"] = (unusual_counts > 1).any(axis=1)
cases["has_repeated_approval"] = activity_counts[CHANGE_APPROVAL] > 1

# --- Invoice before goods receipt ---
cases["first_invoice"] = first_time_of(RECORD_INVOICE)
cases["first_gr"] = first_time_of(RECORD_GR)
cases["has_invoice_and_gr"] = cases["first_invoice"].notna() & cases["first_gr"].notna()
cases["invoice_before_gr"] = cases["has_invoice_and_gr"] & (cases["first_invoice"] < cases["first_gr"])

# --- Payment block release and deleted items ---
cases["has_payment_block_removal"] = activity_counts[REMOVE_PAYMENT_BLOCK] > 0
cases["was_deleted"] = activity_counts[DELETE_PO_ITEM] > 0

# A payment block can be removed by a person or by an automated batch job.
# Batch jobs have user names starting with "batch".
block_removals = df[df[ACTIVITY_COL] == REMOVE_PAYMENT_BLOCK]
removed_by_batch = block_removals[RESOURCE_COL].str.startswith("batch")
removed_by_person = block_removals[~removed_by_batch]
cases_with_person_removal = removed_by_person[CASE_COL].unique()
cases["has_person_block_removal"] = cases.index.isin(cases_with_person_removal)


# ---------------------------------------------------------------
# 3. Data-quality check on throughput
# ---------------------------------------------------------------
measurable = cases["throughput_days"].notna()
zero_or_negative = measurable & (cases["throughput_days"] <= 0)

print("=== Throughput data check ===")
print(f"Cases with both PO creation and invoice clearing: {measurable.sum():,}")
print(f"Of those, zero or negative throughput:            {zero_or_negative.sum():,}")
print()


# ---------------------------------------------------------------
# 4. Summary table by matching type
# ---------------------------------------------------------------
rows = []
for matching_type in TYPE_ORDER:
    group = cases[cases["matching_type"] == matching_type]
    days = group["throughput_days"].dropna()
    with_both = group[group["has_invoice_and_gr"]]

    if len(with_both) > 0:
        pct_invoice_first = with_both["invoice_before_gr"].mean() * 100
    else:
        pct_invoice_first = float("nan")

    rows.append({
        "matching_type": matching_type,
        "cases": len(group),
        "% throughput measurable": len(days) / len(group) * 100,
        "p25 days": days.quantile(0.25),
        "median days": days.median(),
        "p75 days": days.quantile(0.75),
        "p90 days": days.quantile(0.90),
        "% price/qty change": group["has_price_qty_change"].mean() * 100,
        "avg price/qty changes": group["n_price_qty_changes"].mean(),
        "% any repeat": group["has_any_repeat"].mean() * 100,
        "% unusual repeat": group["has_unusual_repeat"].mean() * 100,
        "% repeated approval change": group["has_repeated_approval"].mean() * 100,
        "% with invoice and GR": len(with_both) / len(group) * 100,
        "% invoice before GR": pct_invoice_first,
    })

summary = pd.DataFrame(rows).set_index("matching_type")

pd.set_option("display.width", 200)
pd.set_option("display.float_format", "{:.1f}".format)

print("=== Throughput time (days) by matching type ===")
print(summary[["cases", "% throughput measurable", "p25 days", "median days",
               "p75 days", "p90 days"]].to_string())
print()

print("=== Rework by matching type ===")
print(summary[["% price/qty change", "avg price/qty changes",
               "% any repeat", "% unusual repeat",
               "% repeated approval change"]].to_string(
    formatters={"avg price/qty changes": "{:.2f}".format}))
print()

print("=== Invoice before goods receipt by matching type ===")
print(summary[["% with invoice and GR", "% invoice before GR"]].to_string())
print()

print("=== Baseline KPIs (all matching types) ===")
all_days = cases["throughput_days"].dropna()
print(f"Median PO-to-payment days (items with both events): {all_days.median():.1f}")
print(f"% items with a price or quantity change:            "
      f"{cases['has_price_qty_change'].mean() * 100:.1f}%")
print(f"% items with a payment block removal:               "
      f"{cases['has_payment_block_removal'].mean() * 100:.1f}%")
print(f"% items with a payment block removed by a person:   "
      f"{cases['has_person_block_removal'].mean() * 100:.1f}%")
print(f"% items deleted after the PO was created:           "
      f"{cases['was_deleted'].mean() * 100:.1f}%")
print()

print("=== Who removes payment blocks? ===")
print(f"Payment block removal events: {len(block_removals):,}")
print(f"  By a person:    {len(removed_by_person):,} ({(~removed_by_batch).mean() * 100:.1f}%)")
print(f"  By a batch job: {removed_by_batch.sum():,} ({removed_by_batch.mean() * 100:.1f}%)")
print()

# Payment block removal depending on whether the invoice came before the goods.
# Only items that have both an invoice and a goods receipt.
with_both = cases[cases["has_invoice_and_gr"]]
invoice_first = with_both[with_both["invoice_before_gr"]]
goods_first = with_both[~with_both["invoice_before_gr"]]
print("=== Payment block removal vs. order of invoice and goods receipt ===")
print(f"Invoice recorded before goods: {len(invoice_first):,} items, "
      f"{invoice_first['has_payment_block_removal'].mean() * 100:.1f}% had a payment block removed, "
      f"{invoice_first['has_person_block_removal'].mean() * 100:.1f}% by a person")
print(f"Goods received first:          {len(goods_first):,} items, "
      f"{goods_first['has_payment_block_removal'].mean() * 100:.1f}% had a payment block removed, "
      f"{goods_first['has_person_block_removal'].mean() * 100:.1f}% by a person")
print()

# Throughput with and without a payment block removal (comparison, not cause)
blocked_days = cases.loc[cases["has_payment_block_removal"], "throughput_days"].dropna()
unblocked_days = cases.loc[~cases["has_payment_block_removal"], "throughput_days"].dropna()
print("=== Median PO-to-payment days, with vs. without payment block removal ===")
print(f"With payment block removal:    {blocked_days.median():.1f} days ({len(blocked_days):,} items)")
print(f"Without payment block removal: {unblocked_days.median():.1f} days ({len(unblocked_days):,} items)")
print()

print("=== Most common unusual repeats (cases where the activity occurs 2+ times) ===")
unusual_repeat_cases = (unusual_counts > 1).sum().sort_values(ascending=False)
print(unusual_repeat_cases[unusual_repeat_cases > 0].head(10).to_string())
print()


# ---------------------------------------------------------------
# 5. Charts
# ---------------------------------------------------------------
def short_label(matching_type, n_cases):
    """Shorter type names for chart axes, with the case count."""
    short_names = {
        "3-way match, invoice before GR": "3-way,\ninvoice before GR",
        "3-way match, invoice after GR": "3-way,\ninvoice after GR",
        "Consignment": "Consignment",
        "2-way match": "2-way match",
    }
    return f"{short_names[matching_type]}\n(n={n_cases:,})"


def style_axes(ax):
    """Light grid, no box, muted axis text."""
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=TEXT_SECONDARY)


# --- Chart 1: throughput box plot (log scale) ---
box_data = []
box_labels = []
for matching_type in TYPE_ORDER:
    days = cases.loc[cases["matching_type"] == matching_type, "throughput_days"]
    positive_days = days[days > 0]   # log scale cannot show zero or negative
    box_data.append(positive_days)
    box_labels.append(short_label(matching_type, len(positive_days)))

fig, ax = plt.subplots(figsize=(9, 5.5))
fig.patch.set_facecolor(SURFACE)
ax.boxplot(
    box_data,
    whis=(5, 95),
    showfliers=False,
    patch_artist=True,
    widths=0.5,
    boxprops={"facecolor": SERIES_1, "edgecolor": SERIES_1},
    medianprops={"color": "white", "linewidth": 2},
    whiskerprops={"color": TEXT_SECONDARY},
    capprops={"color": TEXT_SECONDARY},
)
ax.set_xticks(range(1, len(box_labels) + 1))
ax.set_xticklabels(box_labels, fontsize=9)
ax.set_yscale("log")
ax.set_ylabel("Days from PO creation to last invoice clearing (log scale)",
              color=TEXT_SECONDARY)
ax.set_title("Throughput time by matching type\n"
             "Box = middle 50% of cases, white line = median, whiskers = 5th to 95th percentile",
             color=TEXT_PRIMARY, loc="left", fontsize=11)
style_axes(ax)
fig.tight_layout()
fig.savefig("charts/02_throughput_by_type.png", dpi=150)
plt.close(fig)


# --- Chart 2: rework grouped bars ---
labels = [short_label(t, summary.loc[t, "cases"]) for t in TYPE_ORDER]
price_qty = [summary.loc[t, "% price/qty change"] for t in TYPE_ORDER]
unusual = [summary.loc[t, "% unusual repeat"] for t in TYPE_ORDER]

positions = list(range(len(TYPE_ORDER)))
bar_width = 0.36
left_positions = [p - bar_width / 2 - 0.01 for p in positions]
right_positions = [p + bar_width / 2 + 0.01 for p in positions]

fig, ax = plt.subplots(figsize=(9, 5.5))
fig.patch.set_facecolor(SURFACE)
bars1 = ax.bar(left_positions, price_qty, width=bar_width, color=SERIES_1,
               label="Has a price or quantity change")
bars2 = ax.bar(right_positions, unusual, width=bar_width, color=SERIES_2,
               label="Has a repeated activity (excl. normal repeats)")
ax.bar_label(bars1, fmt="%.1f%%", padding=3, fontsize=8, color=TEXT_SECONDARY)
ax.bar_label(bars2, fmt="%.1f%%", padding=3, fontsize=8, color=TEXT_SECONDARY)
ax.set_xticks(positions)
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylabel("% of cases", color=TEXT_SECONDARY)
ax.set_title("Rework by matching type", color=TEXT_PRIMARY, loc="left", fontsize=11)
ax.legend(frameon=False, labelcolor=TEXT_SECONDARY, fontsize=9)
style_axes(ax)
fig.tight_layout()
fig.savefig("charts/02_rework_by_type.png", dpi=150)
plt.close(fig)


# --- Chart 3: invoice before goods receipt ---
invoice_labels = []
invoice_values = []
for matching_type in TYPE_ORDER:
    n_with_both = round(summary.loc[matching_type, "% with invoice and GR"] / 100
                        * summary.loc[matching_type, "cases"])
    invoice_labels.append(short_label(matching_type, n_with_both))
    invoice_values.append(summary.loc[matching_type, "% invoice before GR"])

fig, ax = plt.subplots(figsize=(9, 5.5))
fig.patch.set_facecolor(SURFACE)
bars = ax.bar(positions, invoice_values, width=0.5, color=SERIES_1)
ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9, color=TEXT_SECONDARY)
# Types with no cases that have both events get a note instead of a bar
for position, value in zip(positions, invoice_values):
    if pd.isna(value):
        ax.text(position, 0.2, "Not applicable\n(no case has both)",
                ha="center", fontsize=8, color=TEXT_SECONDARY)
ax.set_xticks(positions)
ax.set_xticklabels(invoice_labels, fontsize=9)
ax.set_ylabel("% of cases with both an invoice and a goods receipt",
              color=TEXT_SECONDARY)
ax.set_title("Invoice recorded before goods receipt, by matching type\n"
             "(n = cases with both an invoice and a goods receipt)",
             color=TEXT_PRIMARY, loc="left", fontsize=11)
style_axes(ax)
fig.tight_layout()
fig.savefig("charts/02_invoice_before_gr_by_type.png", dpi=150)
plt.close(fig)

print("Saved charts:")
print("  charts/02_throughput_by_type.png")
print("  charts/02_rework_by_type.png")
print("  charts/02_invoice_before_gr_by_type.png")
print()


# ---------------------------------------------------------------
# 6. Hypothesis test
# ---------------------------------------------------------------
# Hypothesis: items with price or quantity changes after the PO is created,
# and items invoiced before goods receipt, take noticeably longer to clear
# and account for most of the rework.

def describe_days(days):
    """One line with the number of items and the 25th, 50th and 75th percentile days."""
    return (f"n={len(days):>7,}   p25={days.quantile(0.25):6.1f}   "
            f"median={days.median():6.1f}   p75={days.quantile(0.75):6.1f}")


def print_comparison(label_yes, days_yes, label_no, days_no):
    """Print two groups and the gap between their medians."""
    print(f"  {label_yes:28s} {describe_days(days_yes)}")
    print(f"  {label_no:28s} {describe_days(days_no)}")
    gap = days_yes.median() - days_no.median()
    gap_pct = gap / days_no.median() * 100
    print(f"  Median gap: {gap:+.1f} days ({gap_pct:+.1f}%)")
    print()


measured = cases[cases["throughput_days"].notna()]

print("=== Hypothesis A: items with a price/quantity change take longer ===")
print("All matching types:")
print_comparison(
    "With price/qty change", measured.loc[measured["has_price_qty_change"], "throughput_days"],
    "Without price/qty change", measured.loc[~measured["has_price_qty_change"], "throughput_days"],
)
for matching_type in ["3-way match, invoice before GR", "3-way match, invoice after GR"]:
    group = measured[measured["matching_type"] == matching_type]
    print(f"Within {matching_type}:")
    print_comparison(
        "With price/qty change", group.loc[group["has_price_qty_change"], "throughput_days"],
        "Without price/qty change", group.loc[~group["has_price_qty_change"], "throughput_days"],
    )

print("=== Hypothesis B: items invoiced before goods receipt take longer ===")
print("Within 3-way match, invoice before GR (the only type where invoice-first happens),")
print("items with both an invoice and a goods receipt:")
lenient = measured[(measured["matching_type"] == "3-way match, invoice before GR")
                   & measured["has_invoice_and_gr"]]
invoice_first_days = lenient.loc[lenient["invoice_before_gr"], "throughput_days"]
goods_first_days = lenient.loc[~lenient["invoice_before_gr"], "throughput_days"]
print_comparison("Invoice before goods", invoice_first_days,
                 "Goods before invoice", goods_first_days)

print("=== Hypothesis C: these two groups account for most of the rework ===")
cases["in_either_group"] = cases["has_price_qty_change"] | cases["invoice_before_gr"]
cases["has_rework"] = cases["has_price_qty_change"] | cases["has_unusual_repeat"]

rework_cases = cases[cases["has_rework"]]
print(f"Items with any rework (price/qty change or unusual repeat): {len(rework_cases):,} "
      f"({len(rework_cases) / len(cases) * 100:.1f}% of all items)")
print(f"  Share of rework items with a price/qty change:   "
      f"{rework_cases['has_price_qty_change'].mean() * 100:.1f}%  (counts as rework by definition)")
print(f"  Share of rework items invoiced before goods:     "
      f"{rework_cases['invoice_before_gr'].mean() * 100:.1f}%")
print(f"  Share of rework items in either group:           "
      f"{rework_cases['in_either_group'].mean() * 100:.1f}%")
print()

# Fairer check: unusual repeats only, which are measured separately from the two groups.
# Price/quantity changes are removed from the unusual repeat measure here, so
# the check is not circular.
repeat_counts = unusual_counts.drop(columns=[CHANGE_PRICE, CHANGE_QUANTITY])
cases["has_other_repeat"] = (repeat_counts > 1).any(axis=1)
other_repeat_cases = cases[cases["has_other_repeat"]]
print("Fairer check, using only repeats other than price/quantity changes:")
print(f"Items with such a repeat: {len(other_repeat_cases):,} "
      f"({len(other_repeat_cases) / len(cases) * 100:.1f}% of all items)")
print(f"  Share of these items in either group:  "
      f"{other_repeat_cases['in_either_group'].mean() * 100:.1f}%")
print(f"  Share of ALL items in either group:     "
      f"{cases['in_either_group'].mean() * 100:.1f}%  (what we'd expect if the groups were not special)")
print()


# --- Chart 4: hypothesis A and B side by side ---
fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(10, 5.5), sharey=True)
fig.patch.set_facecolor(SURFACE)

panels = [
    (ax_a, "A: Price or quantity change",
     [measured.loc[~measured["has_price_qty_change"], "throughput_days"],
      measured.loc[measured["has_price_qty_change"], "throughput_days"]],
     ["No change", "Changed"]),
    (ax_b, "B: Order of invoice and goods\n(3-way, invoice before GR only)",
     [goods_first_days, invoice_first_days],
     ["Goods first", "Invoice first"]),
]
for ax, title, data, names in panels:
    ax.boxplot(
        data,
        whis=(5, 95),
        showfliers=False,
        patch_artist=True,
        widths=0.5,
        boxprops={"facecolor": SERIES_1, "edgecolor": SERIES_1},
        medianprops={"color": "white", "linewidth": 2},
        whiskerprops={"color": TEXT_SECONDARY},
        capprops={"color": TEXT_SECONDARY},
    )
    tick_labels = []
    for name, days in zip(names, data):
        tick_labels.append(f"{name}\n(n={len(days):,})\nmedian {days.median():.0f} days")
    ax.set_xticks([1, 2])
    ax.set_xticklabels(tick_labels, fontsize=9)
    ax.set_title(title, color=TEXT_PRIMARY, loc="left", fontsize=10)
    style_axes(ax)

ax_a.set_ylabel("Days from PO creation to last invoice clearing", color=TEXT_SECONDARY)
fig.suptitle("Do changed or invoice-first items take longer to clear?\n"
             "Box = middle 50%, white line = median, whiskers = 5th to 95th percentile",
             color=TEXT_PRIMARY, x=0.01, ha="left", fontsize=11)
fig.tight_layout()
fig.savefig("charts/02_hypothesis_throughput.png", dpi=150)
plt.close(fig)
print("Saved chart: charts/02_hypothesis_throughput.png")
