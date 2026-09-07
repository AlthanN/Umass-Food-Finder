
"""Archived command-line search prototype. Not used by the Flask app."""

from Aidanscrapestore import menu_data

foodName = input("What do you desire: ")

# Flag to check if food is found
found_food = False

# Loop through all the entries in menu_data
for key, data in menu_data.items():
    date = data["date"]
    location = data["location"]
    
    # Loop through meals for each day-location
    for item in data["meals"]:
        if item["food"].lower() == foodName.lower():
            print(f"During {item['meal']} there is {foodName} in {location} on {date}.")
            found_food = True  # Set the flag to True when food is found
            break
    
if not found_food:
    print("Sorry, it is not available.")
    
        
        
