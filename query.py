import os
import requests
import os
from openai import OpenAI
from bs4 import BeautifulSoup
import re
from datetime import datetime
from flask import Flask, render_template, request
from mailer import *
from models import db, Email, Query
from fn import *
import html

using_openai = False

#VARIABLES
if using_openai:
    MODEL_NAME = "gpt-4o"
else:
    MODEL_NAME = "grok-beta"


def call_function_by_name(function_name, arguments, session):
    print("Function call: ", function_name)
    if function_name == "trigger_occured":
        return trigger_occured(session=session, **arguments)
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
        "description": "Search the web for information on a topic",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords of topic you want to search for",
                    "example_value": "SpaceX, Current CEO",
                },
            },
            "required": ["query"],
            "optional": [],
        },
    },
    # {
    #     "name": "search_web",
    #     "description": "Search the web for information on a topic",
    #     "parameters": {
    #         "type": "object",
    #         "properties": {
    #             "query": {
    #                 "type": "string",
    #                 "description": "The topic you want to search for (as detailed as possible)",
    #                 "example_value": "SpaceX Current CEO",
    #             },
    #         },
    #         "required": ["query"],
    #         "optional": [],
    #     },
    # },
    {
        "name": "trigger_occured",
        "description": "Store details in the database for a trigger that has occured",
        "parameters": {
            "type": "object",
            "properties": {
                "heading": {
                    "type": "string",
                    "description": "The title of the trigger",
                },
                "body": {
                    "type": "string",
                    "description": "Details of the trigger event",
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
        "name": "compare_dates",
        "description": "Compare two dates to see which one is earlier",
        "parameters": {
            "type": "object",
            "properties": {
                "date_str_A": {
                    "type": "string",
                    "description": "The date string to compare, in the format '%d %b, %Y'",
                },
                "date_str_B": {
                    "type": "string",
                    "description": "The date string to compare, in the format '%d %b, %Y'",
                },
            },
            "required": ["date_str_A", "date_str_B"],
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

def set_notify(trigger, email, session):
    print("Calling set notify for query", trigger)
    safe_trigger = html.escape(trigger)
    safe_email = html.escape(email)

    messages = [
        {"role": "system", "content": f'''You are an AI system designed to determine whether certain triggers have occured or not. Your job is to honestly and accurately determine whether the trigger has occured or not using the tools available to you.
        If the trigger has occured, you must call the `trigger_occured` tool with the heading and body provided. The user's email for your reference is: {safe_email}. The email body must be in HTML and must have all the details.
        If the trigger has not occured or if the trigger condtion fails, you must do nothing and call the `end` tool.
        
        For reference, the current date is: {get_current_date()}.'''},
        {"role": "user", "content": f'''The trigger is {safe_trigger}''' }
    ]

    if using_openai:
        client = OpenAI()
    else:
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
        
        try:
            print(f"LLM response (cnt: {cnt} messages_length: {len(messages)}):  {response.choices[0].message.content}")
        except:
            pass

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
        if using_openai:
            arguments = json.loads(tool_call.function.arguments)
        else:
            arguments = json.loads(tool_call.function.arguments)

        if function_name == "end":
            print("Called exit function")
            break

        result = call_function_by_name(function_name, arguments, session)
        print(f"Result of {function_name} is", result)

        if using_openai:
            function_call_result_message = {
                "role": "tool",
                "content": str(result),
                "tool_call_id": response.choices[0].message.tool_calls[0].id,
                
            }
        else:
            function_call_result_message = {
            "role": "tool",
            "content": str(result),
            "tool_call_id": response.choices[0].message.tool_calls[0].id
            }
    
        # append tool results to the history and repeat
        messages.append(response.choices[0].message)
        messages.append(function_call_result_message)
    
        cnt += 1
        if cnt > 10:
            print("COUNTER EXCEEDED MAX ALLOWED LIMIT. Deleting query from DB and exiting.")
            # Delete the query from the database
            query_entries = session.query(Query).filter_by(query=query, email=email).all()
            for query_entry in query_entries:
                session.delete(query_entry)
            session.commit()
            break
    
        # print(messages)

    print("*****************************END*********************************")
