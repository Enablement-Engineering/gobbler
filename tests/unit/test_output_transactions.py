"""Tests for atomic output transactions used by frame manifests."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from gobbler_cli.output import AtomicOutputTransaction, persist_text_transactionally


def test_stdout_transaction_buffers_until_finalize(capsys: pytest.CaptureFixture[str]) -> None:
    """Success stdout is invisible until the associated frame commit succeeds."""
    transaction = persist_text_transactionally("success payload", None)

    assert capsys.readouterr().out == ""

    transaction.finalize()

    assert capsys.readouterr().out == "success payload\n"


def test_stdout_transaction_rollback_discards_buffer(capsys: pytest.CaptureFixture[str]) -> None:
    """A failed frame commit emits no buffered success payload."""
    transaction = persist_text_transactionally("stale success", None)

    transaction.rollback()
    transaction.finalize()

    assert capsys.readouterr().out == ""


def test_output_transaction_lock_spans_persist_through_finalize(tmp_path: Path) -> None:
    """The canonical output lock prevents concurrent transactions from interleaving."""
    output = tmp_path / "manifest.md"
    output.write_text("previous", encoding="utf-8")
    first = persist_text_transactionally("first", output)
    second_started = threading.Event()
    second_finished = threading.Event()
    second_transaction: list[AtomicOutputTransaction] = []

    def persist_second() -> None:
        second_started.set()
        second_transaction.append(persist_text_transactionally("second", output))
        second_finished.set()

    thread = threading.Thread(target=persist_second)
    thread.start()
    assert second_started.wait(timeout=1)
    time.sleep(0.05)

    assert not second_finished.is_set()
    assert output.read_text(encoding="utf-8") == "first"

    first.finalize()
    thread.join(timeout=1)
    assert second_finished.is_set()
    assert output.read_text(encoding="utf-8") == "second"

    second_transaction[0].rollback()
    assert output.read_text(encoding="utf-8") == "first"


def test_output_transaction_resolves_symlink_target_without_replacing_link(tmp_path: Path) -> None:
    """Atomic persistence updates a canonical file target and preserves its symlink object."""
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    target = target_dir / "manifest.md"
    target.write_text("previous", encoding="utf-8")
    link = tmp_path / "manifest-link.md"
    link.symlink_to(target)

    transaction = persist_text_transactionally("new", link)

    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "new"

    transaction.rollback()

    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "previous"
