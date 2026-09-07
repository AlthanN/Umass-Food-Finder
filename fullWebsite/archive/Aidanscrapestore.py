"""Archived import-time scraper prototype. Not used by the Flask app."""

from bs4 import BeautifulSoup
import requests
import json
from datetime import datetime


#base_url = (f"https://umassdining.com/foodpro-menu-ajax?tid={id}&date=")
org_url = requests.get('https://umassdining.com/locations-menus/worcester/menu')
soup = BeautifulSoup(org_url.content, 'html.parser')

select_me = soup.find('select',{'id': 'upcoming-foodpro'}) #select menu
tid = {1: "Worcester",
       2: "Franklin",
       3: "Hampshire",
       4: "Berkshire"
       }

def parseResponse(date_val, location_name, location_id, content):
    # print(content)
    json_file = json.loads(content)
    
    new_date = datetime.strptime(date_val,"%m/%d/%Y").strftime("%Y-%m-%d")
    
    doc = {
        "date": new_date,
        "location": location_name,
        "id": f'{date_val}-{location_id}',
    }
    
    doc_meals = []
    for meals in json_file:
        # print(json_file[key])
        for category in json_file[meals]:
            # print(category)
            
            dishes_html = BeautifulSoup(json_file[meals][category], 'html.parser')
            dishes = dishes_html.findAll("a")
            # dish = jsonsoup.get_text('menu-category-name')
            # if dish:
            #     print("THERE IS A DISH")
            for dish in dishes:
                dishes_for_each_meal = {
                    "meal": meals.capitalize(),
                    "category": category,
                    "food": dish.get_text() 
                }
                doc_meals.append(dishes_for_each_meal)
    doc["meals"] = doc_meals
    return doc

menu_data = {}  # Dictionary to hold the data in memory

if select_me:
    opt = select_me.find_all('option')
    for location_id, location_name in tid.items():
        base_url = f"https://umassdining.com/foodpro-menu-ajax?tid={location_id}&date="
        
        MAX_DAYS = 14
        for options in range(MAX_DAYS):
            date_val = opt[options]['value']
            r = requests.get(f'{base_url}{date_val}')
            day = BeautifulSoup(r.content, 'html.parser')
            
            # Parse and store the response in memory instead of a file
            doc = parseResponse(date_val, location_name, location_id, r.content)
            new_date = datetime.strptime(date_val, "%m/%d/%Y").strftime("%Y-%m-%d")
            
            # Store data in memory
            menu_data[f"{new_date}-{location_name}"] = doc
         


