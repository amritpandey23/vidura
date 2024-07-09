from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import or_, desc
import datetime, json, os

from tracker.forms import SettingsForm
from tracker.utils2 import get_or_initialize_config, persist_config_json, initialize_app


app = Flask(__name__)

config = initialize_app(app)

app.config["SITE_NAME"] = config["SITE_NAME"]
app.config["SQLALCHEMY_DATABASE_URI"] = config["SQLALCHEMY_DATABASE_URI"]
app.config["SECRET_KEY"] = config["SECRET_KEY"]

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from tracker.tasks.models import Task
from tracker.tasks.forms import TaskForm, TaskFilterForm
from tracker.daily_logs.forms import DailyLogForm


@app.before_request
def initialize_db():
    config = get_or_initialize_config(app)
    if config["db_initialized"] == None or config["db_initialized"] == "false":
        db.drop_all()
        db.create_all()
        config["db_initialized"] = "true"
        persist_config_json(app, "config", json.dumps(config, indent=4))


@app.route("/", methods=["GET", "POST"])
def home():

    incomplete_high_priority_tasks = Task.query.filter(
        Task.progress_status != "Completed",
        Task.priority == "High",
        Task.progress_status != "Dropped",
    ).all()

    incomplete_medium_priority_tasks = Task.query.filter(
        Task.progress_status != "Completed",
        Task.priority == "Medium",
        Task.progress_status != "Dropped",
    ).all()

    incomplete_low_priority_tasks = Task.query.filter(
        Task.progress_status != "Completed",
        Task.priority == "Low",
        Task.progress_status != "Dropped",
    ).all()

    # Combine incomplete tasks of different priorities
    incomplete_tasks = (
        incomplete_high_priority_tasks
        + incomplete_medium_priority_tasks
        + incomplete_low_priority_tasks
    )

    # tasks = incomplete_tasks
    tasks = sorted(
        incomplete_tasks, key=lambda task: task.date_of_allotment, reverse=True
    )

    dates = json.loads(fetch_config_json(app, "important_dates"))
    notes = json.loads(fetch_config_json(app, "notes"))
    return render("home.html", tasks=tasks, datetime=datetime, dates=dates, notes=notes)


from tracker.tasks.routes import tasks
from tracker.daily_logs.routes import daily_logs

app.register_blueprint(tasks)
app.register_blueprint(daily_logs)


@app.template_filter("date_to_text")
def date_to_text(date_str):
    date = str(date_str)
    date_obj = datetime.datetime.strptime(date, "%Y-%m-%d")
    return date_obj.strftime("%B %d, %Y")


# Register the custom filter
app.jinja_env.filters["date_to_text"] = date_to_text

from tracker.utils import render
from tracker.utils2 import fetch_config_json, persist_config_json


@app.route("/settings", methods=["GET", "POST"])
def settings():
    settings = {}

    settings["config"] = fetch_config_json(app, "config")
    settings["important_dates"] = fetch_config_json(app, "important_dates")
    settings["notes"] = fetch_config_json(app, "notes")

    settings_form = SettingsForm(**settings)

    if settings_form.validate_on_submit():
        config = settings_form.config.data
        important_dates = settings_form.important_dates.data
        notes = settings_form.notes.data
        try:
            persist_config_json(app, "config", config)
            persist_config_json(app, "important_dates", important_dates)
            persist_config_json(app, "notes", notes)
        except json.JSONDecodeError as e:
            flash("Errors in JSON", "danger")
        finally:
            flash("Settings saved successfully!", "success")
    return render("settings.html", settings_form=settings_form)
