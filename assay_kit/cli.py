"""ASSAY method CLI, implemented with the Python standard library."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from .templates import CONTROLS, PROTOCOL, REPORT

FREEZE_INPUTS = ("PROTOCOL.md", "CORPUS.sha256", "PINS.txt")


class Refusal(Exception):
    pass


class OneLineParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise Refusal(message)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def state_path(root: Path) -> Path:
    return root / ".assay" / "state.json"


def load_state(root: Path) -> dict:
    path = state_path(root)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Refusal("invalid assay state") from exc


def save_state(root: Path, state: dict) -> None:
    write(state_path(root), json.dumps(state, indent=2, sort_keys=True) + "\n")


def raw_nonempty(root: Path) -> bool:
    raw = root / "raw"
    return raw.is_dir() and any(path.is_file() for path in raw.rglob("*"))


def guard(root: Path) -> None:
    expected = load_state(root).get("protocol_sha256")
    protocol = root / "PROTOCOL.md"
    if expected and (not protocol.is_file() or digest_file(protocol) != expected):
        raise Refusal("protocol changed after freeze; add an amendment")


def canonical_v1(root: Path) -> tuple[str, bytes]:
    canonical = bytearray(b"assay-freeze-v1\0")
    for name in FREEZE_INPUTS:
        path = root / name
        if not path.is_file():
            raise Refusal(f"missing required freeze input: {name}")
        data = path.read_bytes()
        canonical.extend(name.encode())
        canonical.extend(b"\0")
        canonical.extend(len(data).to_bytes(8, "big"))
        canonical.extend(data)
    digest = digest_bytes(bytes(canonical))
    return digest, f"{digest}  PROTOCOL.md+CORPUS.sha256+PINS.txt\n".encode()


def legacy_v0(root: Path) -> bytes:
    protocol = root / "PROTOCOL.md"
    amendment = root / "AMENDMENT-1.md"
    if not protocol.is_file() or not amendment.is_file():
        raise Refusal("v0 requires PROTOCOL.md and AMENDMENT-1.md")
    heading = amendment.read_text(encoding="utf-8").splitlines()[0]
    match = re.search(r"\((\d{4}-\d{2}-\d{2})", heading)
    if not match:
        raise Refusal("v0 amendment date is missing")
    return (
        f"{digest_file(protocol)}  ASSAY-001-JEV-CALIBRATION-PROTOCOL-2026-09-17.md\n"
        f"{digest_file(amendment)}  ASSAY-001-AMENDMENT-1-{match.group(1)}.md\n"
    ).encode()


def cmd_init(args: argparse.Namespace, _: Path) -> None:
    target = Path(args.name).expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        raise Refusal("target directory is not empty")
    target.mkdir(parents=True, exist_ok=True)
    for directory in ("AMENDMENTS", "raw", "scores", ".assay"):
        (target / directory).mkdir(exist_ok=True)
    write(target / "PROTOCOL.md", PROTOCOL.format(name=args.name))
    print(f"initialized {target}")


def pin_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise Refusal(f"pin source not found: {source}")

    def order(path: Path) -> tuple[int, str]:
        if path.name == "README.md" or "categories" in path.name:
            rank = 0
        elif path.name.startswith("test."):
            rank = 1
        else:
            rank = 2
        return rank, path.relative_to(source).as_posix()

    return sorted((path for path in source.rglob("*") if path.is_file()), key=order)


def read_hash_manifest(path: Path) -> dict[str, str]:
    entries = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
            if match:
                entries[match.group(2)] = match.group(1)
    return entries


def pinned_name(root: Path, source: Path, path: Path, label: str | None) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        if source.is_dir():
            return (Path("corpus") / (label or source.name) / path.relative_to(source)).as_posix()
        return (Path("corpus") / (label or path.name)).as_posix()


def cmd_pin(args: argparse.Namespace, root: Path) -> None:
    parsed = urllib.parse.urlparse(args.source)
    if parsed.scheme in ("http", "https"):
        name = args.label or Path(parsed.path).name
        if not name:
            raise Refusal("URL pin requires --label")
        source = root / "corpus" / name
        source.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(args.source, timeout=30) as response:
                source.write_bytes(response.read())
        except Exception as exc:
            raise Refusal(f"could not fetch pin URL: {exc}") from exc
    else:
        source = Path(args.source).expanduser()
        source = (root / source).resolve() if not source.is_absolute() else source.resolve()

    files = pin_files(source)
    entries = read_hash_manifest(root / "CORPUS.sha256")
    for path in files:
        entries[pinned_name(root, source, path, args.label)] = digest_file(path)
    write(root / "CORPUS.sha256", "".join(f"{value}  {name}\n" for name, value in entries.items()))

    pins_path = root / "PINS.txt"
    pins = []
    if pins_path.is_file():
        pins = [line for line in pins_path.read_text(encoding="utf-8").splitlines() if line and line != "pins:"]
    pin_line = args.pin_line or args.source + (f" @ {args.revision}" if args.revision else "")
    if pin_line not in pins:
        pins.append(pin_line)
    write(pins_path, "pins:\n" + "\n".join(pins) + "\n")
    print(f"pinned {len(files)} file(s)")


def cmd_freeze(args: argparse.Namespace, root: Path) -> None:
    if args.verify:
        if args.canon == "v0":
            expected = legacy_v0(root)
            actual = root / "FREEZE.sha256"
            if not actual.is_file() or actual.read_bytes() != expected:
                raise Refusal("v0 freeze verification failed")
            print(f"verified {digest_file(root / 'PROTOCOL.md')}")
            return
        guard(root)
        digest, manifest = canonical_v1(root)
        actual = root / "FREEZE.sha256"
        if not actual.is_file() or actual.read_bytes() != manifest:
            raise Refusal("freeze verification failed")
        print(f"verified {digest}")
        return

    if raw_nonempty(root):
        raise Refusal("cannot freeze after querying")
    if (root / "FREEZE.sha256").exists():
        guard(root)
        raise Refusal("protocol is already frozen")
    digest, manifest = canonical_v1(root)
    (root / "FREEZE.sha256").write_bytes(manifest)
    state = load_state(root)
    state.update(canon="v1", freeze_sha256=digest, protocol_sha256=digest_file(root / "PROTOCOL.md"))
    save_state(root, state)
    print(digest)


def cmd_controls(_: argparse.Namespace, root: Path) -> None:
    path = root / "controls.py"
    if path.exists():
        raise Refusal("controls.py already exists")
    write(path, CONTROLS)
    path.chmod(0o755)
    print("wrote controls.py")


def amendment_files(root: Path) -> list[Path]:
    return sorted(
        (root / "AMENDMENTS").glob("AMENDMENT-*.md"),
        key=lambda path: int(re.search(r"(\d+)", path.stem).group(1)),
    )


def cmd_amend(args: argparse.Namespace, root: Path) -> None:
    freeze = load_state(root).get("freeze_sha256")
    if not freeze:
        raise Refusal("cannot amend before freeze")
    existing = amendment_files(root)
    number = len(existing) + 1
    previous = digest_file(existing[-1]) if existing else "none"
    timestamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    content = f"""# Amendment {number} — {args.title}

timestamp: {timestamp}
before_first_query: {'false' if raw_nonempty(root) else 'true'}
freeze_sha256: {freeze}
previous_amendment_sha256: {previous}

## Change

Describe the change without editing the frozen protocol.

## Reason

State why this amendment is necessary.
"""
    path = root / "AMENDMENTS" / f"AMENDMENT-{number}.md"
    write(path, content)
    digest = digest_file(path)
    write(path.with_suffix(".sha256"), f"{digest}  {path.name}\n")
    print(f"{path.relative_to(root)} {digest}")


def cmd_seal(args: argparse.Namespace, root: Path) -> None:
    path = Path(args.file).expanduser()
    path = root / path if not path.is_absolute() else path
    if not path.is_file():
        raise Refusal(f"file not found: {args.file}")
    digest = digest_file(path)
    write(path.with_suffix(".sha256"), f"{digest}  {path.name}\n")
    print(digest)


REPORT_CHECKS = (
    ("verdict sentence", re.compile(r"(?im)^(?:#{1,6}\s+Verdicts?\b|\*\*Verdict:\*\*)")),
    ("table", re.compile(r"(?m)^\|(?:\s*:?-+:?\s*\|)+\s*$")),
    ("method", re.compile(r"(?im)^(?:#{1,6}\s+Method\b|\*\*Run:\*\*[\s\S]{0,1200}protocol)")),
    ("amendments", re.compile(r"(?im)^#{1,6}\s+Amendment(?:s|\s+\d+)\b")),
    ("THE LIMIT", re.compile(r"(?im)^#{1,6}\s+THE LIMIT\b")),
    ("cost", re.compile(r"(?im)^(?:#{1,6}\s+Cost\b|\*\*Cost:\*\*)")),
)


def check_report(path: Path) -> None:
    if not path.is_file():
        raise Refusal("missing required section: report")
    text = path.read_text(encoding="utf-8")
    for name, pattern in REPORT_CHECKS:
        if not pattern.search(text):
            raise Refusal(f"missing required section: {name}")


def cmd_report(args: argparse.Namespace, root: Path) -> None:
    path = root / "REPORT.md"
    if args.check:
        check_report(path)
        print("report complete")
    elif path.exists():
        raise Refusal("REPORT.md already exists")
    else:
        write(path, REPORT)
        print("wrote REPORT.md")


def cmd_score(args: argparse.Namespace, root: Path) -> None:
    if not (root / ".assay" / "controls-passed").is_file():
        raise Refusal("cannot score before controls have gone red and green")
    scorer = root / "score.py"
    if not scorer.is_file():
        scorer = root / "harness" / "score.py"
    if not scorer.is_file():
        raise Refusal("no user score.py found")
    completed = subprocess.run([sys.executable, str(scorer), *args.score_args], cwd=root)
    if completed.returncode:
        raise Refusal(f"user scorer exited {completed.returncode}")


def cmd_stamp(args: argparse.Namespace, root: Path) -> None:
    if args.stamp_args:
        raise Refusal("stamp is fixed and accepts no arguments")
    freeze = load_state(root).get("freeze_sha256")
    if not freeze:
        raise Refusal("cannot stamp before freeze")
    print(f"SELF-ASSAYED · {freeze} · {dt.date.today().isoformat()}")


def make_parser() -> argparse.ArgumentParser:
    parser = OneLineParser(prog="assay")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=OneLineParser)

    command = commands.add_parser("init")
    command.add_argument("name")
    command.set_defaults(handler=cmd_init)

    command = commands.add_parser("pin")
    command.add_argument("source")
    command.add_argument("--revision")
    command.add_argument("--label")
    command.add_argument("--pin-line")
    command.set_defaults(handler=cmd_pin)

    command = commands.add_parser("freeze")
    command.add_argument("--verify", action="store_true")
    command.add_argument("--canon", choices=("v0", "v1"), default="v1")
    command.set_defaults(handler=cmd_freeze)

    command = commands.add_parser("controls")
    command.set_defaults(handler=cmd_controls)

    command = commands.add_parser("amend")
    command.add_argument("title")
    command.set_defaults(handler=cmd_amend)

    command = commands.add_parser("seal")
    command.add_argument("file")
    command.set_defaults(handler=cmd_seal)

    command = commands.add_parser("report")
    command.add_argument("--check", action="store_true")
    command.set_defaults(handler=cmd_report)

    command = commands.add_parser("score")
    command.add_argument("score_args", nargs=argparse.REMAINDER)
    command.set_defaults(handler=cmd_score)

    command = commands.add_parser("stamp", add_help=False)
    command.add_argument("stamp_args", nargs=argparse.REMAINDER)
    command.set_defaults(handler=cmd_stamp)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        effective_argv = list(sys.argv[1:] if argv is None else argv)
        if effective_argv[:1] == ["stamp"] and len(effective_argv) != 1:
            raise Refusal("stamp is fixed and accepts no arguments")
        args = make_parser().parse_args(effective_argv)
        root = Path.cwd()
        compat = (
            args.command == "freeze"
            and args.verify
            and args.canon == "v0"
            and not state_path(root).exists()
        )
        if not compat:
            guard(root)
        args.handler(args, root)
        return 0
    except Refusal as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130

