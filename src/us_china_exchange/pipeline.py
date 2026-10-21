"""Revision-aware refreshes and deterministic, offline publication inputs."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .model import coverage, digest, json_text, key, validate
from .sources import ADAPTERS


class SourceUnavailable(RuntimeError):
    pass


class Client:
    def __init__(self, cache, now=None):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.now = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers["User-Agent"] = "BilateralExchangeResearch/1.0 (public aggregate statistics)"
        self.assets = []

    def get(self, url, params=None):
        try:
            response = self.session.get(url, params=params, timeout=(20, 90))
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SourceUnavailable(str(exc)) from exc
        content = response.content
        checksum = digest(content)
        path = self.cache / checksum
        if not path.exists():
            path.write_bytes(content)
        asset = {"url": response.url, "sha256": checksum, "retrieved_at": self.now}
        self.assets.append(asset)
        return content, asset

    @staticmethod
    def json(content):
        try:
            return json.loads(content)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Source returned invalid JSON, not a statistical response") from exc


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def stable_rows(rows):
    return [{k: v for k, v in row.items() if k not in {"retrieved_at", "raw_sha256"}} for row in rows]


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    binary = isinstance(text, bytes)
    with tempfile.NamedTemporaryFile(mode="wb" if binary else "w", dir=path.parent, delete=False,
                                     **({} if binary else {"encoding": "utf-8"})) as handle:
        handle.write(text)
        temporary = handle.name
    os.replace(temporary, path)


def refresh(root, adapters=None, client=None):
    root = Path(root)
    output = root / "data/site"
    old_rows = load(output / "observations.json", [])
    previous = load(output / "sources.json", {})
    client = client or Client(root / "data/local/exchange/raw")
    adapters = ADAPTERS if adapters is None else adapters
    rows = [r for r in old_rows if r["source_id"] not in adapters]
    manifests = {sid: manifest for sid, manifest in previous.items() if sid not in adapters}
    checks = {}
    for source_id, adapter in adapters.items():
        old = [r for r in old_rows if r["source_id"] == source_id]
        prior = previous.get(source_id, {})
        try:
            candidate, vintage, notes = adapter(client)
            if not candidate:
                raise ValueError(source_id + " returned an empty candidate")
            if any(r["source_id"] != source_id for r in candidate):
                raise ValueError("Adapter returned another source's observations")
            candidate = validate(candidate)
            # Rolling publication tables must not erase previously verified history.
            merged = {key(r): r for r in old}
            merged.update({key(r): r for r in candidate})
            candidate = validate(list(merged.values()))
            changed = stable_rows(candidate) != stable_rows(sorted(old, key=key))
            if not changed:
                candidate = old
            rows.extend(candidate)
            manifest = {
                "status": "available", "vintage": vintage, "notes": notes,
                "last_successful_retrieval": client.now if changed else prior.get(
                    "last_successful_retrieval", client.now),
                "last_recorded_check": client.now,
                "observations": len(candidate),
            }
            meaningful = changed or any(prior.get(k) != manifest[k]
                                        for k in ["status", "vintage", "notes"])
            manifests[source_id] = manifest if meaningful else prior
            checks[source_id] = {"status": "available", "checked_at": client.now,
                                 "changed": meaningful}
        except SourceUnavailable as exc:
            rows.extend(old)
            manifest = dict(prior, status="degraded" if old else "unavailable",
                            error=str(exc), last_recorded_check=client.now,
                            observations=len(old))
            if prior.get("status") == manifest["status"] and prior.get("error") == str(exc):
                manifest = prior
            manifests[source_id] = manifest
            checks[source_id] = {"status": manifest["status"], "checked_at": client.now,
                                 "error": str(exc)}
        except Exception as exc:
            checks[source_id] = {"status": "invalid_candidate", "checked_at": client.now,
                                 "error": str(exc)}
            write_atomic(root / "data/local/exchange/check.json", json_text({
                "checked_at": client.now, "publication_changed": False,
                "publication_blocked": True, "sources": checks}))
            raise
    rows = validate(rows)
    for row in rows:
        if not all(row.get(k) for k in ["source_url", "raw_sha256", "retrieved_at", "source_vintage"]):
            raise ValueError("Observation provenance incomplete")
    files = {"observations.json": rows, "sources.json": manifests,
             "coverage.json": coverage(rows)}
    # No candidate publication files are touched until every parser and validator succeeds.
    changed = False
    for filename, value in files.items():
        text = json_text(value)
        path = output / filename
        if not path.exists() or path.read_text() != text:
            write_atomic(path, text)
            changed = True
    report = {"checked_at": client.now, "publication_changed": changed, "sources": checks}
    write_atomic(root / "data/local/exchange/check.json", json_text(report))
    return report
