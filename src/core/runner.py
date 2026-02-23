"""Agent runner to manage sessions"""

import logging
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class AgentRunner:
    """Runner to manage agent sessions and execute queries.
    Args:
        agent (BaseAgent): The agent to run.
        app_name (str): Name of the application.
    """

    def __init__(self, agent: BaseAgent, app_name: str):
        self.agent = agent
        self.app_name = app_name
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent, app_name=self.app_name, session_service=self.session_service
        )

    async def _get_session(self, user_id: str, session_id: str) -> Session | None:
        """Retrieves the session for the given user and session ID.

        Args:
            user_id (str): The user ID.
            session_id (str): The session ID.

        Returns:
            Session | None: The session object or None if not found.
        """
        return await self.session_service.get_session(
            app_name=self.app_name, user_id=user_id, session_id=session_id
        )

    async def run(
        self,
        user_id: str,
        session_id: str,
        query: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> str:
        """Runs the agent with the given query and handles validation retries.

        Args:
            user_id (str): The user ID.
            session_id (str): The session ID.
            query (str): The user query.
            max_retries (int): Maximum number of retries for validation errors.
            **kwargs (Any): Initial state of the session.

        Returns:
            str: Final response text from the agent.
        """
        session = await self._get_session(user_id, session_id)
        if not session:
            await self.session_service.create_session(
                app_name=self.app_name, user_id=user_id, session_id=session_id, state=kwargs
            )

        current_content = types.Content(role="user", parts=[types.Part(text=query)])
        current_state_delta = {
            "current_user_query": query,
            "query_moderator_output": {},
            "query_expander_output": {},
            "query_router_output": {},
        }

        logger.info("Running Query: %s ...", query)

        for attempt in range(max_retries + 1):
            try:
                final_response_text = "Agent did not produce a final response."

                async for event in self.runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=current_content,
                    state_delta=current_state_delta,
                ):
                    logger.debug(
                        "  [Event] Author: %s, Type: %s, Final: %s, Content: %s",
                        event.author,
                        type(event).__name__,
                        event.is_final_response(),
                        event.model_dump_json(indent=2, exclude_none=True),
                    )
                    if event.is_final_response():
                        if event.content and event.content.parts:
                            final_response_text = event.content.parts[0].text or ""
                        elif event.actions and event.actions.escalate:
                            final_response_text = (
                                f"Agent escalated: {event.error_message or 'No specific message.'}"
                            )
                        break

                return final_response_text

            except ValidationError as e:
                logger.warning("Attempt %d failed validation: %s", attempt + 1, e)

                if attempt == max_retries:
                    logger.error("Max retries exceeded.")
                    raise e

                feedback_message = (
                    f"Your previous response failed validation with the following error: {e}. "
                    "Please correct the format and try again."
                )

                current_content = types.Content(
                    role="user", parts=[types.Part(text=feedback_message)]
                )

                # Clear state_delta so we don't overwrite the original query context
                current_state_delta = {}

        return "Agent failed to produce valid output after multiple retries."

    async def get_session_state(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Returns the current state of the session.

        Args:
            user_id (str): The user ID.
            session_id (str): The session ID.

        Returns:
            dict[str, Any]: The session state.
        """
        session = await self._get_session(user_id, session_id)
        if session:
            return session.state
        return {}

    async def get_session_history(self, user_id: str, session_id: str) -> list[Any]:
        """Returns the event history of the session.

        Args:
            user_id (str): The user ID.
            session_id (str): The session ID.

        Returns:
            list[Any]: The list of events in the session.
        """
        session = await self._get_session(user_id, session_id)
        if session:
            return session.events
        return []

    async def reset_session(self, user_id: str, session_id: str) -> None:
        """Completely deletes the session (history and state).

        Args:
            user_id (str): The user ID.
            session_id (str): The session ID.
        """
        logger.info("Resetting session for user: %s, session: %s", user_id, session_id)
        await self.session_service.delete_session(
            app_name=self.app_name, user_id=user_id, session_id=session_id
        )

    async def clear_history_only(self, user_id: str, session_id: str) -> None:
        """Clears the conversation history but keeps the session state.

        Args:
            user_id (str): The user ID.
            session_id (str): The session ID.
        """
        session = await self._get_session(user_id, session_id)
        if session:
            logger.info("Clearing history for user: %s, session: %s", user_id, session_id)
            current_state = session.state

            await self.session_service.delete_session(
                app_name=self.app_name, user_id=user_id, session_id=session_id
            )

            await self.session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
                state=current_state,
            )
