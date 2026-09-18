# assay-kit

**The ASSAY method, open source.** Pre-registration, freeze-by-hash, corpus pinning, positive controls, numbered amendments, a report that refuses to ship with a section missing — as a Python 3, standard-library-only CLI. It is the shape of [`jourdanlabs/assay-001`](https://github.com/jourdanlabs/assay-001) with the Jev-specific parts removed.

Every output this kit can produce is stamped **`SELF-ASSAYED`**.

## 1 — What we are NOT giving away (the reason this is safe)

The service sells things a repo cannot contain:
1. **Independence.** You cannot pay yourself to verify yourself. Definitional, not incentive.
2. Pre-registration executed by a party with no stake, and the discipline to publish when the claim holds.
3. The blind re-score on a different base model.
4. A signed public report with JourdanLabs' name on it.
5. The amendment ledger and the judgment inside it.

> **Free:** run the method on yourself and publish a SELF-ASSAYED result. **Paid:** we run it on you, blind, on a different model, and sign it — ASSAY-VERIFIED. The $990 / 48-hour engagement is the trial; the kit is the mirror.

**SELF-ASSAYED is not ASSAY-VERIFIED.** The kit cannot emit the latter; only an independent party running this method on you can. The paid service is at [assay.jourdanlabs.com](https://assay.jourdanlabs.com); the results live at [donttrustme.ai/claims](https://donttrustme.ai/claims.html).

## Quick start

```bash
git clone https://github.com/jourdanlabs/assay-kit && cd assay-kit
export PYTHONPATH=$PWD            # or: ./bin/assay
python3 -m assay_kit init my-claim && cd my-claim
#   edit PROTOCOL.md — claim verbatim + source URL, corpora, metrics, pass criteria, budget
python3 -m assay_kit pin ./corpus --label banking77 --revision 57ec275d   # hashes every file → CORPUS.sha256 + PINS.txt
python3 -m assay_kit freeze       # FREEZE.sha256 over PROTOCOL.md + CORPUS.sha256 + PINS.txt — before any query
python3 -m assay_kit controls     # writes controls.py: random · always-confident · oracle · broken-schema
#   write your own run.py / score.py for your claim, as we did for Jev; log every request and response
python3 controls.py --all raw/run/*/responses.jsonl    # must go RED, RED, RED, GREEN before you score
python3 -m assay_kit amend "What changed and why"       # numbered, hashed, chained; flags before/after first query
python3 -m assay_kit seal raw/run/banking77/responses.jsonl
python3 -m assay_kit report && python3 -m assay_kit report --check
python3 -m assay_kit stamp        # SELF-ASSAYED · <freeze sha256> · <date>
```

## What the kit refuses to do (these are features)

- `freeze` after `raw/` is non-empty — *cannot freeze after querying*
- `score` before the controls have gone red and green
- `report --check` with any required section missing (verdict sentence · table · method · amendments · the limit · cost)
- any command after the frozen `PROTOCOL.md` changes — *add an amendment*
- any stamp other than `SELF-ASSAYED`; `stamp` takes no arguments

## What is not in the kit

No model client. No scorer for any specific claim. No corpus. You write `run.py` and `score.py` for your claim; the kit gives you the discipline, not the judgment.

`freeze --verify --canon v0` reproduces the historical `FREEZE.sha256` of `assay-001` on its own tree; `v1` is the kit's canonicalization, documented in one paragraph in [`FREEZE-CANON.md`](FREEZE-CANON.md).

## Tests

```bash
ASSAY_KIT_FIXTURE=/path/to/assay-001 python3 -m unittest discover -s tests   # 16 gate checks; 4 skip without the fixture
```

## License

Apache-2.0. See `LICENSE` and `NOTICE`. Built by JourdanLabs.
