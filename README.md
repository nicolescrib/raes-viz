# Reddit after the Yandex strikes

An interactive re-analysis of the [silkier-muses/raes](https://github.com/silkier-muses/raes) dataset: hourly posts + comments for 968 subreddits around the reported October 8, 9 and 11 2026 strikes on Yandex data centers. It responds to the [r/dataisbeautiful post](https://www.reddit.com/r/dataisbeautiful/comments/1x4hhff/oc_subreddit_activity_during_russian_datacenter/) that showed about thirty subreddits with falling activity, and to the criticism in its comments.

The page is a single static site: `index.html` plus two generated data files. Open `index.html` locally or host it with GitHub Pages.

## What it shows

1. **Reddit as a whole did not move.** Daily and hourly totals across all 968 communities. The 12 hours after each strike, relative to the 12 hours before (both normalised to the same hour of the week), were +2.5%, −0.8% and −3.7%. The typical swing on attack-free days is ±3.7%.
2. **Ninety communities fell three times. Chance predicts ninety-five.** At each strike about 45–47% of all subreddits "decreased" under the repository's rule, so independent chance alone puts about 95 communities on the "fell in all three windows" list. The observed distribution (147 / 394 / 337 / 90 for 0 / 1 / 2 / 3 windows) matches the chance model (152 / 389 / 332 / 95).
3. **Placebo tests.** The identical rule evaluated at every hour from Oct 3 to Oct 11 gives 43–50% "decreasing"; the strike hours sit at 45%, 47% and 45%. The identical three-window layout shifted onto attack-free days yields 67–126 "fell three times" communities, averaging 93.
4. **Who makes the list.** Pooled r against community size: the ranking is the lower tail of noise that grows as communities get smaller, and the upper tail is just as large.
5. **An explorer** for any of the 968 subreddits, with observed and expected hourly activity, the strike windows and the Reddit outage marked, plus notes on the communities argued about in the thread (r/news, r/conservative, r/canada, r/nascar, r/baseball, r/2007scape, …).
6. **The thread's criticisms**, each paired with what the page does about it, and a table of figures quoted in the thread against the repository's own numbers (for example r/conservative "+188%" versus +7% / +2% / +88%).

Every chart uses at most two series in a colour-blind-validated palette, has a legend, and has a data-table view.

## Hosting with GitHub Pages

Settings → Pages → Source: *Deploy from a branch* → branch `main`, folder `/ (root)`. The site has no build step. `.nojekyll` is present so the data files are served as-is.

## Rebuilding the data

```bash
git clone https://github.com/silkier-muses/raes
pip install -r analysis/requirements.txt
python analysis/build_data.py ../raes .
```

`analysis/build_data.py` reads `results.csv` and `source_data.zip` from the raes checkout, reproduces the repository's per-incident r and percentage changes to machine precision (it asserts the match), adds the site-wide totals, chance model and placebo runs, and writes `data.js` and `hourly.js`.

## Method notes

- Windows, anchors, baselines (same UTC hour 7, 14 and 21 days earlier), eligibility and the two excluded outage hours are the source repository's. See its [METHODS.md](https://github.com/silkier-muses/raes/blob/main/METHODS.md).
- The dataset snapshot was taken at about 00:20 UTC on Oct 12. Comments keep arriving on recent threads, so the last hours of Oct 11 are undercounted (25% low at 19:00, 45% low at 23:00). No strike window reaches those hours; all series on the page stop at 18:00 Oct 11, and the Oct 11 daily bar is marked partial.
- Placebo hours overlap and are serially dependent; they describe the range of the statistic, not a formal p-value.
- No signal here does not prove no bot network was affected. It shows that community-level hourly totals cannot detect one.
