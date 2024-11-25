from __future__ import print_function
from mailersend import emails
import os
from models import db, Email
import time
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from pprint import pprint

def send_mail(heading, body, recipient_email):
    print("Sending email to", recipient_email)
    print(f"Heading: {heading}\nBody: {body}")
    key = os.environ["MAILSEND_API_KEY"]
    # Initialize configuration instance
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = key
    # Create API client with configuration
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    # Define the email
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": recipient_email}],
        sender={"name": "psy", "email": "sparkros26@gmail.com"},
        subject=heading,
        html_content=body
    )
    # Send the email
    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        pprint(api_response)
    except ApiException as e:
        print("Exception when calling TransactionalEmailsApi->send_transac_email: %s\n" % e)

def send_pending_emails():
    emails_to_send = Email.query.all()
    for email_entry in emails_to_send:
        send_mail(email_entry.heading, email_entry.body, email_entry.recipient_email)
        # Remove the entry after sending the email
        db.session.delete(email_entry)
    db.session.commit()
