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
    # {
    #     "name": "get_current_date",
    #     "description": "Get the current date and time",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {},
    #     }
    # }
]

def set_notify(query, email):
    # print(f"set_notify called with query: {query} and email: {email}")
    messages=[
        {"role": "system", "content": f'''You are a helpful assistant designed to help users schedule email notifications for events according to user requirements.

        The user's email address is: {email} and the current date is {get_current_date()}
        
        Here are the rules you should follow:
        1. You can only schedule emails for events that have already happened or are currently occuring.
        2. You cannot schedule emails for events that will occur in the future. In this case print "exit" along with a detailed reasoning.
        3. Ensure that the current date you use for checking whether an event is in the future is the one provided in the prompt and not some other date.
        4. You can search the web for information using the search_web function. Do so even if you already have knowledge of the event to get up-to-date information.
        5. Do not ask questions. Simply provide the information requested along with detailed reasoning.

        For example:
            User query: Notify me when it's 23 November.
            If the current date is:
                24 Novemeber: Send an email to the user since 23 November has already passed.
                23 Novemeber: Send an email to the user since 23 November is the current date.
                22 Novemeber: Do not send an email to the user since 23 November has not yet occured.
        '''},
        {"role": "user", "content": query}
    ]

    client = OpenAI(
        api_key="xai-UiOih20Ae5VKxD7MGb2llRT5N4VMev11oTFnMS7rjsOuxtqOz7dyvS2oNBbMdrmoEM00vWYuZPQ5zrqX",
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
            # print("INVALID TOOL CALL. SHOULD PRINT EXIT MESSAGE INSTEAD")
            # break
            continue

        # call the tool
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        result = call_function_by_name(function_name, arguments)
        print(f"Result of {function_name} is", result)

        function_call_result_message = {
            "role": "tool",
            "content": result,
            "tool_call_id": response.choices[0].message.tool_calls[0].id
        }
    
        # append tool results to the history and repeat
        messages.append(function_call_result_message)
        if "exit" in response.choices[0].message.content:
            break
    
        cnt += 1
        if cnt > 10:
            print("COUNTER EXCEEDED MAX ALLOWED LIMIT")
            break

    print("*****************************END*********************************")