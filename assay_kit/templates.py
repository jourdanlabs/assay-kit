"""Text emitted by the CLI."""

PROTOCOL = """# {name} — pre-registered protocol

## Claim under test

### Claim verbatim

> Replace this line with the exact claim.

### Source URL

Replace this line with the public source URL.

## Corpora

List each corpus, owner, split, license, and immutable revision.

## Metrics

Define every metric before any query.

## Pass criteria

State each numerical or binary threshold before any query.

## Budget

State the query, token, money, and retry limits.

## What this result does and doesn't apply to

State the exact artifacts, versions, tasks, corpora, and dates in scope, followed by what is outside scope.
"""

REPORT = """# Report

## Verdict sentence

Write one complete verdict sentence that travels whole.

## Results table

| Claim | Result | Criterion | Verdict |
|---|---:|---:|---|
| Replace | Replace | Replace | Replace |

## Method

Name the frozen protocol, corpus pins, run shape, and scoring procedure.

## Amendments

List every numbered amendment, including whether it preceded the first query.

## THE LIMIT

A result applies to the artifacts and criteria examined. It is not a statement about any other task, corpus, version, or day.

## Cost

State the measured cost and the accounting boundary.
"""

CONTROLS = r'''#!/usr/bin/env python3
"""Generic red/green controls for ASSAY-shaped classification records."""
import argparse
import json
import sys
from pathlib import Path

ALIASES = {
    "uniform-random": "random",
    "random": "random",
    "always-confident": "always-confident",
    "overconfident": "always-confident",
    "broken-schema": "broken-schema",
    "oracle": "oracle",
    "perfect-oracle": "oracle",
}

def load(path):
    rows = []
    files = sorted(path.rglob("responses.jsonl")) if path.is_dir() else [path]
    for file in files:
        with file.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"{file}:{number}: invalid JSON") from exc
    if not rows:
        raise ValueError(f"{path}: no records")
    return rows

def green(mode, rows):
    labels = {row.get("label") for row in rows}
    if None in labels or len(labels) < 2:
        raise ValueError("controls require at least two string labels")
    return mode == "oracle"

def discover(root):
    found = {}
    for path in sorted((root / "controls").glob("*/*.jsonl")):
        mode = ALIASES.get(path.stem)
        if mode and mode not in found:
            found[mode] = path
    return found

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--fixture", type=Path, default=Path("."))
    parser.add_argument("--mode", choices=sorted(ALIASES))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    if args.files:
        rows = []
        for path in args.files:
            rows.extend(load(path))
        if args.all:
            states = {mode: green(mode, rows) for mode in {"random", "always-confident", "broken-schema", "oracle"}}
        elif not args.mode:
            print("--mode or --all is required", file=sys.stderr)
            return 2
        else:
            mode = ALIASES[args.mode]
            passed = green(mode, rows)
            print(f"{mode}: {'GREEN' if passed else 'RED'}")
            return 0 if passed else 1
    else:
        found = discover(args.fixture)
        required = {"random", "always-confident", "broken-schema", "oracle"}
        if set(found) != required:
            print("controls incomplete", file=sys.stderr)
            return 2
        states = {mode: green(mode, load(found[mode])) for mode in required}
    for mode in ("random", "always-confident", "broken-schema", "oracle"):
        print(f"{mode}: {'GREEN' if states[mode] else 'RED'}")
    passed = not states["random"] and not states["always-confident"] and not states["broken-schema"] and states["oracle"]
    if passed:
        marker = Path(__file__).resolve().parent / ".assay" / "controls-passed"
        marker.parent.mkdir(exist_ok=True)
        marker.write_text("random=RED\nalways-confident=RED\nbroken-schema=RED\noracle=GREEN\n", encoding="utf-8")
        return 0
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
'''

