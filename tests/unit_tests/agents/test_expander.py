"""Unit tests for the expander agent."""

from unittest.mock import MagicMock, patch

from agents.expander import (
    EXPANDER_SYSTEM_INSTRUCTION,
    QueryExpanderOutput,
    create_expander_agent,
)
from core.config import AgentConfig


class TestExpanderAgent:
    """Test suite for the expander agent."""

    def test_query_expander_output_schema(self) -> None:
        """Test the QueryExpanderOutput schema."""
        output = QueryExpanderOutput(queries=["query1", "query2"])
        assert output.queries == ["query1", "query2"]
        assert len(output.queries) == 2

    @patch("agents.expander.create_agent")
    def test_create_expander_agent(
        self, mock_create_agent: MagicMock, agent_config: AgentConfig
    ) -> None:
        """Test that create_expander_agent calls create_agent with correct parameters."""
        create_expander_agent(agent_config)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        assert call_args.kwargs["agent_config"] == agent_config

        agent_def = call_args.kwargs["agent_definition"]
        assert agent_def.name == "query_expander_agent"
        assert agent_def.description == "Expands user queries to improve search results."
        assert agent_def.output_schema == QueryExpanderOutput
        assert agent_def.output_key == "query_expander_output"
        assert agent_def.instruction == EXPANDER_SYSTEM_INSTRUCTION
