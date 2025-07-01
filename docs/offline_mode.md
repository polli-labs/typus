# Offline mode

`load_expanded_taxa` helps you work without a network connection. It downloads a
prebuilt SQLite dump of the `expanded_taxa` table (or converts a TSV file) and
caches it locally.

```python
from pathlib import Path
from typus.services.sqlite_loader import load_expanded_taxa

load_expanded_taxa(Path("expanded_taxa.sqlite"))
```

## CLI

```bash
typus-load-sqlite --sqlite expanded_taxa.sqlite
```

Pass `--replace` to overwrite, `--tsv my.tsv` to use a local dump. Downloads are
stored in `~/.cache/typus` unless `$TYPUS_CACHE_DIR` is set. Override the source
URL with `--url` or `$TYPUS_EXPANDED_TAXA_URL`.

