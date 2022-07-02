import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import login_required, get_time, get_weather, verify


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///plan.db")


@app.route("/")
@login_required
def index():
    """Redirect to home page"""
    return redirect("/home")

@app.route("/home")
@login_required
def home():
    """Show user info"""

    # Get today's date
    date_now = datetime.datetime.strptime(get_time(), "%Y-%m-%d %H:%M")

    # Get user event info
    events = db.execute("SELECT * FROM events WHERE event_id IN (SELECT event_id FROM event_members WHERE user_id = ?) ORDER BY datetime(date)", session["user_id"])
    my_events = list(filter(lambda i: datetime.datetime.strptime(i['date'], "%Y-%m-%d %H:%M") > date_now, events))

    # Get user's friend list
    friends = db.execute("SELECT * FROM requests WHERE receive_id = ?", session["user_id"])

    return render_template("home.html", events=len(my_events), friends=len(friends))

@app.route("/profile")
@login_required
def profile():
    """Render user's profile"""

    # Get user's info
    user = db.execute("SELECT username, id FROM users WHERE id = ?", session["user_id"])

    return render_template("profile.html", user=user[0])


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("must provide username")
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("must provide password")
            return render_template("login.html")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("invalid username or password")
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # If username is empty or already exists
        username = request.form.get("username")
        user_check = db.execute("SELECT * FROM users WHERE username = ?", username)
        if not username or len(user_check) != 0:
            flash("Invalid Username")
            return render_template("register.html")

        # Check if password fields are empty
        password = request.form.get("password")

        if not password or not request.form.get("password2"):
            flash("Password fields are empty")
            return render_template("register.html")

        # Check if passwords match
        if password != request.form.get("password2"):
            flash("Passwords do not match")
            return render_template("register.html")

        # If register meets all requirements
        # Store users username and hash of password
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                   username, generate_password_hash(password, method='pbkdf2:sha256', salt_length=8))

        # Log our user in and redirect to index
        id = db.execute("SELECT id FROM users WHERE username = :username", username=username)
        session["user_id"] = id[0]["id"]
        return redirect("/")

    # VIA GET REQUEST
    else:
        return render_template("register.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/friends", methods=["GET", "POST"])
@login_required
def friends():
    """View users friends and allow user to add and remove friends"""

    # Find out how many friends user has
    friends = db.execute("SELECT username, id FROM users WHERE id IN (SELECT friend_2 FROM friends WHERE friend_1 = ?)", session["user_id"])

    # Find out how many friend requests user has
    friend_requests = db.execute("SELECT username, id FROM users WHERE id IN (SELECT sender_id FROM requests WHERE receive_id = ?)", session["user_id"])

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        #Initialize some basic variables
        select_id = request.form.get("user_id")
        search = db.execute("SELECT username, id FROM users WHERE id = ?", select_id) # Find users with given id
        found_friend = "" # Flag if user entered a valid user id

        # Make sure the users cannot search for themselves
        if select_id == str(session["user_id" ]):
            result = "You cannot search for yourself"

        # If field is empty
        elif not select_id:
            result = "Empty field"

        # Check if searched user exists
        elif len(search) == 0:
            result = "No user with id of '" + select_id + "' found"

        # Searched for a valid user
        else:
            result = "USERNAME: '" + search[0]["username"] +"' ID: '" + str(search[0]["id"]) + "'"
            found_friend = "true"
            session["temp_req"] = search[0]["id"] # Set a temp global variable to store friend data

        return render_template("friends.html", result=result, found_friend=found_friend, friend_requests=friend_requests, friends=friends)

    # VIA GET REQUEST
    else:
        return render_template("friends.html", friend_requests=friend_requests, friends=friends)


@app.route("/add_friend", methods=["GET", "POST"])
@login_required
def add_friend():
    """Allow user to add friend from friends.html"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Send a friend request

        # Check if user has already send a friend request to the same person
        friend_request = db.execute("SELECT * FROM requests WHERE sender_id = ? AND receive_id = ?", session["user_id"], session["temp_req"])

        # Check if user already has a pending request
        pending_request = db.execute("SELECT * FROM requests WHERE sender_id = ? AND receive_id = ?", session["temp_req"], session["user_id"])

        # Check if both users are already friends
        check_friend = db.execute("SELECT * FROM friends WHERE friend_1 = ? AND friend_2 = ? OR friend_1 = ? AND friend_2 = ?", session["user_id"], session["temp_req"], session["temp_req"], session["user_id"])

        if len(friend_request) != 0:
            flash("You have already sent a friend request to this user")
            return redirect("/friends")

        elif len(pending_request) !=0:
            flash("This user has already sent you a friend request!")
            return redirect("/friends")

        elif len(check_friend) == 2:
            flash("You are already friends with this user")
            return redirect("/friends")

        else:
            db.execute("INSERT INTO requests (sender_id, receive_id) VALUES (?, ?)", session["user_id"], session["temp_req"])
            # Return to friends page
            flash("Friend Request Sent!")
            return redirect("/friends")

    # User reached route via GET
    else:
        return redirect("/friends")


@app.route("/confirm", methods=["GET", "POST"])
@login_required
def confirm():
    """User confirms friend request"""

    # If user reached route via POST
    if request.method == "POST":

        # Add friend
        friend_id = request.form["friend_confirm"]
        db.execute("INSERT INTO friends (friend_1, friend_2) VALUES (?, ?), (?, ?);", session["user_id"], friend_id, friend_id, session["user_id"])

        # Remove friend request
        db.execute("DELETE FROM requests WHERE sender_id = ? AND receive_id = ?", friend_id, session["user_id"])

        # Return to friend page
        flash("Friend added")
        return redirect("/friends")

    # User reached route via GET
    else:
        return redirect("/friends")


@app.route("/delete", methods=["GET", "POST"])
@login_required
def delete():
    """Allow user to delete a friend request"""

    # User reached route via POST
    if request.method == "POST":

        # Delete friend request
        db.execute("DELETE FROM requests WHERE sender_id = ? AND receive_id = ?", int(request.form["friend_delete"]), session["user_id"])

        # Return to friends page
        flash("Deleted!")
        return redirect("/friends")

    # User reached route via GET
    else:
        return redirect("/friends")

@app.route("/remove", methods=["GET", "POST"])
@login_required
def remove():
    """Allow user to remove a friend"""

    # User reached route via post
    if request.method == "POST":

        # Friend to be deleted
        to_delete = int(request.form["friend_remove"])

        #DELETE friend from friend list
        db.execute("DELETE FROM friends WHERE friend_1 = ? AND friend_2 = ? OR friend_1 = ? AND friend_2 = ?", session["user_id"], to_delete, to_delete, session["user_id"])

        # Redirect back to friends page
        flash("Friend removed!")
        return redirect("/friends")

    # User reached route via GET
    else:
        return redirect("/friends")


@app.route("/schedule", methods=["GET", "POST"])
@login_required
def schedule():
    """Display and manipulate user's schedule"""

    # Find all events that user is included in
    my_eventsorg = db.execute("SELECT * FROM events WHERE event_id IN (SELECT event_id FROM event_members WHERE user_id = ?) ORDER BY datetime(date)", session["user_id"])

    # Get time
    now_time = get_time()

    # Format today's date as a strptime
    date_now = datetime.datetime.strptime(now_time, "%Y-%m-%d %H:%M")

    # Convert into a form that html can read
    time = now_time.replace(" ", "T")

    # Remove event if it has passed
    my_events = list(filter(lambda i: datetime.datetime.strptime(i['date'], "%Y-%m-%d %H:%M") >= date_now, my_eventsorg))
    # found from: https://www.geeksforgeeks.org/python-removing-dictionary-from-list-of-dictionaries/

    # User reached route via post
    if request.method == "POST":

        # Initialize some basic variables
        name = request.form.get("event_name")
        date = request.form.get("event_date").replace("T"," ")
        about = request.form.get("about_event")

        # Format form date as a strp time
        try:
            selected_date = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M")
        except ValueError:
            flash("Invalid date")
            return redirect("/schedule")

        # Check name is filled in
        if not name:
            flash("Invalid name")
            return redirect("/schedule")

        # Check date is valid
        elif selected_date < date_now:
            flash("Invalid date")
            return redirect("/schedule")

        # Check info is filled in
        elif not about:
            flash("Invalid info")
            return redirect("/schedule")

        # Add event to database
        event_id = db.execute("INSERT INTO events (name, date, about) VALUES (?, ?, ?)", name, date, about)

        # Add user as a member to the event
        db.execute("INSERT INTO event_members (event_id, user_id) VALUES (?, ?)", event_id, session["user_id"])

        flash("event added")
        return redirect("/schedule")

    # User reached route via get
    else:
        return render_template("schedule.html", time=time, my_events=my_events)


@app.route("/view", methods=["GET", "POST"])
@login_required
def view():
    """Allow user to view an event"""

    # User reached route via post
    if request.method == "POST":

        # Add member
        if "add_member" in request.form:

            # Member to be added
            member = request.form["add_member"]

            # Redirect if member is already in event
            check_added = db.execute("SELECT * FROM event_members WHERE event_id = ? AND user_id = ?", int(session["event"]), member)

            if len(check_added) != 0:
                flash("Member already added")
                return redirect("/view?view=" + session["event"])

            # Add member into event members list
            db.execute("INSERT INTO event_members (event_id, user_id) VALUES (?, ?)", int(session["event"]), member)

            # Redirect back to view page
            flash("Added!")
            return redirect("/view?view=" + session["event"])

        # Remove Member
        elif "remove_member" in request.form:

            # Member to be removed
            member = int(request.form["remove_member"])

            # Remove member
            db.execute("DELETE FROM event_members WHERE event_id = ? AND user_id = ?", int(session["event"]), member)

            # If there are no more members left delete the event
            members = db.execute("SELECT * FROM event_members WHERE event_id = ?", int(session["event"]))

            if len(members) == 0:
                db.execute("DELETE FROM events WHERE event_id = ?", int(session["event"]))

            # Redirect back to view page
            flash("Removed!")
            if member != session["user_id"]:
                return redirect("/view?view=" + session["event"])
            else:
                return redirect("/schedule")


        # User tries something else
        else:
            flash("Invalid")
            return redirect("/view?view=" + session["event"])

    # User reached route via get
    else:

        # Get event info from get parameter
        try:
            event_id = int(request.args.get("view"))
        except ValueError:
            flash("Invalid event")
            return redirect("/schedule")

        my_event = db.execute("SELECT * FROM events WHERE event_id = ?", event_id)

        # Verify user
        if not verify(event_id, session["user_id"]):
            flash("You are not allowed to view this event")
            return redirect("/schedule")

        else:
            # Store temp event id for later use
            session["event"] = str(event_id)

            # Get weather forecast
            weather = get_weather(my_event[0]["date"])

            # Get event members
            members = db.execute("SELECT id, username FROM users WHERE id IN (SELECT user_id FROM event_members WHERE event_id = ?)", event_id)

            # Get user's friends
            friends = db.execute("SELECT username, id FROM users WHERE id IN (SELECT friend_2 FROM friends WHERE friend_1 = ?)", session["user_id"])

            # load view
            return render_template("view.html", my_event=my_event[0], weather=weather, members=members, friends=friends)


@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    """Allow user to edit an event"""

    # User reached route via post
    if request.method == "POST":

        # Initialize some basic variables
        event_id = request.form.get("submit_event")
        name = request.form.get("event_name")
        date = request.form.get("event_date").replace("T"," ")
        about = request.form.get("about_event")

        # Verify that user has access to the event
        if not verify(event_id, session["user_id"]):
            flash("You are not authorized to edit this event")
            return redirect("/schedule")

        # Update event info
        db.execute("UPDATE events SET name = ?, date = ?, about = ? WHERE event_id = ?", name, date, about, int(event_id))

        return redirect("/view?view=" + event_id)

    # User reached route via get
    else:
        # Get event_id
        try:
            event_id = int(request.args.get("edit"))
        except ValueError:
            flash("invalid event")
            return redirect("/schedule")

        # Verify that user has access to the event
        if not verify(event_id, session["user_id"]):
            flash("You are not authorized to view this event")
            return redirect("/schedule")

        # Get event info
        my_event = db.execute("SELECT * FROM events WHERE event_id = ?", event_id)
        my_event[0]["date"] = my_event[0]["date"].replace(" ", "T")

        return render_template("edit.html", my_event=my_event[0])

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return render_template("failure.html")


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)