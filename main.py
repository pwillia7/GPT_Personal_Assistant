import json
import os
import argparse
import re
from datetime import date, datetime, timedelta
from icalendar import Calendar as iCalendar
import openai
from ics import Calendar, Event
import pytz
import webbrowser
import requests

def open_ics_file(file_path):
    try:
        webbrowser.open(file_path)
    except Exception as e:
        print(f"Failed to open the ICS file: {e}")

def configure():
    print("Configuring preferences...")

    # Pre-defined list of common timezones
    common_timezones = [
        "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
        "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid", "Europe/Rome"
    ]

    if os.path.exists('preferences.json'):
        with open('preferences.json', 'r') as file:
            preferences = json.load(file)
            print("Preferences file found!")
    else:
        print("No Preferences file found. Starting Preferences generation.")
        preferences = {}
        preferences['ics_path'] = input("Enter the path to your ICS file: ")
        preferences['txt_path'] = input("Enter the path to your Task txt file: ")

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

        # New user preferences for scheduling
        print("\n(Optional) Scheduling Preferences:")

        preferences['include_existing_events'] = input("NOT WORKING: Do you want to include existing events in the final schedule? (yes/no): ").strip().lower()

        preferences['schedule_meals'] = input("Do you want me to schedule meals? (yes/no): ").strip().lower()
        if preferences['schedule_meals'] == 'yes':
            preferences['meal_prefs'] = input("Share your meal preferences such as which meals to schedule, preferred meal times, and duration, etc.: ").strip()
        else:
            preferences['meal_prefs'] = ''

        preferences['task_preference'] = input("Do you prefer to do your tasks before, after, or in-between your events? You can enter a combination of options: ").strip()
        preferences['specific_times'] = input("Are there specific times you prefer to do certain kinds of tasks? (e.g., creative tasks in the morning): ").strip()
        preferences['schedule_breaks'] = input("Do you want me to schedule breaks throughout the day? (yes/no): ").strip().lower()

        if preferences['schedule_breaks'] == 'yes':
            preferences['break_length'] = input("How long should the breaks be? (e.g., 15m): ").strip()
            preferences['break_frequency'] = input("How often should the breaks be? (e.g., every 2 hours): ").strip()
        else:
            preferences['break_length'] = ''
            preferences['break_frequency'] = ''

        preferences['start_time'] = input("What time do you want to start your day? (Optional, format HH:MM): ").strip()
        preferences['end_time'] = input("What time do you want to end your day? (Optional, format HH:MM): ").strip()

        with open('preferences.json', 'w') as file:
            json.dump(preferences, file)

    return preferences

# Step 2: Data Extraction
def extract_data(preferences):
    print("Extracting Calendar Events and Tasks...")
    ics_path = preferences['ics_path']
    if ics_path.startswith("https://"):
        response = requests.get(ics_path)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx and 5xx)
        ics_content = response.text
    else:
        with open(ics_path, 'r') as f:
            ics_content = f.read()

    ical = Calendar(ics_content)

    timezone_str = preferences["timezone"]
    local_tz = pytz.timezone(timezone_str)
    
    # Determine the target day
    if target_day == 'today':
        today = datetime.now(local_tz).date()
    elif target_day == 'tomorrow':
        today = (datetime.now(local_tz) + timedelta(days=1)).date()
    else:
        try:
            today = datetime.strptime(target_day, '%Y-%m-%d').date()
        except ValueError:
            print("Invalid date format. Defaulting to today's date.")
            today = datetime.now(local_tz).date()

    # Initialize today_events list
    today_events = []

    existing_event_times = set()
    for event in ical.events:
        dtstart = event.begin.datetime
        if dtstart.tzinfo is not None:
            dtstart = dtstart.astimezone(local_tz)
        if dtstart.date() == today:
            dtend = event.end.datetime
            if dtend.tzinfo is not None:
                dtend = dtend.astimezone(local_tz)
            today_events.append({'summary': event.name, 'start': dtstart, 'end': dtend})
            existing_event_times.add((dtstart.strftime('%H:%M'), dtend.strftime('%H:%M')))

    with open(preferences['txt_path'], 'r') as f:
        tasks = f.readlines()

    return today_events, tasks, existing_event_times


# Step 3: Interaction with AI
def interact_with_ai(messages):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or whichever model you're using
            messages=messages
        )
        reply = response['choices'][0]['message']['content'].strip()
        return reply
    except Exception as e:
        print(f"Error in AI interaction: {e}")
        raise

def get_preference_text(pref_key, pref_label):
    return f"{pref_label}: {preferences[pref_key]}" if preferences[pref_key] else ''


def generate_schedule(events, tasks):
    # Convert the events and tasks to text
    events_text = '\n'.join([f"{event['summary']}: {event['start'].strftime('%H:%M')} - {event['end'].strftime('%H:%M')}" for event in events])
    tasks_text = '\n'.join(tasks)
    
    # Construct the initial prompt for the AI
    initial_prompt = f"""
I am going to give you a list of calendar events and tasks for today that we will work together on to make a daily schedule.
User Preferences: {get_preference_text('task_preference', 'Task Preference')}, {get_preference_text('specific_times', 'Specific Times for Tasks')}, {get_preference_text('schedule_breaks', 'Schedule Breaks')}, {get_preference_text('break_length', 'Break Length')}, {get_preference_text('break_frequency', 'Break Frequency')}, {get_preference_text('start_time', 'Start Time')}, {get_preference_text('end_time', 'End Time')}, {get_preference_text('schedule_meals', 'Schedule Meals')}, {get_preference_text('meal_prefs', 'Meal Preferences')}


Use your best guess to determine the length of tasks. Ask up to 6 clarifying questions you have. Feel free to make suggestions you think will make the user's day better and more productive. 

Your questions output must start with a new line that says "Questions:" followed by each question on a new line.

Once the user has confirmed the schedule, output the schedule. The schedule output must have one event on each line and must be in the exact format like this: start time, duration in minutes, event description. An example line looks like this: 09:00, 30m, Book your NYC trip.

Here are the list of events and tasks. Do not change the start time or duration of events:
Events:
{events_text}
Tasks:
{tasks_text}
"""
    
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant tasked with creating a daily schedule based on the user's calendar events, tasks, and personal preferences. Aim to design a balanced and productive day, incorporating any specific user requests and preferences."
        },
        {
            "role": "user",
            "content": initial_prompt
        }
    ]
    schedule_confirmed = False
    print(f"Found Events:\n\n{events_text}\n\nFound Tasks:\n\n{tasks_text}")
    while not schedule_confirmed:

        ai_response = interact_with_ai(messages)

        schedule_lines, ai_questions = process_ai_response(ai_response)        

        if ai_questions:
            user_feedback = get_user_feedback(ai_questions)
            messages.extend([
                {"role": "assistant", "content": ai_questions},
                {"role": "user", "content": user_feedback}
            ])
        elif schedule_lines:
            user_response = get_user_confirmation(schedule_lines)
            if user_response is True:
                schedule_confirmed = True
            else:
                schedule_confirmed, feedback = user_response
                messages.extend([
                    {"role": "assistant", "content": '\n'.join(schedule_lines)},
                    {"role": "user", "content": feedback}
                ])

    return schedule_lines

def process_ai_response(ai_response):
    # Split the response into individual lines
    lines = ai_response.split('\n')
    
    # Initialize empty lists to hold the schedule lines and questions
    schedule_lines = []
    questions = []
    
    # Define a regex pattern to match the schedule line format 'HH:MM, Xm, Description'
    schedule_line_pattern = re.compile(r'\d{2}:\d{2}, \d{1,3}m, .+')
    
    # Initialize flags to indicate when we've started collecting schedule lines or questions
    collecting_schedule_lines = False
    collecting_questions = False
    
    # Iterate through each line in the response
    for line in lines:
        # If the line contains 'Questions:', start collecting questions
        if 'Questions:' in line:
            collecting_questions = True
            collecting_schedule_lines = False  # Stop collecting schedule lines if we were doing so
        
        # If the line matches the schedule line format, start collecting schedule lines
        elif schedule_line_pattern.match(line):
            collecting_schedule_lines = True
            collecting_questions = False  # Stop collecting questions if we were doing so
        
        # If we're collecting questions, add the current line to the questions list
        if collecting_questions:
            questions.append(line)
        
        # If we're collecting schedule lines, add the current line to the schedule lines list
        elif collecting_schedule_lines:
            schedule_lines.append(line)
    
    # Join the questions list into a single string, separating questions with '\n'
    ai_questions = '\n'.join(questions).strip()
    
    return schedule_lines, ai_questions



def get_user_feedback(prompt):
    print("\nGPT has " + str(len(prompt.split('\n')[1:])) +" questions for you.\n")
    feedback = []
    for question in prompt.split('\n')[1:]:  # Skip the 'Questions:' line
        if question:  # Ensure the question is not an empty string
            print(question)
            answer = input("Your Answer: ")
            feedback.append(answer)
    print("\nThanks! Generating your schedule...")
    return '\n'.join(feedback)

def get_user_confirmation(schedule_lines):
    print("\nProposed Schedule:")
    for line in schedule_lines:
        print(line)
    confirmation = input("\nIs this schedule acceptable? (yes/no): ")
    if confirmation.lower() == 'yes':
        return True
    elif confirmation.lower() == 'no':
        feedback = input("Please provide feedback on the schedule: ").strip()
        return False, feedback
    else:
        print("Invalid input. Please enter 'yes' or 'no'.")
        return get_user_confirmation(schedule_lines)
    
# Step 5: Format Validation
def validate_format(schedule):
    def convert_duration_to_minutes(duration):
        if 'hr' in duration:
            hours = int(duration.replace('hr', ''))
            return f'{hours * 60}m'
        return duration

    try:
        normalized_schedule = []  
        for line in schedule:
            if not line or len(line.split(', ')) != 3:
                continue  # Skip lines that don't have three comma-separated values
            values = line.split(', ')
            time, duration, description = values
            assert re.match(r'\d{2}:\d{2}', time), f"Invalid time format in line: {line}"
            
            # If the duration field is empty or invalid, skip this line
            if not re.match(r'\d+m', duration):
                continue

            normalized_duration = convert_duration_to_minutes(duration)
            assert re.match(r'\d+m', normalized_duration), f"Invalid duration format in line: {line}"
            normalized_schedule.append(f"{time}, {normalized_duration}, {description}")
        return normalized_schedule  
    except Exception as e:
        print(f"Error in format validation: {e}")
        raise


def create_ics(schedule, preferences, existing_event_times):
    try:
        ics_content = "BEGIN:VCALENDAR\nVERSION:2.0\n"

        for line in schedule:
            if not line or len(line.split(', ')) != 3 or not line.strip():
                continue
            try:
                start_time_str, duration, description = line.split(', ')
            except ValueError as e:
                print(f"Error parsing line: {line}")
                raise e

            start_time = datetime.combine(date.today(), datetime.strptime(start_time_str, '%H:%M').time())
            duration_minutes = int(duration[:-1])
            end_time = start_time + timedelta(minutes=duration_minutes)

            time_range_str = f"{start_time_str}-{end_time.strftime('%H:%M')}"
            if time_range_str in existing_event_times and preferences['include_existing_events'].lower() == 'no':
                continue  # Skip adding this event if the preference to include existing events is set to 'no'

            timezone = preferences.get('timezone', 'UTC')
            event_string = (
                f"BEGIN:VEVENT\n"
                f"SUMMARY:{description}\n"
                f"DTSTART;TZID={timezone}:"
                f"{start_time.strftime('%Y%m%dT%H%M%S')}\n"
                f"DTEND;TZID={timezone}:"
                f"{end_time.strftime('%Y%m%dT%H%M%S')}\n"
                f"END:VEVENT\n"
            )
            ics_content += event_string

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

def parse_target_day_argument():
    parser = argparse.ArgumentParser(description='Specify the target day for schedule generation.')
    parser.add_argument('--day', type=str, default='today', help='Target day for schedule generation. Accepts "today", "tomorrow", or a specific date in the format "YYYY-MM-DD".')
    args = parser.parse_args()
    return args.day

# Main function
def main():
    global target_day
    target_day = parse_target_day_argument()
    openai.api_key = os.getenv('OPENAI_API_KEY')
    print("Welcome to GPT Personal Assistant! Let's start planning out your day.")
    global preferences
    preferences = configure()
    events, tasks, existing_event_times = extract_data(preferences)
    schedule = generate_schedule(events, tasks)
    validate_format(schedule)
    create_ics(schedule, preferences, existing_event_times)
    open_ics_file("generated_schedule.ics")

if __name__ == '__main__':
    main()

