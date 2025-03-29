import os
# import re
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import googlemaps
import google.auth
from google.cloud import firestore
import vertexai
import vertexai.preview.generative_models as generative_models
import logging
from dotenv import load_dotenv
from datetime import date, datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from vertexai.generative_models import GenerativeModel
# import spacy
import uuid

# user defined
import prompts.prompt_templates as templates
import utils.constants as constants
import utils.helper_functions as helper
import utils.model_generate_functions as gen_func

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Initialize FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
load_dotenv()

# Fetch environment variables
project_id = os.getenv('GOOGLE_PROJECT_ID')
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
google_gemini_api_key = os.getenv("GOOGLE_GEMINI_API_KEY")

# Initialize Google Maps API client
gmaps = googlemaps.Client(key=google_maps_api_key)

# # Load spaCy model for Named Entity Recognition (NER)
# nlp = spacy.load("en_core_web_sm")

# Initialize Firestore
db = firestore.Client(project=project_id, database="test-pitchhub")

# Safety settings for model content filtering
safety_settings = {
    generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT: generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}

# Identifying intent based on user query
def identify_intent(model, query):
    try:
        vertexai.init(project="pitchhubsmes", location="us-central1")
        model = GenerativeModel(
            model,
            system_instruction=["You are an AI assistant tasked with identifying the user's intent based on their query."]
        )
        contents = [templates.identify_intent.format(query=query)]
        response = model.generate_content(
            contents, generation_config=constants.generation_config, safety_settings=safety_settings
        )
        identified_intent = response.text.strip()

        if identified_intent == 'Travel Itinerary':
            prompt = templates.travel_itinerary
        elif identified_intent == 'Weather Forecast':
            prompt = templates.weather_forecast
        elif identified_intent == 'Transit Information':
            prompt = templates.transit_information
        elif identified_intent == 'Google Ratings & Reviews':
            prompt = templates.google_ratings
        elif identified_intent == 'Best Places':
            prompt = templates.best_places
        elif identified_intent == 'Accommodation Suggestions':
            prompt = templates.accommodation_suggestions
        elif identified_intent == 'Upcoming Events':
            prompt = templates.upcoming_events
        elif identified_intent == 'Dining Recommendations':
            prompt = templates.dining_recommendations
        elif identified_intent == 'Travel Tips':
            prompt = templates.travel_tips
        elif identified_intent == 'Ending Chat':
            prompt = templates.bye
        elif identified_intent == 'Out of Context':
            prompt = templates.out_of_context
        else:
            prompt = identify_intent

        # Return both the identified intent and the corresponding prompt
        return prompt, identified_intent

    except Exception as e:
        logging.error(f"Error while identifying intent: {e}", exc_info=True)
        return f"Error while identifying intent: {e}"


# Pydantic model for the chat request (without session_id input)
class ChatRequest(BaseModel):
    username: str
    location: str
    checkin: date
    checkout: date
    query: str

# Greeting message to the user
@app.get("/welcome")
async def welcome(name: str, location: str, checkin: date, checkout: date):
    if not google_maps_api_key:
        return {"error": "Google Maps API key not found in environment variables"}

    # Function to call Google Geocoding API to get place details like coordinates and place_id
    def get_google_geocoding_data(location):
        endpoint = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": location,  # e.g., "Paris"
            "key": google_maps_api_key  # Your Google Maps API key
        }

        response = requests.get(endpoint, params=params)
        data = response.json()

        if response.status_code == 200 and data.get("status") == "OK":
            # Get the first result (you can modify this for multiple results if needed)
            place = data["results"][0]
            coordinates = place["geometry"]["location"]
            place_id = place.get("place_id", "Place ID not found")

            return coordinates, place_id
        else:
            error_message = data.get("status", "Unknown error")
            return None, f"Error: {error_message}"

    # Get coordinates and place_id for the provided location
    coordinates, place_id = get_google_geocoding_data(location)
    
    if not coordinates:
        return {"error": place_id}  # Error message from the geocoding API
    
    # Create the personalized message
    message = f"Hey {name}! 🌟 Your adventure to {location} is almost here! 🏖️ " \
              f"From {checkin} to {checkout}, get ready for an unforgettable journey. ✈️ " \
              f"Need any help planning your dream trip? We're here to make it epic! 😎🌍"
    
    # Return the response with coordinates and place_id
    return {
        "message": message,
        "coordinates": coordinates,
        "place_id": place_id
    }


# Start a chat session
@app.post("/start_chat")
async def start_chat(chat_request: ChatRequest, session_id: str = None):
    username = chat_request.username
    location = chat_request.location
    checkin_dt = chat_request.checkin
    checkout_dt = chat_request.checkout
    query = chat_request.query

    # Convert the date objects to strings before saving to Firestore
    checkin = checkin_dt.isoformat()  # "2025-02-10"
    checkout = checkout_dt.isoformat()  # "2025-02-15"

    #API based intent classification

    places_api_intent = ['Best Places', 'Travel Itinerary']
    nearby_api_intent = ['Accommodation Suggestions', 'Dining Recommendations']
    google_search = ['Upcoming Events', 'Weather Forecast', 'Travel Tips']
    ratings_n_reviews = ['Google Ratings & Reviews']
    get_direction_api = ['Transit Information']

    # intent_places = ['Best Places', 'Accommodation Suggestions', 'Upcoming Events', 'Dining Recommendations',
    # 'Travel Itinerary', 'Weather Forecast', 'Transit Information', 'Google Ratings & Reviews', 'Travel Tips']

    # Initialize an empty dictionary for places_coordinates
    places_coordinates = {}

    if session_id:
        # Continued chat flow
        logging.debug(f"Continued chat 1: {session_id}")
        doc_ref = db.collection("users").document(chat_request.username).collection("chats").document(session_id)
        chat_data = doc_ref.get().to_dict()

        if chat_data:
            # Add new user message to chat history
            new_message = {"role": "user", "message": chat_request.query, "timestamp": datetime.utcnow().isoformat()}
            chat_data["history"].append(new_message)

            # Identify the intent and generate recommendations
            travel_assist_template, intent_id = identify_intent(constants.model, chat_request.query)
            logging.debug(f"----------------Identified intent: {intent_id}-------------")

            if travel_assist_template != 'bye':

                # Check if the identified_intent is in intent_places or intent_others
                if intent_id in places_api_intent:
                    
                    inter_step, place_url, list_of_places, places_coordinates = helper.places_nd_coordinates(chat_request.location, chat_request.checkin, chat_request.checkout, chat_request.query, chat_data["history"])
                    
                    places_response = f"\nPlace of interest based on User query:\n{place_url}"
                    
                    input_variables = {'location': chat_request.location, 'checkin': chat_request.checkin, 'checkout': chat_request.checkout, 'places': places_response, 'chat_history': chat_data["history"], 'query': chat_request.query}
                    recommendations_prompt = helper.dynamic_prompt_generation(templates.format_template, input_variables)
                    
                    model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)
                    
                    #adding intermediate steps
                    Intermediate_Step = {
                        'Step 1': {'Tool Used': 'Google Search', 'Response': list_of_places}, 
                        'Step 2': {'Tool Used': 'Google Maps-Places API', 'Response':inter_step}, 
                        'Step 3': {'Tool Used': 'Gemini API'}
                    }
                    chat_data['history'].append({"role": "assistant", "message": model_response, "places_coordinates": places_coordinates, "timestamp": datetime.utcnow().isoformat()})
                    
                elif intent_id in nearby_api_intent:


                    # Fetch place details for user query
                    inter_step, place_url, list_of_places, places_coordinates = helper.nearby_places(chat_request.location, chat_request.checkin, chat_request.checkout, chat_request.query, chat_data["history"])

                    places_response = f"\nPlace of interest based on User query:\n{place_url}"

                    input_variables = {'location': chat_request.location, 'checkin': chat_request.checkin,'query': chat_request.query,'checkout': chat_request.checkout, 'places': places_response, 'chat_history': chat_data["history"]}
                    recommendations_prompt = helper.dynamic_prompt_generation(templates.format_template, input_variables)
                    model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)

                    print(f'----------------------------------------------------{inter_step}-------\n {place_url}----{list_of_places}--------------------')
                    print(recommendations_prompt)

                    # Add the assistant's response to the chat history

                    Intermediate_Step = {
                        'Step 1': {'Tool Used': 'Google Search', 'Response': list_of_places}, 
                        'Step 2': {'Tool Used': 'Google Maps-Search Nearby', 'Response':inter_step}, 
                        'Step 3': {'Tool Used': 'Gemini API'}
                    }


                    chat_data['history'].append({"role": "assistant", "message": model_response, "places_coordinates": places_coordinates, "timestamp": datetime.utcnow().isoformat()})


                elif intent_id in google_search:
                    # Uses travel assist template
                    input_variables = {'location': chat_request.location, 'checkin': chat_request.checkin, 'checkout': chat_request.checkout, 'query': chat_request.query, 'chat_history': chat_data["history"]}
                    recommendations_prompt = helper.dynamic_prompt_generation(travel_assist_template, input_variables)
                    model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)

                    
                    Intermediate_Step = {
                        'Step 1': {'Tool Used': 'Google Search'},
                    }
                    # Add the assistant's response to the chat history
                    chat_data['history'].append({"role": "assistant", "message": model_response, "timestamp": datetime.utcnow().isoformat()})

                elif intent_id in ratings_n_reviews:
                    inter_step, place_url, list_of_places, places_coordinates = helper.get_url_rating(location, query, chat_data["history"])
                    
                    places_response = f"\nPlace of interest based on User query:\n{place_url}"
                    
                    input_variables = {'location': chat_request.location, 'checkin': chat_request.checkin, 'checkout': chat_request.checkout,'query': query, 'place': places_response, 'chat_history': chat_data["history"]}
                    recommendations_prompt = helper.dynamic_prompt_generation(travel_assist_template, input_variables)
                    
                    model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)
                    
                    #adding intermediate steps
                    Intermediate_Step = {
                        'Step 1': {'Tool Used': 'Gemini API', 'Response': list_of_places}, 
                        'Step 2': {'Tool Used': 'Google Maps-Places API', 'Response':inter_step}, 
                        'Step 3': {'Tool Used': 'Gemini API'}
                    }
                    
                    chat_data['history'].append({"role": "assistant", "message": model_response, "places_coordinates": places_coordinates, "timestamp": datetime.utcnow().isoformat()})

                elif intent_id in get_direction_api:

                    instruction = helper.transit_information(location=chat_request.location, checkin=chat_request.checkin, checkout=chat_request.checkout, query=chat_request.query)
                    input_variables = {'location': chat_request.location, 'checkin': chat_request.checkin, 'checkout': chat_request.checkout, 'query': chat_request.query, 'chat_history': chat_data["history"], 'directions': instruction}
                    recommendations_prompt = helper.dynamic_prompt_generation(travel_assist_template, input_variables)
                    model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)  
                    
                    Intermediate_Step = {
                        'Step 1': {'Tool Used': 'Gemini API'},
                        'Step 2':{'Tool Used': 'Google Maps-Directions API', 'Response': instruction},
                        'Step 3': {'Tool Used': 'Google Search'}
                    }                  

                    chat_data['history'].append({"role": "assistant", "message": model_response, "timestamp": datetime.utcnow().isoformat()})

                #out of content
                else:
                    input_variables = {'location': chat_request.location, 'checkin': chat_request.checkin, 'checkout': chat_request.checkout, 'query': chat_request.query, 'chat_history': chat_data["history"]}
                    recommendations_prompt = helper.dynamic_prompt_generation(travel_assist_template, input_variables)
                    model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)
                    Intermediate_Step = {
                        'Step 1': {'Tool Used': 'Google Search'},
                    }

                    chat_data['history'].append({"role": "assistant", "message": model_response, "timestamp": datetime.utcnow().isoformat()})

                # Update Firestore with the new chat history and unique enriched places
                doc_ref.update({"history": chat_data['history']})

                return {
                    "model_response": model_response,
                    "username": chat_request.username,
                    "places_coordinates": places_coordinates,
                    "session_id": session_id,
                    # 'Intermediate Step': Intermediate_Step
                }
            else:
                return RedirectResponse(url=f"/end_chat/{session_id}?username={username}", status_code=307)

            logging.debug(f"Continued chat 2: {session_id}")
        else:
            return {"message": "Session not found!"}

    else:
        # Start a new chat session
        logging.debug(f"Start chat 1: {session_id}")

        # Generate a unique session ID
        session_id = str(uuid.uuid4())

        # Initialize chat history with the first user query
        chat_history = [{"role": "user", "message": query, "timestamp": datetime.utcnow().isoformat()}]

        # Store the initial chat and session details in Firestore
        chat_data = {
            "username": username,
            "location": location,
            "checkin": checkin,
            "checkout": checkout,
            "user_prompt": query,
            "history": chat_history,
            "session_id": session_id
        }

        # Document reference using session ID as the document ID
        doc_ref = db.collection("users").document(username).collection("chats").document(session_id)
        doc_ref.set(chat_data)
        # print(f'----------------------------------------------------{query}-------------------------------')
        # Initial intent identification and recommendation generation
        travel_assist_template, intent_id = identify_intent(constants.model, query)
        logging.debug(f"----------------Inside Else: Identified intent: {intent_id}-------------")

        if travel_assist_template != 'bye':

            # Check if the identified_intent is in intent_places or intent_others
            if intent_id in places_api_intent:
                
                inter_step, place_url, list_of_places, places_coordinates = helper.places_nd_coordinates(chat_request.location, chat_request.checkin, chat_request.checkout, chat_request.query, chat_history if chat_history else None)
                places_response = f"\nPlace of interest based on User query:\n{place_url}"
                
                input_variables = {'location': chat_request.location, "query": chat_request.query , 'checkin': chat_request.checkin, 'checkout': chat_request.checkout, 'places': places_response, 'chat_history': chat_history if chat_history else None}
                recommendations_prompt = helper.dynamic_prompt_generation(templates.format_template, input_variables)
                
                model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)

                chat_data['history'].append({"role": "assistant", "message": model_response, "places_coordinates": places_coordinates, "timestamp": datetime.utcnow().isoformat()})

                #adding intermediate steps
                Intermediate_Step = {
                    'Step 1': {'Tool Used': 'Google Search', 'Response': list_of_places}, 
                    'Step 2': {'Tool Used': 'Google Maps', 'Response':inter_step}, 
                    'Step 3': {'Tool Used': 'Gemini API'}
                }


            elif intent_id in nearby_api_intent:
                
                # Fetch place details for user query
                inter_step, place_url, list_of_places, places_coordinates = helper.nearby_places(chat_request.location, chat_request.checkin, chat_request.checkout, chat_request.query, chat_history if chat_history else None)

                places_response = f"\nPlace of interest based on User query:\n{place_url}"

                input_variables = {'location': location, 'checkin': checkin, 'checkout': checkout, 'places': places_response, 'chat_history': chat_history if chat_history else None, "query": query}
                recommendations_prompt = helper.dynamic_prompt_generation(templates.format_template, input_variables)
                model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)

                # Add the assistant's response to the chat history
                chat_data['history'].append({"role": "assistant", "message": model_response, "places_coordinates": places_coordinates, "timestamp": datetime.utcnow().isoformat()})

                Intermediate_Step = {
                    'Step 1': {'Tool Used': 'Google Search', 'Response': list_of_places}, 
                    'Step 2': {'Tool Used': 'Google Maps-Search Nearby', 'Response':inter_step}, 
                    'Step 3': {'Tool Used': 'Gemini API'}
                }


                # Add the assistant's response to the chat history
                chat_data['history'].append({"role": "assistant", "message": model_response, "places_coordinates": places_coordinates, "timestamp": datetime.utcnow().isoformat()})

            elif intent_id in google_search:

                input_variables = {'location': location, 'checkin': checkin, 'checkout': checkout, 'query': query, 'chat_history': chat_history if chat_history else None}
                recommendations_prompt = helper.dynamic_prompt_generation(travel_assist_template, input_variables)
                model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)

                               
                Intermediate_Step = {
                        'Step 1': {'Tool Used': 'Google Search'},
                    }

                # Add the assistant's response to the chat history 
                chat_data['history'].append({"role": "assistant", "message": model_response, "timestamp": datetime.utcnow().isoformat()})

            elif intent_id in get_direction_api:
                instruction = helper.transit_information(location=chat_request.location, checkin=chat_request.checkin, checkout=chat_request.checkout, query=chat_request.query)
                input_variables = {'location': location, 'checkin': checkin, 'checkout': checkout, 'query': query, 'chat_history': chat_history if chat_history else None, 'directions': instruction}
                recommendations_prompt = helper.dynamic_prompt_generation(travel_assist_template, input_variables)
                model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)

                Intermediate_Step = {
                    'Step 1': {'Tool Used': 'Gemini API'},
                    'Step 2':{'Tool Used': 'Google Maps-Directions API', 'Response': instruction},
                    'Step 3': {'Tool Used': 'Google Search'}
                    }    

                chat_data['history'].append({"role": "assistant", "message": model_response, "timestamp": datetime.utcnow().isoformat()})



            elif intent_id in ratings_n_reviews:
                inter_step, place_url, list_of_places, places_coordinates = helper.get_url_rating(location, query, chat_history if chat_history else None)
                places_response = f"\nPlace of interest based on User query:\n{place_url}"
                
                input_variables = {'location': chat_request.location, 'checkin': chat_request.checkin, 'checkout': chat_request.checkout,'query': query, 'place': places_response, 'chat_history': chat_history if chat_history else None}
                recommendations_prompt = helper.dynamic_prompt_generation(travel_assist_template, input_variables)
                
                model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)

                #adding intermediate steps
                Intermediate_Step = {
                    'Step 1': {'Tool Used': 'Google Search', 'Response': list_of_places}, 
                    'Step 2': {'Tool Used': 'Google Maps', 'Response':inter_step}, 
                    'Step 3': {'Tool Used': 'Gemini API'}
                }  

                chat_data['history'].append({"role": "assistant", "message": model_response, "places_coordinates": places_coordinates, "timestamp": datetime.utcnow().isoformat()})


            #out of content
            else:
                input_variables = {'location': location, 'checkin': checkin, 'checkout': checkout, 'query': query, 'chat_history': chat_history if chat_history else None}
                recommendations_prompt = helper.dynamic_prompt_generation(travel_assist_template, input_variables)
                model_response = gen_func.generate_recommendations(constants.model, recommendations_prompt)
                
                Intermediate_Step = {
                        'Step 1': {'Tool Used': 'Google Search'},
                    }
                
                chat_data['history'].append({"role": "assistant", "message": model_response, "timestamp": datetime.utcnow().isoformat()})


            # Update Firestore with the new chat history and unique enriched places
            doc_ref.update({"history": chat_history})

            return {
                "model_response": model_response,
                "username": username,
                "places_coordinates": places_coordinates,
                "session_id": session_id,
                # 'Intermediate Step': Intermediate_Step
            }
            logging.debug(f"Start chat 2: {session_id}")
        else:
            return RedirectResponse(url=f"/end_chat/{session_id}?username={username}", status_code=307)

# End the session and retrieve the entire chat history
@app.post("/end_chat/{session_id}")
async def end_chat(session_id: str, username: str):
    try:
        # Retrieve the session chat history from Firestore
        doc_ref = db.collection("users").document(username).collection("chats").document(session_id)
        chat_data = doc_ref.get().to_dict()

        if chat_data:
            return {    
                "message": f"Thanks for chatting with us, {username}! 🙌 Your adventure is just beginning. We’ll be here when you’re ready for your next trip! ✈️🌟"
                    }
        else:
            # If no session data is found, raise a 404 HTTPException
            raise HTTPException(status_code=404, detail="Session not found!")
    
    except HTTPException as e:
        # Handle any unexpected exceptions
        raise HTTPException(status_code=500, detail=f"Something went wrong, {username}. Please try again later! 😓 Error: {str(e)}")

# API to fetch session data based on the username
@app.get("/get_sessions_by_username/{username}")
async def get_sessions_by_username(username: str):
    try:
        # Get all session documents for a particular username
        sessions_ref = db.collection("users").document(username).collection("chats")
        sessions = sessions_ref.stream()

        # Extract relevant session details (session_id, location, checkin, checkout)
        session_data = []
        for session in sessions:
            session_dict = session.to_dict()
            session_data.append({
                "session_id": session.id,
                "location": session_dict["location"],
                "checkin": session_dict["checkin"],
                "checkout": session_dict["checkout"]
            })

        # If no sessions found, return a message
        if not session_data:
            raise HTTPException(status_code=404, detail="No sessions found for this user")

        return {"sessions": session_data}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching sessions: {str(e)}")

# API to fetch chat history for a specific username and session ID
@app.get("/get_chat_history")
async def get_chat_history(username: str, session_id: str):
    try:
        # Retrieve the session chat history from Firestore
        doc_ref = db.collection("users").document(username).collection("chats").document(session_id)
        chat_data = doc_ref.get().to_dict()

        if chat_data:
            # Extract messages and include places_coordinates in each message if available
            messages = []
            for message in chat_data["history"]:

                message_data = {"role": message["role"], "message": message["message"]}
                
                # Include places_coordinates in the message if present
                if "places_coordinates" in message:
                    message_data["places_coordinates"] = message["places_coordinates"]

                messages.append(message_data)


            return {
                "session_id": session_id,
                "username": username,
                "location": chat_data["location"],
                "checkin": chat_data["checkin"],
                "checkout": chat_data["checkout"],
                "messages": messages  # Return messages with places_coordinates included where applicable
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found!")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Something went wrong, {username}. Please try again later! 😓 Error: {str(e)}")

@app.delete("/delete_chat_history/{username}")
async def delete_chat_history(username: str, session_id: Optional[str] = None):
    try:
        # If session_id is provided, delete that specific session's chat history
        if session_id:
            doc_ref = db.collection("users").document(username).collection("chats").document(session_id)
            doc_ref.delete()  # Delete the specific session
            return {"message": f"Chat history for session {session_id} has been deleted."}
        
        # If no session_id is provided, delete all sessions for the user
        else:
            sessions_ref = db.collection("users").document(username).collection("chats")
            sessions = sessions_ref.stream()

            # Iterate through all sessions and delete them
            for session in sessions:
                session.reference.delete()

            return {"message": f"All chat histories for user {username} have been deleted."}

    except Exception as e:
        logging.error(f"Error deleting chat history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting chat history for {username}: {str(e)}")