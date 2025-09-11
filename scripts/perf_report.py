from __future__ import annotations

import asyncio
import os
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from typus.services import (
    PostgresTaxonomyService,
    SQLiteTaxonomyService,
    load_expanded_taxa,
)


@dataclass
class Result:
    backend: str
    scope: str
    mode: str
    fuzzy: bool
    ms_avg: float
    ms_p95: float
    n: int
    count_avg: float
    span_pct: float | None = None


async def _bench_once(
    svc, query: str, scope: str, mode: str, fuzzy: bool
) -> tuple[float, int, list[int]]:
    t0 = time.perf_counter()
    res = await svc.search_taxa(
        query,
        scopes={scope},
        match=mode,
        fuzzy=fuzzy,
        threshold=0.8,
        limit=50,
    )
    ms = (time.perf_counter() - t0) * 1000.0
    try:
        ids = [getattr(t, "taxon_id", None) for t in res]
    except Exception:
        ids = []
    return ms, len(res) if isinstance(res, list) else 0, [i for i in ids if isinstance(i, int)]


def _verify(query: str, scope: str, mode: str, ids: list[int], *, backend: str) -> None:
    if os.getenv("TYPUS_PERF_VERIFY", "0") not in {"1", "true", "TRUE"}:
        return
    # Minimal sanity checks against the shared fixture semantics
    # - scientific/prefix "Apis" contains genus 47220
    # - vernacular/exact "honey bee" contains species 47219
    if scope == "scientific" and mode in {"exact"} and query.lower() == "apis mellifera":
        assert 47219 in ids, "Expected species Apis mellifera (47219) to be present"
    if scope == "scientific" and mode == "prefix" and query.lower().startswith("apis"):
        if backend == "sqlite":
            # Small fixture should include genus Apis in top-k
            assert 47220 in ids, "Expected genus Apis (47220) to be present in sqlite fixture"
        else:
            # Large PG datasets may return many species first; require non-empty
            assert len(ids) > 0, "Expected non-empty results for scientific prefix 'Apis'"
    if scope == "vernacular" and mode == "exact" and query.lower() == "honey bee":
        assert 47219 in ids, "Expected species Apis mellifera (47219) to be present"


async def _bench_backend(backend: str) -> list[Result]:
    # Ensure SQLite DB present
    if backend == "sqlite":
        db = load_expanded_taxa(Path(".cache/typus/expanded_taxa.sqlite"))
        svc = SQLiteTaxonomyService(db)
    else:
        dsn = os.getenv("TYPUS_TEST_DSN") or os.getenv("POSTGRES_DSN")
        if not dsn:
            return []
        svc = PostgresTaxonomyService(dsn)

    # Query matrix
    matrix = [
        ("Apis", "scientific"),
        ("Apis me", "scientific"),
        ("Apis mellifera", "scientific"),
        ("honey bee", "vernacular"),
    ]
    modes = ["exact", "prefix", "substring"]
    fuzzies = [False, True]

    out: list[Result] = []
    for q, scope in matrix:
        for mode in modes:
            for fuzzy in fuzzies:
                samples: list[float] = []
                counts: list[int] = []
                # warm-up + samples
                for i in range(6):
                    ms, count, ids = await _bench_once(svc, q, scope, mode, fuzzy)
                    if i >= 1:
                        _verify(q, scope, mode, ids, backend=backend)
                    if i >= 1:
                        samples.append(ms)
                        counts.append(count)
                if samples:
                    avg = statistics.mean(samples)
                    p95 = (
                        statistics.quantiles(samples, n=20)[18]
                        if len(samples) >= 20
                        else max(samples)
                    )
                    span = (max(samples) - min(samples)) / avg if avg > 0 else 0.0
                    cnt_avg = statistics.mean(counts) if counts else 0.0
                    out.append(
                        Result(backend, scope, mode, fuzzy, avg, p95, len(samples), cnt_avg, span)
                    )
    return out


def _write_report(results: list[Result]) -> None:
    path = Path("dev/agents/perf_report.md")
    lines: list[str] = []
    lines.append("---")
    lines.append("doc_type: docs_page")
    lines.append("title: Typus v0.4.0 – Name Search Perf Baseline")
    lines.append("created: 2025-09-08T00:00:00Z")
    lines.append("updated: 2025-09-08T00:00:00Z")
    lines.append("tags: [perf, search, sqlite, postgres]")
    lines.append("---\n")
    lines.append("# Summary\n")
    lines.append("Timings in milliseconds (avg over 5 samples after warm-up). Lower is better.\n")
    # Table header
    lines.append("backend | scope | mode | fuzzy | avg_ms | p95_ms | n | count_avg | span_pct")
    lines.append("---|---|---|---|---:|---:|--:|--:|--:")
    for r in results:
        span_pct = (r.span_pct or 0.0) * 100.0
        lines.append(
            f"{r.backend} | {r.scope} | {r.mode} | {str(r.fuzzy).lower()} | {r.ms_avg:.2f} | {r.ms_p95:.2f} | {r.n} | {r.count_avg:.1f} | {span_pct:.1f}%"
        )
    lines.append("")
    path.write_text("\n".join(lines))


async def _pg_explain_snippets() -> list[str]:
    dsn = os.getenv("TYPUS_TEST_DSN") or os.getenv("POSTGRES_DSN")
    if not dsn or os.getenv("TYPUS_PERF_EXPLAIN", "0") not in {"1", "true", "TRUE"}:
        return []
    eng = create_async_engine(dsn, pool_pre_ping=True)
    queries = [
        (
            "scientific prefix",
            'SELECT taxonID FROM expanded_taxa WHERE LOWER(name) LIKE \'apis me%\' AND "rankLevel" IN (10,20,30,40,50,60,70) ORDER BY "rankLevel", name LIMIT 50',
        ),
        (
            "scientific substring",
            "SELECT taxonID FROM expanded_taxa WHERE LOWER(name) LIKE '%apis me%' ORDER BY \"rankLevel\", name LIMIT 50",
        ),
    ]
    out: list[str] = []
    async with eng.begin() as conn:
        for label, q in queries:
            try:
                res = await conn.exec_driver_sql(
                    f"EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) {q}"
                )
                plan = "\n".join(r[0] for r in res)
                out.append(f"### PG EXPLAIN – {label}\n\n```\n{plan}\n```\n")
            except Exception as e:
                out.append(f"### PG EXPLAIN – {label} (error)\n\n{e}\n")
    await eng.dispose()
    return out


async def main() -> int:
    res_sqlite = await _bench_backend("sqlite")
    res_pg = await _bench_backend("postgres")
    results = res_sqlite + res_pg
    for r in results:
        span_pct = (r.span_pct or 0.0) * 100.0
        warn = " [VAR]" if (r.span_pct or 0.0) > 0.25 else ""
        print(
            f"{r.backend}/{r.scope}/{r.mode}/fuzzy={r.fuzzy} -> avg={r.ms_avg:.2f} ms p95={r.ms_p95:.2f} ms (n={r.n}, count~{r.count_avg:.1f}, span={span_pct:.1f}%)"
            + warn
        )
    if os.getenv("TYPUS_PERF_WRITE", "1") in {"1", "true", "TRUE"}:
        _write_report(results)
        # Append PG explain snippets if requested
        snippets = await _pg_explain_snippets()
        if snippets:
            path = Path("dev/agents/perf_report.md")
            with path.open("a") as fh:
                fh.write("\n\n" + "\n\n".join(snippets))
        print("perf report written to dev/agents/perf_report.md")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(asyncio.run(main()))
