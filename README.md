# North MCP Python SDK

This sdk builds on top of the original sdk. Please refer to the [Readme](https://cohereai.slack.com/archives/C08J3LZF7J6/p1746702928707359) of this repository first. This Readme will only include north relevant information.


## Why this repository
This repository includes code that allows your server to use authentication with north, which is a custom extension to the original spec. Other than that we do not make any changes to the sdk, we are building on top of it.


## Main differences

* north does only support the SSE transport (which will be replace by StreamableHTTP) and the stdio transport
* you may protect all requests to your server with a secret
* you may have access to the users oauth token to access third party services on their behalft
* you may have access to users identity (from the identity provider that is being used with north)


## Authentication

This sdk offers several stragies for authenticating your users and authorizing their requests.


#### I only want north to be able to send requests to my server
```python
mcp = NorthMCPServer(name="Demo", port=5222, server_secret="secret")
```

#### I want to get the identity of the north user that is calling my server
Refer to `examples/server.py`. During your request call the following:
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

This guide discribes how you can test your mcp server locally without connecting it to north. For this we will be using the MCP Inspector. You can run it with:
```
npx @modelcontextprotocol/inspector
```

If we do not care about auth and we just want to run it locally we are able to choose the stdio transport. Navigate to the (MCP Inspector)[http://127.0.0.1:6274] and configure it like this:
* Transport Type: stdio
* Command: uv
* Arguments: run examples/server.py --transport stdio

From here:
* Click "Connect"
* Select "Tools" on the top of the screen.
* Click "List Tools" -> "add"
* Add the numbers and click "Run". You should see the sum.


### Adding authentication

If you want to test the authentication mechanism locally you can do the following. First start the server in with the see transport:

```
uv run examples/server.py --transport sse
```

Next we need to create a beaerer token. You can create on using `examples/create_bearer_token.py` or use a pre-made one ()

Navigate to the MCP Inspector and configure it like this:
* Transport Type: SSE
* URL: http://localhost:5222/sse
* Authentication -> Bearer token: eyJzZXJ2ZXJfc2VjcmV0IjogInNlcnZlcl9zZWNyZXQiLCAidXNlcl9pZF90b2tlbiI6ICJleUpoYkdjaU9pSklVekkxTmlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKbGJXRnBiQ0k2SW5SbGMzUkFZMjl0Y0dGdWVTNWpiMjBpZlEuV0pjckVUUi1MZnFtX2xrdE9vdjd0Q1ktTmZYR2JuYTVUMjhaeFhTaEZ4SSIsICJjb25uZWN0b3JfYWNjZXNzX3Rva2VucyI6IHsiZ29vZ2xlIjogImFiYyJ9fQ==

Go through the same process as before. Now when you call the tool you should see the following log in your terminal where you started the server:

```
This tool was called by: test@company.com
```
