# Maintainer metrics

Generate a read-only aggregate report with:

```sh
uv run python -m scripts.maintainer_metrics --public-only --output-dir /path/to/report
```

`--package` and `--repo` override the default package and repository. The output directory contains `maintainer-metrics.json`, `maintainer-metrics.md`, and a 24-hour response cache. A partial report exits nonzero when a required source fails. Cached results retain the time of the provider fetch; refreshes may use conditional requests. Keep the directory if repeated runs should reuse the cache. Copy reports elsewhere explicitly if permanent history is needed.

PyPI Stats reports download events, not users or installations. Its available history is bounded, excludes known mirrors, and is not a lifetime total. Python and operating-system categories reflect download clients. The earliest upload is derived from PyPI release-file timestamps. GitHub issue and pull-request totals are separate public search aggregates; release asset downloads are separate from PyPI downloads. Each section identifies its source, window where supplied, and data availability. No trend is inferred from incomplete history.

Maintainers with existing GitHub CLI access may explicitly add short-window private traffic and referrers locally:

```sh
uv run python -m scripts.maintainer_metrics --output-dir /path/to/private-report --include-private-github-traffic
```

This option is rejected in GitHub Actions and cannot be combined with `--public-only`. New private report and cache files are owner-readable and owner-writable only; protect the output directory and any existing files separately. The command does not configure GitHub credentials. Do not publish private reports or caches.
