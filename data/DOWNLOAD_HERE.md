# Download the data into this folder

No API or code needed. It's a normal browser download.

## Option A: Kaggle mirror (use this while 4TU is under maintenance)
1. Open https://www.kaggle.com/datasets/aaminaalzeri/bpi-challenge-2019-dataset
2. Sign in (free account) and download `BPI_Challenge_2019.xes` (about 730 MB).
3. Unzip if needed and move the `.xes` file into this `data/` folder.

This is a community upload of the official file, so verify it in step 1.
It should have 1,595,923 events and 251,734 cases. If the counts match,
it's the same data. Record that check in the README.

## Option B: Official source (once 4TU is back)
https://data.4tu.nl/articles/dataset/BPI_Challenge_2019/12715853
Permanent DOI: https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1

## Either way
- Cite the official DOI in the README, not the mirror.
- The file is large. It's excluded from Git in `.gitignore`, so it never reaches GitHub.
- Loading a 730 MB XES file is slow. In step 1, read it once and save a copy as
  `data/bpi2019.parquet`, then load the parquet in every later step.
