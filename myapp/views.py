from django.shortcuts import get_object_or_404, render, HttpResponse, redirect
import datetime
from datetime import datetime  
from googleapiclient.errors import HttpError
from .models import Event
from django.utils.timezone import now
from google.oauth2.credentials import Credentials
import os
import google.auth
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from django.shortcuts import redirect
from django.conf import settings
from django.http import HttpResponse
from django.contrib import messages

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

shared_calendar = "1088ada1fc24b3e0ee5110ef549430fd772009d8fed3757ea007daa1a9cae5d9@group.calendar.google.com"
personal = "primary"

# Create your views here.
def login(request): 
    return render(request, 'html/loginpage.html')


def upcoming(request):
    credentials = google.oauth2.credentials.Credentials(
        **request.session['credentials']
    )

    # Build the service
    service = build('calendar', 'v3', credentials=credentials)

    calendar_type = request.GET.get('calendar', 'personal')

    calendar_id = personal if calendar_type == "personal" else shared_calendar

    # Get current time in RFC3339 format
    current_time = datetime.utcnow().isoformat() + 'Z'  # 'Z' means UTC time

    # Call the Calendar API to fetch upcoming events only
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=current_time,  # Fetch only future events
        maxResults=10,
        singleEvents=True,
        orderBy='startTime',
    ).execute()

    events = events_result.get('items', [])

# Add creator_email only for the shared calendar
    if calendar_type == "shared":
        events = process_event_times(events)
        for event in events:
            event['creator_email'] = event.get("creator", {}).get("email", "Unknown")
    
    # Normalize event start and end times for the personal calendar
    if calendar_type == "personal":
        events = process_event_times(events)
    return render(request, "./html/upcoming.html", {'events': events, 'current_calendar': calendar_type})


def google_login(request):
    # Check if the user is already logged in or has a session
    if 'credentials' in request.session:
        del request.session['credentials']

    # Set up the OAuth2 flow
    flow = Flow.from_client_secrets_file(
        'myapp/client_secret.json',  # Path to JSON credentials
        scopes=['https://www.googleapis.com/auth/calendar'],
        redirect_uri='http://127.0.0.1:8000/google/callback/'
    )

    # Request the authorization URL and generate the state
    authorization_url, state = flow.authorization_url(
        access_type='offline',  # Request offline access to allow refresh token
        prompt='select_account'  # Always prompt the user to select an account
    )

    # Store the state in the session for validation during the callback
    request.session['state'] = state

    # Redirect the user to the Google OAuth authorization URL
    return redirect(authorization_url)

def credentials_to_dict(credentials):
    """Converts credentials to a dictionary."""
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
    }


def google_callback(request):
    # Log the state in the session before checking
    print("Session state before callback:", request.session['state'])

    state_from_request = request.GET.get('state')  # Retrieve state from the query parameter
    session_state = request.session.get('state')  # Retrieve state from the session

    # Log both the request state and session state for debugging
    print(f"State from request: {state_from_request}")
    print(f"Session state: {session_state}")

    # Check if the states match
    if state_from_request != session_state:
        return HttpResponse("State mismatch! Possible CSRF attack.", status=400)

    flow = Flow.from_client_secrets_file(
        'myapp/client_secret.json',
        scopes=['https://www.googleapis.com/auth/calendar'],
        state=state_from_request,
        redirect_uri='http://127.0.0.1:8000/google/callback/'
    )
    flow.fetch_token(authorization_response=request.build_absolute_uri())
    credentials = flow.credentials
    request.session['credentials'] = credentials_to_dict(credentials)

    return redirect('upcoming')


def addtask(request):
    """Add a Google Calendar event."""
    credentials = Credentials(**request.session['credentials'])
    service = build('calendar', 'v3', credentials=credentials)

    if request.method == 'POST':
        try:
            # Fetch form data
            summary = request.POST.get("TaskName", "No Title")
            description = request.POST.get("desc", "")
            start_time = request.POST.get("startTime", "")
            end_time = request.POST.get("endTime", "")
            calendar = request.POST.get('calendar', 'personal') 

            # Validate that the start_time and end_time are in correct format
            if "T" not in start_time or "T" not in end_time:
                return HttpResponse("Invalid date-time format. Use YYYY-MM-DDTHH:MM:SS", status=400)

            # If it's a timed event (with "T"), use dateTime and timeZone
            start = start_time
            end = end_time
            TIMEZONE = "GMT"

            start_time = start_time + ":00Z"  # Format as UTC
            end_time = end_time + ":00Z"

            
            if calendar == "personal":
                calendar_id = personal
            else:
                calendar_id = shared_calendar
                conflict = check_event_conflict(service, start_time, end_time)

                if conflict:
                    messages.error(request, "The selected time slot is already occupied by another event.")
                    return redirect("addtask")  # Redirect back to form with message


            # Prepare the event data to match the Google API example structure
            event_data = {
                'summary': summary,
                'description': description,
                "start": {
                    "dateTime": start+":00",
                    "timeZone": TIMEZONE
                },
                "end": {
                    "dateTime": end+":00",
                    "timeZone": TIMEZONE
                },
            }

            # Attempt to create the event on the Google Calendar
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event_data
            ).execute()

            return redirect("upcoming")

        except HttpError as e:
            # Return detailed Google API error message
            error_details = e.content.decode('utf-8')
            print(f"Google API Error: {error_details}")
            return HttpResponse(f"Error creating event: {error_details}", status=400)

    return render(request, "./html/task.html")


def check_event_conflict(service, start_time, end_time):
    print(start_time)
    print(end_time)
    events_result = service.events().list(
        calendarId=shared_calendar,
        timeMin=start_time,
        timeMax=end_time,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    for event in events:
        print(event)
    return len(events) > 0
    

def event_delete(request, event_id, calendar):
    credentials = Credentials(**request.session['credentials'])
    service = build('calendar', 'v3', credentials=credentials)
    if calendar == "personal":
        calendar_id = personal
    else:
        calendar_id = shared_calendar

    # Delete event from Google Calendar
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

    return redirect(f'/upcoming/?calendar={calendar}')


def convert_to_datetime(date_str, is_full_day=False):
    """Convert a string to a datetime object."""
    try:
        if is_full_day:
            return datetime.strptime(date_str, "%Y-%m-%d")
        else:
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None  # Return None if the date format is incorrect or invalid


def format_datetime(dt, format_type="full"):
    if not dt:
        return "Unknown Time"
    
    if format_type == "date":
        return dt.strftime("%d %b") 
    elif format_type == "time":
        return dt.strftime("%H:%M")
    else:
        return dt.strftime("%d %b %H:%M") 
    


def calculate_days_left(event_date):
    """Calculate the number of days between today and the event date."""
    today = datetime.utcnow().date()  # Get today's date (UTC)
    if event_date is None:
        return None
    days_left = (event_date.date() - today).days  # Difference in days
    return days_left


def process_event_times(events):
    """Process all events, converting start_time and end_time correctly."""
    for event in events:
        event['event_id'] = event.get('id')
        start_time_str = event['start'].get('dateTime')
        end_time_str = event['end'].get('dateTime')
        full_day_start = event['start'].get('date') # Full-day event

        # Determine if the event is a full-day event
        is_full_day = bool(full_day_start and not start_time_str)

        # Convert start time
        if start_time_str:
            start_time_dt = convert_to_datetime(start_time_str)
        elif full_day_start:
            start_time_dt = convert_to_datetime(full_day_start, is_full_day=True)
        else:
            start_time_dt = None

        # Convert end time
        if not is_full_day and end_time_str:
            end_time_dt = convert_to_datetime(end_time_str)
        else:
            end_time_dt = None

        # Store both raw and formatted versions
        event['start_date'] = format_datetime(start_time_dt, "date")
        event['start_time'] = format_datetime(start_time_dt, "time")

        if not is_full_day:
            event['end_date'] = format_datetime(end_time_dt, "date")
            event['end_time'] = format_datetime(end_time_dt, "time")
        else:
            event['end_date'] = None
            event['end_time'] = None

        # Calculate days left
        event['days_left'] = calculate_days_left(start_time_dt)

        if event['start_date'] == event['end_date'] or event['end_date'] is None:
            event['display_date'] = event['start_date']  # Only show the start date
        else:
            event['display_date'] = f"{event['start_date']} - {event['end_date']}"  # Show both start and end date

        if  event['end_time'] is None:
            event['display_time'] = "All day"  # Only show the start time
        else:
            event['display_time'] = f"{event['start_time']} - {event['end_time']}"  # Show both start and end time

    return events

