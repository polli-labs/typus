"""Import-purity guards for the dependency-light core (POL-1968 / GEOM-1).

Every check runs in a fresh interpreter via ``subprocess``: pytest's own
conftest and plugin imports already populate ``sys.modules`` in-process, so an
in-process assertion would be meaningless.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

# Dependencies that must never be pulled in by the pure-DTO core.
HEAVY = ("sqlalchemy", "rapidfuzz", "asyncpg", "aiosqlite")


def run_snippet(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )


def assert_clean(module: str) -> None:
    code = f"""
import sys
import {module}
leaked = [m for m in {HEAVY!r} if m in sys.modules]
assert not leaked, f"{module} leaked: {{leaked}}"
print("OK")
"""
    proc = run_snippet(code)
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


@pytest.mark.parametrize(
    "module",
    [
        "typus",
        "typus.models.geometry",
        "typus.ops",
        "typus.models.clade",
        "typus.constants",
        "typus.services.projections",
    ],
)
def test_core_import_is_dependency_light(module: str) -> None:
    assert_clean(module)


def test_acceptance_criterion_geometry() -> None:
    """The literal POL-1968 acceptance command."""
    proc = run_snippet("import typus.models.geometry, sys; assert 'sqlalchemy' not in sys.modules")
    assert proc.returncode == 0, proc.stderr


def test_service_symbols_are_lazy_not_removed() -> None:
    """Laziness must be real deferral: touching a service symbol loads sqlalchemy."""
    code = """
import sys
import typus

assert "sqlalchemy" not in sys.modules
svc = typus.PostgresTaxonomyService
assert svc.__name__ == "PostgresTaxonomyService"
assert "sqlalchemy" in sys.modules

from typus import SQLiteTaxonomyService, TaxonomyService
assert TaxonomyService.__name__ == "AbstractTaxonomyService"
assert SQLiteTaxonomyService.__name__ == "SQLiteTaxonomyService"

# The `typus.services` package shim must keep working for downstream callers.
from typus.services import SQLiteTaxonomyService as ShimService
assert ShimService is SQLiteTaxonomyService
print("OK")
"""
    proc = run_snippet(code)
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_every_public_name_resolves() -> None:
    """No `__all__` entry may be a dangling lazy alias."""
    code = """
import typus

missing = [name for name in typus.__all__ if not hasattr(typus, name)]
assert not missing, f"unresolvable __all__ entries: {missing}"

# The lazy table must not shadow or drop anything from the public surface.
missing_from_all = sorted(set(typus._LAZY) - set(typus.__all__))
assert not missing_from_all, f"lazy names absent from __all__: {missing_from_all}"

assert set(typus.__all__).issubset(set(dir(typus)))
print("OK")
"""
    proc = run_snippet(code)
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_unknown_attribute_still_raises_attribute_error() -> None:
    code = """
import typus
import typus.services

for mod in (typus, typus.services):
    try:
        getattr(mod, "definitely_not_a_real_symbol")
    except AttributeError:
        pass
    else:
        raise AssertionError(f"{mod.__name__} __getattr__ swallowed an unknown name")
print("OK")
"""
    proc = run_snippet(code)
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_infer_rank_exact_path_needs_no_optional_deps() -> None:
    """The exact-match fast path must work before rapidfuzz is ever imported."""
    code = """
import sys
from typus.constants import RankLevel, infer_rank

assert infer_rank("genus") is RankLevel.L20
assert infer_rank("species") is RankLevel.L10
assert "rapidfuzz" not in sys.modules
print("OK")
"""
    proc = run_snippet(code)
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def block_module(blocked: str, *, raise_name: str | None = None) -> str:
    """Snippet that makes importing `blocked` raise ModuleNotFoundError.

    Uses the ``find_spec`` finder protocol. The legacy ``find_module`` /
    ``load_module`` pair was REMOVED in Python 3.12, where such a finder is
    silently ignored — the import then succeeds and the test passes vacuously.
    Local venvs are 3.10 and CI runs 3.12, so that failure mode is invisible
    locally. Hence ``assert_simulation_fired`` below.
    """
    name = raise_name or blocked
    return (
        "import sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        f"        if name == {blocked!r} or name.startswith({blocked + '.'!r}):\n"
        f"            raise ModuleNotFoundError('No module named ' + repr(name), name={name!r})\n"
        "        return None\n"
        "sys.meta_path.insert(0, Block())\n"
    )


def assert_simulation_fired(proc: subprocess.CompletedProcess[str], label: str) -> None:
    """Guard against a vacuous pass: the blocked import must actually have raised."""
    assert proc.stdout.strip(), (
        f"{label}: the import-blocking simulation never fired (empty stdout) — "
        f"the test would pass vacuously. stderr={proc.stderr!r}"
    )


def test_missing_extra_message_names_the_extra_on_both_public_paths() -> None:
    """A missing service dep must name the extra, on `typus` AND `typus.services`.

    Regression guard: the root guard and the `typus.services` guard are separate
    code paths, and only the root one originally wrapped the error.
    `typus.services` is the path linnaeus and the polli docs actually use, so an
    unwrapped `No module named 'sqlalchemy'` there defeats the point of the extras.
    """
    for expr in (
        "from typus import PostgresTaxonomyService",
        "from typus.services import SQLiteTaxonomyService",
    ):
        proc = run_snippet(
            block_module("sqlalchemy") + "try:\n"
            f"    {expr}\n"
            "except ModuleNotFoundError as exc:\n"
            "    print(str(exc))\n"
        )
        assert_simulation_fired(proc, expr)
        assert (
            "polli-typus[services]" in proc.stdout
        ), f"{expr!r} did not name the extra to install; got: {proc.stdout!r}"


def test_internal_import_error_is_not_rebranded_as_a_missing_extra() -> None:
    """A genuine internal bug must not be reported as a packaging problem.

    The guards rewrite ModuleNotFoundError only for known optional dependency
    names; anything else has to surface unchanged, or a typo'd relative import
    inside the package would masquerade as "install polli-typus[services]".
    """
    proc = run_snippet(
        block_module("typus.services.taxonomy", raise_name="typus.internal_typo") + "try:\n"
        "    from typus import PostgresTaxonomyService\n"
        "except ModuleNotFoundError as exc:\n"
        "    print(str(exc))\n"
    )
    assert_simulation_fired(proc, "internal-typo simulation")
    assert (
        "polli-typus[services]" not in proc.stdout
    ), f"internal import failure was rebranded as a missing extra: {proc.stdout!r}"
