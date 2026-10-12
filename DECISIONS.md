# DECISIONS.md — log of choices made inside SCOPE.md

## M1 — Package name
- Date: 2026-10-12
- Decision: Use the PyPI distribution name `imagedatacheck` and the importable package name `imagedatacheck` (CLI command `<pkg>` = `imagedatacheck`).
- Verification: queried `https://pypi.org/pypi/imagedatacheck/json` → HTTP 404, `{"message": "Not Found"}` (free). `datacheck` (the placeholder) is taken by an existing 2018-era data-validation library (HTTP 200).
- Alternatives considered:
  - `datacheck` — taken.
  - `imgscan` — free but ambiguous (could mean "scan an image" not "scan an image dataset").
  - `picheck` — free but obscure.
  - `dataset-audit` — free, descriptive, but ambiguous (could be for tabular datasets too).
- Rationale: `imagedatacheck` is the closest faithful match to the working name "DataCheck" while disambiguating the image-dataset scope. Long but unambiguous, easy to search.
