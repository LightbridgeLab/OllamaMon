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

## Homebrew tap

Install for users:

```bash
brew tap LightbridgeLab/omon
brew install omon
```

### One-time tap setup

1. Create the public repo **`LightbridgeLab/homebrew-omon`** (exact name required for `brew tap LightbridgeLab/omon`).
2. Push the contents of [`homebrew-omon/`](homebrew-omon/) to that repo:

   ```bash
   cd homebrew-omon
   git init
   git add Formula/omon.rb README.md
   git commit -m "feat: initial omon formula"
   gh repo create LightbridgeLab/homebrew-omon --public --source=. --push
   ```

3. Optional — auto-update formula on each GitHub Release:
   - Create a fine-grained PAT with **Contents: Read and write** on `homebrew-omon` only.
   - Add it to this repo as secret **`HOMEBREW_TAP_TOKEN`**.
   - The [`homebrew.yml`](.github/workflows/homebrew.yml) workflow runs on `release: published`.

### Manual formula bump

After the tag is **pushed to GitHub** (the script downloads the release tarball):

```bash
make homebrew-formula              # uses version from pyproject.toml
make homebrew-formula V=0.5.1      # explicit version

# push to your tap clone (default: ../homebrew-omon)
make homebrew-push HOMEBREW_TAP_DIR=../homebrew-omon
```

Or run `make release` for the full PyPI + Homebrew checklist.

### Makefile vs GitHub Actions

| Step | Who does it |
|------|-------------|
| **Auto-bump tap on release** | [`homebrew.yml`](.github/workflows/homebrew.yml) when you publish a GitHub Release and `HOMEBREW_TAP_TOKEN` is set |
| **Local formula preview** | `make homebrew-formula` (updates `homebrew-omon/Formula/omon.rb` in this repo only) |
| **Manual tap push** | `make homebrew-push` if you skip the secret or the workflow failed |

Do **not** hook `homebrew-formula` into `bump-patch` / `_release-commit` — the GitHub tag must exist before the tarball URL and `sha256` are valid.
