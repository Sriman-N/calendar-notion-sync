import os
import re
import pickle
import logging
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timezone, timedelta
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from notion_client import Client
from dotenv import load_dotenv

# Config
load_dotenv()
COURSES_DB_ID = os.getenv("COURSES_DB_ID")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
SCOPES       = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS  = "credentials.json"
TOKEN_FILE   = "token.pickle"
SYNCED_FILE  = "synced_events.txt"
LOG_FILE     = "sync.log"

# Logging setup
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log(msg):
    print(msg)
    logging.info(msg)

def notify(title, message, kind="info"):
    """Show a popup dialog. kind can be 'info', 'warning', or 'error'."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    if kind == "error":
        messagebox.showerror(title, message)
    elif kind == "warning":
        messagebox.showwarning(title, message)
    else:
        messagebox.showinfo(title, message)
    root.destroy()

def get_google_calendar_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("calendar", "v3", credentials=creds)

def get_upcoming_events(service, max_results=50):
    now = datetime.now(timezone.utc).isoformat()
    calendar_list = service.calendarList().list().execute()
    all_events = []
    for calendar in calendar_list.get("items", []):
        cal_name = calendar.get("summary", "")
        if "Canvas" not in cal_name:
            continue
        cal_id = calendar["id"]
        try:
            events_result = service.events().list(
                calendarId=cal_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            all_events.extend(events_result.get("items", []))
        except Exception as e:
            logging.error(f"Failed to fetch calendar {cal_name}: {e}")
    return all_events

def get_synced_titles():
    if not os.path.exists(SYNCED_FILE):
        return set()
    with open(SYNCED_FILE, "r") as f:
        return set(line.strip() for line in f.readlines())

def save_synced_title(title):
    with open(SYNCED_FILE, "a") as f:
        f.write(title + "\n")

def get_type(title):
    title_lower = title.lower()
    if "exam" in title_lower or "midterm" in title_lower or "final" in title_lower:
        return "Exam"
    elif "quiz" in title_lower:
        return "Quiz"
    elif "essay" in title_lower:
        return "Essay"
    else:
        return "Homework"

def build_course_map(notion):
    course_map = {}
    try:
        response = notion.search(query="", filter={"property": "object", "value": "page"})
        for result in response.get("results", []):
            parent = result.get("parent", {})
            if parent.get("database_id", "").replace("-", "") == COURSES_DB_ID.replace("-", ""):
                props = result.get("properties", {})
                code_list = props.get("Course code", {}).get("rich_text", [])
                if code_list:
                    full_code = code_list[0].get("plain_text", "")
                    partial_code = ":".join(full_code.split(":")[:3])
                    course_map[partial_code] = result["id"]
    except Exception as e:
        logging.error(f"Failed to build course map: {e}")
    return course_map

def get_course_id(course_map, event_title):
    match = re.search(r"\[(\d{2}:\d{3}:\d{3})", event_title)
    if not match:
        return None
    return course_map.get(match.group(1))

def clean_title(title):
    return re.sub(r"\s*\[.*?\]\s*$", "", title).strip()

def truncate(text, max_len=2000):
    return text[:max_len] if text and len(text) > max_len else text

def add_to_notion(notion, clean, original_title, start_date, end_date, course_id=None, description=None):
    props = {
        "Name": {"title": [{"text": {"content": truncate(clean, 100)}}]},
        "Status": {"status": {"name": "Not started"}},
        "Type": {"select": {"name": get_type(original_title)}},
    }
    if start_date:
        props["Due date"] = {
            "date": {
                "start": start_date,
                "end": end_date if end_date != start_date else None
            }
        }
    if course_id:
        props["Course"] = {"relation": [{"id": course_id}]}

    children = []
    if description:
        children = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": truncate(description)}}]
                }
            }
        ]

    notion.pages.create(
        parent={"database_id": NOTION_DB_ID},
        properties=props,
        children=children
    )
    log(f"  ✅ Added: {clean}")

def main():
    log("🔄 Syncing Google Calendar → Notion...")

    # Connecting to Google Calendar
    try:
        service = get_google_calendar_service()
    except Exception as e:
        logging.error(f"Failed to connect to Google Calendar: {e}")
        print("❌ Could not connect to Google Calendar. Check your credentials.")
        notify(
            "Calendar Notion Sync — Error",
            "Could not connect to Google Calendar.\n\nYour token may have expired.\nDelete token.pickle and re-run the script.",
            kind="error"
        )
        return

    # Connecting to Notion database
    try:
        notion = Client(auth=NOTION_TOKEN)
    except Exception as e:
        logging.error(f"Failed to connect to Notion: {e}")
        print("❌ Could not connect to Notion. Check your token.")
        notify(
            "Calendar Notion Sync — Error",
            "Could not connect to Notion.\n\nCheck your NOTION_TOKEN in the .env file.",
            kind="error"
        )
        return

    # Taking info from Google Calendar and adding to Notion database
    course_map    = build_course_map(notion)
    events        = get_upcoming_events(service)
    synced_titles = get_synced_titles()

    added = 0
    failed = 0
    for event in events:
        title = event.get("summary", "").strip()
        if not title or title in synced_titles:
            continue

        start = event.get("start", {})
        end   = event.get("end",   {})
        start_date = start.get("dateTime", start.get("date", ""))
        end_date   = end.get("dateTime",   end.get("date",   ""))

        clean       = clean_title(title)
        course_id   = get_course_id(course_map, title)
        description = event.get("description", "")

        try:
            add_to_notion(notion, clean, title, start_date, end_date, course_id, description)
            save_synced_title(title)
            added += 1
        except Exception as e:
            logging.error(f"Failed to add '{title}': {e}")
            print(f"  ❌ Failed: {clean}")
            failed += 1

    log(f"\n✅ Done! {added} new events added to Notion.")
    if failed > 0:
        log(f"⚠️ {failed} events failed — check sync.log for details.")
        notify(
            "Calendar Notion Sync — Warning",
            f"{failed} event(s) failed to sync.\n\nCheck sync.log for details.",
            kind="warning"
        )
    else:
        notify(
            "Calendar Notion Sync — Done",
            f"Sync complete!\n{added} new event(s) added to Notion.",
            kind="info"
        )

if __name__ == "__main__":
    main()