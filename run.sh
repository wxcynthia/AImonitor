#!/bin/bash

# Check if Google Cloud credentials exist
if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "Warning: Google Cloud credentials file not found at $GOOGLE_APPLICATION_CREDENTIALS"
    echo "The application will start, but video analysis functionality will be limited."
fi

# Create necessary directories
mkdir -p /app/data

# Determine which application to run
if [ "$1" == "video" ]; then
    echo "Starting Video Streaming Monitor..."
    python video_monitor.py "$@"
elif [ "$1" == "patient" ]; then
    echo "Starting Patient Monitoring System..."
    python patient_monitor.py "$@"
elif [ "$1" == "shell" ]; then
    echo "Starting shell..."
    /bin/bash
else
    echo "Starting complete monitoring system..."
    # Start both applications with Gradio
    python patient_monitor.py
fi