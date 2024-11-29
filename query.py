import os
import ollama
# from gnews import GNews
from googlesearch import search
import requests
import os
from openai import OpenAI
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
from flask import Flask, render_template, request
from mailer import *
from models import db, Email
import urllib

#VARIABLES
MODEL_NAME = "grok-beta"

def get_current_date():
    return datetime.now().strftime("%d %b, %Y")

def date_has_passed(date_str):
    # Parse the input date string into a date object
    input_date = datetime.strptime(date_str, "%d %b, %Y").date()
    # Get the current date
    current_date = datetime.now().date()
    # Compare dates
    return input_date < current_date

def search_web(query):

    def scrape(url):
        thepage = urllib.request.urlopen(url)
        soup = BeautifulSoup(thepage, "html.parser")
        return soup.get_text()

    print(f"Search for {query}")
    s = search(query, num_results=20, advanced=True)
    ret_str = ""
    for i in s:
        # print("Scraping url:", i.url)
        ret_str += i.description + "\n"
    # print("Search results: ", ret_str)
    return ret_str

def email_exists(recipient_email, heading, body):
    return db.session.query(Email).filter_by(recipient_email=recipient_email, heading=heading, body=body).first() is not None

def store_email_in_db(heading, body, recipient_email):
    print("Storing email in DB")
    assert not email_exists(recipient_email, heading, body), "Duplicate email entry for the same details."
    # Store email details in the database
    email_entry = Email(recipient_email=recipient_email, heading=heading, body=body)
    db.session.add(email_entry)
    db.session.commit()
    return "Email details stored in database."

def call_function_by_name(function_name, arguments):
    print("Function call: ", function_name)
    if function_name == "store_email_in_db":
        return store_email_in_db(**arguments)
    elif function_name == "search_web":
        search_results = search_web(**arguments)
        return search_results
    for function in functions:
        if function["name"] == function_name:
            return globals()[function_name](**arguments)
    raise ValueError(f"Function {function_name} not found")


functions = [
    {
        "name": "search_web",
        "description": "Search the web for anything",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The topic you want to search for (as detailed as possible)",
                    "example_value": "SpaceX Current CEO",
                },
            },
            "required": ["query"],
            "optional": [],
        },
    },
    {
        "name": "store_email_in_db",
        "description": "Store email details in the database to be sent",
        "parameters": {
            "type": "object",
            "properties": {
                "heading": {
                    "type": "string",
                    "description": "The email heading",
                },
                "body": {
                    "type": "string",
                    "description": "The content of the email",
                },
                "recipient_email": {
                    "type": "string",
                    "description": "The recipient's email address",
                }
            },
            "required": ["heading", "body", "recipient_email"],
            "optional": [],
        },
    },
    {
        "name": "date_has_passed",
        "description": "Compare a date with the current date and return if it has already passed",
        "parameters": {
            "type": "object",
            "properties": {
                "date_str": {
                    "type": "string",
                    "description": "The date string to compare, in the format '%d %b, %Y'",
                },
            },
            "required": ["date_str"],
            "optional": [],
        },
    },
]

def set_notify(query, email):
    # print(f"set_notify called with query: {query} and email: {email}")
    import html
    safe_query = html.escape(query)
    safe_email = html.escape(email)
    messages=[
        {"role": "system", "content": f'''You are a helpful assistant designed to notify customer about the things they want to be notified about. It could be anything: concerts, rocket launches, product launches, upcoming podcasts, dates, etc. 
        Please follow these instructions:
        1. Rephrase the question in a way that makes it obvious. For eg. If the customer says "When is starship flight 5 launching", it can rephrased as "Notify me when starship flight 5 launches".
        2. Prepare a search term/phrase that can be used to search the web for information. Search the web for the term (You have tools available for that). The result might be old or new information. Go through it carefully.
        3. Go through the search results and find the date on which the event happened. Call the `date_has_passed` tool provided to you to check if that date has passed.
        4. If the date has passed, you need to create en email with a heading and body. The body should be in the following format: "Hi, you are being notified that......". Use HTML formatting for the body.
        5. If the date has not passed, go to step #6.
        5. Call the `store_email_in_db` tool to store the email details in the database.
        6. Print `exit` to end the conversation.

        The user's email for your reference is: {safe_email}.

        '''},
        {"role": "user", "content": safe_query}
    ]

    client = OpenAI(
        api_key=os.environ['XAI_API_KEY'],
        base_url="https://api.x.ai/v1",
    )

    tools = [{'type': "function", "function": f} for f in functions]

    cnt = 0

    while True:
        # calling xai api
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools,
            temperature=0.0,
        )

        print("LLM response: ", response.choices[0].message.content)

        if "exit" in response.choices[0].message.content:
            break
        try:
            tool_call = response.choices[0].message.tool_calls[0]
        except:
            #exit when no more tool calls left to do
            # assert(0) #invalid call
            print("INVALID TOOL CALL. SHOULD PRINT EXIT MESSAGE INSTEAD")
            break
            # continue/

        # call the tool
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        result = call_function_by_name(function_name, arguments)
        print(f"Result of {function_name} is", result)

        function_call_result_message = {
            "role": "function",
            "name": function_name,
            "content": str(result)  # Convert result to string
        }
    
        # append tool results to the history and repeat
        messages.append(function_call_result_message)
        if "exit" in response.choices[0].message.content.lower():
            break
    
        cnt += 1
        if cnt > 10:
            print("COUNTER EXCEEDED MAX ALLOWED LIMIT")
            break

    print("*****************************END*********************************")