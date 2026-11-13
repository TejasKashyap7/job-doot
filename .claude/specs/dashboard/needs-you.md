# "Needs you" page — what the applier couldn't do, by kind

Decided 2026-11-13 (Tejas). Route `/needs-you`, linked from the Today card's "Need you"
number and from every Needs-you chip in the bell.

## Data
`data/applier/applier.db` → `attempts` with `detail LIKE 'needs_human:%'` (read-only), owner's
applier. Each row is tagged with the shared classifier (`services/problem_tags.py`, same tags as
the bell). Range filter in one row at the top: 7 days · 30 days · All (default All).

## Layout (phone first, one column; >= 900px two columns for the sections)
1. **Header**: total count + range filter.
2. **Overview**: one tall segmented bar of the split by tag (<= 6 parts, tail folded into
   "Other"), share printed on each block where it fits, legend of names below.
   Then a small table: tag · count · share (the table view, a11y).
3. **One section per tag**, largest first, anchor `#<tag key>`:
   - tag chip + count;
   - **"What this means"**: 1–2 very simple sentences (no jargon);
   - **"What happens next"**: one sentence (automation-first; never "do it by hand");
   - **By company**: ranked horizontal bars, largest first, one hue (the tag's colour), count
     printed at the bar end, top 8 + "Others";
   - **By site / system** (only for Account / sign-in wall): Workday, Amazon, SuccessFactors… as
     ranked bars — this is what decides how account automation gets built later;
   - collapsible list of the jobs: date · company · role · link.

## Form choice (dataviz skill, 2026-11-13)
Tejas asked for pie charts. Used instead: the overview as a **tall segmented bar** (one whole,
<= 6 parts, read at a glance) and per-company **ranked horizontal bars** (20+ companies; a pie
can't show that many slices readably). Easy to switch to pies if Tejas prefers after seeing it.

## Colours
Fixed per tag (never by rank), from the validated dark categorical palette (passes all checks on
the card surface #111014): account wall #3987e5, email code #d95926, CAPTCHA #199e70, profile
doesn't fit #c98500, wrong page #d55181, maybe applied #008300, payment #9085e9; any other /
new tag folds to grey #8a8486. Text never wears the series colour.
