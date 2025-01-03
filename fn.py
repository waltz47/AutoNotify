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
import urllib.request
from googlesearch import search
import json

def get_current_date():
    return datetime.now().strftime("%d %b, %Y")

def summarize_str(text, trigger):
    MODEL_NAME = "grok-beta"
    messages=[
        {"role": "system", "content": f'''You are a helpful assistant desinged to summarize text based on a given search phrase. Do not omit any details relevant to the search term.
        The search term is: {trigger}. Simple print the summarized output. Do not print any other text or greetings.'''},
        {"role": "user", "content": text}
    ]
    client_summ = OpenAI(
        api_key=os.environ['XAI_API_KEY'],
        base_url="https://api.x.ai/v1",
    )

    response = client_summ.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.3,
    )
    return response.choices[0].message.content

def get_trigger(query):
    
    MODEL_NAME = "grok-beta"
        
    trigger_prompt = f'''For the given user query, generate the trigger that is appropriate for the user's query in detail. There should be no ambiguity. It should take into account all of the following parameters and more: date of query, type of event, recurring events etc.
    The query was made on the following date: {get_current_date()}.
    
    For example:
    If the user query is: 'Notify me when the CEO of XYZ changes".
    The trigger would be: When the CEO of XYZ changes after <query_date>.
    
    If the user query is: 'When is the next SpaceX launch for starship?'
    The trigger would be: The next SpaceX launch for starship that happens after <query_date>.

    Simply print the trigger in the following format:
    "Trigger: <trigger>"
    '''
    messages=[
        {"role": "system", "content": trigger_prompt},
        {"role": "user", "content": query}
    ]
    client_summ = OpenAI(
        api_key=os.environ['XAI_API_KEY'],
        base_url="https://api.x.ai/v1",
    )

    response = client_summ.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.0,
    )
    return response.choices[0].message.content

def compare_dates(date_str_A, date_str_B):
    print(f"Comparing dates {date_str_A} and {date_str_B}")
    date1 = datetime.strptime(date_str_A, "%d %b, %Y").date()
    date2 = datetime.strptime(date_str_B, "%d %b, %Y").date()
    if date1 < date2:
        return f"{date_str_A} is before {date_str_B}"
    elif date1 == date2:
        return f"{date_str_A} is the same as {date_str_B}"
    else:
        return f"{date_str_A} is after {date_str_B}"

def scrape(url):
    print(f"Scraping {url}")
    try:
        thepage = urllib.request.urlopen(url, timeout=10)
        soup = BeautifulSoup(thepage, "html.parser")
        text = soup.get_text()
        words = text.split()
        limited_text = ' '.join(words[:1000])
        return limited_text
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

def search_web(query):
    print(f"Web Search for {query}")
    s = search(query, num_results=3)
    ret_str = ""
    for url in s:
        content = scrape(url)
        ret_str += content + "\n"
    return ret_str


def search_news(query):
    print(f"News Search for {query}")
    googlenews = GNews(max_results=5)
    articles = googlenews.get_news(query)
    # print(articles)
    ret_str = "*********************************** NEWS ARTICLES ***********************************\n"
    for article in articles:
        try:
            real_url = article.get('url')
            ret_str += f"Title: {article.get('title')}\n"
            ret_str += f"Published Date: {article.get('published date')}\n"
            ret_str += f"Description: {article.get('description')}\n"
            ret_str += f"Content:\n{scrape(new_decoderv1(real_url,0)['decoded_url'])}\n\n"
        except Exception as e:
            print(f"Error fetching article {article.get('title')}: {e}")
            continue
    ret_str += "*********************************** END OF NEWS ARTICLES ***********************************\n"
    news_articles = ret_str

    news_articles += "\n\n" + search_web(query)
    return summarize_str(news_articles, query)

def email_exists(recipient_email, heading, body):
    return db.session.query(Email).filter_by(recipient_email=recipient_email, heading=heading, body=body).first() is not None

def trigger_occured(heading, body, recipient_email, session):
    print("Storing email in DB")
    assert not email_exists(recipient_email, heading, body), "Duplicate email entry for the same details."
    # Store email details in the database
    email_entry = Email(recipient_email=recipient_email, heading=heading, body=body)
    session.add(email_entry)
    session.commit()
    # Delete the Query entries instead of updating them
    query_entries = session.query(Query).filter_by(email=recipient_email).all()
    for query_entry in query_entries:
        session.delete(query_entry)
    session.commit()
    return "Email details stored in database and query deleted."

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
    # print(json.dumps(response.json(),indent=4))
    return summarize_str(str(response.json()['data']['filterStats']))

def compare_numbers(number1, number2):
    print(f"Comparing {number1} and {number2}")
    if number1 < number2:
        return f"{number1} is less than {number2}"
    elif number1 == number2:
        return f"{number1} is equal to {number2}"
    else:
        return f"{number1} is greater than {number2}"

def get_random_events():
    return [
        {"query": "Invasion of Earth by Interdimensional Beings", "email": "interdimensional@earth.com (mailto:interdimensional@earth.com)", "trigger_time": "1m", "deadline": "2024-02-14"},
        {"query": "Global Dance-Off for World Peace", "email": "dance@peace.com (mailto:dance@peace.com)", "trigger_time": "1m", "deadline": "2024-03-21"},
        {"query": "Revival of Dinosaurs in Jurassic Park 2.0", "email": "dinosaurs@park.com (mailto:dinosaurs@park.com)", "trigger_time": "1m", "deadline": "2024-04-01"},
        {"query": "Establishment of Underwater Cities", "email": "aquacity@ocean.com (mailto:aquacity@ocean.com)", "trigger_time": "1m", "deadline": "2025-07-04"},
        {"query": "Creation of Edible Clothing", "email": "fashion@food.com (mailto:fashion@food.com)", "trigger_time": "1m", "deadline": "2024-11-23"},
        {"query": "Humans Gain Ability to Breathe Underwater", "email": "breathe@ocean.com (mailto:breathe@ocean.com)", "trigger_time": "1m", "deadline": "2025-08-12"},
        {"query": "World's First AI President Elected", "email": "ai@politics.com (mailto:ai@politics.com)", "trigger_time": "1m", "deadline": "2024-11-05"},
        {"query": "Discovery of a Hollow Earth", "email": "hollow@earth.com (mailto:hollow@earth.com)", "trigger_time": "1m", "deadline": "2024-06-21"},
        {"query": "First Human Telepathic Communication", "email": "mind@link.com (mailto:mind@link.com)", "trigger_time": "1m", "deadline": "2025-01-15"},
        {"query": "Invention of Personal Weather Control Devices", "email": "weather@control.com (mailto:weather@control.com)", "trigger_time": "1m", "deadline": "2025-05-05"},
        {"query": "Cure for Aging Discovered", "email": "youth@eternal.com (mailto:youth@eternal.com)", "trigger_time": "1m", "deadline": "2025-03-20"},
        {"query": "Global Language Unification to Emoji", "email": "emoji@world.com (mailto:emoji@world.com)", "trigger_time": "1m", "deadline": "2025-09-19"},
        {"query": "Establishment of a Floating Space Hotel", "email": "space@hotel.com (mailto:space@hotel.com)", "trigger_time": "1m", "deadline": "2024-12-31"},
        {"query": "Discovery of Invisible Creatures", "email": "invisible@nature.com (mailto:invisible@nature.com)", "trigger_time": "1m", "deadline": "2025-07-15"},
        {"query": "First Successful Human Cloning for Organ Donation", "email": "clone@health.com (mailto:clone@health.com)", "trigger_time": "1m", "deadline": "2024-10-31"},
        {"query": "Invention of Instant Language Translator Glasses", "email": "translate@vision.com (mailto:translate@vision.com)", "trigger_time": "1m", "deadline": "2025-04-01"},
        {"query": "Reintroduction of Mammoths into Siberia", "email": "mammoth@revive.com (mailto:mammoth@revive.com)", "trigger_time": "1m", "deadline": "2026-01-01"},
        {"query": "Development of Real Invisibility Cloaks", "email": "invisible@cloak.com (mailto:invisible@cloak.com)", "trigger_time": "1m", "deadline": "2025-08-18"},
        {"query": "Global Implementation of Holographic Pets", "email": "hologram@pet.com (mailto:hologram@pet.com)", "trigger_time": "1m", "deadline": "2024-12-25"},
        {"query": "First Contact with Time Travelers from 2300", "email": "time@travelers.com (mailto:time@travelers.com)", "trigger_time": "1m", "deadline": "2025-02-29"},
        {"query": "Creation of a Moon Theme Park", "email": "lunarpark@space.com (mailto:lunarpark@space.com)", "trigger_time": "1m", "deadline": "2025-07-20"},
        {"query": "Introduction of Smell-O-Vision TV", "email": "smell@vision.com (mailto:smell@vision.com)", "trigger_time": "1m", "deadline": "2024-05-05"},
        {"query": "Discovery of a Parallel Universe Where Dinosaurs Never Went Extinct", "email": "dino@parallel.com (mailto:dino@parallel.com)", "trigger_time": "1m", "deadline": "2024-12-25"},
        {"query": "Worldwide Ban on Artificial Intelligence", "email": "noai@future.com (mailto:noai@future.com)", "trigger_time": "1m", "deadline": "2025-04-15"},
        {"query": "First Human Hibernation for Space Travel", "email": "sleep@space.com (mailto:sleep@space.com)", "trigger_time": "1m", "deadline": "2025-10-01"},
        {"query": "Resurrection of Cleopatra for a Public Talk Show", "email": "cleopatra@history.com (mailto:cleopatra@history.com)", "trigger_time": "1m", "deadline": "2025-05-01"},
        {"query": "Successful Creation of Human-AI Hybrid", "email": "cyborg@future.com (mailto:cyborg@future.com)", "trigger_time": "1m", "deadline": "2024-09-30"},
        {"query": "Implementation of Dream-Streaming Service", "email": "dream@stream.com (mailto:dream@stream.com)", "trigger_time": "1m", "deadline": "2025-06-15"},
        {"query": "Invention of Anti-Gravity Shoes", "email": "float@shoes.com (mailto:float@shoes.com)", "trigger_time": "1m", "deadline": "2025-11-11"},
        {"query": "Global Election of a Non-Human Species as World Leader", "email": "alien@leader.com (mailto:alien@leader.com)", "trigger_time": "1m", "deadline": "2026-01-01"},
        {"query": "Discovery of a Fountain of Youth in the Amazon", "email": "youth@amazon.com (mailto:youth@amazon.com)", "trigger_time": "1m", "deadline": "2025-02-14"},
        {"query": "Introduction of Personal Force Field Generators", "email": "shield@security.com (mailto:shield@security.com)", "trigger_time": "1m", "deadline": "2024-11-11"},
        {"query": "First Successful Brain Upload to Cloud", "email": "upload@mind.com (mailto:upload@mind.com)", "trigger_time": "1m", "deadline": "2025-08-08"},
        {"query": "Creation of a Virtual Reality Earth", "email": "vr@earth.com (mailto:vr@earth.com)", "trigger_time": "1m", "deadline": "2026-03-21"},
        {"query": "Discovery of a New Continent in the Pacific", "email": "newland@ocean.com (mailto:newland@ocean.com)", "trigger_time": "1m", "deadline": "2025-07-04"},
        {"query": "Invention of Time-Slowing Bubble", "email": "slow@time.com (mailto:slow@time.com)", "trigger_time": "1m", "deadline": "2024-12-31"},
        {"query": "First Human-Made Star in Space", "email": "star@creation.com (mailto:star@creation.com)", "trigger_time": "1m", "deadline": "2027-01-01"},
        {"query": "Global Shift to Underwater Living for Climate Change", "email": "aquatic@life.com (mailto:aquatic@life.com)", "trigger_time": "1m", "deadline": "2026-05-22"},
        {"query": "Establishment of a Time Police Force", "email": "time@police.com (mailto:time@police.com)", "trigger_time": "1m", "deadline": "2025-09-21"},
        {"query": "First Contact with Sentient Plants", "email": "plant@intelligence.com (mailto:plant@intelligence.com)", "trigger_time": "1m", "deadline": "2025-06-05"}
    ]
