# Where Purchase-to-Pay Breaks

A process analysis of 1.6 million purchase order events from a real manufacturer.

**Case study:** [read the full report](https://medhadev.github.io/p2p-process-analysis/case_study.html)

## Question

Where does a company's purchase-to-pay process break down, and what should it fix first?

## Hypothesis

Before looking at the data, I expected that order lines with price or quantity changes after the order is created, and lines invoiced before the goods arrive, take noticeably longer to pay and account for most of the rework.

That breaks into three testable claims:

- **A.** Corrected lines take longer to pay.
- **B.** Invoice-first lines take longer to pay.
- **C.** These two groups account for most of the rework.

## Approach

- Data: BPI Challenge 2019 event log from a multinational coatings and paints company, 2018: 251,734 purchase order lines, 1,595,923 events. Counts verified against the official figures.
- Measured order-to-payment time, rework, and payment-control compliance for each order line, and compared the four invoice matching types.
- Tested the hypothesis by comparing median days within the same matching type, so a mix of fast and slow types can't create a false gap.
- Mapped the most common process paths with pm4py.

## Findings

- Orders corrected after placing take a median 19 days (25%) longer to pay; 10.5% of lines are corrected.
- Invoice-first lines are not slower (75.8 vs 77.9 days), but they are put on payment hold 97% of the time.
- The strictest payment control is never broken and costs no extra time.
- 10 of 11,912 process paths cover 59.5% of lines.

**Hypothesis verdict: partly supported.**

| Claim | Result | Verdict |
|---|---|---|
| A. Corrected lines take longer | 94.9 vs 75.9 median days (+19 days) | Supported |
| B. Invoice-first lines take longer | 75.8 vs 77.9 median days | Not supported |
| C. They cause most of the rework | 38.1% of repeat-work lines vs 16.3% of all lines | Partly: over-represented, but not "most" |

## Recommendation

Fix order corrections first: confirm price and quantity before the order is sent. Measure it with a pilot against a comparison group, tracking the correction rate (baseline 10.5%) and median order-to-payment days (baseline 77.3 for 3-way lines).

## Limitations

- Shows what happened, not why: findings are comparisons, not proof of cause.
- Can't separate supplier delivery time and payment terms from internal delay.
- Unpaid lines at the data cut-off are excluded from time measures.
- One company, one year, anonymised.

## What I'd do differently

- Measure time spent in each step to find exactly where lines get stuck.
- Put a cost on the delay and the handling effort.
- Build an interactive dashboard.

## Data

van Dongen, B.F. (2019). BPI Challenge 2019. 4TU.ResearchData. https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1

The raw file is not in this repo; see `data/DOWNLOAD_HERE.md`.

## How to run

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
brew install graphviz
python 01_load_profile.py
python 02_matching_types.py
python 03_variants.py
quarto render
```
