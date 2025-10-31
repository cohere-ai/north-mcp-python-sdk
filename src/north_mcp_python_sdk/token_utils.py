import json
import logging
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence

import jwt
from jwt import PyJWKClient


class TokenVerificationError(Exception):
    """Raised when a user ID token fails verification against trusted issuers."""


def decode_user_id_token(
    raw_token: str | None,
    *,
    logger: logging.Logger | None = None,
) -> dict[str, Any] | None:
    """
    Decode the payload section of a JWT without verifying the signature.

    Args:
        raw_token: Raw JWT string to decode.
        logger: Optional logger for debug output.

    Returns:
        A dictionary of claims when decoding succeeds, otherwise None.
    """
    if not raw_token:
        return None

    parts = raw_token.split(".")
    if len(parts) < 2:
        return None

    payload_segment = parts[1]
    padding = (-len(payload_segment)) % 4
    padded_payload = payload_segment + ("=" * padding)

    try:
        payload_bytes = jwt.utils.base64url_decode(padded_payload.encode())
        claims = json.loads(payload_bytes.decode())
    except (ValueError, json.JSONDecodeError, jwt.InvalidTokenError) as exc:
        if logger:
            logger.debug("Failed to decode user_id_token payload: %s", exc)
        return None

    if isinstance(claims, dict):
        return claims
    return None


def verify_user_id_token(
    raw_token: str,
    trusted_issuers: Sequence[str],
    *,
    logger: logging.Logger | None = None,
) -> Mapping[str, Any]:
    """
    Verify a user ID token against trusted issuers and return the validated claims.

    Args:
        raw_token: JWT string to verify.
        trusted_issuers: Collection of allowed issuer URLs.
        logger: Optional logger for diagnostic messages.

    Returns:
        Mapping containing the verified JWT claims.

    Raises:
        TokenVerificationError: When verification fails for any reason.
    """
    if not raw_token:
        raise TokenVerificationError("user ID token missing")

    if not trusted_issuers:
        raise TokenVerificationError("trusted issuers not configured")

    try:
        unverified_claims = jwt.decode(
            jwt=raw_token,
            options={"verify_signature": False},
        )
    except jwt.PyJWTError as exc:  # pragma: no cover - defensive
        if logger:
            logger.debug("Failed to decode user ID token: %s", exc)
        raise TokenVerificationError("unable to decode user ID token") from exc

    issuer = unverified_claims.get("iss")
    if not isinstance(issuer, str) or not issuer:
        raise TokenVerificationError("token missing issuer")

    if issuer not in trusted_issuers:
        raise TokenVerificationError(f"untrusted issuer: {issuer}")

    openid_config_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        with urllib.request.urlopen(openid_config_url, timeout=10) as response:
            openid_config = json.load(response)
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
    ) as exc:
        if logger:
            logger.error(
                "Failed to fetch OpenID configuration from %s: %s",
                issuer,
                exc,
            )
        raise TokenVerificationError(
            "failed to verify token: unable to fetch issuer configuration"
        ) from exc

    jwks_uri = openid_config.get("jwks_uri")
    if not isinstance(jwks_uri, str) or not jwks_uri:
        raise TokenVerificationError("issuer configuration missing jwks_uri")

    try:
        unverified_header = jwt.get_unverified_header(raw_token)
    except jwt.PyJWTError as exc:
        if logger:
            logger.debug("Failed to decode token header: %s", exc)
        raise TokenVerificationError("unable to inspect token header") from exc

    kid = unverified_header.get("kid")
    algorithm = unverified_header.get("alg", "RS256")

    if not kid:
        raise TokenVerificationError("token missing key identifier")

    jwks_client = PyJWKClient(jwks_uri, cache_keys=True)

    try:
        signing_key = jwks_client.get_signing_key(kid).key
        verified_claims = jwt.decode(
            jwt=raw_token,
            key=signing_key,
            algorithms=[algorithm],
            issuer=issuer,
            options={"verify_signature": True, "verify_aud": False},
        )
    except (jwt.PyJWTError, Exception) as exc:  # pragma: no cover - defensive
        if logger:
            logger.debug("Failed to verify user ID token signature: %s", exc)
        raise TokenVerificationError("token signature verification failed") from exc

    return verified_claims


__all__ = [
    "TokenVerificationError",
    "decode_user_id_token",
    "verify_user_id_token",
]
