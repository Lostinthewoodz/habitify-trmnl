import os
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

HABITIFY_API_KEY = os.environ["HABITIFY_API_KEY"]
TRMNL_PLUGIN_UUID = os.environ["TRMNL_PLUGIN_UUID"]
TRMNL_WEBHOOK_URL = f"https://trmnl.com/api/custom_plugins/{TRMNL_PLUGIN_UUID}"
HABITIFY_BASE = "https://api.habitify.me/v2"
HEADERS = {"X-API-Key": HABITIFY_API_KEY}
DAYS = 14
USERNAME = "Woody"
BAR_MAX_PX = 36


def get_active_habits():
    resp = requests.get(f"{HABITIFY_BASE}/habits", headers=HEADERS, params={"archived": "false"})
    resp.raise_for_status()
    return resp.json()["data"]


def get_daily_progress(habit_id):
    resp = requests.get(f"{HABITIFY_BASE}/habits/{habit_id}/statistics", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()["data"]["dailyProgress"]


def build_grid(daily_progress):
    today = date.today()
    start = today - timedelta(days=DAYS - 1)
    by_date = {e["date"]: e["status"] for e in daily_progress}
    return [1 if by_date.get((start + timedelta(days=i)).isoformat()) == "completed" else 0 for i in range(DAYS)]


def compute_streak(daily_progress):
    today = date.today()
    by_date = {e["date"]: e["status"] for e in daily_progress}
    streak = 0
    for i in range(365):
        d = (today - timedelta(days=i)).isoformat()
        if by_date.get(d) == "completed":
            streak += 1
        else:
            break
    return streak


def build_col_labels():
    today = date.today()
    start = today - timedelta(days=DAYS - 1)
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return [
        {"day": day_names[(start + timedelta(days=i)).weekday()], "num": (start + timedelta(days=i)).day}
        for i in range(DAYS)
    ]


def main():
    habits = get_active_habits()
    today = date.today()
    start = today - timedelta(days=DAYS - 1)

    payload_habits = []
    for habit in habits:
        daily_progress = get_daily_progress(habit["id"])
        grid = build_grid(daily_progress)
        payload_habits.append({
            "name": habit["name"],
            "days": grid,
            "streak": compute_streak(daily_progress),
            "rate": round(sum(grid) / DAYS * 100),
        })

    num_habits = len(payload_habits)
    daily_totals = []
    for i in range(DAYS):
        count = sum(h["days"][i] for h in payload_habits)
        height_px = round(count / num_habits * BAR_MAX_PX) if num_habits else 0
        daily_totals.append({"count": count, "height_px": max(height_px, 2)})

    total_completed = sum(sum(h["days"]) for h in payload_habits)
    total_possible = num_habits * DAYS

    merge_variables = {
        "habits": payload_habits,
        "col_labels": build_col_labels(),
        "daily_totals": daily_totals,
        "total_completed": total_completed,
        "total_possible": total_possible,
        "date_start": start.strftime("%b %-d").upper(),
        "date_end": today.strftime("%b %-d").upper(),
        "year": today.year,
        "today_display": today.strftime("%B %-d"),
        "username": USERNAME,
    }

    resp = requests.post(TRMNL_WEBHOOK_URL, json={"merge_variables": merge_variables})
    resp.raise_for_status()
    print(f"Pushed to TRMNL: {resp.status_code}")


if __name__ == "__main__":
    main()
