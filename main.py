import argparse
import json
import os
import re
from datetime import date, datetime, timedelta
from icalendar import Calendar as iCalendar
import openai
from ics import Calendar, Event
import pytz



def configure():
    # Pre-defined list of common timezones
    common_timezones = [
        "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
        "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid", "Europe/Rome"
    ]

    if os.path.exists('preferences.json'):
        with open('preferences.json', 'r') as file:
            preferences = json.load(file)
    else:
        preferences = {}
        preferences['ics_path'] = input("Enter the path to your ICS file: ")
        preferences['txt_path'] = input("Enter the path to your text file: ")

        # Display the common timezones and ask for user input
        print("Select a timezone from the list below:")
        for idx, tz in enumerate(common_timezones, start=1):
            print(f"{idx}. {tz}")
        print(f"{len(common_timezones) + 1}. Enter your own")

        tz_choice = int(input("Enter the number corresponding to your timezone: "))
        if 1 <= tz_choice <= len(common_timezones):
            preferences['timezone'] = common_timezones[tz_choice - 1]
        elif tz_choice == len(common_timezones) + 1:
            custom_tz = input("Enter your timezone (e.g., America/Chicago): ")
            # Validate the custom timezone
            if custom_tz in pytz.all_timezones:
                preferences['timezone'] = custom_tz
            else:
                print("Invalid timezone. Defaulting to UTC.")
                preferences['timezone'] = "UTC"
        else:
            print("Invalid selection. Defaulting to UTC.")
            preferences['timezone'] = "UTC"

        with open('preferences.json', 'w') as file:
            json.dump(preferences, file)

    return preferences

# Step 2: Data Extraction
def extract_data(preferences):
    # Load the ICS file
    with open(preferences['ics_path'], 'r') as f:
        ics_content = f.read()

    # Parse the ICS file
    ical = Calendar(ics_content)

    # Get the configured timezone or default to UTC if not set
    timezone_str = preferences["timezone"]
    local_tz = pytz.timezone(timezone_str)

    # Get the current date in the configured timezone
    today = datetime.now(local_tz).date()

    # Extract today's events from the ICS file
    today_events = []
    for event in ical.events:
        dtstart = event.begin.datetime
        # Convert to the configured timezone if it's a timezone-aware datetime
        if dtstart.tzinfo is not None:
            dtstart = dtstart.astimezone(local_tz)
        if dtstart.date() == today:
            dtend = event.end.datetime
            if dtend.tzinfo is not None:
                dtend = dtend.astimezone(local_tz)
            today_events.append({'summary': event.name, 'start': dtstart, 'end': dtend})

    # Load the text file and extract tasks
    with open(preferences['txt_path'], 'r') as f:
        tasks = f.readlines()

    return today_events, tasks
# Step 3: Interaction with AI
def interact_with_ai(messages):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or whichever model you're using
            messages=messages
        )
        reply = response['choices'][0]['message']['content'].strip()
        print(f"AI Response: {reply}")  # Debug output
        return reply
    except Exception as e:
        print(f"Error in AI interaction: {e}")
        raise

def generate_schedule(events, tasks):
    # Convert the events and tasks to text
    events_text = '\n'.join([f"{event['summary']}: {event['start'].strftime('%H:%M')} - {event['end'].strftime('%H:%M')}" for event in events])
    tasks_text = '\n'.join(tasks)
    
    # Construct the initial prompt for the AI
    prompt = f"""
    I am going to give you a list of calendar events and tasks for today that we will work together on to make a daily schedule. 
    Here is the list of events and tasks: 
    Events:
    {events_text}
    Tasks:
    {tasks_text}
    """

    prompt = f"""
    I am going to give you a list of calendar events and tasks for today that we will work together on to make a daily schedule. The schedule output  must have one event on each line and must be in the exact format like this: start time, duration in minutes, event description. An example line looks like this: 09:00, 30m, Book your NYC trip. Only output the schedule output and no additional text or information.

    Events:
    {events_text}
    Tasks:
    {tasks_text}
    """

    
    print(f"Initial Prompt: {prompt}")  # Debug output
    
    # Initial message to the AI
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    # Send the initial prompt to the AI
    reply = interact_with_ai(messages)
    
    schedule_lines = []
    for line in reply.split('\n'):  # Loop through each line of the output
        match = re.match(r'(\d+:\d+),\s*(\d+)m,\s*(.+)', line)  # Updated regex pattern to match the new schedule format
        if match:
            start_time, duration_minutes, description = match.groups()
            # Convert to 24-hour format
            start_hour, start_minute = map(int, start_time.split(':'))
            # Calculate end time in minutes
            end_time_minutes = (start_hour * 60 + start_minute) + int(duration_minutes)
            # Convert back to hour and minute format
            end_hour = end_time_minutes // 60
            end_minute = end_time_minutes % 60
            formatted_line = f"{start_hour:02d}:{start_minute:02d}-{end_hour:02d}:{end_minute:02d}, {duration_minutes}m, {description}"
            schedule_lines.append(formatted_line)
    if schedule_lines:  # Check if there are any schedule lines in the output
        print(f"Schedule: {schedule_lines}")
        return schedule_lines
    else:
        raise ValueError("No schedule lines found in the output")  # Throw an error if the output is empty





# Step 5: Format Validation
def validate_format(schedule):
    try:
        for line in schedule:
            values = line.split(', ')
            if len(values) != 3:
                raise ValueError(f"Unexpected format: {line}. Expected format: 'HH:MM, Xm, Description'")
            time, duration, description = values
            assert re.match(r'\d{2}:\d{2}', time), f"Invalid time format in line: {line}"
            assert re.match(r'\d+m', duration), f"Invalid duration format in line: {line}"
    except Exception as e:
        print(f"Error in format validation: {e}")
        raise

def create_ics(schedule, preferences):
    try:
        # Create the header of the ICS file
        ics_content = "BEGIN:VCALENDAR\nVERSION:2.0\n"
        
        for line in schedule:
            time_str, duration, description = line.split(', ')
            # Split the time string into start and end times
            start_time_str, end_time_str = time_str.split('-')
            # Parse the start time
            start_time = datetime.combine(date.today(), datetime.strptime(start_time_str, '%H:%M').time())
            # Calculate the end time
            duration_minutes = int(duration[:-1])
            end_time = start_time + timedelta(minutes=duration_minutes)
            timezone = preferences.get('timezone', 'UTC')
            # Create the event string in ICS format
            event_string = (
                f"BEGIN:VEVENT\n"
                f"SUMMARY:{description}\n"
                f"DTSTART;TZID={timezone}:"
                f"{start_time.strftime('%Y%m%dT%H%M%S')}\n"
                f"DTEND;TZID={timezone}:"
                f"{end_time.strftime('%Y%m%dT%H%M%S')}\n"
                f"END:VEVENT\n"
            )
            # Append the event string to the ICS content
            ics_content += event_string
        
        # Create the footer of the ICS file
        ics_content += "END:VCALENDAR\n"
        
        with open('generated_schedule.ics', 'wt', encoding='utf-8') as file:
            file.write(ics_content)
    except Exception as e:
        print(f"Error in ICS file creation: {e}")
        raise





# Function to calculate the end time based on the start time and duration
def calculate_end_time(start_time, duration):
    # Split the start time into hours and minutes
    start_hour, start_minute = map(int, start_time.split(':'))
    
    # Split the duration into hours and minutes
    duration_hours, duration_minutes = divmod(int(duration[:-1]), 60)
    
    # Calculate the end time
    end_hour = start_hour + duration_hours
    end_minute = start_minute + duration_minutes
    
    # Adjust the hours and minutes if necessary
    if end_minute >= 60:
        end_hour += 1
        end_minute -= 60
    
    return f'{end_hour:02d}:{end_minute:02d}'

# Main function
def main():
    openai.api_key = os.getenv('OPENAI_API_KEY')
    preferences = configure()
    events, tasks = extract_data(preferences)
    schedule = generate_schedule(events, tasks)
    validate_format(schedule)
    create_ics(schedule, preferences)

if __name__ == '__main__':
    main()
