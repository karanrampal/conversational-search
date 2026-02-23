#!/usr/bin/env python
"""ETL job to load embeddings to vector database."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from google.cloud import bigquery
from qdrant_client.models import PointStruct

from core.config import load_config
from core.logger import setup_logger
from core.sql_loader import get_bq_data, load_sql_template
from database.qdrant_manager import QdrantManager

logger = logging.getLogger(__name__)


def args_parser() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="ETL job to load embeddings into Qdrant.")
    parser.add_argument(
        "-c", "--config", type=str, default="configs/config.yaml", help="Path to configuration file"
    )
    parser.add_argument(
        "-n",
        "--collection-name",
        type=str,
        default="articles_collection",
        help="Qdrant collection name",
    )
    parser.add_argument(
        "-b", "--batch-size", type=int, default=512, help="Batch size for Qdrant upload"
    )
    parser.add_argument(
        "-v",
        "--vector-size",
        type=int,
        default=1408,
        help="Vector size for the collection",
    )
    parser.add_argument(
        "-r",
        "--replication-factor",
        type=int,
        default=None,
        help="Replication factor for the collection (overrides config)",
    )

    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("Batch size must be a positive integer.")
    if args.vector_size <= 0:
        parser.error("Vector size must be a positive integer.")
    if args.collection_name.strip() == "":
        parser.error("Collection name cannot be empty.")
    if args.replication_factor is not None and args.replication_factor <= 0:
        parser.error("Replication factor must be a positive integer if specified.")

    return args


def mapper(row: bigquery.Row) -> PointStruct:
    """Map a BigQuery row to a Qdrant PointStruct.

    Args:
        row (bigquery.Row): A BigQuery row with 'castor', 'features' and 'groups' fields.
    """
    return PointStruct(
        id=int(row.castor),
        vector={"image": row.features},
        payload={"group": row.groups},
    )


async def main() -> None:
    """Main function to load embeddings to vector database."""
    args = args_parser()

    setup_logger(exclude_loggers=["httpx"])

    try:
        configs = load_config(args.config)
        qdb_config = configs.qdrant
    except FileNotFoundError as e:
        logger.error("Failed to load configuration: (%s: %s) ", type(e).__name__, e)
        sys.exit(1)

    if not qdb_config.api_key.get_secret_value():
        logger.error("QDRANT_API_KEY environment variable is not set.")
        sys.exit(1)

    qm_ = QdrantManager(
        **qdb_config.model_dump(exclude={"collection_name", "api_key", "replication_factor"}),
        api_key=qdb_config.api_key.get_secret_value(),
    )

    collection_name = qdb_config.collection_name or args.collection_name

    logger.info("Checking if collection '%s' exists.", collection_name)
    try:
        if not await qm_.collection_exists(collection_name):
            logger.info("Creating collection '%s'.", collection_name)
            replication_factor = args.replication_factor or qdb_config.replication_factor
            await qm_.create_collection(
                collection_name=collection_name,
                vector_configs={"image": (args.vector_size, "Cosine")},
                replication_factor=replication_factor,
            )

        collection_info = await qm_.get_collection_info(collection_name)
        logger.info("Collection status: %s", collection_info.status)

        sql_path = Path(__file__).parent / "queries" / "extract_vectors.sql"
        query = load_sql_template(
            sql_path,
            {
                "articles_table": configs.embeddings.articles_table,
                "features_table": configs.embeddings.features_table,
            },
        )
        logger.info("Loaded SQL query from %s", sql_path)

        logger.info("Fetching data from BigQuery.")
        bq_itr = get_bq_data(
            project_id=configs.project.id,
            location=configs.project.location,
            query=query,
        )

        logger.info("Starting upload to Qdrant...")
        qm_.upload(
            collection_name=collection_name,
            entities=bq_itr,
            mapper=mapper,
            batch_size=args.batch_size,
        )

        cnt = await qm_.count_points(collection_name=collection_name)
        logger.info("Total points in collection '%s': %s", collection_name, cnt)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("(%s: %s): An error occurred during the ETL process.", type(e).__name__, e)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ETL job interrupted by user.")
        sys.exit(0)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception("(%s: %s): Fatal error in ETL job.", type(e).__name__, e)
        sys.exit(1)
