# import pandas as pd
from google.cloud import storage
# import langchain
# import langchain_community
import requests
import vertexai
import vertexai.preview.generative_models as generative_models
from vertexai.generative_models import GenerativeModel, Part, FinishReason
from vertexai.generative_models import (FunctionDeclaration, Tool, grounding)
import google.generativeai as genai
# from langchain_core.messages import HumanMessage
# from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAI
# from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
# from typing import List
from google.api_core.client_options import ClientOptions
# from google.cloud import discoveryengine_v1 as discoveryengine
import numpy as np

# User defined
import utils.constants as constants
import utils.helper_functions as helper
import prompts.prompt_templates as templates
# import utils.loggers as logger
# logg = logger.get_logger(constants.log_filename)

#Grounding tool setup
tool = Tool.from_google_search_retrieval(grounding.GoogleSearchRetrieval())

#safety setting
safety_settings = {
    generative_models.HarmCategory.HARM_CATEGORY_HATE_SPEECH:
    generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    generative_models.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT:
    generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    generative_models.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT:
    generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    generative_models.HarmCategory.HARM_CATEGORY_HARASSMENT:
    generative_models.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}


def generate_recommendations(model, prompt):
    """
    In this function model generates recommendations based on point of interest.
    Args:
    model:"gemini-1.5-flash-001"
    """
    try:
        vertexai.init(project="pitchhubsmes", location="us-central1")
        model = GenerativeModel(
            model,
            system_instruction=[
                """You are a helpful travel assistant in providing recommendations
                based on point of interest."""
            ],
        )
        contents = [prompt]
        response = model.generate_content(
            contents,
            tools= [tool],
            generation_config=constants.generation_config,
            safety_settings=safety_settings,
        )

        # Adding citation to response
        if response.candidates[0].grounding_metadata.grounding_chunks:
            citation = 'Source: '
            for i in response.candidates[0].grounding_metadata.grounding_chunks:
                # Format the citation as a markdown hyperlink: [title](URL)
                citation += f'[{i.web.title}]({i.web.uri})'  # Note the markdown format here
            return (f'{response.text} \n \n {citation}')
        else:
            return response.text

    except Exception as e:
        # logg.error("""Error while model generating travel
        # recommendations:""", exc_info=True)
        return f"Error while model generating travel recommendations: {e}"


def llm(model, prompt):
    """
    In this function model generates recommendations based on point of interest.
    Args:
    model:"gemini-1.5-flash-001"
    """
    try:
        vertexai.init(project="pitchhubsmes", location="us-central1")
        model = GenerativeModel(
            model,
            system_instruction=[
                """You are a helpful travel assistant in providing recommendations
                based on point of interest."""
            ],
        )
        contents = [prompt]
        response = model.generate_content(
            contents,
            tools= [tool],
            generation_config=constants.generation_config,
            safety_settings=safety_settings,
        )
        return response.text

    except Exception as e:
        # logg.error("""Error while model generating travel
        # recommendations:""", exc_info=True)
        return f"Error while model generating travel recommendations: {e}"
