# imagedatacheck

A fast, trustworthy CLI that scans an image dataset folder and reports
data-quality problems before training: corrupt files, duplicates, class imbalance,
leakage between train/val/test splits and conflicting labels.

> Status: **early development**. The CLI shell, packaging and CI matrix are in
> place (M1). Scanning, integrity, duplicate detection, dataset checks, reports
> and packaging land in milestones M2..M7.

## Quick start

```bash
pip install -e .[dev]
imagedatacheck --version
imagedatacheck --help
```

## License

MIT — see `LICENSE`.