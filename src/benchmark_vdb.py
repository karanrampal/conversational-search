#!/usr/bin/env python
# pylint: disable=duplicate-code
"""Script to embed text and search in vector database."""

import argparse
import asyncio
import logging
import random
import statistics
import sys
import time
from dataclasses import dataclass

from core.config import load_config
from core.logger import setup_logger
from database.qdrant_manager import QdrantManager
from embeddings.text_embeddings import TextEmbeddingsGen

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkArgs:
    """Dataclass to hold benchmark arguments."""

    runs: int
    warmup: int
    concurrency: int


def args_parser() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Embed question and search in vector database.")
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
        "-q",
        "--question",
        type=str,
        default="Do you have any red t-shirts?",
        help="Question to embed and search",
    )
    parser.add_argument(
        "-b",
        "--benchmark",
        action="store_true",
        help="Run latency benchmark",
    )
    parser.add_argument(
        "-r",
        "--runs",
        type=int,
        default=100,
        help="Number of runs for benchmark",
    )
    parser.add_argument(
        "-w",
        "--warmup",
        type=int,
        default=3,
        help="Number of warmup runs before benchmark",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent requests",
    )
    parser.add_argument(
        "-s",
        "--synthetic-query",
        action="store_true",
        help="Use synthetic (random) vectors instead of generating embeddings via Vertex AI",
    )

    args = parser.parse_args()

    if args.runs <= 0:
        parser.error("Number of runs must be a positive integer.")
    if args.warmup < 0:
        parser.error("Number of warmup runs cannot be negative.")
    if args.concurrency < 1:
        parser.error("Concurrency must be at least 1.")
    return args


async def run_benchmark(
    qm_: QdrantManager,
    collection_name: str,
    embedding: list[float],
    benchmark_args: BenchmarkArgs,
) -> None:
    """Run latency benchmark for Qdrant search.

    Args:
        qm_ (QdrantManager): Qdrant manager instance.
        collection_name (str): Name of the collection.
        embedding (list[float]): Query embedding vector.
        benchmark_args (BenchmarkArgs): Benchmark arguments including runs, warmup, and concurrency.
    """
    if benchmark_args.warmup > 0:
        logger.info("Performing %d warmup runs...", benchmark_args.warmup)
        for _ in range(benchmark_args.warmup):
            await qm_.search_points(
                collection_name=collection_name,
                query=embedding,
                vector_name="image",
                limit=3,
            )

    logger.info(
        "Starting benchmark with %d runs (concurrency=%d)...",
        benchmark_args.runs,
        benchmark_args.concurrency,
    )

    sem = asyncio.Semaphore(benchmark_args.concurrency)

    async def task_wrapper() -> float:
        async with sem:
            start_time = time.perf_counter()
            await qm_.search_points(
                collection_name=collection_name,
                query=embedding,
                vector_name="image",
                limit=3,
            )
            end_time = time.perf_counter()
            return (end_time - start_time) * 1000

    tasks = [task_wrapper() for _ in range(benchmark_args.runs)]
    latencies = []

    for i, coro in enumerate(asyncio.as_completed(tasks)):
        latency = await coro
        latencies.append(latency)
        if (i + 1) % 10 == 0 or (i + 1) == benchmark_args.runs:
            print(f"Completed {i + 1}/{benchmark_args.runs} runs", end="\r", flush=True)

    print("\n")
    mean_latency = statistics.mean(latencies)
    p95 = statistics.quantiles(latencies, n=20)[18]
    p99 = statistics.quantiles(latencies, n=100)[98]

    logger.info("Benchmark Results (ms):")
    logger.info("Average Latency: %.2f ms", mean_latency)
    logger.info("P95 Latency:     %.2f ms", p95)
    logger.info("P99 Latency:     %.2f ms", p99)


async def main() -> None:
    """Main function to test vector embeddings"""
    args = args_parser()

    setup_logger(exclude_loggers=["httpx", "database.qdrant_manager"])

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

    tmp = await qm_.list_collections()
    logger.info("Available collections in Qdrant: %s", tmp)

    collection_name = qdb_config.collection_name or args.collection_name

    if args.synthetic_query:
        logger.info("Using synthetic query embedding (dimension: 1408)")
        embedding = [random.uniform(-1.0, 1.0) for _ in range(1408)]
    else:
        te_client = TextEmbeddingsGen(project="hm-contextual-search-f3d5", location="europe-west1")
        embedding = await te_client.get_multimodal_text_embeddings(args.question)

    logger.info("Embedding length for the question '%s' : %s", args.question, len(embedding))

    if args.benchmark:
        await run_benchmark(
            qm_,
            collection_name,
            embedding,
            BenchmarkArgs(runs=args.runs, warmup=args.warmup, concurrency=args.concurrency),
        )

    else:
        res = await qm_.search_points(
            collection_name=collection_name,
            query=embedding,
            vector_name="image",
            limit=3,
        )
        for item in res:
            logger.info("Found point ID: %s with score: %s", item.id, item.score)


if __name__ == "__main__":
    asyncio.run(main())
