# "Needs you" page — what the applier couldn't do, by kind

Decided 2026-11-13 (Tejas). Route `/needs-you`, linked from the Today card's "Need you"
number and from every Needs-you chip in the bell.

**Navigation (Tejas, 2026-11-13):** the page is its own tab, **"Blockers"**, replacing
"Archive" in the bottom tab bar (phone) and the left rail (desktop). Archive is still one tap
away via the "Applied" chip on Jobs (and Archive highlights the Jobs tab).

## Data
`data/applier/applier.db` → `attempts` with `detail LIKE 'needs_human:%'` (read-only), owner's
applier. Each row is tagged with the shared classifier (`services/problem_tags.py`, same tags as
the bell). Range filter in one row at the top: 7 days · 30 days · All (default All).

## Layout (phone first, one column; >= 900px two columns for the sections)
1. **Header**: total count + range filter.
2. **Overview**: a donut of the split by tag (<= 6 slices, tail folded into "Other"), total in
   the centre; the table below it is the legend.
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

## Form choice
Overview = **pie (donut)**, Tejas's explicit choice (2026-11-13, after first seeing a segmented
bar): <= 6 slices + "Other", 2px gaps between slices, total in the centre, hover title per slice.
The table right under it is the legend (colour chip · name · count · share), so identity is never
colour-alone; no separate side legend (it truncated names on phones and repeated the table).
Per-company breakdown stays **ranked horizontal bars** (20+ companies can't be read as slices).

## Colours
Fixed per tag (never by rank), from the validated dark categorical palette (passes all checks on
the card surface #111014): account wall #3987e5, email code #d95926, CAPTCHA #199e70, profile
doesn't fit #c98500, wrong page #d55181, maybe applied #008300, payment #9085e9; any other /
new tag folds to grey #8a8486. Text never wears the series colour.
