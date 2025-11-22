# Typus publish checklist (v0.4.x)

> Source of truth: GitHub Actions workflow `.github/workflows/publish.yml`.
> Publishing is handled by the `Build & publish` workflow on tag push; local
> `twine` uploads are *optional* and generally not used.

## Prerequisites
- Clean working tree (`git status` empty) on the release branch.
- Version bump applied in `pyproject.toml`, `CHANGELOG.md`, and docs.
- Tests and schemas green locally:
  - `make test`
  - `TYPUS_TEST_DSN=… make test-pg` (optional but recommended)
  - `make ci`
  - `make schemas`

## 1. Prepare and merge
1. Work on a release branch, e.g. `v0.4.2-taxonomy-summary`.
2. Open a PR against `main`, get review, and merge.
3. Locally, fast‑forward `main` and ensure the release commit is on `main`:
   ```bash
   git checkout main
   git pull origin main
   ```

## 2. Tag to trigger CI + publish
From the up‑to‑date `main`:

```bash
export VERSION=0.4.2  # adjust
git tag v${VERSION}
git push origin v${VERSION}
git push origin main
```

This will trigger the `Build & publish` workflow, which:
- runs tests on the tagged commit,
- builds the wheel via `hatch build -t wheel`,
- publishes to **TestPyPI** and then **PyPI** (using org secrets),
- uploads the wheel as a GitHub release asset,
- builds and deploys docs to `docs.polli.ai/typus/`.

## 3. Monitor workflow
Use the GitHub UI or `gh`:

```bash
gh run list --workflow "Build & publish" --limit 5
gh run watch <run-id>  # optional, best run in tmux
```

The `build-and-publish` job must be green for a successful release. The
`deploy-docs` job should also be green for docs to update; if it fails,
investigate SSH connectivity or server issues and re‑run that job.

## 4. Post-release checks
- Verify PyPI:
  - `https://pypi.org/project/polli-typus/` shows the new version.
  - `pip install polli-typus==<version>` works in a fresh venv.
- Verify docs:
  - `https://docs.polli.ai/typus/` reflects the new API (TaxonSummary,
    PollinatorGroup, etc.).
- Update `dev/agents/typus-v<version>-notes.md` with any follow‑ups.
