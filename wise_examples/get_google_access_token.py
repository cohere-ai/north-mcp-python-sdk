from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file(
    "client_secret.json", SCOPES
)

creds = flow.run_local_server(port=0)

service = build("calendar", "v3", credentials=creds)

print("Access token:", creds.token)
print("Refresh token:", creds.refresh_token)