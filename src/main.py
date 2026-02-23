#!/usr/bin/env python
"""Test LLM agent using cli input query"""

import argparse
import asyncio
import json
import logging
from datetime import datetime

from agents.hm_parallel_agent import create_hm_parallel_agent
from core.config import load_config
from core.logger import setup_logger
from core.runner import AgentRunner

logger = logging.getLogger(__name__)


def args_parser() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(description="Test the H&M agent.")

    parser.add_argument(
        "-c",
        "--config-path",
        type=str,
        default="configs/config.yaml",
        help="Path to the configuration YAML file.",
    )
    parser.add_argument(
        "-q",
        "--question",
        type=str,
        default="i need something for an interview.",
        help="The user query to test the agent with.",
    )
    return parser.parse_args()


async def main() -> None:
    """Main function to test the query moderator agent asynchronously."""
    setup_logger(logging.DEBUG)
    args = args_parser()

    try:
        configs = load_config(args.config_path)
    except FileNotFoundError as e:
        logger.exception("Failed to load configuration: (%s: %s) ", type(e).__name__, e)
        return

    logger.info("Starting HM Agent Test...")
    hm_agent = create_hm_parallel_agent(configs)

    cur_date = datetime.now().strftime("%Y-%m-%d")
    app_name = "HM-App"
    user_id = "karan-test"
    session_id = f"session-{user_id}-{app_name}-{cur_date}"

    runner = AgentRunner(agent=hm_agent, app_name=app_name)

    logger.info("Testing Agent ...")
    response = await runner.run(
        user_id=user_id,
        session_id=session_id,
        query=args.question,
        country_name=configs.project.country_name,
        cur_date=cur_date,
        num_queries=configs.project.num_queries,
    )
    logger.info("Final Response: %s", response)

    while False:  # Change to True to enable interactive follow-up questions
        user_input = input("\nEnter follow-up question (or 'exit' to quit): ")
        if user_input.lower() in ("exit", "quit"):
            break

        response = await runner.run(
            user_id=user_id,
            session_id=session_id,
            query=user_input,
        )
        logger.info("Final Response: %s", response)

    state = await runner.get_session_state(user_id=user_id, session_id=session_id)
    logger.debug("Session state: %s", json.dumps(state, indent=2))

    history = await runner.get_session_history(user_id=user_id, session_id=session_id)
    logger.debug("Session history: %s", history)


if __name__ == "__main__":
    asyncio.run(main())
