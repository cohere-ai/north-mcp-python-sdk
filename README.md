# North MCP Python SDK

This SDK builds on top of the original SDK. Please refer to the [original repository's README](https://github.com/modelcontextprotocol/python-sdk) for general information. This README focuses on North-specific details.


## Installation

```
uv pip install git+ssh://git@github.com/cohere-ai/north-mcp-python-sdk.git
```


## Why this repository
This repository provides code to enable your server to use authentication with North, a custom extension to the original specification. Other than that, no changes are made to the SDK; this builds on top of it.


## Main differences

* North only supports the StreamableHTTP transport. The sse transport is deprecated, it will work for backwards compatibility, but you shouldn't use it if you are creating new servers
* You can protect all requests to your server with a secret.
* You can access the user's OAuth token to interact with third-party services on their behalf.
* You can access the user's identity (from the identity provider used with North).

## Examples

This repository contains example servers that you can use as a quickstart. You can find them in the [examples directory](https://github.com/cohere-ai/north-mcp-python-sdk/tree/main/examples).

There are 2 examples, one that uses the auth to get the user making the tool call, and the other one shows how to send the right metadata so that the North UI can display the tool call results correctly.


## Authentication

This SDK offers several strategies for authenticating users and authorizing their requests.


#### I only want north to be able to send requests to my server
```python
mcp = NorthMCPServer(name="Demo", port=5222, server_secret="secret")
```

#### I want to get the identity of the north user that is calling my server
Refer to `examples/server_with_auth.py`. During your request call the following:
```python
user = get_authenticated_user()
print(user.email)
```


#### I need access to a third party service via oauth (e.g.: google drive, slack, etc...)
Similar as above:
```
user = get_authenticated_user()
print(user.connector_access_tokens)
```

## Local Development without North

This guide describes how to test your MCP server locally without connecting it to North. For this, we will use the MCP Inspector. You can run it with:
```
npx @modelcontextprotocol/inspector
```

If authentication is not required and you just want to run it locally, you can choose the stdio transport. Navigate to the [MCP Inspector](http://127.0.0.1:6274) and configure it as follows:
* Transport Type: stdio
* Command: uv
* Arguments: run examples/server_with_auth.py --transport stdio

From here:
* Click "Connect"
* Select "Tools" on the top of the screen.
* Click "List Tools" -> "add"
* Add the numbers and click "Run". You should see the sum.


### Adding authentication

If you want to test the authentication mechanism locally you can do the following. First start the server with the streamable http transport:

```
uv run examples/server_with_auth.py --transport streamable-http
```

Next, create a bearer token. You can generate one using `examples/create_bearer_token.py` or use a pre-made one.

Navigate to the MCP Inspector and configure it like this:
* Transport Type: Streamable HTTP
* URL: http://localhost:5222/mcp
* Authentication -> Bearer token: eyJzZXJ2ZXJfc2VjcmV0IjogInNlcnZlcl9zZWNyZXQiLCAidXNlcl9pZF90b2tlbiI6ICJleUpoYkdjaU9pSklVekkxTmlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKbGJXRnBiQ0k2SW5SbGMzUkFZMjl0Y0dGdWVTNWpiMjBpZlEuV0pjckVUUi1MZnFtX2xrdE9vdjd0Q1ktTmZYR2JuYTVUMjhaeFhTaEZ4SSIsICJjb25uZWN0b3JfYWNjZXNzX3Rva2VucyI6IHsiZ29vZ2xlIjogImFiYyJ9fQ==

Follow the same process as before. When you call the tool, you should see the following log in the terminal where you started the server:

```
This tool was called by: test@company.com
```
