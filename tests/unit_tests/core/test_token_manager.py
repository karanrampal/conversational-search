"""Unit tests for the token manager module."""

from unittest.mock import MagicMock, patch

import jwt
import pytest
from google.auth.exceptions import GoogleAuthError

from core.token_manager import TokenManager


class TestTokenManager:
    """Test suite for the TokenManager class."""

    # pylint: disable=protected-access

    @pytest.fixture
    def token_manager(self) -> TokenManager:
        """Fixture that returns a fresh TokenManager instance."""
        return TokenManager("https://example.com")

    def test_init_empty_audience(self) -> None:
        """Test initialization with empty audience."""
        with pytest.raises(ValueError, match="target_audience cannot be empty"):
            TokenManager("")

    @patch("core.token_manager.time.time")
    def test_needs_refresh_no_token(
        self, mock_time: MagicMock, token_manager: TokenManager
    ) -> None:
        """Test needs_refresh when no token exists."""
        mock_time.return_value = 1000
        assert token_manager._needs_refresh()

    @patch("core.token_manager.time.time")
    def test_needs_refresh_expired(self, mock_time: MagicMock, token_manager: TokenManager) -> None:
        """Test needs_refresh when token is expired."""
        mock_time.return_value = 1000
        token_manager._token = "some-token"
        # buffer is 300s. If expiry is 1200, time left is 200 (needs refresh)
        token_manager._expiry = 1200
        assert token_manager._needs_refresh()

    @patch("core.token_manager.time.time")
    def test_needs_refresh_not_needed(
        self, mock_time: MagicMock, token_manager: TokenManager
    ) -> None:
        """Test needs_refresh when token is valid."""
        mock_time.return_value = 1000
        token_manager._token = "some-token"
        # buffer is 300s. If expiry is 1400, time left is 400 (no refresh needed)
        token_manager._expiry = 1400
        assert not token_manager._needs_refresh()

    def test_get_token_success_google_auth(self, token_manager: TokenManager) -> None:
        """Test get_token success using Google Auth."""
        with (
            patch("core.token_manager.time.time") as mock_time,
            patch("core.token_manager.jwt.decode") as mock_jwt_decode,
            patch("core.token_manager.google.oauth2.id_token.fetch_id_token") as mock_fetch_token,
        ):
            mock_time.return_value = 1000
            mock_fetch_token.return_value = "google-token"
            mock_jwt_decode.return_value = {"exp": 2000}

            token = token_manager.get_token()

            assert token == "google-token"
            assert token_manager._expiry == 2000
            mock_fetch_token.assert_called_once()

    def test_get_token_fallback_gcloud(self, token_manager: TokenManager) -> None:
        """Test get_token fallback to gcloud CLI."""
        with (
            patch("core.token_manager.time.time") as mock_time,
            patch("core.token_manager.jwt.decode") as mock_jwt_decode,
            patch("core.token_manager.subprocess.check_output") as mock_subprocess,
            patch("core.token_manager.google.oauth2.id_token.fetch_id_token") as mock_fetch_token,
        ):
            mock_time.return_value = 1000
            mock_fetch_token.side_effect = GoogleAuthError("Auth failed")

            mock_subprocess.return_value = b"gcloud-token\n"
            mock_jwt_decode.return_value = {"exp": 2000}

            token = token_manager.get_token()

            assert token == "gcloud-token"
            mock_fetch_token.assert_called_once()
            mock_subprocess.assert_called_once_with(
                ["gcloud", "auth", "print-identity-token", "-q"]
            )

    def test_get_token_failure_both_methods(self, token_manager: TokenManager) -> None:
        """Test get_token failure when both methods fail."""
        with (
            patch("core.token_manager.subprocess.check_output") as mock_subprocess,
            patch("core.token_manager.google.oauth2.id_token.fetch_id_token") as mock_fetch_token,
        ):
            mock_fetch_token.side_effect = GoogleAuthError("Auth failed")
            mock_subprocess.side_effect = Exception("Process failed")

            with pytest.raises(GoogleAuthError):
                token_manager.get_token()

            assert token_manager._token is None

    def test_refresh_token_empty_response(self, token_manager: TokenManager) -> None:
        """Test refresh_token failure when response is empty."""
        with (
            patch("core.token_manager.jwt.decode") as mock_jwt_decode,
            patch("core.token_manager.google.oauth2.id_token.fetch_id_token") as mock_fetch_token,
        ):
            del mock_jwt_decode  # Unused
            mock_fetch_token.return_value = ""  # Empty token

            with pytest.raises(GoogleAuthError, match="Token refresh failed"):
                token_manager._refresh_token()

    def test_extract_token_expiry_success(self, token_manager: TokenManager) -> None:
        """Test successful token expiry extraction."""
        with patch("core.token_manager.jwt.decode", return_value={"exp": 12345}):
            expiry = token_manager._extract_token_expiry("token")
            assert expiry == 12345

    def test_extract_token_expiry_missing_claim(self, token_manager: TokenManager) -> None:
        """Test failure when expiry claim is missing."""
        with (
            patch("core.token_manager.jwt.decode", return_value={"other": 123}),
            pytest.raises(ValueError, match="Token does not contain 'exp' claim"),
        ):
            token_manager._extract_token_expiry("token")

    def test_extract_token_expiry_decode_error(self, token_manager: TokenManager) -> None:
        """Test failure when token decoding fails."""
        with (
            patch("core.token_manager.jwt.decode", side_effect=jwt.DecodeError("Bad token")),
            pytest.raises(ValueError, match="Invalid token format"),
        ):
            token_manager._extract_token_expiry("token")

    def test_clear_token(self, token_manager: TokenManager) -> None:
        """Test token clearing."""
        token_manager._token = "existing"
        token_manager._expiry = 12345

        token_manager.clear_token()

        assert token_manager._token is None
        assert token_manager._expiry is None
