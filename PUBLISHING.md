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
git add -A && git commit -m "..."   # only if you have pending changes
make bump-patch                     # or bump-minor / bump-major
make deploy-prod
```

`make bump-patch` updates `pyproject.toml` and `src/omon/__init__.py`, commits them, and creates tag `vX.Y.Z`.

`make deploy-prod` runs tests, builds the wheel, pushes to GitHub, and creates the GitHub Release. That triggers `publish.yml` (PyPI) and `homebrew.yml` (tap).

Commit anything else **before** bumping — bump only stages the two version files.

## Verify locally

`make check` runs tests only. `make deploy-prod` runs tests + build before it pushes (after `make bump-*`).

From the repo root (macOS often has `python3` but not `python`; `build` is not in the stdlib):

```bash
python3 -m venv .venv
.venv/bin/pip install build
.venv/bin/python -m build
pipx install dist/omon-0.5.0-py3-none-any.whl
omon --version
```

Replace `0.5.0` with the version in `pyproject.toml` if you have bumped it.

## Homebrew tap

Install for users:

```bash
brew tap LightbridgeLab/omon
brew install omon
```

### Repository layout

The Homebrew formula is maintained in two places:

| Repo | Role |
|------|------|
| **[OllamaMon](https://github.com/LightbridgeLab/OllamaMon)** | [`homebrew-omon/`](homebrew-omon/) holds the formula template and tap README. Edit and commit these files with the main project. |
| **[homebrew-omon](https://github.com/LightbridgeLab/homebrew-omon)** | Homebrew clones this repo for `brew tap LightbridgeLab/omon`. Updated on each release by CI, or manually with `make homebrew-push`. |

### One-time maintainer setup

```bash
make homebrew-tap-clone
```

Add **`HOMEBREW_TAP_TOKEN`** to OllamaMon repo secrets (fine-grained PAT with **Contents: Read and write** on `homebrew-omon`).

Default local clone path: `../OllamaMon_Homebrew_Tap` (override with `HOMEBREW_TAP_DIR`).

### Each release

Commit pending changes (if any), then `make bump-patch` and `make deploy-prod`.

### Manual tap push (CI fallback)

After the tag is on GitHub:

```bash
make homebrew-formula V=x.y.z    # optional: refresh formula in OllamaMon
make homebrew-push V=x.y.z       # push to local tap clone
```

Use explicit `V=` when `pyproject.toml` differs from the released tag.

To update the tap without re-publishing a release: **Actions** → **Update Homebrew formula** → **Run workflow** → enter the version (e.g. `0.6.2`).

### Makefile vs GitHub Actions

| Step | Who does it |
|------|-------------|
| **Auto-bump tap on release** | [`homebrew.yml`](.github/workflows/homebrew.yml) when you publish a GitHub Release and `HOMEBREW_TAP_TOKEN` is set |
| **Local formula preview** | `make homebrew-formula` (updates `homebrew-omon/Formula/omon.rb` in this repo only) |
| **Manual tap push** | `make homebrew-push` |

Do **not** hook `homebrew-formula` into `bump-patch` / `_release-commit` — the GitHub tag must exist on the remote before the tarball URL and `sha256` can be computed.
