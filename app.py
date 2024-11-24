from flask import Flask, render_template, request, redirect, url_for
from query import set_notify
from models import db, Email, Query
from threading import Thread
import time
from mailer import send_pending_emails

app = Flask(__name__)
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
        store_query_in_db(query, email)
        return redirect(url_for('confirmation', email=email))
    return render_template('index.html')

@app.route('/confirmation', methods=['GET'])
def confirmation():
    email = request.args.get('email')
    return render_template('confirmation.html', email=email)

def store_query_in_db(query, email):
    query_entry = Query(query=query, email=email)
    db.session.add(query_entry)
    db.session.commit()

query_processor_thread = None

def process_queries():
    while True:
        with app.app_context():
            print("process_queries function called")
            queries = db.session.query(Query).filter_by(is_processing=False).all()
            for query_entry in queries:
                print(f"Processing query: {query_entry.query} for email: {query_entry.email}")
                query_entry.is_processing = True
                db.session.commit()
                set_notify(query_entry.query, query_entry.email)
                db.session.delete(query_entry)
            db.session.commit()
        time.sleep(10)

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

if __name__ == '__main__':
    start_query_processor()
    start_email_sender()
    app.run(debug=True)
