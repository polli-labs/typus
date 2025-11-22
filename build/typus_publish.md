# Typus publish checklist (v0.4.x)

> Keep this in sync with README references. Update the version in `pyproject.toml`
> and changelog before starting the flow.

## Prerequisites
- PyPI + TestPyPI credentials available to `twine`
- Clean working tree (`git status` empty)
- Local env set up: `uv pip install -e ".[dev,sqlite]"` (plus `[postgres]` if needed)

## Validation
1. `make ci`  # SQLite/CI subset
2. Optionally `make test` with `TYPUS_TEST_DSN` set for Postgres coverage
3. `uv run python -m typus.export_schemas`  # ensure schemas are fresh

## Build
```
rm -rf dist/*
uv run python -m build
```

## TestPyPI upload (recommended)
```
uv run twine upload --repository testpypi dist/*
python -m venv /tmp/typus-venv
source /tmp/typus-venv/bin/activate
pip install --extra-index-url https://test.pypi.org/simple polli-typus==<version>
python - <<'PY'
import typus
print(typus.__version__)
PY
deactivate
```

## PyPI upload
```
uv run twine upload dist/*
```

## Tag & push
```
git tag v<version>
git push origin v<version>
git push origin HEAD
```

## Post-release
- Verify https://pypi.org/project/polli-typus/ shows the new version
- Check docs build (GitHub Actions) completed on tag push
- Post notes in `dev/agents/typus-v<version>-notes.md`
