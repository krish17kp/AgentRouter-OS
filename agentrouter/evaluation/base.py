"""DatasetAdapter contract (program §5 + real/fixture source axis).

Every dataset — local gold or external public benchmark — is exposed through
this one interface. Two explicit sources:

- ``fixture`` (default): the small committed JSONL smoke sample. Always offline.
- ``real``: the actual dataset via the ``datasets`` lib / network.

A ``real`` load NEVER silently falls back to the fixture: if the real data is
unavailable it raises ``AdapterError`` (SKIPPED_EXTERNAL) so CI and users can
tell a real run from a smoke run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .sampling import deterministic_sample
from .schema import EvaluationCase

# valid source values for load/sample/checksum
FIXTURE = "fixture"
REAL = "real"


class Availability(str, Enum):
    READY = "ready"  # real data present locally
    FIXTURE_ONLY = "fixture_only"  # only the committed smoke fixture is available
    SKIPPED_EXTERNAL = "skipped_external"  # needs network/Docker/creds not present


@dataclass(frozen=True)
class DatasetMetadata:
    name: str
    version: str
    license: str
    source: str
    description: str
    requires_network: bool = False
    requires_docker: bool = False
    languages: tuple[str, ...] = ("en",)


class AdapterError(Exception):
    """Raised on a malformed dataset or a genuinely unusable adapter state."""


class SkippedExternal(AdapterError):
    """Real data is unavailable (network/deps/Docker/creds). Never a silent pass."""


def datasets_available() -> bool:
    """True if the optional `datasets` library is importable."""
    import importlib.util

    return importlib.util.find_spec("datasets") is not None


def _dedup_by_hash(cases: list[EvaluationCase]) -> list[EvaluationCase]:
    """Drop later cases whose normalized task hash was already seen."""
    seen: set[str] = set()
    out: list[EvaluationCase] = []
    for c in cases:
        h = c.task_hash
        if h not in seen:
            seen.add(h)
            out.append(c)
    return out


class DatasetAdapter:
    """Base adapter. Subclasses set `meta`, implement `_load_raw` (fixture) and
    optionally `_load_real` (real dataset). Common methods live here so adapters
    stay small and consistent.
    """

    meta: DatasetMetadata
    #: path to the committed smoke fixture (JSONL of EvaluationCase dicts)
    fixture_path: Path | None = None
    #: HuggingFace dataset repo id + pinned revision for the real load (if any)
    hf_repo: str | None = None
    hf_config: str | None = None
    hf_revision: str | None = None

    # --- metadata / availability --------------------------------------------

    def metadata(self) -> DatasetMetadata:
        return self.meta

    def availability(self) -> Availability:
        """Fixture if present, else skipped. Override for locally-present real data."""
        if self.fixture_path and self.fixture_path.exists():
            return Availability.FIXTURE_ONLY
        return Availability.SKIPPED_EXTERNAL

    def real_availability(self) -> tuple[bool, str]:
        """(can_run_real, reason). Real needs a repo + the `datasets` lib."""
        if not self.hf_repo:
            return False, f"{self.meta.name}: no real loader configured (source unverified)"
        if not datasets_available():
            return False, "the `datasets` library is not installed (pip install -e '.[eval]')"
        return True, "ready"

    # --- loading -------------------------------------------------------------

    def _load_raw(self) -> list[EvaluationCase]:
        """Fixture load. Subclasses point this at `self._load_fixture()`."""
        raise NotImplementedError

    def _load_real(self) -> list[EvaluationCase]:
        """Real dataset load. Default: not implemented -> SKIPPED_EXTERNAL."""
        raise SkippedExternal(f"{self.meta.name}: real mode not implemented for this dataset")

    def load(self, source: str = FIXTURE) -> list[EvaluationCase]:
        if source == REAL:
            ok, reason = self.real_availability()
            if not ok:
                raise SkippedExternal(f"{self.meta.name}: {reason}")
            raw = self._load_real()  # may raise SkippedExternal on network/SSL failure
            # Real dataset dumps legitimately contain exact/near-dup utterances;
            # drop later exact-normalized dups so each graded task is unique.
            raw = _dedup_by_hash(raw)
        elif source == FIXTURE:
            raw = self._load_raw()
        else:
            raise AdapterError(f"{self.meta.name}: unknown source '{source}'")
        cases = [c.with_checksum() for c in raw]
        self.validate(cases)
        return cases

    def _load_fixture(self) -> list[EvaluationCase]:
        if not self.fixture_path or not self.fixture_path.exists():
            raise AdapterError(f"{self.meta.name}: fixture not found at {self.fixture_path}")
        out: list[EvaluationCase] = []
        for line in self.fixture_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(EvaluationCase.model_validate_json(line))
        return out

    def _hf_load(self, split: str | None = None):
        """Load the configured HF dataset, translating failures into SkippedExternal."""
        ok, reason = self.real_availability()
        if not ok:
            raise SkippedExternal(f"{self.meta.name}: {reason}")
        try:
            from datasets import load_dataset
        except ImportError as e:  # pragma: no cover - guarded by real_availability
            raise SkippedExternal(f"{self.meta.name}: datasets import failed: {e}") from e
        try:
            # trust_remote_code: classic datasets (clinc_oos, banking77, massive) ship
            # a loader script. Real mode is explicit opt-in, so we allow it here.
            return load_dataset(
                self.hf_repo,
                self.hf_config,
                split=split,
                revision=self.hf_revision,
                trust_remote_code=True,
            )
        except Exception as e:  # noqa: BLE001 - network/SSL/auth all become one honest signal
            raise SkippedExternal(
                f"{self.meta.name}: real download failed ({type(e).__name__}: {str(e)[:160]})"
            ) from e

    def prepare(self, limit: int | None = None) -> dict:
        """Download + normalize the real dataset; return a provenance report.

        Never writes into the repo. Raises SkippedExternal if unavailable.
        """
        cases = self.load(source=REAL)
        return {
            "dataset": self.meta.name,
            "source": self.meta.source,
            "hf_repo": self.hf_repo,
            "revision": self.hf_revision,
            "license": self.meta.license,
            "downloaded_records": len(cases),
            "status": "REAL",
        }

    # --- shared helpers ------------------------------------------------------

    def sample(
        self, limit: int | None = None, seed: int = 0, source: str = FIXTURE
    ) -> list[EvaluationCase]:
        cases = self.load(source=source)
        if limit is None or limit >= len(cases):
            return cases
        return deterministic_sample(cases, limit, seed, key=lambda c: c.id)

    def validate(self, cases: list[EvaluationCase]) -> None:
        ids = [c.id for c in cases]
        if len(set(ids)) != len(ids):
            raise AdapterError(f"{self.meta.name}: duplicate case ids")
        if not self.meta.source or not self.meta.license:
            raise AdapterError(f"{self.meta.name}: missing source/license metadata")
        hashes = [c.task_hash for c in cases]
        if len(set(hashes)) != len(hashes):
            dupes = len(hashes) - len(set(hashes))
            raise AdapterError(f"{self.meta.name}: {dupes} exact-duplicate task(s)")

    def checksum(self, source: str = FIXTURE) -> str:
        """Stable content checksum over the loaded cases (order-independent)."""
        payload = sorted(c.task_hash for c in self.load(source=source))
        return hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest()[:16]

    def describe(self) -> dict:
        m = self.meta
        real_ok, real_reason = self.real_availability()
        return {
            "name": m.name,
            "version": m.version,
            "license": m.license,
            "source": m.source,
            "availability": self.availability().value,
            "real_available": real_ok,
            "real_reason": real_reason,
            "hf_repo": self.hf_repo,
            "requires_network": m.requires_network,
            "requires_docker": m.requires_docker,
            "languages": list(m.languages),
        }
