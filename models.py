from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_email = db.Column(db.String(120), nullable=False)
    heading = db.Column(db.String(255))
    body = db.Column(db.Text)

class Query(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    is_processing = db.Column(db.Boolean, default=False)
    trigger_time = db.Column(db.String(50), nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    last_run_time = db.Column(db.DateTime)
    email_sent = db.Column(db.Boolean, default=False)