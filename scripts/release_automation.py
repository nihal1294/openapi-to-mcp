"""Check release proposals and bind publication to their reviewed evidence."""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

try:
    from scripts.release_metadata import (
        RELEASE_BRANCH,
        artifact_hashes,
        git,
        metadata_digest,
        project_version,
        resolve,
        validate_evidence,
        validate_release_files,
        validate_release_pr,
    )
    from scripts.release_policy import (
        analyze_changes,
        parse_intent,
        validate_intent,
        validate_version,
    )
except ModuleNotFoundError:
    from release_metadata import (
        RELEASE_BRANCH,
        artifact_hashes,
        git,
        metadata_digest,
        project_version,
        resolve,
        validate_evidence,
        validate_release_files,
        validate_release_pr,
    )
    from release_policy import (
        analyze_changes,
        parse_intent,
        validate_intent,
        validate_version,
    )

IMPACTS = ("none", "patch", "minor", "breaking")
PAGE_SIZE = 100
MAX_EVIDENCE_BYTES = 5_000_000
SQUASH_FIELDS = 2


def api(
    path: str, *, method: str = "GET", body: dict | None = None
) -> dict | list | None:
    command = ["gh", "api", "--method", method, path]
    if body is not None:
        command += ["--input", "-"]
    result = subprocess.run(  # noqa: S603
        command,
        input=json.dumps(body) if body is not None else None,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def pages(path: str, key: str | None = None) -> list:
    items = []
    for page in range(1, 101):
        separator = "&" if "?" in path else "?"
        response = api(f"{path}{separator}per_page=100&page={page}")
        batch = response[key] if key else response
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            return items
    raise ValueError(
        "GitHub result exceeded pagination limit; narrow the release range."
    )


def summary(text: str) -> None:
    sys.stdout.write(text + "\n")
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(text + "\n")


def output(**values: str | int | bool) -> None:
    if path := os.environ.get("GITHUB_OUTPUT"):
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.writelines(
                f"{key}={str(value).lower() if isinstance(value, bool) else value}\n"
                for key, value in values.items()
            )


def override_message(message: str, body: str) -> str:
    begin, end = "BEGIN_COMMIT_OVERRIDE", "END_COMMIT_OVERRIDE"
    if begin not in body and end not in body:
        return message
    if (
        body.count(begin) != 1
        or body.count(end) != 1
        or body.index(begin) > body.index(end)
    ):
        raise ValueError(
            "Expected one complete BEGIN_COMMIT_OVERRIDE/END_COMMIT_OVERRIDE block."
        )
    return body.split(begin, 1)[1].split(end, 1)[0].strip()


def intent_message(message: str, body: str) -> str:
    effective = override_message(message, body)
    notes = re.search(
        r"(?im)^[ \t]*migration(?:[ \t]+notes?)?[ \t]*:[ \t]*(\S[^\n]*)", body
    )
    if notes and not re.search(r"(?im)^migration(?:\s+notes?)?\s*:", effective):
        effective += "\n\nMigration: " + notes.group(1)
    return effective


def release_range(repository: str, baseline: str, head: str) -> dict:
    """Check the same squash messages and PR overrides consumed by Release Please."""
    maximum = "none"
    changes = []
    for sha in git(
        "rev-list", "--first-parent", "--reverse", f"{baseline}..{head}"
    ).splitlines():
        message = git("show", "-s", "--format=%B", sha)
        associated = api(f"repos/{repository}/commits/{sha}/pulls")
        merged = [
            p
            for p in associated
            if p.get("merge_commit_sha") == sha and p.get("merged_at")
        ]
        if len(merged) > 1:
            raise ValueError(f"Ambiguous merged PR for {sha}.")
        pr = api(f"repos/{repository}/pulls/{merged[0]['number']}") if merged else None
        body = (pr.get("body") or "") if pr else ""
        message = intent_message(message, body)
        minimum = analyze_changes(resolve(f"{sha}^"), sha)["minimum"]
        try:
            intent = validate_intent(message, minimum)
        except ValueError:
            # Older non-releasing maintenance titles are harmless. Product
            # changes must be explicitly classified, even before adoption.
            if (
                minimum != "none"
                or re.match(r"[a-z]+(?:\([^)]+\))?!?:", message)
                or re.search(
                    r"Release-As:|BREAKING[ -]CHANGE|COMMIT_OVERRIDE",
                    message,
                    re.IGNORECASE,
                )
            ):
                raise ValueError(
                    f"Classify merged PR #{pr['number'] if pr else sha} with a Conventional Commit override before proposing a release."
                ) from None
            intent = {"impact": "none"}
        impact = intent["impact"]
        maximum = max((maximum, impact), key=IMPACTS.index)
        changes.append(
            {
                "sha": sha,
                "pr": pr["number"] if pr else None,
                "message": message,
                "impact": impact,
            }
        )
    return {"impact": maximum, "changes": changes}


def contracts(base: str, head: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="release-contracts-") as directory:
        report = Path(directory) / "contracts.json"
        subprocess.run(  # noqa: S603
            [
                sys.executable,
                "scripts/release_contracts.py",
                "--base",
                base,
                "--head",
                head,
                "--output",
                str(report),
            ],
            check=True,
        )
        result = json.loads(report.read_text(encoding="utf-8"))
    if (
        not result.get("complete")
        or result.get("base_sha") != base
        or result.get("head_sha") != head
    ):
        raise ValueError("Incomplete or mismatched compatibility evidence.")
    return result


def check_pr(event_path: Path, report_path: Path) -> None:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    repository = event["repository"]["full_name"]
    pr = api(f"repos/{repository}/pulls/{event['number']}")
    head, base = pr["head"]["sha"], pr["base"]["sha"]
    if (
        head != event["pull_request"]["head"]["sha"]
        or base != event["pull_request"]["base"]["sha"]
    ):
        raise ValueError(
            "PR changed while CI started; rerun against its current head and base."
        )
    if resolve("HEAD") != head:
        raise ValueError("Release checks must run on the exact PR head.")
    report = {
        "schema": 1,
        "repository": repository,
        "pr_number": pr["number"],
        "head_sha": head,
        "base_sha": base,
        "metadata_digest": metadata_digest(pr),
        "complete": False,
    }
    is_release = pr["head"]["ref"] == RELEASE_BRANCH
    if is_release:
        validate_release_pr(pr, repository)
        version = validate_release_files(base, head)
        baseline = resolve(f"v{project_version(base)}")
        history = release_range(repository, baseline, base)
        comparison = contracts(baseline, head)
        impact = max((history["impact"], comparison["minimum"]), key=IMPACTS.index)
        validate_version(project_version(base), version, impact)
        report.update(
            version=version,
            tag=f"v{version}",
            baseline_sha=baseline,
            history=history,
            contracts=comparison,
            impact=impact,
        )
    else:
        if project_version(base) != project_version(head):
            raise ValueError(
                "Package versions are changed only by the release automation PR."
            )
        commits = pages(f"repos/{repository}/pulls/{pr['number']}/commits")
        squash = (
            pr["title"] + "\n\n" + "\n\n".join(c["commit"]["message"] for c in commits)
        )
        # The title governs squash intent; body migration notes document !.
        parse_intent(intent_message(pr["title"], pr.get("body") or ""))
        minimum = analyze_changes(base, head)
        comparison = (
            contracts(base, head)
            if minimum["minimum"] != "none"
            else {"minimum": "none", "complete": True, "checks": []}
        )
        floor = max((minimum["minimum"], comparison["minimum"]), key=IMPACTS.index)
        intent = validate_intent(intent_message(squash, pr.get("body") or ""), floor)
        report.update(impact=intent["impact"], changes=minimum, contracts=comparison)
    report["complete"] = True
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary(
        f"### Release impact: {report['impact']}\n\nEvidence compares `{base}` to `{head}`.\n\n```json\n{json.dumps(report, indent=2)}\n```\n"
    )


def preflight(repository: str) -> None:
    pending = pages(
        f"repos/{repository}/issues?state=closed&labels=autorelease%3A%20pending"
    )
    for issue in pending:
        if "pull_request" in issue:
            pr = api(f"repos/{repository}/pulls/{issue['number']}")
            if pr["merged"]:
                summary(
                    f"Release PR #{pr['number']} is awaiting publication/finalization. No new proposal."
                )
                output(ready=False)
                return
    head = resolve("HEAD")
    if head != api(f"repos/{repository}/git/ref/heads/master")["object"]["sha"]:
        summary("A newer master commit will prepare the rolling release proposal.")
        output(ready=False)
        return
    history = release_range(repository, resolve(f"v{project_version(head)}"), head)
    summary(
        f"Release proposal impact: {history['impact']}\n\n```json\n{json.dumps(history, indent=2)}\n```\n"
    )
    output(ready=history["impact"] != "none")


def prepare_labels(repository: str) -> None:
    existing = {label["name"] for label in pages(f"repos/{repository}/labels")}
    for name, color, description in (
        ("autorelease: pending", "ededed", "Release PR awaiting publication"),
        ("autorelease: tagged", "0e8a16", "Release publication and artifacts verified"),
    ):
        if name not in existing:
            api(
                f"repos/{repository}/labels",
                method="POST",
                body={"name": name, "color": color, "description": description},
            )


def read_evidence(repository: str, pr: dict) -> dict:
    name = f"release-evidence-{pr['number']}-{pr['head']['sha']}"
    runs = pages(
        f"repos/{repository}/actions/workflows/ci.yml/runs?event=pull_request&head_sha={pr['head']['sha']}",
        "workflow_runs",
    )
    for run in runs:
        if (
            run["conclusion"] != "success"
            or run["head_sha"] != pr["head"]["sha"]
            or run["path"] != ".github/workflows/ci.yml"
        ):
            continue
        artifacts = pages(
            f"repos/{repository}/actions/runs/{run['id']}/artifacts", "artifacts"
        )
        for artifact in artifacts:
            if artifact["name"] != name or artifact["expired"]:
                continue
            data = subprocess.check_output(  # noqa: S603
                [  # noqa: S607
                    "gh",
                    "api",
                    f"repos/{repository}/actions/artifacts/{artifact['id']}/zip",
                ]
            )
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.getinfo("release-evidence.json")
                if info.file_size > MAX_EVIDENCE_BYTES:
                    raise ValueError("Release evidence exceeds the size limit.")
                return json.loads(archive.read(info))
    raise ValueError(
        "No successful exact-head CI run with retained release evidence; rerun release PR CI."
    )


def authorize(repository: str, sha: str) -> None:
    sha = resolve(sha)
    candidates = api(f"repos/{repository}/commits/{sha}/pulls")
    candidates = [
        p for p in candidates if p.get("merge_commit_sha") == sha and p.get("merged_at")
    ]
    if len(candidates) != 1:
        raise ValueError(
            "Expected one merged release PR for the version-change commit."
        )
    pr = api(f"repos/{repository}/pulls/{candidates[0]['number']}")
    validate_release_pr(pr, repository, merge_sha=sha)
    parents = git("rev-list", "--parents", "-n", "1", sha).split()
    if len(parents) != SQUASH_FIELDS:
        raise ValueError("Release requires a squash merge with one tested parent.")
    parent = parents[1]
    fetch_command = ["git", "fetch", "--no-tags", "origin", pr["head"]["sha"]]
    subprocess.run(fetch_command, check=True)  # noqa: S603
    if git("rev-parse", f"{sha}^{{tree}}") != git(
        "rev-parse", f"{pr['head']['sha']}^{{tree}}"
    ):
        raise ValueError("Merged release tree differs from the reviewed release head.")
    version = validate_release_files(parent, sha)
    evidence = read_evidence(repository, pr)
    validate_evidence(evidence, pr, repository, parent, version)
    baseline = resolve(f"v{project_version(parent)}")
    if evidence["baseline_sha"] != baseline:
        raise ValueError("Published baseline differs from the reviewed evidence.")
    history = release_range(repository, baseline, parent)
    if evidence["history"] != history:
        raise ValueError(
            "Release classification changed after CI; refreshed review is required."
        )
    comparison = contracts(baseline, sha)
    impact = max((history["impact"], comparison["minimum"]), key=IMPACTS.index)
    validate_version(project_version(parent), version, impact)
    output(pr_number=pr["number"])
    summary(
        f"Human merge of release PR #{pr['number']} authorizes `{version}` at `{sha}`."
    )


def verify_pypi(version: str, hashes: dict[str, str]) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid stable version.")
    url = f"https://pypi.org/pypi/openapi-to-mcp-cli/{version}/json"
    with urllib.request.urlopen(url, timeout=30) as response:
        published = json.load(response)
    actual = {item["filename"]: item["digests"]["sha256"] for item in published["urls"]}
    if actual != hashes:
        raise ValueError(
            "PyPI distributions do not match this run's original artifacts."
        )


def finalize(repository: str, number: int, sha: str, version: str, dist: Path) -> None:
    pr = api(f"repos/{repository}/pulls/{number}")
    validate_release_pr(pr, repository, merge_sha=sha)
    tag = f"v{version}"
    hashes = artifact_hashes(dist)
    verify_pypi(version, hashes)
    ref = api(f"repos/{repository}/git/ref/tags/{tag}")
    if ref["object"]["type"] != "commit" or ref["object"]["sha"] != sha:
        raise ValueError("Release tag must point directly to the authorized merge SHA.")
    release = api(f"repos/{repository}/releases/tags/{tag}")
    assets = {asset["name"]: asset.get("digest") for asset in release["assets"]}
    if (
        release["draft"]
        or release["prerelease"]
        or assets != {name: f"sha256:{digest}" for name, digest in hashes.items()}
    ):
        raise ValueError("GitHub release assets do not match the published artifacts.")
    # Adding tagged before removing pending makes interrupted retries safe.
    api(
        f"repos/{repository}/issues/{number}/labels",
        method="POST",
        body={"labels": ["autorelease: tagged"]},
    )
    if any(label["name"] == "autorelease: pending" for label in pr["labels"]):
        api(
            f"repos/{repository}/issues/{number}/labels/autorelease%3A%20pending",
            method="DELETE",
        )
    summary(
        f"Finalized `{tag}` from PR #{number}; publication hashes and tag verified."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-pr")
    check.add_argument("--event", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    proposal = commands.add_parser("preflight")
    proposal.add_argument("--repository", required=True)
    labels = commands.add_parser("prepare-labels")
    labels.add_argument("--repository", required=True)
    publish = commands.add_parser("authorize")
    publish.add_argument("--repository", required=True)
    publish.add_argument("--sha", required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--repository", required=True)
    finish.add_argument("--pr", type=int, required=True)
    finish.add_argument("--sha", required=True)
    finish.add_argument("--version", required=True)
    finish.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "check-pr":
        check_pr(args.event, args.output)
    elif args.command == "preflight":
        preflight(args.repository)
    elif args.command == "prepare-labels":
        prepare_labels(args.repository)
    elif args.command == "authorize":
        authorize(args.repository, args.sha)
    else:
        finalize(args.repository, args.pr, args.sha, args.version, args.dist)


if __name__ == "__main__":
    main()
