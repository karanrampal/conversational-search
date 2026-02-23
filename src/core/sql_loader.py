"""SQL query loader with variable substitution."""

import logging
import string
from pathlib import Path
from typing import Any

from google.cloud import bigquery

logger = logging.getLogger(__name__)


def load_sql_template(file_path: str | Path, params: dict[str, Any]) -> str:
    """Load a SQL file and substitute variables using string.Template.

    Args:
        file_path (str | Path): Path to the SQL file.
        params (dict[str, Any]): Dictionary of parameters to substitute.

    Returns:
        str: The formatted SQL query.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {file_path}")

    with open(path, encoding="utf-8") as f:
        template = string.Template(f.read())

    return template.substitute(params)


def get_bq_data(project_id: str, location: str, query: str) -> bigquery.table.RowIterator:
    """Fetch data from BigQuery.

    Args:
        project_id (str): GCP project ID.
        location (str): GCP location.
        query (str): SQL query to execute.

    Returns:
        An iterator over the query results.
    """
    bq_client = bigquery.Client(project=project_id, location=location)
    bq_itr = bq_client.query(query).result()
    return bq_itr
