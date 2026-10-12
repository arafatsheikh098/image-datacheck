# Releasing imagedatacheck

This document walks through every manual step required to publish a new
release of `imagedatacheck` to PyPI. The release workflow itself
(`.github/workflows/release.yml`) builds the wheel and sdist, but the
**publish** step uses PyPI trusted publishing with a manual-approval
environment so the final push is human-gated.

## One-time setup

### 1. Configure the PyPI project

* Create the project on PyPI (or claim the existing one). The package
  name is `imagedatacheck`.
* Under **Publishing** → **Trusted publishers** add a new pending
  publisher with these values:
  * Owner: your GitHub org or user
  * Repository: `imagedatacheck`
  * Workflow filename: `release.yml`
  * Environment name: `pypi`

### 2. Configure the GitHub environment

* In the repository settings → **Environments** create an environment
  named `pypi` with:
  * Required reviewers: at least one maintainer
  * Deployment branches: only `main` and tags matching `v*`

### 3. (Optional) Configure TestPyPI

If you want a dry run on TestPyPI first, add a second trusted publisher
with environment name `testpypi` and a separate workflow file
(e.g. `release-test.yml`). The shipped `release.yml` targets production
PyPI only.

## Cutting a release

### 1. Verify the working tree

```sh
git checkout main
git pull
python -m pip install -e .[dev]
pytest -q
ruff check .
mypy src/imagedatacheck
```

### 2. Bump the version

Edit `src/imagedatacheck/__init__.py` (`__version__ = "x.y.z"`).
Update `CHANGELOG.md` to move the `[Unreleased]` section into a new
dated heading.

Commit and push:

```sh
git add -A
git commit -m "chore: bump version to x.y.z"
git push
```

### 3. Tag the release

Tags follow `v<version>` and must match `__version__`.

```sh
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

### 4. Approve the publish

Pushing the tag triggers `.github/workflows/release.yml`. The job
builds the wheel/sdist, runs `twine check`, and then pauses on the
`pypi` environment waiting for a reviewer. A maintainer must approve
the deployment in the GitHub UI before the publish step runs.

### 5. Smoke-test the published wheel

In a clean virtualenv:

```sh
python -m venv /tmp/idc-smoke
/tmp/idc-smoke/bin/pip install imagedatacheck==X.Y.Z
/tmp/idc-smoke/bin/imagedatacheck --version
/tmp/idc-smoke/bin/imagedatacheck scan examples/demo --quiet
```

### 6. Publish the sample report (Pages)

The Pages workflow (`.github/workflows/pages.yml`) runs on every push to
main, regenerates the demo dataset, builds an HTML report, and
publishes it to GitHub Pages. No manual step required; verify the
pages site after the next push to main.

## What never runs on a PR

* The `release.yml` workflow only triggers on tags of the form `v*`.
  Pull requests cannot trigger a publish.
* The Pages workflow only triggers on `main` pushes.
* All other CI workflows ignore tag pushes and only run on PR + main
  pushes.

## Rollback

If a release has a critical bug:

1. `git tag -d vX.Y.Z` and `git push --delete origin vX.Y.Z` (removes
   the tag; the GitHub release can be deleted from the UI).
2. Yank the release on PyPI under **Releases** → click the version →
   **Options** → **Yank**. This prevents new installs but does not
   break existing pins.
3. Ship a fix as `X.Y.Z+1`.
