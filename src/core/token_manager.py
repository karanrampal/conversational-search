"""Token manger for IAM"""

import logging
import subprocess
import threading
import time

import google.oauth2.id_token
import jwt
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages Google Cloud identity tokens with automatic refresh.
    Args:
        target_audience: The URL of the Cloud Run service
        refresh_buffer_seconds: Seconds before expiry to refresh (default: 300 = 5 minutes)
    """

    def __init__(self, target_audience: str, refresh_buffer_seconds: int = 300):
        if not target_audience:
            raise ValueError("target_audience cannot be empty")

        self.target_audience = target_audience
        self.refresh_buffer_seconds = refresh_buffer_seconds
        self._token: str | None = None
        self._expiry: float | None = None
        self._lock = threading.Lock()

        logger.info(
            "Initialized TokenManager for audience: %s with %ds refresh buffer",
            target_audience,
            refresh_buffer_seconds,
        )

    def get_token(self) -> str:
        """Get a valid token, refreshing if necessary.
        Returns:
            A valid identity token string
        Raises:
            GoogleAuthError: If token fetch/refresh fails
            ValueError: If token is invalid or cannot be decoded
        """
        with self._lock:
            if self._needs_refresh():
                self._refresh_token()

            if self._token is None:
                raise RuntimeError("Failed to obtain a valid token")

            return self._token

    def _needs_refresh(self) -> bool:
        """Check if the token needs to be refreshed."""
        if self._token is None or self._expiry is None:
            return True

        time_until_expiry = self._expiry - time.time()
        needs_refresh = time_until_expiry <= self.refresh_buffer_seconds

        if needs_refresh:
            logger.debug(
                "Token needs refresh. Time until expiry: %.0fs, buffer: %ds",
                time_until_expiry,
                self.refresh_buffer_seconds,
            )

        return needs_refresh

    def _refresh_token(self) -> None:
        """Fetch a new token and extract its expiry time.
        Raises:
            GoogleAuthError: If authentication fails
            ValueError: If token cannot be decoded
        """
        try:
            logger.debug("Refreshing token for audience: %s", self.target_audience)
            auth_req = Request()
            try:
                token = google.oauth2.id_token.fetch_id_token(auth_req, self.target_audience)
            except GoogleAuthError:
                logger.warning(
                    "Failed to fetch ID token via google-auth, falling back to gcloud CLI."
                )
                token = (
                    subprocess.check_output(["gcloud", "auth", "print-identity-token", "-q"])
                    .decode()
                    .strip()
                )

            if not token:
                raise ValueError("Received empty token from Google Auth")

            self._token = token
            self._expiry = self._extract_token_expiry(token)

            time_until_expiry = self._expiry - time.time()
            logger.debug(
                "Token refreshed successfully. Expires in %.0fs (%.2f hours)",
                time_until_expiry,
                time_until_expiry / 3600,
            )

        except GoogleAuthError as e:
            logger.error("Failed to fetch ID token: %s", e)
            self._token = None
            self._expiry = None
            raise
        except Exception as e:
            logger.error("Unexpected error during token refresh: %s", e)
            self._token = None
            self._expiry = None
            raise GoogleAuthError(f"Token refresh failed: {e}") from e

    def _extract_token_expiry(self, token: str) -> float:
        """Extract expiry timestamp from JWT token.
        Args:
            token: The JWT token string
        Returns:
            Unix timestamp of token expiry
        Raises:
            ValueError: If token cannot be decoded or has no expiry
        """
        try:
            decoded = jwt.decode(token, options={"verify_signature": False})

            if "exp" not in decoded:
                raise ValueError("Token does not contain 'exp' claim")

            expiry_timestamp = float(decoded["exp"])
            logger.debug("Extracted token expiry: %s", expiry_timestamp)

            return expiry_timestamp

        except jwt.DecodeError as e:
            logger.error("Failed to decode token: %s", e)
            raise ValueError(f"Invalid token format: {e}") from e
        except (KeyError, ValueError, TypeError) as e:
            logger.error("Failed to extract expiry from token: %s", e)
            raise ValueError(f"Cannot extract token expiry: {e}") from e

    def clear_token(self) -> None:
        """Clear the cached token, forcing a refresh on next get_token() call."""
        with self._lock:
            logger.debug("Clearing cached token")
            self._token = None
            self._expiry = None
