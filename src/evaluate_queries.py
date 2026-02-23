#!/usr/bin/env python
"""Script to evaluate user queries from a CSV file."""

import argparse
import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from agents.hm_parallel_agent import create_hm_parallel_agent
from core.config import AppConfig, load_config
from core.logger import setup_logger
from core.runner import AgentRunner

logger = logging.getLogger(__name__)


def check_positive_int(value: str) -> int:
    """Checks if the value is a positive integer.

    Args:
        value (str): The value to check.
    """
    ivalue = int(value)
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"{value} is an invalid positive int value")
    return ivalue


def check_non_negative_float(value: str) -> float:
    """Checks if the value is a non-negative float.

    Args:
        value (str): The value to check.
    """
    fvalue = float(value)
    if fvalue < 0:
        raise argparse.ArgumentTypeError(f"{value} must be non-negative")
    return fvalue


def args_parser() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(description="Evaluate H&M agent with queries from CSV.")

    parser.add_argument(
        "-c",
        "--cfg-path",
        type=str,
        default="./configs/config.yaml",
        help="Configuration file path.",
    )
    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        default="data/queries.csv",
        help="Path to the input CSV file containing queries.",
    )
    parser.add_argument(
        "-o",
        "--output-file",
        type=str,
        default="data/evaluation_results.xlsx",
        help="Path to the output excel file for results.",
    )
    parser.add_argument(
        "-m",
        "--max-concurrent",
        type=check_positive_int,
        default=1,
        help="Maximum number of concurrent requests.",
    )
    parser.add_argument(
        "-r",
        "--requests-per-second",
        type=check_non_negative_float,
        default=0.0,
        help="Maximum number of requests per second (0 for no limit).",
    )
    parser.add_argument(
        "--log-steps",
        type=int,
        default=10,
        help="Log progress every N steps.",
    )
    parser.add_argument(
        "--warmup-count",
        type=int,
        default=3,
        help="Number of warm-up queries to run before evaluation.",
    )
    return parser.parse_args()


def read_input_data(file_path: str) -> pd.DataFrame:
    """Reads input data from a CSV file using pandas.

    Args:
        file_path (str): Path to the CSV file.

    Returns:
        pd.DataFrame: DataFrame containing the queries.
    """
    path = Path(file_path)
    if not path.exists():
        logger.error("Input file not found: %s", file_path)
        raise FileNotFoundError(f"Input file not found: {file_path}")

    try:
        df = pd.read_csv(path)
        if "user_queries" not in df.columns:
            raise ValueError("Input CSV must have a 'user_queries' column.")
        return df
    except Exception as e:
        logger.exception("Error reading input file: %s", e)
        raise


def save_results(results: list[dict[str, Any]], file_path: str) -> None:
    """Saves evaluation results to a CSV file using pandas.

    Args:
        results (list[dict[str, Any]]): List of result dictionaries.
        file_path (str): Path to the output CSV file.
    """
    if not results:
        logger.warning("No results to save.")
        return

    try:
        df = pd.DataFrame(results)
        output_path = Path(file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(output_path, index=False)
        logger.info("Results saved to %s", file_path)
    except Exception as e:
        logger.exception("Error saving results: %s", e)
        raise


@dataclass
class EvaluationConfig:
    """Configuration for the evaluation process."""

    max_concurrent: int
    requests_per_second: float
    log_steps: int
    warmup_count: int


@dataclass
class ExecutionContext:
    """Context for query execution."""

    semaphore: asyncio.Semaphore
    rate_limiter: asyncio.Queue[None] | None
    progress_counter: list[int]
    total_queries: int
    log_steps: int


async def process_single_query(
    runner: AgentRunner,
    query: str,
    configs: AppConfig,
    context: ExecutionContext,
) -> dict[str, Any]:
    """Processes a single query with concurrency control.

    Args:
        runner (AgentRunner): The agent runner instance.
        query (str): The user query to process.
        configs (AppConfig): The loaded configuration.
        context (ExecutionContext): The execution context.

    Returns:
        dict[str, Any]: The result dictionary including latency and response.
    """
    if context.rate_limiter:
        await context.rate_limiter.get()

    async with context.semaphore:
        logger.debug("Processing query: %s", query)
        start_time = time.perf_counter()
        try:
            response = await runner.run(
                user_id=f"eval-user-{uuid.uuid4()}",
                session_id=str(uuid.uuid4()),
                query=query,
                country_name=configs.project.country_name,
                cur_date=datetime.now().strftime("%Y-%m-%d"),
                num_queries=configs.project.num_queries,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error processing query '%s': %s", query, e)
            response = json.dumps({"error": f"ERROR: {e}"})

        end_time = time.perf_counter()
        latency = end_time - start_time

        context.progress_counter[0] += 1
        if (
            context.progress_counter[0] % context.log_steps == 0
            or context.progress_counter[0] == context.total_queries
        ):
            logger.info(
                "Progress: %d/%d queries completed.\n",
                context.progress_counter[0],
                context.total_queries,
            )

        try:
            response_dict = json.loads(response)
        except json.JSONDecodeError:
            response_dict = {"raw_response": response}

        return {"query": query, "latency_seconds": latency} | response_dict


async def rate_limit_producer(queue: asyncio.Queue, rate: float, total: int) -> None:
    """Produces tokens into the queue at a specific rate.

    Args:
        queue (asyncio.Queue): The queue to put tokens into.
        rate (float): The rate (tokens per second).
        total (int): Total number of tokens to produce.
    """
    interval = 1.0 / rate
    for _ in range(total):
        await queue.put(None)
        await asyncio.sleep(interval)


async def run_warmup(
    valid_queries: list[str], warmup_count: int, runner: AgentRunner, configs: AppConfig
) -> None:
    """Runs warm-up queries to initialize the agent.

    Args:
        valid_queries (list[str]): List of valid queries.
        warmup_count (int): Number of warm-up queries to run.
        runner (AgentRunner): The agent runner instance.
        configs (AppConfig): The loaded configuration.
    """
    if warmup_count > 0 and valid_queries:
        logger.info("Running %d warm-up queries...", warmup_count)
        warmup_subset = random.sample(valid_queries, min(warmup_count, len(valid_queries)))
        for i, query in enumerate(warmup_subset, 1):
            logger.debug("Warm-up %d/%d: %s", i, len(warmup_subset), query)
            try:
                await runner.run(
                    user_id=f"warmup-user-{uuid.uuid4()}",
                    session_id=str(uuid.uuid4()),
                    query=query,
                    country_name=configs.project.country_name,
                    cur_date=datetime.now().strftime("%Y-%m-%d"),
                    num_queries=configs.project.num_queries,
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Warm-up query failed: %s", e)
        logger.info("Warm-up complete. Starting main evaluation...\n")


def create_execution_context(
    eval_config: EvaluationConfig, total_queries: int
) -> tuple[ExecutionContext, asyncio.Queue[None] | None]:
    """Creates the execution context and rate limiter."""
    semaphore = asyncio.Semaphore(eval_config.max_concurrent)
    rate_limiter: asyncio.Queue[None] | None = (
        asyncio.Queue() if eval_config.requests_per_second > 0 else None
    )
    progress_counter = [0]

    context = ExecutionContext(
        semaphore=semaphore,
        rate_limiter=rate_limiter,
        progress_counter=progress_counter,
        total_queries=total_queries,
        log_steps=eval_config.log_steps,
    )
    return context, rate_limiter


def calculate_and_log_stats(results: list[dict[str, Any]]) -> None:
    """Calculates and logs statistics for the evaluation results."""
    total_latency = sum(r["latency_seconds"] for r in results)
    query_count = len(results)

    if query_count > 0:
        avg_latency = total_latency / query_count
        logger.info("Evaluation complete. Processed %d queries.", query_count)
        logger.info("Average Latency: %.4f seconds", avg_latency)
        results.append({"query": "AVERAGE", "latency_seconds": avg_latency})
    else:
        logger.warning("No valid queries processed.")


async def process_queries(
    queries: list[str],
    config_path: str,
    eval_config: EvaluationConfig,
) -> list[dict[str, Any]]:
    """Runs queries against the agent and returns results.

    Args:
        queries (list[str]): List of user queries.
        config_path (str): Path to the agent configuration.
        eval_config (EvaluationConfig): Configuration for evaluation.

    Returns:
        list[dict[str, Any]]: List of evaluation results.
    """
    try:
        configs = load_config(config_path)
    except FileNotFoundError as e:
        logger.exception("Failed to load configuration: (%s: %s) ", type(e).__name__, e)
        return []

    logger.info("Initializing HM Agent...")
    runner = AgentRunner(agent=create_hm_parallel_agent(configs), app_name="HM-Eval-App")

    valid_queries = [str(q).strip() for q in queries if str(q).strip()]

    await run_warmup(valid_queries, eval_config.warmup_count, runner, configs)

    logger.info(
        "Starting evaluation of %d queries (max_concurrent=%d, rps=%.1f)...\n",
        len(queries),
        eval_config.max_concurrent,
        eval_config.requests_per_second,
    )

    total_queries = len(valid_queries)
    context, rate_limiter = create_execution_context(eval_config, total_queries)

    if rate_limiter:
        asyncio.create_task(
            rate_limit_producer(rate_limiter, eval_config.requests_per_second, total_queries)
        )

    tasks = [process_single_query(runner, query, configs, context) for query in valid_queries]

    results = await asyncio.gather(*tasks)

    calculate_and_log_stats(results)

    return results


async def main() -> None:
    """Main function to orchestrate the evaluation."""
    setup_logger(keep_loggers=["__main__"])
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    args = args_parser()

    eval_config = EvaluationConfig(
        max_concurrent=args.max_concurrent,
        requests_per_second=args.requests_per_second,
        log_steps=args.log_steps,
        warmup_count=args.warmup_count,
    )

    try:
        logger.info("Reading input data from %s...", args.input_file)
        df = read_input_data(args.input_file)
        queries = df["user_queries"].tolist()

        results = await process_queries(
            queries,
            args.cfg_path,
            eval_config,
        )

        logger.info("Saving results to %s...", args.output_file)
        save_results(results, args.output_file)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Evaluation failed: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
