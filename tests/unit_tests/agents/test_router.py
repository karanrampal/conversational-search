"""Unit tests for the router agent."""

from unittest.mock import MagicMock, patch

import pytest

from agents.router import (
    ROUTER_SYSTEM_INSTRUCTION,
    QueryRouterOutput,
    create_router_agent,
)
from core.config import AgentConfig


class TestRouterAgent:
    """Test suite for the router agent."""

    def test_query_router_output_schema(self) -> None:
        """Test the QueryRouterOutput schema."""
        output = QueryRouterOutput(group="ladies")
        assert output.group == "ladies"

        # Test with invalid group (pydantic validation)
        with pytest.raises(Exception):
            QueryRouterOutput(group="invalid_group")  # type: ignore

    @patch("agents.router.create_agent")
    def test_create_router_agent(
        self, mock_create_agent: MagicMock, agent_config: AgentConfig
    ) -> None:
        """Test that create_router_agent calls create_agent with correct parameters."""
        create_router_agent(agent_config)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        assert call_args.kwargs["agent_config"] == agent_config

        agent_def = call_args.kwargs["agent_definition"]
        assert agent_def.name == "query_router_agent"
        assert agent_def.description == "Maps user queries to the correct product group."
        assert agent_def.output_schema == QueryRouterOutput
        assert agent_def.output_key == "query_router_output"
        assert agent_def.instruction == ROUTER_SYSTEM_INSTRUCTION
