"""Cold-gate coverage for GATE-WS0 A1 through B12 and hygiene checks."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = KIT.parent / "assay-001-ground-truth"
FIXTURE = Path(os.environ.get("ASSAY_KIT_FIXTURE", DEFAULT_FIXTURE)).resolve()
HAS_FIXTURE = FIXTURE.is_dir()
RESERVED_MARK = "ASSAY-" + "VERIFIED"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GateCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(KIT)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assay(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "assay_kit", *args],
            cwd=cwd or self.root,
            env=self.env,
            text=True,
            capture_output=True,
        )

    def init_project(self) -> Path:
        result = self.assay("init", "replay")
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.root / "replay"

    def freeze_project(self) -> Path:
        project = self.init_project()
        (project / "CORPUS.sha256").write_text("", encoding="utf-8")
        (project / "PINS.txt").write_text("pins:\n", encoding="utf-8")
        result = self.assay("freeze", cwd=project)
        self.assertEqual(result.returncode, 0, result.stderr)
        return project

    def assert_one_line_refusal(self, result: subprocess.CompletedProcess[str], reason: str) -> None:
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.strip(), reason)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)


class StructureGate(GateCase):
    def test_A1_init_structure_and_protocol_sections(self) -> None:
        project = self.init_project()
        self.assertTrue((project / "PROTOCOL.md").is_file())
        for directory in ("AMENDMENTS", "raw", "scores"):
            self.assertTrue((project / directory).is_dir())
        protocol = (project / "PROTOCOL.md").read_text(encoding="utf-8").lower()
        for section in (
            "claim verbatim",
            "source url",
            "corpora",
            "metrics",
            "pass criteria",
            "budget",
            "what this result does and doesn't apply to",
        ):
            self.assertIn(section, protocol)

    @unittest.skipUnless(HAS_FIXTURE, "ASSAY_KIT_FIXTURE is absent")
    def test_A2_pin_reproduces_corpus_hashes_and_pins(self) -> None:
        project = self.init_project()
        shutil.copytree(FIXTURE / "corpus", project / "corpus")
        pin_lines = (FIXTURE / "PINS.txt").read_text(encoding="utf-8").splitlines()[1:]
        for label, line in zip(("banking77", "clinc150"), pin_lines):
            result = self.assay(
                "pin",
                f"corpus/{label}",
                "--label",
                label,
                "--pin-line",
                line,
                cwd=project,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((project / "CORPUS.sha256").read_bytes(), (FIXTURE / "CORPUS.sha256").read_bytes())
        self.assertEqual((project / "PINS.txt").read_bytes(), (FIXTURE / "PINS.txt").read_bytes())

    @unittest.skipUnless(HAS_FIXTURE, "ASSAY_KIT_FIXTURE is absent")
    def test_A3_v0_reproduces_and_verifies_historical_freeze(self) -> None:
        result = self.assay("freeze", "--verify", "--canon", "v0", cwd=FIXTURE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), f"verified {sha(FIXTURE / 'PROTOCOL.md')}")

    @unittest.skipUnless(HAS_FIXTURE, "ASSAY_KIT_FIXTURE is absent")
    def test_A4_controls_are_three_red_one_green_by_exit_code(self) -> None:
        project = self.freeze_project()
        result = self.assay("controls", cwd=project)
        self.assertEqual(result.returncode, 0, result.stderr)
        script = project / "controls.py"
        modes = {
            "uniform-random": 1,
            "always-confident": 1,
            "broken-schema": 1,
            "oracle": 0,
        }
        for mode, expected in modes.items():
            run = subprocess.run(
                [sys.executable, str(script), str(FIXTURE / "raw" / "run"), "--mode", mode],
                cwd=project,
                text=True,
                capture_output=True,
            )
            self.assertEqual(run.returncode, expected, f"{mode}: {run.stdout} {run.stderr}")
        all_controls = subprocess.run(
            [sys.executable, str(script), str(FIXTURE / "raw" / "run"), "--all"],
            cwd=project,
            text=True,
            capture_output=True,
        )
        self.assertEqual(all_controls.returncode, 0, all_controls.stderr)
        self.assertTrue((project / ".assay" / "controls-passed").is_file())

    def test_A5_amendments_are_numbered_timed_hashed_and_chained(self) -> None:
        project = self.freeze_project()
        first = self.assay("amend", "Which field is calibrated", cwd=project)
        self.assertEqual(first.returncode, 0, first.stderr)
        first_path = project / "AMENDMENTS" / "AMENDMENT-1.md"
        text = first_path.read_text(encoding="utf-8")
        state = json.loads((project / ".assay" / "state.json").read_text(encoding="utf-8"))
        self.assertIn("before_first_query: true", text)
        self.assertIn(f"freeze_sha256: {state['freeze_sha256']}", text)
        self.assertIn("previous_amendment_sha256: none", text)
        self.assertRegex(text, r"timestamp: \d{4}-\d{2}-\d{2}T")
        self.assertTrue(first_path.with_suffix(".sha256").is_file())
        (project / "raw" / "one.jsonl").write_text("{}\n", encoding="utf-8")
        second = self.assay("amend", "Rounding tolerance", cwd=project)
        self.assertEqual(second.returncode, 0, second.stderr)
        second_text = (project / "AMENDMENTS" / "AMENDMENT-2.md").read_text(encoding="utf-8")
        self.assertIn("before_first_query: false", second_text)
        self.assertIn(f"previous_amendment_sha256: {sha(first_path)}", second_text)

    @unittest.skipUnless(HAS_FIXTURE, "ASSAY_KIT_FIXTURE is absent")
    def test_A6_report_skeleton_and_published_report_check(self) -> None:
        project = self.freeze_project()
        result = self.assay("report", cwd=project)
        self.assertEqual(result.returncode, 0, result.stderr)
        check = self.assay("report", "--check", cwd=project)
        self.assertEqual(check.returncode, 0, check.stderr)
        shutil.copyfile(FIXTURE / "REPORT.md", project / "REPORT.md")
        published = self.assay("report", "--check", cwd=project)
        self.assertEqual(published.returncode, 0, published.stderr)

    def test_A7_stamp_is_exact(self) -> None:
        project = self.freeze_project()
        state = json.loads((project / ".assay" / "state.json").read_text(encoding="utf-8"))
        result = self.assay("stamp", cwd=project)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = f"SELF-ASSAYED · {state['freeze_sha256']} · {dt.date.today().isoformat()}\n"
        self.assertEqual(result.stdout, expected)


class RefusalGate(GateCase):
    def test_B8_freeze_after_query_refuses(self) -> None:
        project = self.init_project()
        (project / "raw" / "response.jsonl").write_text("{}\n", encoding="utf-8")
        result = self.assay("freeze", cwd=project)
        self.assert_one_line_refusal(result, "cannot freeze after querying")

    def test_B9_score_before_controls_refuses(self) -> None:
        project = self.freeze_project()
        result = self.assay("score", cwd=project)
        self.assert_one_line_refusal(result, "cannot score before controls have gone red and green")

    def test_B10_report_check_names_missing_section(self) -> None:
        project = self.freeze_project()
        created = self.assay("report", cwd=project)
        self.assertEqual(created.returncode, 0, created.stderr)
        report = (project / "REPORT.md").read_text(encoding="utf-8")
        cases = {
            "verdict sentence": ("## Verdict sentence", "## Finding"),
            "table": ("|---|---:|---:|---|", "not a table separator"),
            "method": ("## Method", "## Procedure"),
            "amendments": ("## Amendments", "## Changes"),
            "THE LIMIT": ("## THE LIMIT", "## Scope"),
            "cost": ("## Cost", "## Expense"),
        }
        for name, (old, new) in cases.items():
            with self.subTest(section=name):
                (project / "REPORT.md").write_text(report.replace(old, new), encoding="utf-8")
                result = self.assay("report", "--check", cwd=project)
                self.assert_one_line_refusal(result, f"missing required section: {name}")

    def test_B11_every_command_refuses_after_protocol_drift(self) -> None:
        project = self.freeze_project()
        with (project / "PROTOCOL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nchanged\n")
        for command in (
            ("init", "nested"),
            ("pin", "PROTOCOL.md"),
            ("freeze",),
            ("freeze", "--verify"),
            ("freeze", "--verify", "--canon", "v0"),
            ("controls",),
            ("amend", "change"),
            ("seal", "PROTOCOL.md"),
            ("report",),
            ("report", "--check"),
            ("score",),
            ("stamp",),
        ):
            result = self.assay(*command, cwd=project)
            self.assert_one_line_refusal(result, "protocol changed after freeze; add an amendment")

    def test_B12_reserved_mark_absent_and_stamp_arguments_refuse(self) -> None:
        # Gate amendment 2026-09-18 (Pan): scope is the kit's SOURCE and its EMITTED OUTPUT.
        # README/NOTICE may name the reserved mark once, to say the kit cannot produce it.
        for path in list((KIT / "assay_kit").rglob("*")) + list((KIT / "bin").rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                self.assertNotIn(RESERVED_MARK.encode(), path.read_bytes(), str(path))
        project = self.freeze_project()
        result = self.assay("stamp", "--anything", cwd=project)
        self.assert_one_line_refusal(result, "stamp is fixed and accepts no arguments")


class HygieneGate(GateCase):
    def test_C13_import_and_shim_use_standard_library_only(self) -> None:
        imported = subprocess.run(
            [sys.executable, "-I", "-c", f"import sys;sys.path.insert(0,{str(KIT)!r});import assay_kit"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertTrue((KIT / "bin" / "assay").is_file())

    def test_C14_gate_tests_are_present(self) -> None:
        names = {name for name in dir(StructureGate) + dir(RefusalGate) if name.startswith("test_")}
        for item in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "B8", "B9", "B10", "B11", "B12"):
            self.assertTrue(any(item in name for name in names), item)

    def test_C15_license_notice_and_readme_boundary(self) -> None:
        self.assertIn("Apache License", (KIT / "LICENSE").read_text(encoding="utf-8"))
        self.assertIn("JourdanLabs", (KIT / "NOTICE").read_text(encoding="utf-8"))
        readme = (KIT / "README.md").read_text(encoding="utf-8")
        self.assertIn("What we are NOT giving away", readme)
        self.assertIn("SELF-ASSAYED is not " + RESERVED_MARK, readme)

    def test_C16_no_model_client_specific_scorer_or_corpus(self) -> None:
        self.assertFalse((KIT / "corpus").exists())
        self.assertFalse((KIT / "assay-001-ground-truth").exists())
        sources = "\n".join(path.read_text(encoding="utf-8") for path in (KIT / "assay_kit").glob("*.py"))
        self.assertNotIn("typesafe.ai", sources.lower())
        self.assertNotIn("numpy", sources.lower())
        self.assertNotIn("pandas", sources.lower())


if __name__ == "__main__":
    unittest.main()

