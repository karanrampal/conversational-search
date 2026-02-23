"""Unit tests for the moderator agent."""

from unittest.mock import MagicMock, patch

from agents.moderator import (
    MODERATOR_SYSTEM_INSTRUCTION,
    QueryModeratorOutput,
    create_moderator_agent,
)
from core.config import AgentConfig


class TestModeratorAgent:
    """Test suite for the moderator agent."""

    def test_query_moderator_output_schema(self) -> None:
        """Test the QueryModeratorOutput schema."""
        output = QueryModeratorOutput(block=True)
        assert output.block is True

        output = QueryModeratorOutput(block=False)
        assert output.block is False

    @patch("agents.moderator.create_agent")
    def test_create_moderator_agent(
        self, mock_create_agent: MagicMock, agent_config: AgentConfig
    ) -> None:
        """Test that create_moderator_agent calls create_agent with correct parameters."""
        create_moderator_agent(agent_config)

        mock_create_agent.assert_called_once()
        call_args = mock_create_agent.call_args
        assert call_args.kwargs["agent_config"] == agent_config

        agent_def = call_args.kwargs["agent_definition"]
        assert agent_def.name == "query_moderator_agent"
        assert agent_def.description == (
            "Moderates user queries by checking if they contain harmful or unsafe content."
        )
        assert agent_def.output_schema == QueryModeratorOutput
        assert agent_def.output_key == "query_moderator_output"
        assert agent_def.instruction == MODERATOR_SYSTEM_INSTRUCTION
