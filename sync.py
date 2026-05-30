import os
import requests
from datetime import timedelta
from datetime import datetime
import zoneinfo
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

TZ = zoneinfo.ZoneInfo("America/Los_Angeles")


def today():
    return datetime.now(TZ).date()


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


def build_grid(daily_progress, goal_value=1):
    now = today()
    start = now - timedelta(days=DAYS - 1)
    by_date = {}
    for e in daily_progress:
        status = e.get("status", "")
        if status == "completed":
            ratio = 1.0
        else:
            total_log = e.get("totalLog") or 0
            ratio = min(float(total_log) / float(goal_value), 1.0) if goal_value > 0 and total_log > 0 else 0.0
        by_date[e["date"]] = ratio
    return [by_date.get((start + timedelta(days=i)).isoformat(), 0.0) for i in range(DAYS)]


def compute_streak(daily_progress):
    now = today()
    by_date = {e["date"]: e["status"] for e in daily_progress}
    streak = 0
    for i in range(365):
        d = (now - timedelta(days=i)).isoformat()
        if by_date.get(d) == "completed":
            streak += 1
        else:
            break
    return streak



def main():
    habits = get_active_habits()
    now = today()
    start = now - timedelta(days=DAYS - 1)

    # Indices (0-based) of columns that fall on Sunday — used by template for week dividers
    sunday_cols = [i for i in range(DAYS) if (start + timedelta(days=i)).weekday() == 6]

    _abbrevs = ["M", "T", "W", "Th", "F", "S", "S"]
    day_letters = [_abbrevs[(start + timedelta(days=i)).weekday()] for i in range(DAYS)]

    grids = []
    payload_habits = []
    for habit in habits:
        daily_progress = get_daily_progress(habit["id"])
        active_goals = [g for g in habit.get("goals", []) if g.get("isActive")]
        goal_value = active_goals[0]["value"] if active_goals else 1
        grid = build_grid(daily_progress, goal_value)  # list of floats 0.0–1.0
        grids.append(grid)
        payload_habits.append({
            "name": habit["name"],
            "days": [{"fill": round(r * 100)} for r in grid],
            "streak": compute_streak(daily_progress),
            "rate": round(sum(grid) / DAYS * 100),
        })

    num_habits = len(payload_habits)
    daily_totals = []
    for i in range(DAYS):
        ratio_sum = sum(g[i] for g in grids)
        height_px = round(ratio_sum / num_habits * BAR_MAX_PX) if num_habits else 0
        daily_totals.append({"count": ratio_sum, "height_px": max(height_px, 2)})

    total_completed = sum(1 for g in grids for r in g if r >= 1.0)
    total_possible = num_habits * DAYS

    merge_variables = {
        "habits": payload_habits,
        "sunday_cols": sunday_cols,
        "day_letters": day_letters,
        "daily_totals": daily_totals,
        "total_completed": total_completed,
        "total_possible": total_possible,
        "date_start": start.strftime("%b %-d").upper(),
        "date_end": now.strftime("%b %-d").upper(),
        "year": now.year,
        "today_display": now.strftime("%B %-d"),
        "username": USERNAME,
    }

    resp = requests.post(TRMNL_WEBHOOK_URL, json={"merge_variables": merge_variables})
    if not resp.ok:
        print(f"Error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    print(f"Pushed to TRMNL: {resp.status_code}")

    os.makedirs("public", exist_ok=True)
    env = Environment(loader=FileSystemLoader("."))
    html = env.get_template("template_jinja.html").render(**merge_variables)
    with open("public/index.html", "w") as f:
        f.write(html)
    print("Rendered public/index.html")


if __name__ == "__main__":
    main()
