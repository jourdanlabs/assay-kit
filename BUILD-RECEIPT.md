# BUILD RECEIPT

Date: 2026-09-18

## Result

The package, CLI shim, tests, license, notice, README, and freeze-canonicalization document are present. The final fixture-backed suite passes 16 tests. One acceptance requirement is not satisfied: README A15 conflicts directly with B12 and the build prompt's reserved-mark prohibition. The prohibited paid stamp token is therefore absent from this tree; README keeps PBB §1 verbatim but replaces the paid-line token and the required final sentence with plain independent-verification wording. This is not a claim that all 16 written checks are simultaneously satisfiable.

## Commands and observed outputs

Ground-truth byte hashes:

```text
$ shasum -a 256 assay-001-ground-truth/PROTOCOL.md assay-001-ground-truth/AMENDMENT-1.md assay-001-ground-truth/FREEZE.sha256 assay-001-ground-truth/CORPUS.sha256 assay-001-ground-truth/PINS.txt
f8ce3f5b72abd4f48b8da0efdd1769d12f5e111d6e905b298cf0251bc4a09b48  assay-001-ground-truth/PROTOCOL.md
8b68335ae02718b65dd58c678368002fdde1103c69992a1bac04178037e89f79  assay-001-ground-truth/AMENDMENT-1.md
b500f7d1210d3e68abbfe4ba847318db80f308edb67af38edffc9616d4dbf027  assay-001-ground-truth/FREEZE.sha256
25d113581f3191354ab3543d3450df18c97132189d5ab6c5a0f803b82d02dfd8  assay-001-ground-truth/CORPUS.sha256
962f61aca557ee9e8cfb6212cf92bb481905423c487bccef36ac776a832311c5  assay-001-ground-truth/PINS.txt
```

Historical freeze compatibility:

```text
$ PYTHONPATH=../assay-kit python3 -m assay_kit freeze --verify --canon v0
verified f8ce3f5b72abd4f48b8da0efdd1769d12f5e111d6e905b298cf0251bc4a09b48
```

The same command was first invoked from `assay-kit/`, which is not an ASSAY-001 tree, and correctly failed:

```text
v0 requires PROTOCOL.md and AMENDMENT-1.md
```

Final requested test command:

```text
$ python3 -m unittest discover -s assay-kit/tests -v
Ran 16 tests in 4.218s
OK
```

The earlier test runs were not clean: the first complete run had three failures (the README still contained the prohibited token, the hygiene test wrongly rejected the required legacy Jev filename, and B12 found the README token); the next run had one failure because `stamp --anything` returned argparse's generic one-line reason instead of the required fixed-stamp reason. Those defects were corrected before the final run.

Missing-fixture behavior:

```text
$ ASSAY_KIT_FIXTURE=/tmp/assay-kit-fixture-does-not-exist python3 -m unittest discover -s assay-kit/tests -v
Ran 16 tests in 2.376s
OK (skipped=4)
```

Compilation and shim smoke test:

```text
$ python3 -m py_compile assay_kit/*.py tests/*.py
$ ./bin/assay --help
py_compile=OK
bin_help=OK
```

Reserved-mark scan (the variable is split here so the forbidden token is not introduced into this receipt):

```text
$ RESERVED_MARK='ASSAY-''VERIFIED'; if rg -n "$RESERVED_MARK" .; then exit 1; else printf 'reserved_mark_hits=0\n'; fi
reserved_mark_hits=0
```

## Deliverable hashes

```text
0fff4137a5fb5a03be1f273574b88f03621d3e96ebd05d755292e6533db73a8a  assay_kit/__init__.py
3d2438ae92f4746e9ffaa1f837b1fe803f6281091d1f31f8c95643716f257d9a  assay_kit/__main__.py
08a382d5d516c9c575ebfa099ed141d96f7820328dde78e785e99981fa60036b  assay_kit/cli.py
d33f51fdcbe4717f38d406ade7dd9d74053e2c64c6d9ad15dcf1ffd7c0876f14  assay_kit/templates.py
2941136d9c5be27070d6e8052823e245db37f5e9deb200b30e4803b6460524a9  tests/test_gate_ws0.py
ee232a5de90dd7a1b730064ad8cb484ff609d4d9f4f6c5d791664b973cc6eca1  README.md
0f79f7b7604be46abf8e12b039f8dfe67836406a75eed552505c5955c9f4810d  FREEZE-CANON.md
877b602fb1ee93049c83d280a2044e20a710cc1f8cd940b1c94f9b28de5b547a  LICENSE
df70ddf65fdba295492094f10f74bfba682227f1f76a39d031371d04a7959826  NOTICE
653418c56b6f5b9f848aa7d47f1d9e1f51a09f002e0ee8ac1b625f36bc7f0a4e  bin/assay
```

`BUILD-RECEIPT.md` is excluded from the inventory above because embedding its own digest would change that digest.

## Limits and unsatisfied items

- A15's demanded paid line and final sentence cannot coexist with B12's recursive zero-hit command and the build prompt's stronger source/output prohibition. The no-token boundary was selected; A15 is not verbatim.
- Compatibility mode v0 intentionally implements only the historical ASSAY-001 two-file manifest shape. It is not presented as a general legacy format.
- The controls scaffold is limited to the classification response structure published by ASSAY-001. It does not claim to generalize to extraction, generation, or other scoring tasks.
- No model client, claim-specific scorer, corpus, or ground-truth copy is included.
- The workspace is not a Git repository, so no commit was created.

