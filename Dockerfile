FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-rtsp \
    gstreamer1.0-libav \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py /app/
COPY run.sh /app/

# Make the run script executable
RUN chmod +x /app/run.sh

# Create a volume for data persistence
VOLUME /app/data

# Default port for Gradio
EXPOSE 7860

# Define environment variable for the Google Cloud credentials
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/data/credentials.json"

# Run the application
ENTRYPOINT ["/app/run.sh"]