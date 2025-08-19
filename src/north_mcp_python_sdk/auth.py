import base64
import contextvars
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import jwt
from pydantic import BaseModel, Field, ValidationError
from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    BaseUser,
)
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class AuthHeaderTokens(BaseModel):
    """
    Model for North's JWT authentication token format.
    
    Supports both the current North format and backward compatibility.
    """
    server_secret: str | None = None
    user_id_token: str | None = None
    connector_access_tokens: dict[str, str] = Field(default_factory=dict)
    auth_token: str | None = None  # North's dex access token (optional)


class AuthenticatedNorthUser(BaseUser):
    def __init__(
        self,
        connector_access_tokens: dict[str, str],
        email: str | None = None,
    ):
        self.connector_access_tokens = connector_access_tokens
        self.email = email


class AuthProvider(ABC):
    """
    Abstract base class for authentication providers.
    
    Each provider implements a specific authentication method (Bearer tokens, OAuth, API keys, etc.)
    and returns an AuthenticatedNorthUser if authentication succeeds, or None if it fails.
    """
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(f"NorthMCP.{self.__class__.__name__}")
        if debug:
            self.logger.setLevel(logging.DEBUG)
    
    @abstractmethod
    async def authenticate(self, conn: HTTPConnection) -> Optional[AuthenticatedNorthUser]:
        """
        Authenticate a request and return the authenticated user.
        
        Args:
            conn: The HTTP connection containing headers and request info
            
        Returns:
            AuthenticatedNorthUser if authentication succeeds, None otherwise
            
        Raises:
            AuthenticationError: If authentication fails in a way that should return 401
        """
        pass
    
    @abstractmethod
    def get_scheme(self) -> str:
        """Return the authentication scheme this provider handles (e.g., 'Bearer', 'Basic')"""
        pass


class BearerTokenAuthProvider(AuthProvider):
    """
    Authentication provider for North's Bearer token format.
    
    Validates Base64-encoded JSON tokens containing server_secret, user_id_token, 
    and connector_access_tokens. This is the original North authentication method.
    """
    
    def __init__(self, server_secret: str | None = None, debug: bool = False):
        super().__init__(debug)
        self._server_secret = server_secret
    
    def get_scheme(self) -> str:
        return "Bearer"
    
    async def authenticate(self, conn: HTTPConnection) -> Optional[AuthenticatedNorthUser]:
        auth_header = conn.headers.get("Authorization", "")
        
        if not auth_header:
            self.logger.debug("No Authorization header found")
            return None
        
        # North sends base64 tokens in two formats:
        # 1. "Bearer <base64-token>" (standard format)
        # 2. "<base64-token>" (North's current direct format)
        if auth_header.startswith("Bearer "):
            self.logger.debug("Processing Bearer token authentication (standard format)")
            token = auth_header[7:]  # Remove "Bearer " prefix
        else:
            # Check if this looks like a base64 encoded token (North's format)
            try:
                # Quick validation: base64 should be divisible by 4 and contain valid chars
                if len(auth_header) % 4 == 0 and all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in auth_header):
                    self.logger.debug("Processing North-format authentication (raw base64)")
                    token = auth_header
                else:
                    self.logger.debug("Authorization header doesn't match Bearer token or North format")
                    return None
            except:
                self.logger.debug("Authorization header validation failed")
                return None
        
        try:
            decoded_auth_header = base64.b64decode(token).decode()
            self.logger.debug("Successfully decoded base64 auth header")
        except Exception as e:
            self.logger.debug("Failed to decode base64 auth header: %s", e)
            raise AuthenticationError("invalid bearer token format")

        try:
            tokens = AuthHeaderTokens.model_validate_json(decoded_auth_header)
            self.logger.debug("Successfully parsed auth tokens. Has server_secret: %s, Has user_id_token: %s, Connector count: %d", 
                            tokens.server_secret is not None, tokens.user_id_token is not None, len(tokens.connector_access_tokens))
            self.logger.debug("Available connectors: %s", list(tokens.connector_access_tokens.keys()))
        except ValidationError as e:
            self.logger.debug("Failed to validate auth tokens: %s", e)
            raise AuthenticationError("invalid bearer token format")

        if self._server_secret and self._server_secret != tokens.server_secret:
            self.logger.debug("Server secret mismatch - access denied")
            raise AuthenticationError("access denied")

        if tokens.user_id_token:
            try:
                user_id_token = jwt.decode(
                    jwt=tokens.user_id_token,
                    verify=False,
                    options={"verify_signature": False},
                )

                email = user_id_token.get("email")
                
                self.logger.debug("Successfully decoded user ID token. Email: %s", email)
                
                if not email:
                    self.logger.debug("Authentication failed: no email found in user ID token")
                    raise AuthenticationError("email required in user id token")

                return AuthenticatedNorthUser(
                    connector_access_tokens=tokens.connector_access_tokens, email=email
                )
            except Exception as e:
                self.logger.debug("Failed to decode user ID token: %s", e)
                raise AuthenticationError("invalid user id token")

        self.logger.debug("Authentication successful without user ID token")

        return AuthenticatedNorthUser(
            connector_access_tokens=tokens.connector_access_tokens,
        )


class APIKeyAuthProvider(AuthProvider):
    """
    Authentication provider for API key-based authentication.
    
    Validates API keys passed via Authorization header as "Bearer <api_key>"
    or via X-API-Key header.
    """
    
    def __init__(self, valid_keys: List[str], debug: bool = False):
        super().__init__(debug)
        self.valid_keys = set(valid_keys)
    
    def get_scheme(self) -> str:
        return "ApiKey"
    
    async def authenticate(self, conn: HTTPConnection) -> Optional[AuthenticatedNorthUser]:
        # Try X-API-Key header first
        api_key = conn.headers.get("X-API-Key")
        if not api_key:
            # Try Authorization header with Bearer
            auth_header = conn.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]  # Remove "Bearer " prefix
        
        if not api_key:
            self.logger.debug("No API key found in headers")
            return None
        
        self.logger.debug("Processing API key authentication")
        
        if api_key in self.valid_keys:
            self.logger.debug("API key authentication successful")
            return AuthenticatedNorthUser(
                connector_access_tokens={},
                email=f"api-key-user-{hash(api_key) % 10000}"  # Generate deterministic email
            )
        else:
            self.logger.debug("Invalid API key provided")
            raise AuthenticationError("invalid api key")


class OAuthAuthProvider(AuthProvider):
    """
    Authentication provider for OAuth-based authentication.
    
    Validates OAuth access tokens using introspection endpoint or JWT validation.
    Designed to integrate with North's existing Dex-based OAuth flow while
    maintaining compatibility with the existing JWT token format.
    
    Supports multiple OAuth validation methods:
    1. JWT validation with public key/secret
    2. Token introspection endpoint
    3. Custom validation callback
    """
    
    def __init__(
        self,
        # JWT validation options
        jwt_secret: Optional[str] = None,
        jwt_algorithm: str = "HS256",
        # Token introspection options  
        introspection_endpoint: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        # Custom validation
        custom_validator: Optional[callable] = None,
        # Email extraction
        email_claim: str = "email",
        debug: bool = False
    ):
        super().__init__(debug)
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.introspection_endpoint = introspection_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.custom_validator = custom_validator
        self.email_claim = email_claim
        
        if not any([jwt_secret, introspection_endpoint, custom_validator]):
            raise ValueError("Must provide either jwt_secret, introspection_endpoint, or custom_validator")
    
    def get_scheme(self) -> str:
        return "OAuth"
    
    async def authenticate(self, conn: HTTPConnection) -> Optional[AuthenticatedNorthUser]:
        auth_header = conn.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            self.logger.debug("No Bearer token found for OAuth authentication")
            return None
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        self.logger.debug("Processing OAuth token authentication")
        
        try:
            # Try different validation methods in order of preference
            user_info = None
            
            # 1. Custom validator (highest priority)
            if self.custom_validator:
                self.logger.debug("Using custom OAuth validator")
                user_info = await self._validate_with_custom(token)
            
            # 2. JWT validation
            elif self.jwt_secret:
                self.logger.debug("Using JWT validation for OAuth token")
                user_info = await self._validate_jwt(token)
            
            # 3. Token introspection
            elif self.introspection_endpoint:
                self.logger.debug("Using token introspection for OAuth validation")
                user_info = await self._validate_with_introspection(token)
            
            if not user_info:
                self.logger.debug("OAuth token validation failed")
                raise AuthenticationError("invalid oauth token")
            
            email = user_info.get(self.email_claim)
            if not email:
                self.logger.debug("No email found in OAuth token claims")
                raise AuthenticationError("email required in oauth token")
            
            # Extract connector tokens if present (for North compatibility)
            connector_tokens = user_info.get("connector_access_tokens", {})
            
            self.logger.debug("OAuth authentication successful for email: %s", email)
            return AuthenticatedNorthUser(
                connector_access_tokens=connector_tokens,
                email=email
            )
            
        except AuthenticationError:
            raise
        except Exception as e:
            self.logger.debug("OAuth authentication failed with error: %s", e)
            raise AuthenticationError("oauth validation failed")
    
    async def _validate_jwt(self, token: str) -> Optional[dict]:
        """Validate JWT token with configured secret."""
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            self.logger.debug("JWT validation successful")
            return payload
        except Exception as e:
            self.logger.debug("JWT validation failed: %s", e)
            return None
    
    async def _validate_with_introspection(self, token: str) -> Optional[dict]:
        """Validate token using OAuth introspection endpoint."""
        try:
            import httpx
            import base64
            
            # Prepare introspection request
            auth_value = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            headers = {
                "Authorization": f"Basic {auth_value}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {"token": token}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.introspection_endpoint,
                    headers=headers,
                    data=data
                )
                
                if response.status_code == 200:
                    introspection_result = response.json()
                    if introspection_result.get("active", False):
                        self.logger.debug("Token introspection successful")
                        return introspection_result
                    else:
                        self.logger.debug("Token is not active according to introspection endpoint")
                        return None
                else:
                    self.logger.debug("Introspection endpoint returned status: %s", response.status_code)
                    return None
                    
        except Exception as e:
            self.logger.debug("Token introspection failed: %s", e)
            return None
    
    async def _validate_with_custom(self, token: str) -> Optional[dict]:
        """Validate token using custom validator function."""
        try:
            if callable(self.custom_validator):
                result = self.custom_validator(token)
                # Handle both sync and async custom validators
                if hasattr(result, '__await__'):
                    result = await result
                return result
            else:
                self.logger.debug("Custom validator is not callable")
                return None
        except Exception as e:
            self.logger.debug("Custom validation failed: %s", e)
            return None


class NorthAuthenticationMiddleware:
    """
    North's authentication middleware for MCP servers that applies authentication 
    only to MCP protocol endpoints (/mcp, /sse). Custom routes bypass authentication
    and are intended for operational purposes like Kubernetes health checks.
    
    MCP servers typically only need two authenticated endpoints:
    - /mcp: JSON-RPC protocol endpoint for MCP communication
    - /sse: Server-sent events endpoint for streaming transport
    
    Custom routes are automatically public and designed for:
    - Kubernetes liveness/readiness probes (/health, /ready)
    - Monitoring and metrics endpoints (/metrics, /status)
    - Other operational/orchestration needs
    
    No configuration needed - this behavior follows MCP best practices.
    """

    def __init__(
        self, 
        app: ASGIApp, 
        backend: AuthenticationBackend,
        on_error,
        protected_paths: list[str] | None = None,
        debug: bool = False
    ):
        self.app = app
        self.backend = backend
        self.on_error = on_error
        # Default protected paths - only MCP protocol routes require auth
        self.protected_paths = protected_paths or ["/mcp", "/sse"]
        self.debug = debug
        self.logger = logging.getLogger("NorthMCP.Auth")
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def _should_authenticate(self, path: str) -> bool:
        """
        Check if the given path requires authentication.
        Only MCP protocol paths (/mcp, /sse) require auth by default.
        """
        return path in self.protected_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")
        
        if not self._should_authenticate(path):
            self.logger.debug(
                "Path %s is a custom route (likely operational endpoint like health check), "
                "authentication is optional", 
                path
            )
            # For custom routes, try to authenticate but don't require it
            conn = HTTPConnection(scope)
            try:
                auth_result = await self.backend.authenticate(conn)
                if auth_result is None:
                    auth, user = AuthCredentials(), None
                else:
                    auth, user = auth_result
                self.logger.debug("Optional authentication successful for custom route")
            except AuthenticationError:
                # Authentication failed, but that's ok for custom routes
                self.logger.debug("Optional authentication failed for custom route, continuing without auth")
                auth, user = AuthCredentials(), None
            except Exception as e:
                # Unexpected error, but don't fail the request for custom routes
                self.logger.debug("Unexpected error during optional authentication: %s", e)
                auth, user = AuthCredentials(), None
            
            scope["user"] = user
            scope["auth"] = auth
            return await self.app(scope, receive, send)

        self.logger.debug("Path %s is an MCP protocol endpoint, applying authentication", path)
        
        # Apply authentication for protected paths
        conn = HTTPConnection(scope)
        try:
            auth_result = await self.backend.authenticate(conn)
        except AuthenticationError as exc:
            response = self.on_error(conn, exc)
            return await response(scope, receive, send)

        if auth_result is None:
            auth, user = AuthCredentials(), None
        else:
            auth, user = auth_result

        scope["user"] = user
        scope["auth"] = auth
        await self.app(scope, receive, send)


auth_context_var = contextvars.ContextVar[AuthenticatedNorthUser | None](
    "north_auth_context", default=None
)


def on_auth_error(request: HTTPConnection, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=401)


def get_authenticated_user() -> AuthenticatedNorthUser:
    user = auth_context_var.get()
    if not user:
        raise Exception("user not found in context")

    return user


def get_authenticated_user_optional() -> AuthenticatedNorthUser | None:
    """Get the authenticated user if available, or None for custom routes."""
    return auth_context_var.get()


class AuthContextMiddleware:
    """
    Middleware that extracts the authenticated user from the request
    and sets it in a contextvar for easy access throughout the request lifecycle.

    This middleware should be added after the AuthenticationMiddleware in the
    middleware stack to ensure that the user is properly authenticated before
    being stored in the context.
    """

    def __init__(self, app: ASGIApp, debug: bool = False):
        self.app = app
        self.debug = debug
        self.logger = logging.getLogger("NorthMCP.AuthContext")
        if debug:
            self.logger.setLevel(logging.DEBUG)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "lifespan":
            return await self.app(scope, receive, send)

        user = scope.get("user")
        
        # For custom routes that don't require auth, user will be None
        if user is None:
            self.logger.debug("Custom route accessed without authentication (operational endpoint)")
            token = auth_context_var.set(None)
            try:
                await self.app(scope, receive, send)
            finally:
                auth_context_var.reset(token)
            return
        
        if not isinstance(user, AuthenticatedNorthUser):
            self.logger.debug("Authentication failed: user not found in context. User type: %s", type(user))
            raise AuthenticationError("user not found in context")

        self.logger.debug("Setting authenticated user in context: email=%s, connectors=%s", user.email, list(user.connector_access_tokens.keys()))

        token = auth_context_var.set(user)
        try:
            await self.app(scope, receive, send)
        finally:
            auth_context_var.reset(token)


class NorthAuthBackend(AuthenticationBackend):
    """
    Modular authentication backend that tries multiple authentication providers.
    
    Providers are tried in order until one succeeds or all fail.
    Maintains backward compatibility with the original Bearer token auth.
    """

    def __init__(self, providers: Optional[List[AuthProvider]] = None, server_secret: str | None = None, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger("NorthMCP.AuthBackend")
        if debug:
            self.logger.setLevel(logging.DEBUG)
        
        # If providers are specified, use them
        if providers is not None:
            self.providers = providers
        else:
            # Backward compatibility: create BearerTokenAuthProvider with server_secret
            self.providers = [BearerTokenAuthProvider(server_secret=server_secret, debug=debug)]
        
        self.logger.debug("Initialized with %d auth providers: %s", len(self.providers), [p.__class__.__name__ for p in self.providers])

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, BaseUser] | None:
        self.logger.debug("Authenticating request from %s", conn.client)
        
        if self.debug:
            headers_debug = {k: v for k, v in conn.headers.items()}
            self.logger.debug("Request headers: %s", headers_debug)

        # Try each provider in order
        for provider in self.providers:
            try:
                self.logger.debug("Trying provider: %s", provider.__class__.__name__)
                user = await provider.authenticate(conn)
                if user:
                    self.logger.debug("Authentication successful with provider: %s", provider.__class__.__name__)
                    return AuthCredentials(), user
                else:
                    self.logger.debug("Provider %s returned None, trying next", provider.__class__.__name__)
            except AuthenticationError as e:
                self.logger.debug("Provider %s failed with AuthenticationError: %s", provider.__class__.__name__, e)
                # Continue to next provider unless this was the last one
                if provider == self.providers[-1]:
                    raise  # Re-raise the last provider's error
            except Exception as e:
                self.logger.debug("Provider %s failed with unexpected error: %s", provider.__class__.__name__, e)
                # Continue to next provider
                
        # No provider succeeded
        self.logger.debug("All authentication providers failed")
        raise AuthenticationError("authentication failed")
