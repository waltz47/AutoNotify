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

#VARIABLES
MODEL_NAME = "grok-beta"

def search_web(query):
    print(f"Search for {query}")
    s = search(query, num_results=10,advanced=True)
    ret_str = ""
    for i in s:
        ret_str += i.description + "\n"
    return ret_str

def store_email_in_db(heading, body, recipient_email):
    # Store email details in the database
    email_entry = Email(recipient_email=recipient_email, heading=heading, body=body)
    db.session.add(email_entry)
    db.session.commit()
    return "Email details stored in database."

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
        "description": "Store email details in the database",
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
]

def call_function_by_name(function_name, arguments):
    if function_name == "store_email_in_db":
        return store_email_in_db(**arguments)
    for function in functions:
        if function["name"] == function_name:
            return globals()[function_name](**arguments)
    raise ValueError(f"Function {function_name} not found")

def set_notify(query, email):
    messages=[
        {"role": "system", "content": f'''You are a helpful assistant designed to notify users about certain events.
        For every event, send an email if the event the user asked about has happened or is currently happening. Search the web so you have the most up-to-date information.
        If event has already occured,  send an email with the heading "Event has occured" and the body "The event has already occured.".
        Once you're done, you can exit the conversation by typing "exit".

        The user's email address is: {email}
        The current date is: {datetime.today().strftime('%Y-%m-%d')}'''},
        {"role": "user", "content": query}
    ]

    client = OpenAI(
        api_key="xai-UiOih20Ae5VKxD7MGb2llRT5N4VMev11oTFnMS7rjsOuxtqOz7dyvS2oNBbMdrmoEM00vWYuZPQ5zrqX",
        base_url="https://api.x.ai/v1",
    )

    tools = [{'type': "function", "function": f} for f in functions]

    while True:

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools
        )

        if "exit" in response.choices[0].message.content:
            break

        print(response.choices[0].message.content)
        try:
            tool_call = response.choices[0].message.tool_calls[0]
        except:
            #exit when no more tool calls left to do
            assert(0) #invalid call
            break

        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        result = call_function_by_name(function_name, arguments)
        # print(f"Result of {function_name} is", result)

        function_call_result_message = {
            "role": "tool",
            "content": result,
            "tool_call_id": response.choices[0].message.tool_calls[0].id
        }
    
        messages.append(function_call_result_message)
        if "exit" in response.choices[0].message.content:
            break

    print("*****************************END*********************************")