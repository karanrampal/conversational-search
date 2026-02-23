"""Module for creating a Query Router Agent."""

import logging
from typing import Literal

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

from agents.base import AgentDefinition, create_agent
from core.config import AgentConfig

logger = logging.getLogger(__name__)


ROUTER_SYSTEM_INSTRUCTION = """You are an agent that routes/maps user queries to the correct product
group based on gender and age/size. Use the following product group and their descriptions to output
the group.

# Product groups: descriptions
- ladies: Women's clothing
- men: Men's clothing
- boy_50_98: Boys clothing sizes 50-98cm (babies and toddlers up to ~3 years)
- boy_92_140: Boys clothing sizes 92-140cm (children ~3-10 years)
- boy_134_170: Boys clothing sizes 134-170cm (older children/teens ~10-16 years)
- girl_50_98: Girls clothing sizes 50-98cm (babies and toddlers up to ~3 years)
- girl_92_140: Girls clothing sizes 92-140cm (children ~3-10 years) [use if the query mentions kids without specifying age/size]
- girl_134_170: Girls clothing sizes 134-170cm (older children/teens ~10-16 years)

# Additional instructions
- If the user only mentions kids without providing age or size details, return 'girl_92_140'.
- If unsure, default to 'ladies'.

# Response format
Return a JSON object with a single string field 'group' and nothing else.
"""  # noqa: E501


class QueryRouterOutput(BaseModel):
    """Response schema for query_router_agent."""

    group: Literal[
        "ladies",
        "men",
        "boy_50_98",
        "boy_92_140",
        "boy_134_170",
        "girl_50_98",
        "girl_92_140",
        "girl_134_170",
    ] = Field(
        default="ladies",
        description="Group to which the user query maps to. It will be one of these only 'ladies',"
        " 'men', 'boy_50_98', 'boy_92_140', 'boy_134_170', 'girl_50_98', 'girl_92_140',"
        " 'girl_134_170'",
    )


def create_router_agent(agent_config: AgentConfig) -> LlmAgent:
    """Creates the Query Router Agent.
    Args:
        agent_config (AgentConfig): Configuration for the agent.
    Returns:
        LlmAgent: Configured Query Router Agent.
    """
    return create_agent(
        agent_config=agent_config,
        agent_definition=AgentDefinition(
            name="query_router_agent",
            description="Maps user queries to the correct product group.",
            output_schema=QueryRouterOutput,
            output_key="query_router_output",
            instruction=ROUTER_SYSTEM_INSTRUCTION,
        ),
    )
