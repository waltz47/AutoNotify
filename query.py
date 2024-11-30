import os
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
from models import db, Email, Query
import urllib
from gnews import GNews
from googlenewsdecoder import new_decoderv1
import urllib.request
from fn import *
import html

#VARIABLES
MODEL_NAME = "grok-beta"

def call_function_by_name(function_name, arguments, session):
    print("Function call: ", function_name)
    if function_name == "store_email_in_db":
        return store_email_in_db(session=session, **arguments)
    elif function_name == "search_news":
        search_results = search_news(**arguments)
        return search_results
    elif function_name == "search_flights":
        return search_flights(**arguments)
    elif function_name == "compare_numbers":
        return compare_numbers(**arguments)
    for function in functions:
        if function["name"] == function_name:
            return globals()[function_name](**arguments)
    raise ValueError(f"Function {function_name} not found")


functions = [
    {
        "name": "search_news",
        "description": "Search the web for latest/old news",
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
        "name": "search_web",
        "description": "Search the web for information on a topic",
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
    {
        "name": "search_flights",
        "description": "Search for flights between two locations on a specific date",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "The IATA code of the origin airport (e.g., 'PNQ')",
                },
                "destination": {
                    "type": "string",
                    "description": "The IATA code of the destination airport (e.g., 'BLR')",
                },
                "depart_date": {
                    "type": "string",
                    "description": "The departure date in 'YYYY-MM-DD' format",
                },
            },
            "required": ["origin", "destination", "depart_date"],
        },
    },
    {
        "name": "compare_numbers",
        "description": "Compare two numbers and returns the comparison result",
        "parameters": {
            "type": "object",
            "properties": {
                "number1": {
                    "type": "number",
                    "description": "The first number to compare",
                },
                "number2": {
                    "type": "number",
                    "description": "The second number to compare",
                },
            },
            "required": ["number1", "number2"],
        },
    },
    {
        "name": "end",
        "description": "Ends the conversation",
        "parameters": {
            "type": "object",
            "properties": {
            },
            "required": [],
        },
    },
]

def set_notify(query, email, session):
    safe_query = html.escape(query)
    safe_email = html.escape(email)
    messages=[
        {"role": "system", "content": f'''You are a helpful assistant designed to notify customer about the things they want to be notified about. It could be anything: concerts, rocket launches, product launches, upcoming podcasts, dates, flight prices etc. 
        Please follow these instructions:
            1. Prepare a search term/phrase that can be used to search the web for news and articles. Use the tools at your disposal to get the latest information. The result might be old or new information. Go through it carefully.
            2. For dates or numbers, use the provided tools for comparisons.
            3. If the event has occured, you need to create en email with a heading and body. The body should be in the following format: 
                "Hi, 
                you are being notified that......". 
            Use HTML formatting for the body. The email should contain all the details. Sign off as 'AutoNotify'.
            4. If the event has not occured, go to step #6 and end the conversation.
            5. Use the `store_email_in_db` tool to store the email details in the database to be sent.
            6. End the conversation using the `end` tool.

        The user's email for your reference is: {safe_email}.'''},
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

        print(f"LLM response (cnt: {cnt} messages_length: {len(messages)}):  {response.choices[0].message.content}")

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

        if function_name == "end":
            print("Called exit function")
            break

        result = call_function_by_name(function_name, arguments, session)
        print(f"Result of {function_name} is", result)

        function_call_result_message = {
            "role": "function",
            "name": function_name,
            "content": str(result)  # Convert result to string
        }
    
        # append tool results to the history and repeat
        messages.append(function_call_result_message)
    
        cnt += 1
        if cnt > 10:
            print("COUNTER EXCEEDED MAX ALLOWED LIMIT")
            break

    print("*****************************END*********************************")
