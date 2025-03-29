# Travel AI

Travel AI is an application designed to enhance travel planning and provide personalized recommendations using AI. The application leverages Google Maps API, Google Cloud Firestore, and Vertex AI to offer features like itinerary planning, weather forecasts, transit information, and more.

## Features

- **Chat Interface:** Start a chat session to get personalized travel recommendations.
- **Intent Identification:** Identify user intent based on their query and provide relevant information.
- **Google Maps Integration:** Fetch place details, coordinates, and place IDs using Google Maps API.
- **Firestore Integration:** Store and retrieve chat history and session data using Google Cloud Firestore.
- **Vertex AI Integration:** Use Vertex AI for generating content and identifying user intent.

## Code Repository Structure

The repository is organized as follows:

```
travel_ai/
├── app.py                     # Main FastAPI application file
├── README.md                  # Project documentation
├── requirements.txt           # Python dependencies
├── app.yaml                   # Configuration file for Google App Engine deployment
├── .env                       # Environment variables (not included in the repo)
├── prompts/                   # Directory for prompt templates
│   └── prompt_templates.py    # Predefined templates for AI prompts
├── utils/                     # Utility functions and constants
│   ├── helper_functions.py    # Helper functions for API interactions and data processing
│   ├── model_generate_functions.py # Functions for AI model interactions
│   ├── constants.py           # Constants and configuration variables

```

## Setup

### Prerequisites

- Python 3.8 or higher
- Google Cloud account with access to Firestore and Vertex AI
- Google Maps API key

### Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/rakeshgowdasn/travel_ai.git
    cd travel_ai
    ```

2. Create a virtual environment and activate it:

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3. Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. Set up environment variables:

    Create a `.env` file in the root directory and add the following variables:

    ```plaintext
    GOOGLE_PROJECT_ID=your-google-project-id
    GOOGLE_MAPS_API_KEY=your-google-maps-api-key
    GOOGLE_GEMINI_API_KEY=your-google-gemini-api-key
    ```

5. Initialize Firestore:

    Ensure that your Google Cloud project has Firestore enabled and set up.

## Usage

### Running the Application Locally

1. Start the FastAPI server:

    ```bash
    uvicorn app:app --reload
    ```

2. Open your browser and navigate to `http://127.0.0.1:8000/docs` to access the Swagger UI and test the API endpoints.

### Deploying to Google App Engine

To deploy the application on **Google App Engine**, follow these steps:

1. **Create an `app.yaml` file** in the root directory of your project with the following content:

    ```yaml
    runtime: python39
    entrypoint: uvicorn app:app --host 0.0.0.0 --port $PORT

    env_variables:
      GOOGLE_PROJECT_ID: your-google-project-id
      GOOGLE_MAPS_API_KEY: your-google-maps-api-key
      GOOGLE_GEMINI_API_KEY: your-google-gemini-api-key

    handlers:
    - url: /.*
      script: auto
    ```

2. **Install the Google Cloud SDK** if you haven't already. Follow the instructions [here](https://cloud.google.com/sdk/docs/install).

3. **Authenticate with Google Cloud**:

    ```bash
    gcloud auth login
    ```

4. **Set your Google Cloud project**:

    ```bash
    gcloud config set project your-google-project-id
    ```

5. **Deploy the application**:

    ```bash
    gcloud app deploy
    ```

6. **Access the deployed application**:

    After deployment, Google App Engine will provide a URL where your application is hosted. Open the URL in your browser to access the application.

### API Endpoints

- **`GET /welcome`**: Greeting message to the user.
- **`POST /start_chat`**: Start a chat session with the AI assistant.
- **`POST /end_chat/{session_id}`**: End the chat session and retrieve the entire chat history.
- **`GET /get_sessions_by_username/{username}`**: Fetch session data based on the username.
- **`GET /get_chat_history`**: Fetch chat history for a specific username and session ID.
- **`DELETE /delete_chat_history/{username}`**: Delete chat history for a specific username or session.

### Example Requests

#### Start a Chat Session

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/start_chat' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "john_doe",
    "location": "Paris",
    "checkin": "2025-02-10",
    "checkout": "2025-02-15",
    "query": "What are the best places to visit?"
  }'
```

#### End a Chat Session

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/end_chat/{session_id}?username=john_doe' \
  -H 'accept: application/json'
```

#### Get Sessions by Username

```bash
curl -X 'GET' \
  'http://127.0.0.1:8000/get_sessions_by_username/john_doe' \
  -H 'accept: application/json'
```

#### Get Chat History

```bash
curl -X 'GET' \
  'http://127.0.0.1:8000/get_chat_history?username=john_doe&session_id={session_id}' \
  -H 'accept: application/json'
```

#### Delete Chat History

```bash
curl -X 'DELETE' \
  'http://127.0.0.1:8000/delete_chat_history/john_doe' \
  -H 'accept: application/json'
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
