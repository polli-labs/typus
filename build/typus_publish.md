# Typus publish checklist

> Source of truth: GitHub Actions workflow `.github/workflows/publish.yml`.
> Publishing is handled by the `Build & publish` workflow on tag push in the
> public `polli-labs/typus` repository. Local `twine` uploads are *optional*
> and generally not used.

Typus uses the private-development/public-release split:

- Private daily development repo: `polli-labs/typus-dev`.
- Public release repo: `polli-labs/typus`.
- In the private clone/worktree, `origin` is private and `public` is the release
  repo. A tag pushed only to `origin` will not publish to PyPI.

## Prerequisites
- Clean working tree (`git status` empty) on the release branch.
- Version bump applied in `pyproject.toml`, `CHANGELOG.md`, and docs.
- Tests and schemas green locally:
  - `make check-all`
  - `uv build --clear`
  - `uv run --locked --extra dev twine check dist/*`
  - `TYPUS_TEST_DSN=… make test-pg-smoke && make test-pg` (optional but recommended)
- `uv.lock` is current and passes the seven-day upload-age cooldown.
- Public/private parity has been checked against
  `docs/migration/dev_public_release_contract.md`.

## 1. Prepare and merge private
1. Work on a private release branch, e.g. `caleb/release-typus-0.6.0`.
2. Open a PR against `polli-labs/typus-dev:main`, get review, and merge.
3. Locally, fast-forward private `main` and ensure the release commit is on `main`:
   ```bash
   git checkout main
   git pull origin main
   ```

## 2. Promote to public
Promote the public-safe release commit to `polli-labs/typus:main` using the
repo's current public/private sync posture. Do not tag until the public repo has
the exact release content.

In a private worktree, remember:

```bash
git push public HEAD:main
```

or open/merge a public release PR if that is the selected release shape.

## 3. Tag public to trigger CI + publish
From the up-to-date public release surface:

```bash
export VERSION=0.6.0  # adjust
git tag v${VERSION}
git push origin v${VERSION}   # when cwd is ~/dev/typus/public/typus
# OR, from a private worktree:
git push public v${VERSION}
```

This will trigger the `Build & publish` workflow, which:
- runs tests on the tagged commit,
- builds wheel + sdist via `uv build`,
- validates artifacts with locked `twine`,
- publishes to **TestPyPI** and then **PyPI** (using org secrets),
- uploads built artifacts as GitHub release assets,
- builds and deploys docs to `docs.polli.ai/typus/`.

## 4. Monitor workflow
Use the GitHub UI or `gh`:

```bash
gh run list --repo polli-labs/typus --workflow "Build & publish" --limit 5
gh run watch <run-id>  # optional, best run in tmux
```

The `build-and-publish` job must be green for a successful release. The
`deploy-docs` job should also be green for docs to update; if it fails,
investigate SSH connectivity or server issues and re-run that job.

## 5. Post-release checks
- Verify PyPI:
  - `https://pypi.org/project/polli-typus/` shows the new version.
  - `uv pip install polli-typus==<version>` works in a fresh venv.
- Verify docs:
  - `https://docs.polli.ai/typus/` reflects the new API (TaxonSummary,
    PollinatorGroup, etc.).
- Update `dev/agents/typus-v<version>-notes.md` with any follow‑ups.
