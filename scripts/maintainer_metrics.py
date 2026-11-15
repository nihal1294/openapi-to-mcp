# ruff: noqa: ANN001, ANN201, ANN204, FBT002, PTH101, PTH105, PTH108, C901, PLR0912, PLR0911, PLR0915, PLR2004, FURB162, S603, S607, TRY301, TRY004, T201
"""Create a read-only report from public package and repository aggregates."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

import requests

PACKAGE = re.compile(r"^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TIMEOUT = (5, 20)


def now():
    return datetime.now(UTC)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def write_json(path, value, private=False):
    write_file(path, json.dumps(value, indent=2, ensure_ascii=True) + "\n", private)


def write_file(path, content, private=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".metrics-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        if private:
            os.chmod(name, 0o600)
        else:
            os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Sources:
    def __init__(self, directory, private=False, session=None, clock=now):
        self.directory = directory
        self.private = private
        self.session = session or requests.Session()
        # Public requests must not acquire credentials from the environment or netrc.
        self.session.trust_env = False
        self.clock = clock

    def get(self, name, identifier, url, *, release=False, gh=False):
        key = hashlib.sha256((identifier + "\n" + url).encode()).hexdigest()
        path = self.directory / "cache" / "v1" / f"{name}-{key}.json"
        cached = None
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(
                cached["fetched_at"].replace("Z", "+00:00")
            )
            if (
                cached["version"] != 1
                or cached["url"] != url
                or cached["identifier"] != identifier
            ):
                raise ValueError("invalid cache")
            if cached["status"] not in (200, 304) and not (
                name == "release" and cached["status"] == 404 and cached["body"] is None
            ):
                raise ValueError("invalid cache status")
            reduced = reduce_body(name, cached["body"])
            if (
                name == "repository"
                and reduced["full_name"].lower() != identifier.lower()
            ):
                raise ValueError("repository mismatch")
            if fetched.tzinfo is None:
                raise ValueError("invalid cache timestamp")
            canonical = {
                "version": 1,
                "url": url,
                "identifier": identifier,
                "fetched_at": stamp(fetched.astimezone(UTC)),
                "status": 404 if name == "release" and reduced is None else 200,
                "body": reduced,
            }
            if canonical != cached:
                write_json(path, canonical, self.private)
            cached = canonical
            if cached is not None and timedelta(
                0
            ) <= self.clock() - fetched < timedelta(hours=24):
                return cached["body"], {
                    "url": url,
                    "fetched_at": cached["fetched_at"],
                    "cache": True,
                    "status": cached["status"],
                }
        except OSError, ValueError, KeyError, TypeError, AttributeError:
            cached = None
            with suppress(OSError):
                path.unlink(missing_ok=True)
        status = None
        try:
            if gh:
                result = subprocess.run(
                    ["gh", "api", url],
                    capture_output=True,
                    text=True,
                    timeout=25,
                    check=False,
                )
                if result.returncode:
                    raise ValueError("command failed")
                body = json.loads(result.stdout)
                status = 200
            else:
                response = self.session.get(url, timeout=TIMEOUT)
                status = response.status_code
                if status == 404 and release:
                    body = None
                elif status != 200:
                    raise ValueError("http failure")
                else:
                    body = response.json()
            body = reduce_body(name, body)
            if name == "repository" and body["full_name"].lower() != identifier.lower():
                raise ValueError("repository mismatch")
            entry = {
                "version": 1,
                "url": url,
                "identifier": identifier,
                "fetched_at": stamp(self.clock()),
                "status": status,
                "body": body,
            }
            write_json(path, entry, self.private)
            return body, {
                "url": url,
                "fetched_at": entry["fetched_at"],
                "cache": False,
                "status": status,
            }
        except (
            requests.RequestException,
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            subprocess.SubprocessError,
        ):
            return None, {"url": url, "state": "unavailable", "status": status}


def count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def row_data(body, category=None):
    if not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise ValueError("invalid rows")
    rows = body["data"]
    for row in rows:
        if (
            not isinstance(row, dict)
            or not count(row.get("downloads"))
            or not isinstance(row.get("date"), str)
        ):
            raise ValueError("invalid row")
        datetime.fromisoformat(row["date"])
        if "category" not in row or (
            row["category"] is not None and not isinstance(row["category"], str)
        ):
            raise ValueError("invalid category")
    selected = [r for r in rows if category is None or r["category"] == category]
    dates = sorted(r["date"] for r in selected)
    return selected, {"start": dates[0], "end": dates[-1]} if dates else None


def normalize(name, body):
    if name == "recent":
        data = body["data"]
        if not isinstance(data, dict):
            raise ValueError("invalid recent")
        result = {}
        for field in ("last_day", "last_week", "last_month"):
            value = data.get(field)
            if value is not None and not count(value):
                raise ValueError("invalid recent count")
            result[field] = {
                "state": "missing"
                if value is None
                else ("zero" if value == 0 else "available"),
                "value": value,
            }
        return result, None
    if name in ("overall", "python_minor", "system"):
        rows, window = row_data(body, "without_mirrors" if name == "overall" else None)
        if name == "overall":
            if not rows:
                return {"state": "missing", "downloads": None}, window
            return {
                "state": "zero"
                if sum(r["downloads"] for r in rows) == 0
                else "available",
                "downloads": sum(r["downloads"] for r in rows),
                "history": "insufficient_history"
                if len({r["date"] for r in rows}) < 180
                else "available",
            }, window
        totals = {}
        for row in rows:
            key = row["category"] if row["category"] is not None else "unknown"
            totals[key] = totals.get(key, 0) + row["downloads"]
        return {
            "state": "available" if rows else "missing",
            "downloads_by_category": totals,
        }, window
    if name == "pypi":
        releases = body["releases"]
        if not isinstance(releases, dict):
            raise ValueError("invalid releases")
        timestamps = []
        for files in releases.values():
            if not isinstance(files, list):
                raise ValueError("invalid files")
            for item in files:
                if isinstance(item, dict) and item.get("upload_time_iso_8601"):
                    try:
                        parsed = datetime.fromisoformat(
                            item["upload_time_iso_8601"].replace("Z", "+00:00")
                        )
                        if parsed.tzinfo is not None:
                            timestamps.append(parsed.astimezone(UTC))
                    except ValueError, TypeError:
                        pass
        return {
            "first_upload": stamp(min(timestamps)) if timestamps else None,
            "state": "available" if timestamps else "missing",
        }, None
    if name == "repository":
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("full_name"), str)
            or body.get("private") is not False
        ):
            raise ValueError("invalid repository")
        return {
            "full_name": body["full_name"],
            "default_branch": body.get("default_branch"),
            "state": "available",
        }, None
    if name == "release":
        if body is None:
            return {"state": "available", "published_release": None}, None
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("tag_name"), str)
            or not isinstance(body.get("assets"), list)
        ):
            raise ValueError("invalid release")
        assets = body["assets"]
        if any(
            not isinstance(a, dict) or not count(a.get("download_count"))
            for a in assets
        ):
            raise ValueError("invalid assets")
        return {
            "state": "available",
            "tag": body["tag_name"],
            "name": body.get("name"),
            "published_at": body.get("published_at"),
            "asset_downloads": sum(a["download_count"] for a in assets),
        }, None
    if name in ("issues", "pull_requests"):
        if (
            not isinstance(body, dict)
            or body.get("incomplete_results") is not False
            or not count(body.get("total_count"))
        ):
            raise ValueError("invalid search")
        return {
            "state": "zero" if body["total_count"] == 0 else "available",
            "count": body["total_count"],
        }, None
    if name in ("views", "clones"):
        if (
            not isinstance(body, dict)
            or not count(body.get("count"))
            or not count(body.get("uniques"))
            or not isinstance(body.get(name), list)
        ):
            raise ValueError("invalid traffic")
        rows = body[name]
        dates = sorted(
            r["timestamp"]
            for r in rows
            if isinstance(r, dict) and isinstance(r.get("timestamp"), str)
        )
        return {
            "state": "available",
            "count": body["count"],
            "uniques": body["uniques"],
        }, {"start": dates[0], "end": dates[-1]} if dates else None
    if name == "referrers":
        if not isinstance(body, list) or any(
            not isinstance(r, dict)
            or not isinstance(r.get("referrer"), str)
            or not count(r.get("count"))
            or not count(r.get("uniques"))
            for r in body
        ):
            raise ValueError("invalid referrers")
        return {
            "state": "available" if body else "zero",
            "referrers": [
                {
                    "referrer": r["referrer"],
                    "count": r["count"],
                    "uniques": r["uniques"],
                }
                for r in body
            ],
        }, None
    raise ValueError("unknown source")


def safe_referrer(value):
    """Map known services to fixed labels; never retain arbitrary host text."""
    try:
        host = urlsplit(value if "://" in value else "//" + value).hostname
    except ValueError:
        return "other"
    if host:
        host = host.lower().rstrip(".")
        for domain in (
            "github.com",
            "google.com",
            "bing.com",
            "reddit.com",
            "stackoverflow.com",
            "pypi.org",
        ):
            if host == domain or host.endswith("." + domain):
                return domain
    return "other"


def reduce_body(name, body):
    """Keep only fields needed by the report before writing a provider response."""
    data, _ = normalize(name, body)
    if name == "recent":
        return {"data": {key: value["value"] for key, value in data.items()}}
    if name in ("overall", "python_minor", "system"):
        rows, _ = row_data(body)
        cleaned = []
        for row in rows:
            category = row["category"]
            if name == "overall":
                category = (
                    category
                    if category in ("with_mirrors", "without_mirrors")
                    else None
                )
            elif name == "python_minor":
                category = (
                    category
                    if isinstance(category, str)
                    and re.fullmatch(r"[0-9]{1,2}\.[0-9]{1,3}", category)
                    else None
                )
            else:
                category = (
                    category
                    if category
                    in (
                        "Linux",
                        "Windows",
                        "Darwin",
                        "FreeBSD",
                        "OpenBSD",
                        "NetBSD",
                        "SunOS",
                        "AIX",
                    )
                    else None
                )
            cleaned.append(
                {
                    "category": category,
                    "date": row["date"],
                    "downloads": row["downloads"],
                }
            )
        return {"data": cleaned}
    if name == "pypi":
        timestamp = data["first_upload"]
        return {
            "releases": {
                "earliest": [{"upload_time_iso_8601": timestamp}] if timestamp else []
            }
        }
    if name == "repository":
        full_name = data["full_name"]
        if not REPO.fullmatch(full_name):
            raise ValueError("invalid repository name")
        return {"full_name": full_name, "private": False, "default_branch": None}
    if name == "release":
        if body is None:
            return None
        tag = data["tag"]
        if not re.fullmatch(r"v?[0-9][A-Za-z0-9._+-]{0,63}", tag):
            tag = "unknown"
        published = data["published_at"]
        try:
            published = stamp(datetime.fromisoformat(published.replace("Z", "+00:00")))
        except AttributeError, TypeError, ValueError:
            published = None
        return {
            "tag_name": tag,
            "name": None,
            "published_at": published,
            "assets": [{"download_count": data["asset_downloads"]}],
        }
    if name in ("issues", "pull_requests"):
        return {"total_count": data["count"], "incomplete_results": False}
    if name in ("views", "clones"):
        rows = []
        for row in body[name]:
            try:
                date = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                rows.append({"timestamp": stamp(date)})
            except KeyError, AttributeError, TypeError, ValueError:
                continue
        return {"count": data["count"], "uniques": data["uniques"], name: rows}
    if name == "referrers":
        return [
            {
                "referrer": safe_referrer(row["referrer"]),
                "count": row["count"],
                "uniques": row["uniques"],
            }
            for row in body
        ]
    raise ValueError("unknown source")


def build_report(package, repo, sources, private=False):
    p = quote(package, safe="")
    r = quote(repo, safe="/")
    base = f"https://pypistats.org/api/packages/{p}"
    github = f"https://api.github.com/repos/{r}"
    specs = [
        (
            "recent",
            f"{base}/recent",
            "Recent download events; provider day, week and month windows.",
        ),
        (
            "overall",
            f"{base}/overall?mirrors=false",
            "Available daily history, known mirrors excluded; not a lifetime total.",
        ),
        (
            "python_minor",
            f"{base}/python_minor",
            "Download events by reported Python minor version.",
        ),
        ("system", f"{base}/system", "Download events by reported operating system."),
        (
            "pypi",
            f"https://pypi.org/pypi/{p}/json",
            "Earliest parseable release file upload timestamp.",
        ),
        ("repository", github, "Public repository identity."),
        (
            "release",
            f"{github}/releases/latest",
            "Latest qualifying published GitHub release; asset downloads are separate from PyPI.",
        ),
        (
            "issues",
            "https://api.github.com/search/issues?"
            + urlencode({"q": f"repo:{repo} is:issue is:open", "per_page": 1}),
            "Public open issues (GitHub search aggregate).",
        ),
        (
            "pull_requests",
            "https://api.github.com/search/issues?"
            + urlencode({"q": f"repo:{repo} is:pr is:open", "per_page": 1}),
            "Public open pull requests (GitHub search aggregate).",
        ),
    ]
    if private:
        specs.extend(
            (
                name,
                f"{github}/traffic/{name if name != 'referrers' else 'popular/referrers'}",
                "Private GitHub traffic; short provider window, not active users.",
            )
            for name in ("views", "clones", "referrers")
        )
    sections = {}
    for name, url, methodology in specs:
        body, provenance = sources.get(
            name,
            package
            if name in ("recent", "overall", "python_minor", "system", "pypi")
            else repo,
            url,
            release=name == "release",
            gh=name in ("views", "clones", "referrers"),
        )
        try:
            if provenance.get("state") == "unavailable":
                raise ValueError("source unavailable")
            data, window = normalize(name, body)
        except ValueError, TypeError, KeyError, AttributeError:
            data, window = {"state": "unavailable"}, None
        sections[name] = {
            "data": data,
            "window": window,
            "methodology": methodology,
            "source": provenance,
        }
    recent = sections["recent"]["data"]
    complete = all(
        section["data"]["state"] != "unavailable"
        and (name != "overall" or section["data"]["state"] != "missing")
        for name, section in sections.items()
        if "state" in section["data"]
    ) and all(
        isinstance(v, dict) and v.get("state") != "missing" for v in recent.values()
    )
    return {
        "schema_version": 1,
        "observed_at": stamp(sources.clock()),
        "package": package,
        "repository": repo,
        "completeness": "complete" if complete else "partial",
        "sections": sections,
    }


def render(report):
    lines = [
        "# Maintainer metrics",
        "",
        f"Observed: {report['observed_at']}",
        f"Package: {report['package']}  ",
        f"Repository: {report['repository']}  ",
        f"Completeness: {report['completeness']}",
        "",
    ]
    for name, section in report["sections"].items():
        lines.extend(
            [
                f"## {name.replace('_', ' ').title()}",
                "",
                section["methodology"],
                "",
                f"Source: {section['source']['url']}",
                f"Fetched: {section['source'].get('fetched_at', 'unavailable')} (cached: {section['source'].get('cache', False)})",
                f"Window: {json.dumps(section['window']) if section['window'] else 'not supplied'}",
                "",
                "```json",
                json.dumps(section["data"], indent=2, ensure_ascii=True),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="openapi-to-mcp-cli")
    parser.add_argument("--repo", default="nihal1294/openapi-to-mcp")
    parser.add_argument("--output-dir", required=True, type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--include-private-github-traffic", action="store_true")
    group.add_argument("--public-only", action="store_true")
    args = parser.parse_args(argv)
    if (
        not PACKAGE.fullmatch(args.package)
        or not REPO.fullmatch(args.repo)
        or any(part in (".", "..") for part in args.repo.split("/"))
    ):
        parser.error("invalid package or repository identifier")
    if (
        args.include_private_github_traffic
        and os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    ):
        parser.error("private GitHub traffic is unavailable in GitHub Actions")
    private = args.include_private_github_traffic
    try:
        report = build_report(
            args.package, args.repo, Sources(args.output_dir, private), private
        )
        write_json(args.output_dir / "maintainer-metrics.json", report, private)
        write_file(args.output_dir / "maintainer-metrics.md", render(report), private)
    except OSError:
        print("Unable to write report to the output directory.")
        return 1
    return 0 if report["completeness"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
