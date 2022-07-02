from cs50 import SQL
import datetime

from helpers import login_required, lookup, usd, get_time, get_weather

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///plan.db")

def schedule():
    """Display and manipulate user's schedule"""

    # Find all events that user is included in
    my_events = db.execute("SELECT * FROM events WHERE event_id IN (SELECT event_id FROM event_members WHERE user_id = ?) ORDER BY datetime(date)", 1)

    # Get time
    now_time = get_time()

    # Format today's date as a strptime
    date_now = datetime.datetime.strptime(now_time, "%Y-%m-%d %H:%M")

    # Remove event if it has passed
    for i, event in enumerate(my_events, start = 0):
        if datetime.datetime.strptime(event["date"], "%Y-%m-%d %H:%M") < date_now:
            del my_events[i]

    print(my_events)

schedule()
