import json
from icalendar import Calendar, Event
from dateutil import parser, relativedelta
import openai
import argparse
import unittest
import re
import datetime

preferences = {}

def read_input_file(input_file):
    try:
        with open(input_file, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error in read_input_file function: {e}")
        raise

def write_output_file(output_file, output_data):
    try:
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=4)
        print(f"Output file {output_file} written successfully.")
    except Exception as e:
        print(f"Error in write_output_file function: {e}")
        raise

def parse_ics_file(ics_file):
    # global preferences
    try:
        with open(ics_file, "r") as f:
            content = f.read()
        cal = Calendar.from_ical(content)
        events = []
        today = parser.parse(preferences["date"])
        for component in cal.walk():
            if component.name == "VEVENT":
                start = component.get("dtstart").dt
                end = component.get("dtend").dt
                if start.date() == today.date():
                    duration = int((end - start).total_seconds() / 60)
                    summary = str(component.get("summary"))
                    location = str(component.get("location")) or None
                    event = {
                        "start": start,
                        "end": end,
                        "duration": duration,
                        "description": summary,
                        "location": location,
                        "type": "event"
                    }
                    events.append(event)
        return events
    except Exception as e:
        print(f"Error in parse_ics_file function: {e}")
        raise

def parse_text_file(text_file):
    # global preferences
    try:
        with open(text_file, "r") as f:
            lines = f.readlines()
        tasks = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                match = re.match(r"(.+?)\s*(\((.+?)\))?\s*(\[(.+?)\])?\s*(\[(.+?)\])?$", line)
                if match:
                    groups = match.groups()
                    description = groups[0]
                    try:
                        due_date = parser.parse(groups[2])
                    except:
                        due_date = None
                    try:
                        duration = int(groups[4])
                    except:
                        duration = None
                    try:
                        priority = int(groups[6])
                    except:
                        priority = None
                    task = {
                        "description": description,
                        "due_date": due_date,
                        "duration": duration,
                        "priority": priority,
                        "type": "task"
                    }
                    tasks.append(task)
        return tasks
    except Exception as e:
        print(f"Error in parse_text_file function: {e}")
        raise

def generate_schedule(events, tasks):
    # global preferences
    try:
        schedule = []
        day_start = parser.parse(preferences["day_start"])
        day_end = parser.parse(preferences["day_end"])
        events.sort(key=lambda x: x["start"])
        tasks.sort(key=lambda x: (x["priority"], x["due_date"]))
        current_time = day_start
        for event in events:
            if current_time < event["start"]:
                available_time = int((event["start"] - current_time).total_seconds() / 60)
                allocated_tasks = allocate_tasks(tasks, available_time, current_time)
                schedule.extend(allocated_tasks)
                current_time = allocated_tasks[-1]["end"]
            schedule.append(event)
            current_time = event["end"]
        if current_time < day_end:
            available_time = int((day_end - current_time).total_seconds() / 60)
            allocated_tasks = allocate_tasks(tasks, available_time, current_time)
            schedule.extend(allocated_tasks)
            current_time = allocated_tasks[-1]["end"]
        return schedule
    except Exception as e:
        print(f"Error in generate_schedule function: {e}")
        raise

def allocate_tasks(tasks, available_time, current_time):
    # global preferences
    try:
        allocated_tasks = []
        remaining_time = available_time
        for task in tasks:
            if remaining_time == 0:
                break 
            if task["duration"] is None:
                question = f"How long do you think it will take you to {task['description']}?"
                answer = ask_user(question)
                try:
                    task["duration"] = int(answer)
                except:
                    task["duration"] = None 
            if task["duration"] is None:
                continue 
            if task["duration"] <= remaining_time:
                task["start"] = current_time 
                task["end"] = current_time + relativedelta(minutes=task["duration"])
                allocated_tasks.append(task)
                remaining_time -= task["duration"]
                current_time += relativedelta(minutes=task["duration"])
                tasks.remove(task)
            else:
                part1 = task.copy()
                part1["start"] = current_time 
                part1["end"] = current_time + relativedelta(minutes=remaining_time)
                part1["description"] += " (part 1)"
                part1["duration"] = remaining_time 
                allocated_tasks.append(part1)
                part2 = task.copy()
                part2["description"] += " (part 2)"
                part2["duration"] -= remaining_time 
                tasks[tasks.index(task)] = part2 
                remaining_time = 0 
                current_time += relativedelta(minutes=remaining_time)
        return allocated_tasks
    except Exception as e:
        print(f"Error in allocate_tasks function: {e}")
        raise

def ask_user(question):
    # global preferences
    try:
        prompt = preferences["prompt"]
        prompt += "\n\n" + question + "\n"
        params = {
            "engine": "davinci",
            "prompt": prompt,
            "temperature": 0.5,
            "max_tokens": 50,
            "stop": "\n"
        }
        response = openai.Completion.create(**params)
        answer = response["choices"][0]["text"].strip()
        return answer
    except Exception as e:
        print(f"Error in ask_user function: {e}")
        raise

def create_ics_calendar(schedule):
    # global preferences
    try:
        cal = Calendar()
        cal.add("prodid", "-//Bing//Schedule Generator//EN")
        cal.add("version", "2.0")
        for item in schedule:
            event = Event()
            event.add("dtstart", item["start"])
            event.add("dtend", item["end"])
            event.add("summary", item["description"])
            if item["type"] == "event" and item["location"]:
                event.add("location", item["location"])
            cal.add_component(event)
        return cal
    except Exception as e:
        print(f"Error in create_ics_calendar function: {e}")
        raise

def validate_schedule_calendar(schedule, calendar):
    # global preferences
    try:
        events = [component for component in calendar.walk() if component.name == "VEVENT"]
        assert len(events) == len(schedule), "The number of events in the calendar does not match the number of items in the schedule."
        for event, item in zip(events, schedule):
            assert event.get("dtstart").dt == item["start"], f"The start time of the event {event.get('summary')} does not match the start time of the item {item['description']}."
            assert event.get("dtend").dt == item["end"], f"The end time of the event {event.get('summary')} does not match the end time of the item {item['description']}."
            assert event.get("summary") == item["description"], f"The summary of the event {event.get('summary')} does not match the description of the item {item['description']}."
        for i in range(len(schedule) - 1):
            current_item = schedule[i]
            next_item = schedule[i + 1]
            assert current_item["end"] <= next_item["start"], f"There is a conflict or overlap between {current_item['description']} and {next_item['description']}."
            assert 0 < current_item["duration"] <= 1440, f"The duration of {current_item['description']} is unreasonable: {current_item['duration']} minutes."
            gap = int((next_item["start"] - current_item["end"]).total_seconds() / 60)
            assert 0 <= gap <= 240, f"The gap between {current_item['description']} and {next_item['description']} is unreasonable: {gap} minutes."
        print(f"Schedule and calendar validated successfully.")
    except Exception as e:
        print(f"Error in validate_schedule_calendar function: {e}") 
        raise

def main(): 
    parser = argparse.ArgumentParser(description="A program to help people make a daily schedule based on their calendar events and tasks.") 
    parser.add_argument("-i", "--input", type=str, default="input.json", help="The name of the input file with preferences and settings.")
    parser.add_argument("-o", "--output", type=str, default="output.json", help="The name of the output file with schedule and calendar.")
    args = parser.parse_args() 
    try: 
        preferences = read_input_file(args.input) 
        print(f"Input file {args.input} read successfully.") 
        events = parse_ics_file(preferences["ics_file"]) 
        tasks = parse_text_file(preferences["text_file"]) 
        print(f"ICS and text files parsed successfully.") 
        schedule = generate_schedule(events, tasks) 
        print(f"Schedule: {schedule}") 
        calendar = create_ics_calendar(schedule) 
        print(f"Calendar created successfully.") 
        validate_schedule_calendar(schedule, calendar) 
        write_output_file(args.output, {"schedule": schedule, "calendar": calendar.to_ical().decode("utf-8")}) 
    except Exception as e: 
        print(f"Error in main function: {e}") 
        exit(1)

if __name__ == "__main__":
    main()
