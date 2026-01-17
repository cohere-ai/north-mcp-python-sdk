import httpx
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import Context
from north_mcp_python_sdk import NorthMCPServer

load_dotenv()

# update all the mcp tool functions to be <firstname_lastname>_<tool>
# since mcp tool names MUST be unique

mcp = NorthMCPServer(
    name="Google Calendar",
    host="0.0.0.0",
    port=3002
)

CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"

def _get_google_token():
    return os.getenv("ACCESS_TOKEN")


async def _fetch_calendar_data(access_token: str, url: str, params: dict = None):
    """Helper function for GET requests to Google Calendar API"""
    # Authorization header authenticates with Google using OAuth2 bearer token
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Using async/await for non-blocking I/O - allows the server to handle multiple
    # calendar requests concurrently while waiting for Google API responses
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        # raise_for_status() converts HTTP errors (401, 404, 500, etc.) into exceptions
        # immediately, preventing attempts to parse error responses as valid JSON
        response.raise_for_status()
        return response.json()


async def _modify_calendar_data(access_token: str, url: str, method: str, json_payload: dict = None):
    """Helper function for POST/DELETE requests to Google Calendar API"""
    # Authorization header authenticates with Google using OAuth2 bearer token
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Content-Type header tells Google the payload format (only needed when sending data)
    if json_payload:
        headers["Content-Type"] = "application/json"
    
    async with httpx.AsyncClient() as client:
        # json_payload is the request body containing data to send (e.g., event details
        # for creating/updating events). It's automatically serialized to JSON format.
        response = await client.request(
            method,
            url,
            headers=headers,
            json=json_payload
        )
        response.raise_for_status()
        
        # 204 = "No Content" - request succeeded but no response body (typical for DELETE)
        # Return success dict instead of trying to parse empty response as JSON
        if response.status_code == 204:
            return {"success": True}
        
        return response.json()



def format_event_to_document(event):
    """Convert a calendar event to a well-formatted document"""
    summary = event.get("summary", "(No title)")
    description = event.get("description", "")
    location = event.get("location", "")
    html_link = event.get("htmlLink", "")
    
    # Format start and end times
    # Google Calendar has two event types:
    # - Timed events: {"start": {"dateTime": "2026-01-15T10:00:00Z"}}
    # - All-day events: {"start": {"date": "2026-01-15"}}
    start = event.get("start", {})
    end = event.get("end", {})
    # Nested fallback: try dateTime first (timed events), then date (all-day), then default
    start_time = start.get("dateTime", start.get("date", "Not specified"))
    end_time = end.get("dateTime", end.get("date", "Not specified"))
    
    # Format attendees
    attendees = event.get("attendees", [])
    attendees_formatted = []
    for attendee in attendees:
        name = attendee.get("displayName", attendee.get("email", "Unknown"))
        status = attendee.get("responseStatus", "needsAction")
        organizer = " (Organizer)" if attendee.get("organizer") else ""
        attendees_formatted.append(f"{name} - {status}{organizer}")
    
    # Format conference data
    # Entry points are different ways to join a meeting: video link, phone dial-in, SIP address
    # We filter for "video" type to get the clickable URL (Google Meet/Zoom link)
    conference_link = ""
    conference_data = event.get("conferenceData", {})
    if conference_data:
        entry_points = conference_data.get("entryPoints", [])
        for entry in entry_points:
            # Only extract video conference link (e.g., meet.google.com/abc-defg-hij)
            if entry.get("entryPointType") == "video":
                conference_link = entry.get("uri", "")
                break  # Stop after finding the first video link
    
    
    # Build formatted content
    content = f"# {summary}\n\n"
    
    if description:
        content += f"**Description:** {description}\n\n"
    
    content += f"**Start:** {start_time}\n"
    content += f"**End:** {end_time}\n\n"
    
    if location:
        content += f"**Location:** {location}\n\n"
    if attendees_formatted:
        content += f"**Attendees ({len(attendees_formatted)}):**\n"
        for attendee in attendees_formatted:
            content += f"  - {attendee}\n"
        content += "\n"
    
    if conference_link:
        content += f"**Video Conference:** {conference_link}\n\n"
    status = event.get("status", "confirmed")
    content += f"**Status:** {status}\n"
    
    if html_link:
        content += f"**Link:** {html_link}\n"
    
    return {
        "id": event.get("id"),
        "kind": event.get("kind", "calendar#event"),
        "title": summary,
        "url": html_link,
        "content": content.strip(),
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
        "attendees_count": len(attendees)
    }


@mcp.tool()
async def firstname_lastname_list_calendar_events(
    ctx: Context,
    max_results: int = 10,
    time_min: str = None,
    time_max: str = None,
    search_query: str = None
):
    """List events from the user's primary calendar with optional filtering
    Args:
        ctx: Request context
        max_results: Maximum number of events to return (default: 10)
        time_min: Lower bound for event start time (RFC3339 format, e.g., "2024-01-15T00:00:00Z")
        time_max: Upper bound for event end time (RFC3339 format)
        search_query: Free text search to find events matching keywords
    Returns:
        List of formatted calendar events with detailed information
    """
    token = _get_google_token()
    
    # Build query parameters for Google Calendar API
    params = {
        "maxResults": max_results,
        "singleEvents": True,  # Expand recurring events into individual instances
        "orderBy": "startTime"  # Sort chronologically (requires singleEvents=True)
    }
    
    # Add optional filters if provided
    if time_min:
        params["timeMin"] = time_min
    if time_max:
        params["timeMax"] = time_max
    if search_query:
        params["q"] = search_query  # Free text search across event fields
    
    # Fetch events from the user's primary calendar
    response = await _fetch_calendar_data(
        token,
        f"{CALENDAR_API_BASE}/calendars/primary/events",
        params=params
    )
    
    # Convert raw API response items to formatted documents
    events = [format_event_to_document(item) for item in response.get("items", [])]
    
    result = {
        "events": events,
        "total_returned": len(events)
    }
    
    # Handle pagination - Google splits large result sets across multiple requests
    # If there are more events beyond maxResults, Google returns a nextPageToken
    # (e.g., "CiQKGjBhaWs...XyZ") that can be used to fetch the next batch of events
    # To get the next page, pass this token as the 'pageToken' parameter in a new request
    if response.get("nextPageToken"):
        result["next_page_token"] = response["nextPageToken"]
        result["has_more"] = True  # Signal to caller that more data is available
    
    return result


# destructiveHint=True triggers safety prompts, asking the user to confirm
# before creating a calendar event (prevents accidental data modifications)
@mcp.tool(annotations={"destructiveHint": True})
async def firstname_lastname_create_calendar_event(
    ctx: Context,
    title: str,
    start_time: str,
    end_time: str,
    description: str = "",
    location: str = "",
    attendees: str = None
):
    """Create a new calendar event with optional attendees and location
    Args:
        ctx: Request context
        title: Event title/summary
        start_time: Start time in RFC3339 format (e.g., "2024-01-15T10:00:00Z")
        end_time: End time in RFC3339 format (e.g., "2024-01-15T11:00:00Z")
        description: Optional event description
        location: Optional event location
        attendees: Comma-separated list of email addresses (e.g., "user1@example.com,user2@example.com")
    Returns:
        Created event details with formatted information
    """
    token = _get_google_token()
    event_data = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_time, "timeZone": "UTC"},
        "end": {"dateTime": end_time, "timeZone": "UTC"}
    }
    
    if location:
        event_data["location"] = location
    if attendees:
        email_list = [email.strip() for email in attendees.split(",")]
        event_data["attendees"] = [{"email": email} for email in email_list]
    
    response = await _modify_calendar_data(
        token,
        f"{CALENDAR_API_BASE}/calendars/primary/events",
        method="POST",
        json_payload=event_data
    )
    
    return format_event_to_document(response)


@mcp.tool()
async def firstname_lastname_get_calendar_event(ctx: Context, event_id: str):
    """Get detailed information about a specific calendar event
    Args:
        ctx: Request context
        event_id: The ID of the event to retrieve
    Returns:
        Detailed event information with formatted content
    """
    token = _get_google_token()
    response = await _fetch_calendar_data(
        token,
        f"{CALENDAR_API_BASE}/calendars/primary/events/{event_id}"
    )
    
    return format_event_to_document(response)


# destructiveHint=True triggers safety prompts, asking the user to confirm
# before deleting a calendar event (prevents accidental data loss)
@mcp.tool(annotations={"destructiveHint": True})
async def firstname_lastname_delete_calendar_event(ctx: Context, event_id: str):
    """Delete a calendar event by ID
    Args:
        ctx: Request context
        event_id: The ID of the event to delete
    Returns:
        Success confirmation
    """
    token = _get_google_token()
    await _modify_calendar_data(
        token,
        f"{CALENDAR_API_BASE}/calendars/primary/events/{event_id}",
        method="DELETE"
    )
    
    return {"success": True, "message": f"Event {event_id} deleted successfully"}


# destructiveHint=True triggers safety prompts, asking the user to confirm
# before updating a calendar event (prevents accidental data modifications)
@mcp.tool(annotations={"destructiveHint": True})
async def firstname_lastname_update_calendar_event(
    ctx: Context,
    event_id: str,
    title: str = None,
    start_time: str = None,
    end_time: str = None,
    description: str = None,
    location: str = None,
    attendees: str = None
):
    """Update an existing calendar event
    Args:
        ctx: Request context
        event_id: The ID of the event to update
        title: New event title/summary (optional)
        start_time: New start time in RFC3339 format (optional)
        end_time: New end time in RFC3339 format (optional)
        description: New event description (optional)
        location: New event location (optional)
        attendees: New comma-separated list of email addresses (optional)
    Returns:
        Updated event details with formatted information
    """
    token = _get_google_token()
    
    # First, get the current event
    current_event = await _fetch_calendar_data(
        token,
        f"{CALENDAR_API_BASE}/calendars/primary/events/{event_id}"
    )
    
    # Update only the provided fields
    if title is not None:
        current_event["summary"] = title
    if description is not None:
        current_event["description"] = description
    if location is not None:
        current_event["location"] = location
    if start_time is not None:
        current_event["start"] = {"dateTime": start_time, "timeZone": "UTC"}
    if end_time is not None:
        current_event["end"] = {"dateTime": end_time, "timeZone": "UTC"}
    if attendees is not None:
        email_list = [email.strip() for email in attendees.split(",")]
        current_event["attendees"] = [{"email": email} for email in email_list]
    
    response = await _modify_calendar_data(
        token,
        f"{CALENDAR_API_BASE}/calendars/primary/events/{event_id}",
        method="PUT",
        json_payload=current_event
    )
    
    return format_event_to_document(response)


# Use streamable-http transport to enable streaming responses over HTTP.
# This allows the server to send data to the client incrementally (in chunks),
# improving responsiveness for long-running or large operations.
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
