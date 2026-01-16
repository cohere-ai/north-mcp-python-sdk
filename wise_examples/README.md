## Adding your own MCP server walkthough ##

### 1. Get your enviornment set up ###

```bash
# clone this repo
git clone https://github.com/cohere-ai/north-mcp-python-sdk.git

# enter the repo
cd north-mcp-python-sdk

# switch to our wise branch
git switch wise_2026_conference

# go into our example directory
cd wise_examples

# install uv 
curl -LsSf https://astral.sh/uv/install.sh | sh

# install the requirements
uv sync

# activate the newly created environment
source .venv/bin/activate
```

If you have not previously run ngrok you will get the following error when running 
```bash 
ngrok http <port>

ValueError: ('failed to connect session', 'Usage of ngrok requires a verified account and authtoken.\
Sign up for an account: https://dashboard.ngrok.com/signup\n \
Install your authtoken: https://dashboard.ngrok.com/get-started/your-authtoken', 'ERR_NGROK_4018')
```

You must create an account and get your authtoken
```bash
https://dashboard.ngrok.com/signup
https://dashboard.ngrok.com/get-started/your-authtoken
```

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/b8cc8b48-5e5d-415d-bf55-975731fe8ac9"
    width="600"
  />
</p>

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/986304ca-6caa-4863-9997-a250221ce1c9"
    width="900"
  />
</p>

To add your authtoken you can run 
```bash 
ngrok config add-authtoken $YOUR_AUTHTOKEN
```
<br />

---

<br />

### 2. Create your MCP servers

_**Full code will be available after the workshop!**_

```bash
code simple_calculator.py
code <mcp_server_filename>
```


Start your server with 
```bash
uv run <mcp_server_filename>
```
<p align="center">
  <img
    src="https://github.com/user-attachments/assets/53c510f7-39b6-4e71-bd84-9c65bfd99996"
    width="600"
  />
</p>



Start your ngrok server with
```bash
ngrok http <port>
ie. ngrok http 3001
```
<p align="center">
  <img
    src="https://github.com/user-attachments/assets/f05a0b4c-980b-45cc-8354-96af3032799d"
    width="600"
  />
</p>


<br />

---

<br />

### 3. (Optional) Hard-code your connector credentials

In some instances your MCP server will need to connect to another service such as the google api (for google calendar, gmail, drive, etc.) or spotify, linear, etc.

Here's how to get the credentials for a common connector: Google API



Step-by-step to get OAuth Client ID and Secret:

1. Go to https://console.cloud.google.com
2. Create/Select a Project:
3. Click the project dropdown at the top
4. Click "New Project" or select an existing one

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/b99aa112-ccff-4f96-93df-f5f232b9eaf8"
    width="600"
  />
</p>

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/0585d53a-1cfe-408c-b086-15a56622c0da"
    width="600"
  />
</p>

Enable Calendar API:

5. Go to "APIs & Services" → "Library" (left sidebar)
6. Search for "Google Calendar API"
7. Click it and press "Enable"

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/cca3cefd-b6f1-4111-84fa-e412f0fb689c"
    width="600"
  />
</p>

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/b39b9765-b8a5-441b-a4bf-f89340fd702a"
    width="600"
  />
</p>


Create OAuth Credentials:

8. Go to "APIs & Services" → "Credentials" (left sidebar)

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/cca3cefd-b6f1-4111-84fa-e412f0fb689c"
    width="600"
  />
</p>

9. Click "Create Credentials" → "OAuth client ID"

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/65f7577a-f871-4212-800e-0bc760633115"
    width="600"
  />
</p>

10. If prompted, configure the OAuth consent screen first:

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/c2d136da-28bf-42f2-83dd-6cf8ee4d8a8c"
    width="600"
  />
</p>

11. Fill in app name (e.g., "My Calendar App")
12. Add your email
13. Choose "External"

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/f1cb0ccd-0d60-4569-a5bc-c377d2e80153"
    width="600"
  />
</p>


Back to Create OAuth client ID:

14. Choose "Desktop app" as Application type
15. Give it a name (e.g., "Calendar Desktop Client")

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/ef04341b-e9a6-42ac-b01c-b7aecbf51b32"
    width="600"
  />
</p>

Get Your Credentials:

16. A popup shows your Client ID and Client Secret; Copy both and/or download the JSON file. You can always view them again in the Credentials page

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/8ae5c7ae-0508-4c6d-91ea-0639e1907ec8"
    width="600"
  />
</p>

Next we need to use these to get our access token.

17. Add your downloaded JSON file with the Client ID and Client Secret to <code>client_secret.json</code>

18. Run <code>get_google_access_token.py</code> and it'll output both an access token (will expire in ~1 hour) and a refresh token (will be used to create a new access token once it expires) !

We can now use all these tokens to hardcode our credentials in our google calendar mcp server

<br />

---

<br />

### 4. Add your MCP server to North

To get your North Token go to https://gtxcc.democloud.cohere.com/developer/python
<p align="center">
  <img
    src="https://github.com/user-attachments/assets/23102dad-1011-4929-8908-c24cf7ce5216"
    width="600"
  />
</p>

Run the following commands:

```bash 
export NORTH_TOKEN=<north token>
export HOST=https://gtxcc.democloud.cohere.com/api
export URL=<ngrok url>
```

To see which servers are running:
```bash
curl --location "${HOST}/internal/v1/mcp_servers" --header "Content-Type: application/json" --header "Authorization: Bearer ${NORTH_TOKEN}"
```

To register your server:
```bash
curl --location "${HOST}/internal/v1/mcp_servers" \
--header "Content-Type: application/json" \
--header "Authorization: Bearer ${NORTH_TOKEN}" \
--data '{
    "url": "'"${URL}"'",
    "name": "Google Calendar"
}'
```

To delete your server:
```bash
curl --location --request DELETE "${HOST}/internal/v1/mcp_servers/<server_id>" \
--header "Content-Type: application/json" \
--header "Authorization: Bearer ${NORTH_TOKEN}"
```

Your server is now running!

Sign into North here to try it out!

```bash
https://gtxcc.democloud.cohere.com/
```

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/1ebba75f-bd1e-4f51-971d-eb1fa9338c58"
    width="600"
  />
</p>

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/717a0e5c-85d9-4c1b-a78b-d90b2b974389"
    width="600"
  />
</p>

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/2f50639f-dac6-49ba-bcd2-37e47055abc1"
    width="800"
  />
</p>

<p align="center">
  <img
    src="https://github.com/user-attachments/assets/b33a1aca-38bf-4860-9350-0f02c95d5a6c"
    width="700"
  />
</p>


You'll now be able to see the new connector. Click to enable it!


https://github.com/user-attachments/assets/086afa4c-eb1f-45de-84cf-2d8551edfb74

