"""Performance/Latency tests for the HM Parallel Agent Pipeline."""

import asyncio
import json
import time
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from agents.hm_parallel_agent import create_hm_parallel_agent
from core.config import AppConfig
from core.runner import AgentRunner


class TestAgentPipelinePerformance:  # pylint: disable=too-few-public-methods,duplicate-code
    """Performance test suite for the HM Parallel Agent pipeline."""

    @pytest.mark.asyncio
    async def test_agent_pipeline_latency(self, app_config: AppConfig) -> None:
        """Benchmark the overhead of the parallel agent orchestration."""

        simulated_llm_latency = 0.01

        async def mock_generate_content(
            _llm_request: LlmRequest,
            stream: bool = False,  # pylint: disable=unused-argument
        ) -> AsyncGenerator[LlmResponse, None]:
            await asyncio.sleep(simulated_llm_latency)

            consolidated_response = {
                "block": False,
                "queries": ["benchmark query"],
                "group": "ladies",
            }
            response_text = json.dumps(consolidated_response)

            yield LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text=response_text)])
            )

        with patch("agents.base.AuthenticatedLiteLlm.generate_content_async") as mock_generate:
            mock_generate.side_effect = mock_generate_content

            hm_agent = create_hm_parallel_agent(app_config)
            runner = AgentRunner(agent=hm_agent, app_name="perf_test_app")

            await runner.run(
                user_id="perf_user",
                session_id="perf_session",
                query="warmup",
                num_queries=2,
                country_name="US",
                cur_date="2024-01-01",
            )

            start_time = time.perf_counter()
            iterations = 5
            for i in range(iterations):
                await runner.run(
                    user_id="perf_user",
                    session_id="perf_session",
                    query=f"bench_{i}",
                    num_queries=2,
                    country_name="US",
                    cur_date="2024-01-01",
                )
            end_time = time.perf_counter()

            total_time = end_time - start_time
            avg_time = total_time / iterations

            print(
                f"\nPipeline Average Latency (simulated LLM="
                f"{simulated_llm_latency * 1000}ms): "
                f"{avg_time * 1000:.2f}ms"
            )

            # Allowing 500ms overhead for python/asyncio/ADK framework.
            assert avg_time < (simulated_llm_latency + 0.5), (
                f"Pipeline too slow! Avg: {avg_time * 1000:.2f}ms"
            )
