# pylint: disable=duplicate-code
"""Custom implementation of a parallel llm agent for H&M."""

import json
import logging
from collections.abc import AsyncGenerator
from typing import cast, override

from google.adk.agents import BaseAgent, LlmAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events.event import Event, EventActions
from google.genai import types

from agents.expander import create_expander_agent
from agents.moderator import create_moderator_agent
from agents.router import create_router_agent
from core.config import AppConfig

logger = logging.getLogger(__name__)


class HMParallelAgent(BaseAgent):  # pylint: disable=abstract-method
    """An agent that will check if the moderate the query, expand the query and route the query in
    parallel (async).
    """

    moderator_agent: LlmAgent
    expander_agent: LlmAgent
    router_agent: LlmAgent
    parallel_agent: ParallelAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,  # pylint: disable=unused-argument
        moderator_agent: LlmAgent,
        expander_agent: LlmAgent,
        router_agent: LlmAgent,
    ):
        parallel_agent = ParallelAgent(
            name="parallel_agent",
            description="Runs moderator, expander and router agents in parallel.",
            sub_agents=[moderator_agent, expander_agent, router_agent],
        )
        sub_agent_lists: list[BaseAgent] = [parallel_agent]

        super().__init__(
            name="hm_agent",
            description="H&M Shopping assistant that will moderate, expand and route user queries.",
            moderator_agent=moderator_agent,
            expander_agent=expander_agent,
            router_agent=router_agent,
            parallel_agent=parallel_agent,
            sub_agents=sub_agent_lists,
        )  # type: ignore [call-arg]

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        logger.info("%s: Starting execution.", self.name)

        query_moderator_output: dict[str, bool] = {}
        query_expander_output: dict[str, list[str]] = {}
        query_router_output: dict[str, str] = {}

        async for event in self.parallel_agent.run_async(ctx):
            logger.debug(
                "[%s] Event from parallel_agent: %s",
                self.name,
                event.model_dump_json(indent=2, exclude_none=True),
            )
            if event.actions and event.actions.state_delta:
                if "query_moderator_output" in event.actions.state_delta:
                    query_moderator_output = cast(
                        dict[str, bool], event.actions.state_delta["query_moderator_output"]
                    )
                if "query_expander_output" in event.actions.state_delta:
                    query_expander_output = cast(
                        dict[str, list[str]], event.actions.state_delta["query_expander_output"]
                    )
                if "query_router_output" in event.actions.state_delta:
                    query_router_output = cast(
                        dict[str, str], event.actions.state_delta["query_router_output"]
                    )

        if not query_moderator_output or not query_expander_output or not query_router_output:
            logger.error(
                "%s: Missing 'query_moderator_output' or 'query_expander_output' or"
                " 'query_router_output' after parallel_agent run.",
                self.name,
            )
            # We might want to stop even if one is missing, but for now let's log error and continue
            # return

        logger.info(
            "%s: Retrieved 'query_moderator_output': %s",
            self.name,
            json.dumps(query_moderator_output, indent=2),
        )
        logger.info(
            "%s: Retrieved 'query_expander_output': %s",
            self.name,
            json.dumps(query_expander_output, indent=2),
        )
        logger.info(
            "%s: Retrieved 'query_router_output': %s",
            self.name,
            json.dumps(query_router_output, indent=2),
        )
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=(
                            json.dumps(
                                query_moderator_output | query_expander_output | query_router_output
                            )
                        )
                    )
                ],
            ),
            actions=EventActions(
                state_delta={
                    "query_moderator_output": query_moderator_output,
                    "query_expander_output": query_expander_output,
                    "query_router_output": query_router_output,
                }
            ),
        )
        logger.info("%s: Finished execution.", self.name)


def create_hm_parallel_agent(agent_config: AppConfig) -> HMParallelAgent:
    """Creates the H&M Agent.
    Args:
        agent_config (AppConfig): Configuration for the agent.
    Returns:
        HMParallelAgent: Configured H&M Parallel Agent.
    """
    return HMParallelAgent(
        name="hm_agent",
        moderator_agent=create_moderator_agent(agent_config.agents["query_moderator"]),
        expander_agent=create_expander_agent(agent_config.agents["query_expander"]),
        router_agent=create_router_agent(agent_config.agents["query_router"]),
    )
