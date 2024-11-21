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

#VARIABLES
MODEL_NAME = "grok-beta"

def search_web(query):
    print(f"Search for {query}")
    s = search(query, num_results=10,advanced=True)
    ret_str = ""
    for i in s:
        ret_str += i.description + "\n"
    return ret_str

def send_mail(heading, body):
    s = f"Email sent with heading: {heading} and body: {body}"
    print(s)
    return s

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
        "name": "send_mail",
        "description": "Send an email with the given heading and body",
        "parameters": {
            "type": "object",
            "properties": {
                "heading": {
                    "type": "string",
                    "description": "the email heading",
                },
                "body": {
                    "type": "string",
                    "description": "test content of the email",
                },
            },
            "required": ["heading", "body"],
            "optional": [],
        },
    },
]

def call_function_by_name(function_name, arguments):
    for function in functions:
        if function["name"] == function_name:
            return globals()[function_name](**arguments)
    raise ValueError(f"Function {function_name} not found")

query = input("Enter your query: ")
messages=[
        {"role": "system", "content": '''You are a helpful assistant designed to notify users about certain events.
        For every event, send an email if the event the user asked about about has happened or is currently happening. Search the web so you have the most up-to-date information.'''},
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

    # print(response.choices[0])
    try:
        tool_call = response.choices[0].message.tool_calls[0]
    except:
        #exit when no more tool calls left to do
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

print("*****************************END*********************************")