"""Base module for creating agents."""

import logging
from collections.abc import AsyncGenerator
from typing import Any, override

import litellm
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.planners import BuiltInPlanner
from google.genai import types
from pydantic import BaseModel, PrivateAttr

from core.config import AgentConfig
from core.token_manager import TokenManager

logger = logging.getLogger(__name__)


class AuthenticatedLiteLlm(LiteLlm):  # pylint: disable=abstract-method
    """LiteLlm wrapper that automatically refreshes the authentication token.

    Args:
        token_manager (TokenManager): The token manager to retrieve fresh tokens.
    """

    _token_manager: TokenManager = PrivateAttr()

    def __init__(self, token_manager: TokenManager, **kwargs: Any):
        super().__init__(**kwargs)
        self._token_manager = token_manager

    @override
    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Generates content asynchronously with a fresh token.

        Args:
            llm_request (LlmRequest): The request to send to the model.
            stream (bool): Whether to stream the response.

        Yields:
            LlmResponse: The response from the model.
        """
        self._additional_args["api_key"] = self._token_manager.get_token()
        async for response in super().generate_content_async(llm_request, stream=stream):
            yield response


def register_model(model_name: str) -> None:
    """Registers the model with LiteLLM if not already registered.

    Args:
        model_name (str): Name of the model to register.
    """
    if model_name not in litellm.model_cost:
        logger.info("Registering model '%s' with LiteLLM.", model_name)
        lite_llm_provider = model_name.split("/")[0]
        litellm.model_cost[model_name] = {
            "max_tokens": 8192,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
            "litellm_provider": lite_llm_provider,
            "mode": "chat",
        }


def get_model_client(agent_config: AgentConfig) -> LiteLlm | str:
    """Creates and returns a configured LiteLlm client or model name string.

    Args:
        agent_config (AgentConfig): Configuration for the agent.

    Returns:
        LiteLlm | str: Configured LiteLlm client or model name.
    """
    model_name = agent_config.model_name
    base_url = agent_config.base_url

    # Register model to avoid "not mapped" errors
    register_model(model_name)

    if base_url:
        token_manager = TokenManager(target_audience=base_url)
        return AuthenticatedLiteLlm(
            token_manager=token_manager,
            model=model_name,
            api_base=f"{base_url}/v1",
        )
    return model_name


class AgentDefinition(BaseModel):
    """Definition of an agent's identity and behavior.

    Args:
        name (str): Name of the agent.
        description (str): Description of the agent.
        output_schema (Type[BaseModel]): Pydantic model for the output schema.
        output_key (str): Key to store the output in the session state.
        instruction (str): Instruction for the agent.
    """

    name: str
    description: str
    output_schema: type[BaseModel]
    output_key: str
    instruction: str


def create_agent(
    agent_config: AgentConfig,
    agent_definition: AgentDefinition,
) -> LlmAgent:
    """Creates a configured LlmAgent.

    Args:
        agent_config (AgentConfig): Configuration for the agent.
        agent_definition (AgentDefinition): Definition of the agent.

    Returns:
        LlmAgent: Configured LlmAgent.
    """
    model_client = get_model_client(agent_config)
    thinking_budget = agent_config.thinking_budget
    include_thoughts = thinking_budget > 0

    return LlmAgent(
        model=model_client,
        name=agent_definition.name,
        description=agent_definition.description,
        planner=BuiltInPlanner(
            thinking_config=types.ThinkingConfig(
                include_thoughts=include_thoughts, thinking_budget=thinking_budget
            )
        ),
        generate_content_config=types.GenerateContentConfig(
            temperature=agent_config.temperature,
            top_p=agent_config.top_p,
            max_output_tokens=agent_config.max_output_tokens,
            safety_settings=[
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=types.HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                ),
            ],
        ),
        output_schema=agent_definition.output_schema,
        output_key=agent_definition.output_key,
        instruction=agent_definition.instruction,
    )
