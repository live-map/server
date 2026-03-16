"""
OAuth provider configuration using Authlib.

Handles OAuth authorization URL generation and token exchange
for Google and Kakao providers.
"""

import logging

from authlib.integrations.httpx_client import AsyncOAuth2Client

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# Provider Configurations
# ============================================================

OAUTH_PROVIDERS: dict[str, dict] = {
    "google": {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v3/userinfo",
        "scope": "openid email profile",
    },
    "kakao": {
        "client_id": settings.KAKAO_CLIENT_ID,
        "client_secret": settings.KAKAO_CLIENT_SECRET,
        "authorize_url": "https://kauth.kakao.com/oauth/authorize",
        "token_url": "https://kauth.kakao.com/oauth/token",
        "userinfo_url": "https://kapi.kakao.com/v2/user/me",
        "scope": "profile_nickname profile_image account_email",
    },
}


def get_provider_config(provider: str) -> dict:
    """Get OAuth provider configuration."""
    config = OAUTH_PROVIDERS.get(provider)
    if not config:
        raise ValueError(f"Unsupported OAuth provider: {provider}")
    return config


def create_oauth_client(provider: str, redirect_uri: str) -> AsyncOAuth2Client:
    """Create an Authlib async OAuth2 client for the given provider."""
    config = get_provider_config(provider)
    return AsyncOAuth2Client(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        redirect_uri=redirect_uri,
        scope=config["scope"],
    )


def get_authorization_url(provider: str, redirect_uri: str, state: str) -> str:
    """
    Generate the OAuth authorization URL for the provider.

    Args:
        provider: OAuth provider name ("google" or "kakao")
        redirect_uri: Where the provider should redirect after consent
        state: CSRF protection state parameter

    Returns:
        The full authorization URL to redirect the user to
    """
    config = get_provider_config(provider)
    client = create_oauth_client(provider, redirect_uri)
    url, _ = client.create_authorization_url(
        config["authorize_url"],
        state=state,
    )
    return url


async def exchange_code_for_token(provider: str, code: str, redirect_uri: str) -> dict:
    """
    Exchange an authorization code for an access token.

    Args:
        provider: OAuth provider name
        code: Authorization code from the provider callback
        redirect_uri: Must match the redirect_uri used in the authorization request

    Returns:
        Token response dict containing access_token, etc.
    """
    config = get_provider_config(provider)
    client = create_oauth_client(provider, redirect_uri)

    token = await client.fetch_token(
        config["token_url"],
        code=code,
    )
    return dict(token)


async def fetch_user_profile(provider: str, access_token: str) -> dict:
    """
    Fetch user profile from the OAuth provider's resource server.

    Args:
        provider: OAuth provider name
        access_token: Valid access token from the provider

    Returns:
        Normalized user profile dict with: provider_account_id, email, name, image
    """
    config = get_provider_config(provider)

    async with AsyncOAuth2Client(token={"access_token": access_token, "token_type": "Bearer"}) as client:
        resp = await client.get(config["userinfo_url"])
        resp.raise_for_status()
        data = resp.json()

    if provider == "google":
        return {
            "provider_account_id": data["sub"],
            "email": data.get("email"),
            "name": data.get("name"),
            "image": data.get("picture"),
        }
    elif provider == "kakao":
        account = data.get("kakao_account", {})
        profile = account.get("profile", {})
        return {
            "provider_account_id": str(data["id"]),
            "email": account.get("email"),
            "name": profile.get("nickname"),
            "image": profile.get("profile_image_url"),
        }
    else:
        raise ValueError(f"Unsupported provider for profile parsing: {provider}")
