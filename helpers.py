import os
import requests
import urllib.parse
import datetime

from flask import redirect, render_template, request, session, flash
from functools import wraps
from cs50 import SQL

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def four_day():
    """Look up 4 day weather forecast"""

    # Contact API
    try:
        response = requests.get("https://api.data.gov.sg/v1/environment/4-day-weather-forecast")
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return quote["items"][0]["forecasts"]
    except (KeyError, TypeError, ValueError):
        return None

def today():
    """Look up 24 hour weather forecast"""

    # Contact API
    try:
        response = requests.get("https://api.data.gov.sg/v1/environment/24-hour-weather-forecast")
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return quote["items"][0]["general"]
    except (KeyError, TypeError, ValueError):
        return None

def get_time():
    """Format time appropriate formate"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    now_object = datetime.datetime.strptime(now, "%Y-%m-%d %H:%M") 
    now = now_object.strftime("%Y-%m-%d %H:%M")
    return now

def get_weather(date):
    """Get 5 day weather forecast from date"""

    # Date now
    now = datetime.datetime.strptime(get_time()[:-6], "%Y-%m-%d")

    # Date is more 5 days
    dateobj = datetime.datetime.strptime(date[:-6], "%Y-%m-%d")
    plus_5 = now + datetime.timedelta(days=4)
    if dateobj > plus_5 or dateobj < now:
        return("Weather Unavailable")

    else:

        # Date is today's date
        if dateobj == now:

            # Look up today's weather forecast
            forecast = today()

            # Check if API is successfull
            if forecast == None:
                return("Weather Unavailable")

            return forecast

        # Date is within next 4 days
        else:

            # Fetch 4 day weather outlook
            forecasts = four_day()

            if forecasts == None:
                return("Weather Unavailable")

            # Find forecast for the given date
            for forecast in forecasts:
                if forecast["date"] == date[:-6]:
                    forecast["type"] = "four_day"
                    return forecast

            return("Weather Unavailable")

def verify(event_id, user_id):
    """Verify that user has access to event"""
    verify_event = SQL("sqlite:///plan.db").execute("SELECT * FROM event_members WHERE event_id = ? AND user_id = ?", event_id, user_id)
    if len(verify_event) == 0:
        return False
    else:
        return True