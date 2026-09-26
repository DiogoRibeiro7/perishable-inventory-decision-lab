"""Translate failures at file boundaries while retaining their original causes."""

from __future__ import annotations

import json
import pickle
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml
from dataexcept import DataLoadingError, FileWriteError


@contextmanager
def loading(path: str | Path) -> Iterator[None]:
    """Attach the source path to read, decoding, and format errors."""
    try:
        yield
    except (
        OSError,
        UnicodeError,
        pd.errors.ParserError,
        yaml.YAMLError,
        json.JSONDecodeError,
        pickle.UnpicklingError,
        EOFError,
    ) as exc:
        raise DataLoadingError(str(path), exc) from exc


@contextmanager
def writing(path: str | Path) -> Iterator[None]:
    """Attach the destination path to filesystem and encoding errors."""
    try:
        yield
    except (OSError, UnicodeError) as exc:
        raise FileWriteError(str(path), exc) from exc


def read_csv(path: str | Path, **kwargs: Any) -> pd.DataFrame:
    """Read CSV data while preserving the source of an operational failure."""
    with loading(path):
        return cast(pd.DataFrame, pd.read_csv(path, **kwargs))


def read_parquet(path: str | Path, **kwargs: Any) -> pd.DataFrame:
    """Read Parquet data while preserving the source of an operational failure."""
    with loading(path):
        return pd.read_parquet(path, **kwargs)


def create_directory(path: Path) -> None:
    """Create an artifact directory or report its failed destination."""
    with writing(path):
        path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    """Write a UTF-8 text artifact or report its failed destination."""
    with writing(path):
        path.write_text(content, encoding="utf-8")


def write_csv(frame: pd.DataFrame, path: Path, **kwargs: Any) -> None:
    """Write a CSV artifact or report its failed destination."""
    with writing(path):
        frame.to_csv(path, index=False, **kwargs)
