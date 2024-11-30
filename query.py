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
from models import db, Email, Query
import urllib
# from GoogleNews import GoogleNews
from gnews import GNews
from googlenewsdecoder import new_decoderv1

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
    import urllib.request

    def scrape(url):
        print(f"Scraping {url}")
        try:
            thepage = urllib.request.urlopen(url, timeout=10)
            soup = BeautifulSoup(thepage, "html.parser")
            text = soup.get_text()
            words = text.split()
            limited_text = ' '.join(words[:500])
            return limited_text
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return ""

    print(f"Search for {query}")
    googlenews = GNews(max_results=10)
    articles = googlenews.get_news(query)
    # print(articles)
    ret_str = "***********************************ARTICLES***********************************\n"
    for article in articles:
        try:
            real_url = article.get('url')
            ret_str += f"Title: {article.get('title')}\n"
            ret_str += f"Published Date: {article.get('published date')}\n"
            ret_str += f"Description: {article.get('description')}\n"
            # ret_str += f"Content:\n{scrape(new_decoderv1(real_url,0)['decoded_url'])}\n\n"
        except Exception as e:
            print(f"Error fetching article {article.get('title')}: {e}")
            continue
    ret_str += "***********************************END OF ARTICLES***********************************\n"
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
    # Remove the corresponding event (Query entry)
    query_entries = db.session.query(Query).filter_by(email=recipient_email).all()
    for query_entry in query_entries:
        db.session.delete(query_entry)
    db.session.commit()
    return "Email details stored in database."

def search_flights(origin, destination, depart_date):
    import requests
    import json
    url = "https://sky-scanner3.p.rapidapi.com/flights/search-multi-city"
    payload = {
        "market": "IN",
        "locale": "en-US",
        "currency": "INR",
        "adults": 1,
        "children": 0,
        "infants": 0,
        "cabinClass": "economy",
        "stops": ["direct"],
        "sort": "cheapest_first",
        "flights": [
            {
                "fromEntityId": origin,
                "toEntityId": destination,
                "departDate": depart_date
            }
        ]
    }
    headers = {
        "x-rapidapi-key": os.environ.get("RAPIDAPI_KEY"),
        "x-rapidapi-host": "sky-scanner3.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()['data']['filterStats']['stopPrices']

def is_number_less_than(number1, number2):
    return number1 < number2

def call_function_by_name(function_name, arguments):
    print("Function call: ", function_name)
    if function_name == "store_email_in_db":
        return store_email_in_db(**arguments)
    elif function_name == "search_web":
        search_results = search_web(**arguments)
        return search_results
    elif function_name == "search_flights":
        return search_flights(**arguments)
    elif function_name == "is_number_less_than":
        return is_number_less_than(**arguments)
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
        "name": "is_number_less_than",
        "description": "Compare two numbers and return if the first is less than the second",
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
        2. Prepare a search term/phrase that can be used to search the web for news and information. Use the tools at your disposal to get the latest information. The result might be old or new information. Go through it carefully.
        3. Go through the search results and find the relevant data. For dates or numbers, use the tools for comparison. Ensure to pass the input in the correct format and make decisions based only on the tool results.
        4. If the event has already occured, you need to create en email with a heading and body. The body should be in the following format: "Hi, you are being notified that......". Use HTML formatting for the body. The email should contain all the relevant details. Sign off as 'AutoNotify'.
        5. If the event has not occured, go to step #6.
        5. Use the `store_email_in_db` tool to store the email details in the database to be sent.
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
