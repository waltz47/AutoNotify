from flask import Flask, render_template, request, redirect, url_for, jsonify
from query import set_notify
from models import db, Email, Query
from threading import Thread
import time
from mailer import send_pending_emails
from flask_wtf import CSRFProtect
from datetime import datetime, timedelta
from fn import get_random_events, get_trigger
import argparse
from secrets import token_hex

app = Flask(__name__)
app.secret_key = token_hex(16)  # Replace with your secret key
csrf = CSRFProtect(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emails.db'
db.init_app(app)
with app.app_context():
    db.create_all()

debug_mode = False  # Default debug mode
frequency = 1800    # Default frequency

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query = request.form['query']
        email = request.form['email']
        trigger_time = request.form['trigger_time']
        deadline = request.form['deadline']
        Thread(target=handle_user_query, args=(query, email, trigger_time, deadline, db.session)).start()
        return redirect(url_for('confirmation', email=email))
    return render_template('index.html')

@app.route('/confirmation', methods=['GET'])
def confirmation():
    email = request.args.get('email')
    return render_template('confirmation.html', email=email)

@app.route('/events', methods=['GET'])
def events():
    return jsonify(get_random_events())

def handle_user_query(query, email, trigger_time, deadline, session):
    with app.app_context():
        trigger = get_trigger(query)
        deadline_dt = datetime.strptime(deadline, '%Y-%m-%d')
        deadline_dt = deadline_dt.replace(hour=23, minute=59, second=59)
        new_query = Query(query=query, email=email, trigger_time=trigger_time, deadline=deadline_dt, last_run_time=None, is_processing=False, trigger=trigger)
        session.add(new_query)
        session.commit()

query_processor_thread = None

def process_queries():
    while True:
        with app.app_context():
            print("Processing queries")
            # Fetch queries that are not being processed and have a trigger
            queries = db.session.query(Query).filter(Query.is_processing == False, Query.trigger.isnot(None)).all()
            for query_entry in queries:
                # Check if deadline has passed
                if datetime.now() > query_entry.deadline:
                    db.session.delete(query_entry)
                    db.session.commit()
                    continue
                # Determine if it's time to trigger the query
                should_run = False
                if query_entry.last_run_time is None:
                    should_run = True
                else:
                    interval = parse_interval(query_entry.trigger_time)
                    if datetime.now() - query_entry.last_run_time >= interval:
                        should_run = True
                if should_run:
                    try:
                        # Set is_processing to True and commit before processing
                        query_entry.is_processing = True
                        query_entry.last_run_time = datetime.now()
                        db.session.commit()
                        # Process the query
                        set_notify(query_entry.trigger, query_entry.email, session=db.session)
                        # After processing, reset is_processing to False
                        query_entry.is_processing = False
                        db.session.commit()
                        # No need to delete the Query entry here
                    except Exception as e:
                        # In case of an error, reset is_processing and log the error
                        query_entry.is_processing = False
                        db.session.commit()
                        print(f"Error processing query {query_entry.id}: {e}")
            db.session.commit()
            time.sleep(frequency)  # Adjust sleep time based on debug mode

def parse_interval(trigger_time):
    # Removed the "60s" option
    if trigger_time == '1h':
        return timedelta(hours=1)
    elif trigger_time == '1d':
        return timedelta(days=1)
    elif trigger_time == '1w':
        return timedelta(weeks=1)
    elif trigger_time == '1m':
        return timedelta(days=30)
    else:
        return timedelta(seconds=3000)  # Default interval

def check_email_sent(email):
    return db.session.query(Email).filter_by(recipient_email=email).first() is not None

def start_query_processor():
    global query_processor_thread
    if query_processor_thread is None:
        query_processor_thread = Thread(target=process_queries)
        query_processor_thread.daemon = True
        query_processor_thread.start()

def start_email_sender():
    def run():
        while True:
            with app.app_context():
                send_pending_emails()
            time.sleep(frequency)
    thread = Thread(target=run)
    thread.daemon = True
    thread.start()

start_query_processor()
start_email_sender()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AutoNotifier Application')
    parser.add_argument('--debug', action='store_true', help='Run the application in debug mode')
    args = parser.parse_args()
    debug_mode = args.debug
    frequency = 10 if debug_mode else 1800
    app.run(debug=debug_mode)  # Set debug based on argument
