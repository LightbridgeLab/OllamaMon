# Publishing to PyPI

PyPI publishing is automated via GitHub Actions when you create a GitHub Release.

## One-time setup

1. Create the `omon` project on [PyPI](https://pypi.org/) (if it does not exist yet).
2. On PyPI → **Publishing** → **Add a new pending publisher**:
   - PyPI project name: `omon`
   - Owner: `LightbridgeLab`
   - Repository: `OllamaMon`
   - Workflow: `publish.yml`
   - Environment: (leave blank)
3. Push this repo and make it public on GitHub.

## Publish a release

```bash
git tag v0.5.0
git push origin v0.5.0
```

Then on GitHub: **Releases** → **Draft a new release** → select tag `v0.5.0` → **Publish release**.

The `publish.yml` workflow builds and uploads to PyPI using OIDC (no API token stored in GitHub secrets).

## Verify locally

Optional smoke test before you tag — **does not require a tag or GitHub release**. CI builds the same way on publish.

From the repo root (macOS often has `python3` but not `python`; `build` is not in the stdlib):

```bash
python3 -m venv .venv
.venv/bin/pip install build
.venv/bin/python -m build
pipx install dist/omon-0.5.0-py3-none-any.whl
omon --version
```

Replace `0.5.0` with the version in `pyproject.toml` if you have bumped it.
