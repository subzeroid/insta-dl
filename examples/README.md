# Examples

Working scripts that exercise insta-dl's Python API. Each is self-contained — copy, adjust, run.

| Script | What it does |
|---|---|
| [`sync_profiles.py`](sync_profiles.py) | Incrementally archive a list of profiles read from a file, with `--fast-update` and stamp persistence. |
| [`filter_by_date.py`](filter_by_date.py) | Download only posts from a given year/month using the AST-restricted `--post-filter` compiler from Python. |
| [`hashtag_sample.py`](hashtag_sample.py) | Pull the first N posts of a hashtag (early break out of the cursor) with comments saved as JSONL. |

All examples assume `HIKERAPI_TOKEN` is set in the environment. They use `make_backend("hiker", token=…)` directly so they're easy to adapt to other backends as new ones land.
