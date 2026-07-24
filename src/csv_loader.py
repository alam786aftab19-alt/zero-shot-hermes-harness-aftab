"""CSV loading utilities for the agent."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
from typing import Dict

UPLOAD_DIR = Path("data/uploads")


def load_dataframes(dataset_id: str) -> Dict[str, pd.DataFrame]:
    """Load all CSV files for the given dataset_id into DataFrames."""
    dataset_dir = UPLOAD_DIR / dataset_id
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset {dataset_id} not found")
    dataframes = {}
    for csv_path in dataset_dir.glob("*.csv"):
        df = pd.read_csv(csv_path)
        table_name = csv_path.stem
        dataframes[table_name] = df
    if not dataframes:
        raise ValueError(f"No CSV files found in dataset {dataset_id}")
    return dataframes


def get_schema(dataframes: Dict[str, pd.DataFrame]) -> str:
    """Generate a text description of the schemas for LLM prompts."""
    lines = []
    for name, df in dataframes.items():
        lines.append(f"Table: {name}")
        lines.append("Columns:")
        for col, dtype in zip(df.columns, df.dtypes):
            lines.append(f"- {col} ({dtype})")
        lines.append("")
    return "\n".join(lines)
