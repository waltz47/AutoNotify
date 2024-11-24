
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_email = db.Column(db.String(120), nullable=False)
    heading = db.Column(db.String(255))
    body = db.Column(db.Text)