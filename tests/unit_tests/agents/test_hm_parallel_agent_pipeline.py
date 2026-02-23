"""Integration/Pipeline tests for the HM Parallel Agent using mocked LLM."""

import json
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from agents.hm_parallel_agent import create_hm_parallel_agent
from core.config import AppConfig
from core.runner import AgentRunner


class TestHMParallelAgentPipeline:  # pylint: disable=too-few-public-methods
    """Test suite for the HM Parallel Agent pipeline with mocked LLM."""

    @pytest.mark.asyncio
    async def test_run_hm_agent_pipeline(self, app_config: AppConfig) -> None:
        """Test the full pipeline of HMParallelAgent with mocked responses."""

        async def mock_generate_content(  # pylint: disable=unused-argument
            llm_request: LlmRequest,
            stream: bool = False,
        ) -> AsyncGenerator[LlmResponse, None]:
            consolidated_response = {
                "block": False,
                "queries": ["black dress", "little black dress"],
                "group": "ladies",
            }
            response_text = json.dumps(consolidated_response)

            yield LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text=response_text)])
            )

        with patch("agents.base.AuthenticatedLiteLlm.generate_content_async") as mock_generate:
            mock_generate.side_effect = mock_generate_content

            hm_agent = create_hm_parallel_agent(app_config)

            runner = AgentRunner(agent=hm_agent, app_name="test_app")

            final_response_json = await runner.run(
                user_id="test_user",
                session_id="test_session",
                query="I need a black dress",
                num_queries=2,
                country_name="US",
                cur_date="2024-01-01",
            )

            assert final_response_json is not None
            response_json = json.loads(final_response_json)

            assert response_json["block"] is False
            assert response_json["queries"] == ["black dress", "little black dress"]
            assert response_json["group"] == "ladies"
