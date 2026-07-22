"""Source adapters for local and cloud retail tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, cast

import pandas as pd


class RetailTableAdapter(Protocol):
    """Protocol implemented by source systems that expose named tables."""

    def read_table(self, table_name: str) -> pd.DataFrame:
        """Return one source table as a pandas data frame."""


class LocalFileRetailAdapter:
    """Read source tables from a directory of CSV or Parquet files."""

    def __init__(self, root: Path, *, extension: str = "csv") -> None:
        self.root = root
        self.extension = extension.lstrip(".")

    def read_table(self, table_name: str) -> pd.DataFrame:
        """Read a table from `<root>/<table_name>.<extension>`."""
        path = self.root / f"{table_name}.{self.extension}"
        if not path.exists():
            raise FileNotFoundError(path)
        if self.extension == "csv":
            return pd.read_csv(path)
        if self.extension == "parquet":
            return pd.read_parquet(path)
        raise ValueError(f"Unsupported table extension: {self.extension}")


class BigQueryRetailAdapter:
    """Read source tables from BigQuery through an injected client."""

    def __init__(self, client: Any, *, project: str, dataset: str) -> None:
        self.client = client
        self.project = project
        self.dataset = dataset

    def read_table(self, table_name: str) -> pd.DataFrame:
        """Read a BigQuery table using the client's query interface."""
        query = f"select * from `{self.project}.{self.dataset}.{table_name}`"
        return cast(pd.DataFrame, self.client.query(query).to_dataframe())


__all__ = ["BigQueryRetailAdapter", "LocalFileRetailAdapter", "RetailTableAdapter"]
