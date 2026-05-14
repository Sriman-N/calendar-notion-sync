# Calendar Notion Sync

A Python script that automatically syncs your Canvas assignments from Google Calendar to a Notion database. Runs automatically every time you log into Windows.

**Note:** This project is designed for Windows. The automatic scheduling uses Windows Task Scheduler.

---

## What it does

- Pulls upcoming assignments from your Canvas Google Calendar
- Creates entries in your Notion To-do's database with:
  - Clean assignment name (course code stripped from title)
  - Due date
  - Course (linked to your Courses database)
  - Type (Homework, Exam, Quiz, Essay — auto-detected from title)
  - Status (set to "Not started" by default)
  - Description (assignment details from Canvas)
- Skips duplicates so assignments are never added twice
- Logs all activity to `sync.log`

---

## Setup

### 1. Prerequisites

- Python 3.x installed
- A Google account with Canvas synced to Google Calendar
- A Notion account with a To-do's database and a Courses database

### 2. Clone the repo

```bash
git clone https://github.com/Sriman-N/calendar-notion-sync
cd calendar-notion-sync
```

### 3. Install dependencies

```bash
pip install google-auth-oauthlib google-api-python-client notion-client python-dotenv
```

### 4. Google Calendar API

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a project (or use an existing one)
3. Enable the **Google Calendar API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth Client ID**
5. Select **Desktop app**, click Create
6. Download the JSON file and save it as `credentials.json` in the project folder
7. Go to **OAuth consent screen → Audience** and add your Google email as a test user

### 5. Notion API

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New connection**, name it `Calendar-notion-sync`, click Create
3. Copy the **Access token**
4. Open your **To-do's database** in Notion, click `...` → Connections → Add `Calendar-notion-sync`
5. Do the same for your **Courses database**
6. Copy both database IDs from their URLs (the string before `?v=`)

### 6. Create .env file

Create a `.env` file in the project folder:

```
NOTION_TOKEN=your_notion_token_here
NOTION_DB_ID=your_todos_database_id_here
COURSES_DB_ID=your_courses_database_id_here
```

### 7. Courses database setup

Make sure each course in your Notion Courses database has a **Course code** field (text) with the course code exactly as it appears in Canvas (e.g. `01:640:251:03`). The script matches on the first 3 parts (e.g. `01:640:251`) and ignores the section number.

---

## Running manually

```bash
python sync.py
```

The first time you run it, a browser window will open asking you to log in with Google and approve access. After that it runs silently.

---

## Automatic setup (Windows Task Scheduler)

1. Make sure `run_sync.bat` is in the project folder
2. Open **Task Scheduler** and click **Create Basic Task**
3. Name it `Calendar Notion Sync`
4. Set trigger to **When I log on**
5. Set action to **Start a program**
6. Set program to: `C:\Users\{YOUR_USERNAME}\{PATH_TO_PROJECT}\calendar-notion-sync\run_sync.bat`
7. Set **Start in** to: `C:\Users\{YOUR_USERNAME}\{PATH_TO_PROJECT}\calendar-notion-sync`
8. Click Finish

The script will now run automatically every time you log into Windows.

---

## Files

| File | Description |
|------|-------------|
| `sync.py` | Main script |
| `run_sync.bat` | Batch file for Task Scheduler |
| `credentials.json` | Google OAuth credentials (not in GitHub) |
| `token.pickle` | Google auth token, auto-generated (not in GitHub) |
| `.env` | API keys and database IDs (not in GitHub) |
| `synced_events.txt` | Tracks added events to prevent duplicates (not in GitHub) |
| `sync.log` | Log of all sync activity (not in GitHub) |

---

## Notes

- The script only pulls from your Canvas calendar, ignoring personal and birthday calendars
- Events are matched to courses by the course code in the title (e.g. `[01:640:251:01]`)
- If a Canvas assignment description is longer than 2000 characters it will be truncated
- To test with past events, temporarily change `now = datetime.now(timezone.utc).isoformat()` to use `timedelta(days=60)` to look back 60 days
