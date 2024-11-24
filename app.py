from flask import Flask, render_template, request, redirect, url_for
from query import set_notify
from models import db, Email
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
        return redirect(url_for('email', query=query))
    return render_template('index.html')

@app.route('/email', methods=['GET', 'POST'])
def email():
    query = request.args.get('query')
    if request.method == 'POST':
        email = request.form['email']
        new_email = Email(recipient_email=email)
        db.session.add(new_email)
        db.session.commit()
        set_notify(query, email)
        return f"Notification set for your query. Confirmation sent to {email}."
    return render_template('email.html', query=query)

def start_email_sender():
    def run():
        while True:
            with app.app_context():
                send_pending_emails()
            time.sleep(5)
    thread = Thread(target=run)
    thread.daemon = True
    thread.start()

if __name__ == '__main__':
    start_email_sender()
    app.run(debug=True)
