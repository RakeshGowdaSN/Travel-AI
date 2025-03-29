import os
import re
import requests
import vertexai
import vertexai.preview.generative_models as generative_models
import google.generativeai as genai
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv
import googlemaps

# # user defined
import prompts.prompt_templates as templates
import utils.constants as constants
import utils.model_generate_functions as gen_fun
# import utils.loggers as logger

# logg = logger.get_logger(constants.log_filename)
# # --------loading Google api key-------------#
parser = JsonOutputParser()
load_dotenv()
GOOGLE_GEMINI_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
# --------------------------------------------#
PROJECT_ID = constants.PROJECT_ID
REGION = constants.REGION
# BUCKET = constants.BUCKET
LOCATION = constants.LOCATION
search_location = "global"
vertexai.init(project=PROJECT_ID, location=LOCATION)
#gmap client 
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
gmaps = googlemaps.Client(key=google_maps_api_key)

# # Load spaCy's English model for NER
# nlp = spacy.load('en_core_web_sm')

# Initialize Google Maps API client
def dynamic_prompt_generation(prompt_template, input_variables):
    try:
        system_message_prompt = PromptTemplate(
            input_variables=list(
                input_variables.keys()), template=prompt_template)
        final_prompt = system_message_prompt.format(**input_variables)
        print(final_prompt)
        return final_prompt
    except Exception as e:
        # logg.error("Error creating dynamic prompts", exc_info=True)
        return f"Error creating dynamic prompts: {e}"

def extract_places_coordinates(response, places_coordinates=None):
    """
    This function extracts place names and their corresponding coordinates from a given response string.
    The places_coordinates dictionary is only initialized if a condition is met.
    
    :param response: A string containing the place details with Google Maps URLs
    :param places_coordinates: A dictionary to store the extracted place names and coordinates (default is None)
    :return: A dictionary where keys are place names and values are tuples containing latitude and longitude
    """
    # Initialize places_coordinates if not provided
    if places_coordinates is None:
        places_coordinates = {}
    
    # Check if the response contains place data
    if response.strip():  # Assuming we only process if there is valid response content
        # Regular expression to match the place name and coordinates from the URL
        pattern = r"\[([^\]]+)\]\(https://www.google.com/maps/place/?q=place_id:{place_id})"

        # Find all matches using the regular expression
        matches = re.findall(pattern, response)

        # Store the extracted data in the dictionary
        for match in matches:
            place_name = match[0]  # Place name
            latitude = match[1]  # Latitude
            longitude = match[2]  # Longitude
            places_coordinates[place_name] = (latitude, longitude)

    return places_coordinates


def places_nd_coordinates(location, checkin, checkout, query, chat_history= None):
    
    list_of_places = parser.parse(gen_fun.generate_recommendations(constants.model, templates.extract_place_prompt.format(location=location, checkin=checkin, checkout=checkout, query=query, chat_history=chat_history)))
    place_url = {}
    overall_res = {}
    coordinates_fe = {}

    for i in list_of_places:
        map_res = gmaps.places(f'{i},{location}')
        place_id = map_res['results'][0]['place_id']
        map_url = f'https://www.google.com/maps/place/?q=place_id:{place_id}'
        overall_res[i] = gmaps.places(i)
        place_url[i] = map_url
        # coordinates_fe[i] = (map_res['results'][0]['geometry']['location']['lat'], map_res['results'][0]['geometry']['location']['lng'])

        # Fetch coordinates from the map result and convert them to string format
        latitude = map_res['results'][0]['geometry']['location']['lat']
        longitude = map_res['results'][0]['geometry']['location']['lng']
        
        # Store coordinates as strings in an array
        coordinates_fe[i] = [str(latitude), str(longitude)]  # Convert to strings

    return overall_res, place_url, list_of_places, coordinates_fe

def nearby_places(location, checkin, checkout, query, chat_history= None):
    place_of_interest = parser.parse(gen_fun.generate_recommendations(constants.model,templates.nearby_place_prompt.format(location = location, checkin = checkin, checkout = checkout, query = query, chat_history = chat_history)))

    place_coordinates = gmaps.places(place_of_interest['Place'])
    poi_coordinates = (place_coordinates['results'][0]['geometry']['location']['lat'], place_coordinates['results'][0]['geometry']['location']['lng'])
    
    overall_res = gmaps.places_nearby(poi_coordinates, radius = 5000, keyword=place_of_interest['Topic of Interest'], page_token=None)
    n = place_of_interest['Number of places']

    coordinates_fe = {}
    # places_coordinates[place_name] = (latitude, longitude)
    
    place_url = {}
    for i in overall_res['results'][0:int(n)]:
        place_url[i['name']] = f'https://www.google.com/maps/place/?q=place_id:{i["place_id"]}'
        coordinates_fe[i['name']] = (i['geometry']['location']['lat'], i['geometry']['location']['lng'])

    return overall_res, place_url, place_of_interest, coordinates_fe


def transit_information(location, checkin, checkout, query, chat_history= None):
    OriginDestination  = parser.parse(gen_fun.llm(constants.model,templates.Origin_nd_Destination_prompt.format(location = location, checkin = checkin, checkout = checkout, query = query, chat_history = chat_history)))
    origin = OriginDestination['Origin']
    destination = OriginDestination['Destination']

    transit_modes = ["bus", "subway", "train", "tram", "rail"] # Added the transit mode subway

    all_directions = {}

    for mode in transit_modes:
        try:
            # Try to fetch directions for each transit mode
            res = gmaps.directions(origin, destination, mode="transit", transit_mode=mode)
            if res:  # Check if the response is not empty
                all_directions[mode] = res
            else:
                all_directions[mode] = None  # No route found for this mode
        except googlemaps.exceptions.ApiError as e:
            # Log the error and set None for the mode if there's an API error
            print(f"Error fetching transit directions for {mode}: {e}")
            all_directions[mode] = None

    # Prepare the results
    routes = {}
    for mode, directions in all_directions.items():
        if directions is None:
            routes[mode] = "No transit information available"  # No routes found or error occurred
        else:
            print(f"Transit mode: {mode}")
            for leg in directions[0]['legs']:
                # Store details in the routes dictionary
                routes[mode] = {
                    'Distance': leg['distance']['text'],
                    'Duration': leg['duration']['text'],
                    'Start Address': leg['start_address'],
                    'End Address': leg['end_address']
                }
                
                # Concatenate step instructions
                instructions = ''
                for step in leg['steps']:
                    instructions += step['html_instructions'] + ' '  # Assuming you want the step instructions
                routes[mode]['Instructions'] = instructions  # Store instructions in the nested dictionary

    return routes


def get_url_rating(location, query, chat_history= None):
    list_of_places = parser.parse(gen_fun.generate_recommendations(constants.model,templates.place_for_rating.format(location = location, query = query, chat_history = chat_history)))
    place_url = {}
    overall_res = {}
    coordinates_fe = {}

    for i in list_of_places:
        map_res = gmaps.places(f'{i},{location}')
        place_id = map_res['results'][0]['place_id']
        map_url = f'https://www.google.com/maps/place/?q=place_id:{place_id}'
        overall_res[i] = gmaps.places(i)
        place_url[i] = map_url
        coordinates_fe[i] = (map_res['results'][0]['geometry']['location']['lat'], map_res['results'][0]['geometry']['location']['lng'])
    return overall_res, place_url, list_of_places, coordinates_fe