"""Archived early scraper prototype. Not used by the Flask app."""

from bs4 import BeautifulSoup
import requests
import csv
import html

#base_url = (f"https://umassdining.com/foodpro-menu-ajax?tid={id}&date=")
org_url = requests.get('https://umassdining.com/locations-menus/worcester/menu')
soup = BeautifulSoup(org_url.content, 'html.parser')

select_me = soup.find('select',{'id': 'upcoming-foodpro'}) #select menu
tid = {1: "Worcester",
       2: "Franklin",
       3: "Hampshire",
       4: "Berkshire"
       }

if select_me:
    opt = select_me.find_all('option') #option tag
    #extracts data from each option
    for location_id, location_name in tid.items(): #iterating through the dining halls
            # Construct the URL with the correct tid for each location
            base_url = (f"https://umassdining.com/foodpro-menu-ajax?tid={location_id}&date=")
            print(f"Fetching menu for {location_name}")
            
            # You can now send a request to the constructed URL
            response = requests.get(base_url)
            for options in range(3): #amount of days 1-14 (13 days ahead?)
                    date_val = opt[options]['value'] #the date 11/10/2024 format
                #requests for each date that we get 
                    r = requests.get(f'{base_url}{date_val}')
                    day = BeautifulSoup(r.content, 'html.parser')

                    #food_items = day.find_all('li')
                    print(f"Menu for date {date_val}")
                    dish_name = day.find_all('a')  
                    
                    """titles = day.find_all('h2', class_="menu_category_name")  # Find all category titles
                    for title in titles: # some of the titles , still not formatted right but some extra info but works if you uncomment
                        name = title.get_text()
                        name = html.unescape(name).split('<')[0].strip() # Get text from <h2> and strip whitespace
                        name = name.replace(r'\/', '/')
                        if name:
                            print(name)
                        """
                        
                    for dish in dish_name: # All dishes from breakfast to late night
                        name = dish.get_text('data-dish-name')
                        name = html.unescape(name).split('<')[0].strip()
                        name = name.replace(r'\/', '/') # Fix formatting
                        if name:
                            print(f"Dish: {name}")
                    print()
         
# figure out how to organize all and what to do with it as we continue
