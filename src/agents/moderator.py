"""Module for creating a Query Moderator Agent."""

import logging

from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

from agents.base import AgentDefinition, create_agent
from core.config import AgentConfig

logger = logging.getLogger(__name__)


MODERATOR_SYSTEM_INSTRUCTION = """You are an agent that checks for unsafe content. Use the following
guidelines to determine if the input query contains any prohibited topics:

# Prohibited topics: descriptions
- Sexual Content: Content that is sexually explicit in nature.
- Hate Speech: Content that promotes violence, incites hatred, promotes discrimination, or
  disparages on the basis of race or ethnic origin, religion, disability, age, nationality, veteran 
  status, sexual orientation, sex, gender, gender identity, caste, immigration status, or any other
  characteristic that is associated with systemic discrimination or marginalization.
- Harassment and Bullying: Content that is malicious, intimidating, bullying, or abusive towards
  another individual.
- Dangerous Content: Content that facilitates, promotes, or enables access to harmful goods,
  services, and activities.
- Toxic Content: Content that is rude, disrespectful, or unreasonable.
- Derogatory Content: Content that makes negative or harmful comments about any individual or group
  based on their identity or protected attributes.
- Violent Content: Content that describes scenarios that depict violence, gore, or harm against
  individuals or groups.
- Insults: Content that may be insulting, inflammatory, or negative towards any person or group.
- Profanity: Content that includes obscene or vulgar language.
- Illegal: Content that assists in illegal activities such as malware creation, fraud, spam
  generation, or spreading misinformation.
- Death, Harm & Tragedy: Content that includes detailed descriptions of human deaths, tragedies,
  accidents, disasters, and self-harm.
- Firearms & Weapons: Content that promotes firearms, weapons, or related accessories
  unless absolutely necessary and in a safe and responsible context.

# Response format
Return a JSON object with a single boolean field 'block' and nothing else.
"""


class QueryModeratorOutput(BaseModel):
    """Response schema for query_moderator_agent."""

    block: bool = Field(default=False, description="True if the query contains prohibited topics")


def create_moderator_agent(agent_config: AgentConfig) -> LlmAgent:
    """Creates the Query Moderator Agent.
    Args:
        agent_config (AgentConfig): Configuration for the agent.
    Returns:
        LlmAgent: Configured Query Moderator Agent.
    """
    return create_agent(
        agent_config=agent_config,
        agent_definition=AgentDefinition(
            name="query_moderator_agent",
            description=(
                "Moderates user queries by checking if they contain harmful or unsafe content."
            ),
            output_schema=QueryModeratorOutput,
            output_key="query_moderator_output",
            instruction=MODERATOR_SYSTEM_INSTRUCTION,
        ),
    )
