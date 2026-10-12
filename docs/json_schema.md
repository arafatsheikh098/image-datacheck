# JSON schema for imagedatacheck reports

The `report --json` output is a single JSON object with the following
top-level keys. The shape is versioned via `schema_version`; downstream
consumers should refuse unknown major versions.

Current version: `1`.

```json
{
  "schema_version": 1,
  "root": "/abs/path/to/dataset",
  "layout": "split_class_folders" | "class_folders" | "flat",
  "files": [ FileInfo, ... ],
  "findings": [ Finding, ... ]
}
```

## FileInfo

```json
{
  "path": "/abs/path/to/file.jpg",
  "rel_path": "train/cat/file.jpg",
  "size": 12345,
  "split": "train" | null,
  "label": "cat" | null
}
```

* `split` is `null` for the `class_folders` and `flat` layouts.
* `label` is `null` for the `flat` layout.

## Finding

```json
{
  "code": "W_EXACT_DUPLICATE",
  "severity": "error" | "warning" | "info",
  "message": "Exact duplicate group abc123 has 2 members.",
  "files": ["/abs/path/a.jpg", "/abs/path/b.jpg"],
  "extra": { "...": "..." }
}
```

The `extra` payload is code-specific. See the table below for the
documented codes.

## Codes

| Code | Severity | Extra fields |
| --- | --- | --- |
| `E_ROOT_MISSING` | error | — |
| `E_ROOT_NOT_DIR` | error | — |
| `E_EMPTY` | error | — |
| `E_DIR_UNREADABLE` | error | — |
| `E_UNREADABLE` | error | — |
| `E_ZERO_BYTE` | error | — |
| `E_TOO_SMALL` | error | — |
| `E_TRUNCATED` | error | — |
| `E_DECOMPRESSION_BOMB` | error | — |
| `E_WRONG_EXTENSION` | error | — |
| `I_CMYK` | info | — |
| `I_PALETTE_TRANSPARENCY` | info | — |
| `I_EXIF_ORIENTATION` | info | — |
| `W_LOW_INFORMATION` | warning | — |
| `W_SYMLINK_LOOP` | warning | — |
| `W_EXACT_DUPLICATE` | warning | `group_id`, `kind: "exact"` |
| `W_NEAR_DUPLICATE` | warning | `group_id`, `kind: "near"` |
| `W_IMBALANCE` | warning | `ratio`, `max_count`, `min_count`, `counts` |
| `W_EMPTY_CLASS` | warning | `label` |
| `W_CLASS_NAME_COLLISION` | warning | `normalized`, `labels` |
| `W_CROSS_SPLIT_LEAKAGE` | warning | `group_id`, `kind`, `splits`, `label` |
| `W_CONFLICTING_LABELS` | warning | `group_id`, `kind`, `labels`, `splits` |

## Determinism

The JSON output is byte-identical between runs that produce the same
findings on the same dataset, with no timestamps embedded. This makes
the output suitable for golden-file testing and `diff`-based code review.
