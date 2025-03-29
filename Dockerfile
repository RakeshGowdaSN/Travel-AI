# Use the official Python image from Docker Hub as a base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /pitch-hub

# Copy the requirements.txt into the container at /app
COPY requirements.txt .

# Install the dependencies in the requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
# COPY . /pitch-hub/
COPY . .

# Expose the port that FastAPI will run on (default 8000)
EXPOSE 8080

# Set the environment variable for FastAPI
# ENV PYTHONUNBUFFERED=1

# Run the FastAPI app using Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]

# Start the FastAPI app with Gunicorn
# CMD ["gunicorn", "-b", ":8080", "app:app"]