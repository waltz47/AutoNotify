from flask import Flask, render_template, request, redirect, url_for
from query import set_notify
from models import db, Email, Query
from threading import Thread
import time
from mailer import send_pending_emails
from flask_wtf import CSRFProtect
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with your secret key
csrf = CSRFProtect(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emails.db'
db.init_app(app)
with app.app_context():
    db.drop_all()
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query = request.form['query']
        email = request.form['email']
        trigger_time = request.form['trigger_time']
        deadline = request.form['deadline']
        store_query_in_db(query, email, trigger_time, deadline)
        return redirect(url_for('confirmation', email=email))
    return render_template('index.html')

@app.route('/confirmation', methods=['GET'])
def confirmation():
    email = request.args.get('email')
    return render_template('confirmation.html', email=email)

def store_query_in_db(query, email, trigger_time, deadline):
    deadline_dt = datetime.strptime(deadline, '%Y-%m-%d')
    # Assume End Of Day if time is not provided
    deadline_dt = deadline_dt.replace(hour=23, minute=59, second=59)
    query_entry = Query(query=query, email=email, trigger_time=trigger_time, deadline=deadline_dt)
    db.session.add(query_entry)
    db.session.commit()

query_processor_thread = None

def process_queries():
    while True:
        with app.app_context():
            print("process_queries function called")
            # Fetch queries that are not being processed
            queries = db.session.query(Query).filter(Query.email_sent == False, Query.is_processing == False).all()
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
                        set_notify(query_entry.query, query_entry.email)
                        # After processing, reset is_processing to False
                        query_entry.is_processing = False
                        db.session.commit()
                    except Exception as e:
                        # In case of an error, reset is_processing and log the error
                        query_entry.is_processing = False
                        db.session.commit()
                        print(f"Error processing query {query_entry.id}: {e}")
            time.sleep(10)  # Adjust sleep time if necessary

def parse_interval(trigger_time):
    if trigger_time == '30s':
        return timedelta(seconds=30)
    elif trigger_time == '1h':
        return timedelta(hours=1)
    elif trigger_time == '1d':
        return timedelta(days=1)
    elif trigger_time == '1w':
        return timedelta(weeks=1)
    elif trigger_time == '1m':
        return timedelta(days=30)
    else:
        return timedelta(seconds=30)  # Default interval

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
            time.sleep(10)
    thread = Thread(target=run)
    thread.daemon = True
    thread.start()

start_query_processor()
start_email_sender()

if __name__ == '__main__':
    app.run(debug=True)  # Set debug to False for deployment
