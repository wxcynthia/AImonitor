#!/usr/bin/env python3
"""
Video Streaming Monitor
----------------------
This script provides a bridge between video streams and Google Cloud Video Intelligence API.
It can process:
1. Local video files
2. RTSP streams (e.g., IP cameras)
3. Webcam feeds
4. Video files uploaded through the Gradio interface

The script provides real-time analysis of video content to detect potential PTSD triggers.
"""

import os
import sys
import time
import json
import tempfile
import subprocess
import threading
import cv2
import numpy as np
import gradio as gr
from google.cloud import videointelligence
from google.cloud import storage
from datetime import datetime

# Configuration
CONFIDENCE_THRESHOLD = 0.60  # Minimum confidence score for detections
TRIGGER_OBJECTS = ["car", "vehicle", "truck", "automobile", "traffic", "bus", "motorcycle"]
GOOGLE_CREDENTIALS_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
GCS_BUCKET = "your-temp-video-bucket"  # Change to your bucket

class VideoAnalyzer:
    """Handles video analysis using Google Cloud Video Intelligence API"""
    
    def __init__(self, credentials_path=None):
        """Initialize the analyzer with Google Cloud credentials"""
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            
        # Initialize Video Intelligence client
        self.video_client = videointelligence.VideoIntelligenceServiceClient()
        self.storage_client = storage.Client()
        self.detections = []
        self.processing = False
        
    def ensure_bucket_exists(self, bucket_name):
        """Ensure the GCS bucket exists, create if it doesn't"""
        try:
            return self.storage_client.get_bucket(bucket_name)
        except Exception:
            print(f"Creating bucket {bucket_name}...")
            return self.storage_client.create_bucket(bucket_name)
    
    def upload_to_gcs(self, file_path, bucket_name):
        """Upload a file to Google Cloud Storage"""
        try:
            bucket = self.ensure_bucket_exists(bucket_name)
            blob_name = f"stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(file_path)}"
            blob = bucket.blob(blob_name)
            blob.upload_from_filename(file_path)
            return f"gs://{bucket_name}/{blob_name}"
        except Exception as e:
            print(f"Error uploading to GCS: {e}")
            return None
    
    def analyze_file(self, file_path):
        """Analyze a video file for PTSD triggers"""
        if self.processing:
            return "Analysis already in progress"
        
        self.processing = True
        self.detections = []
        
        try:
            # For files larger than 10MB, upload to GCS
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            if file_size > 10:
                print(f"File is {file_size:.2f}MB, uploading to GCS...")
                gcs_uri = self.upload_to_gcs(file_path, GCS_BUCKET)
                if not gcs_uri:
                    raise Exception("Failed to upload to GCS")
                input_uri = gcs_uri
            else:
                # For smaller files, read into memory
                with open(file_path, "rb") as f:
                    input_content = f.read()
                input_uri = None
            
            # Configure the request
            features = [
                videointelligence.Feature.LABEL_DETECTION,
                videointelligence.Feature.OBJECT_TRACKING
            ]
            
            # Set video context
            video_context = videointelligence.VideoContext(
                label_detection_config=videointelligence.LabelDetectionConfig(
                    frame_confidence_threshold=CONFIDENCE_THRESHOLD
                )
            )
            
            # Make the request
            if input_uri:
                operation = self.video_client.annotate_video(
                    request={"features": features, "input_uri": input_uri, "video_context": video_context}
                )
            else:
                operation = self.video_client.annotate_video(
                    request={"features": features, "input_content": input_content, "video_context": video_context}
                )
            
            print("Processing video... This may take a few minutes.")
            result = operation.result(timeout=300)  # 5-minute timeout
            
            # Process results
            self.detections = self._process_results(result)
            print(f"Analysis complete. Found {len(self.detections)} potential triggers.")
            
            return self.detections
            
        except Exception as e:
            print(f"Error analyzing video: {e}")
            import traceback
            traceback.print_exc()
            return [{"error": str(e)}]
        finally:
            self.processing = False
    
    def _process_results(self, result):
        """Process video analysis results to find triggers"""
        detections = []
        
        # Process the first annotation result
        annotation_result = result.annotation_results[0]
        
        # Check segment label annotations
        if hasattr(annotation_result, 'segment_label_annotations'):
            for label in annotation_result.segment_label_annotations:
                label_name = label.entity.description.lower()
                
                # Check if this is a trigger label
                if any(trigger in label_name for trigger in TRIGGER_OBJECTS):
                    for segment in label.segments:
                        confidence = segment.confidence
                        if confidence >= CONFIDENCE_THRESHOLD:
                            start_time = self._format_time_offset(segment.segment.start_time_offset)
                            end_time = self._format_time_offset(segment.segment.end_time_offset)
                            
                            detections.append({
                                "type": "segment",
                                "label": label_name,
                                "confidence": float(confidence),
                                "start_time": start_time,
                                "end_time": end_time,
                                "description": f"Segment: {label_name} (confidence: {confidence:.2f})"
                            })
        
        # Check object annotations
        if hasattr(annotation_result, 'object_annotations'):
            for object_annotation in annotation_result.object_annotations:
                object_name = object_annotation.entity.description.lower()
                
                # Check if this is a trigger object
                if any(trigger in object_name for trigger in TRIGGER_OBJECTS):
                    confidence = object_annotation.confidence
                    if confidence >= CONFIDENCE_THRESHOLD:
                        # Get timestamp from the first frame
                        if object_annotation.frames:
                            timestamp = self._format_time_offset(object_annotation.frames[0].time_offset)
                            
                            detections.append({
                                "type": "object",
                                "label": object_name,
                                "confidence": float(confidence),
                                "timestamp": timestamp,
                                "description": f"Object: {object_name} (confidence: {confidence:.2f})"
                            })
        
        return detections
    
    def _format_time_offset(self, time_offset):
        """Format a time offset from the API into a readable string"""
        seconds = time_offset.seconds + time_offset.microseconds / 1000000
        return f"{seconds:.2f}s"

class StreamProcessor:
    """Handles video stream capture and processing"""
    
    def __init__(self, analyzer):
        """Initialize the stream processor"""
        self.analyzer = analyzer
        self.cap = None
        self.is_streaming = False
        self.temp_dir = tempfile.mkdtemp()
        self.stream_thread = None
        self.current_frame = None
        self.recording = False
        self.record_file = None
        self.record_writer = None
        
    def start_webcam(self, device_id=0):
        """Start capturing from webcam"""
        if self.is_streaming:
            self.stop_stream()
        
        self.cap = cv2.VideoCapture(device_id)
        if not self.cap.isOpened():
            return "Failed to open webcam"
        
        self.is_streaming = True
        self.stream_thread = threading.Thread(target=self._process_stream)
        self.stream_thread.daemon = True
        self.stream_thread.start()
        
        return "Webcam started"
    
    def start_rtsp(self, rtsp_url):
        """Start capturing from RTSP stream"""
        if self.is_streaming:
            self.stop_stream()
        
        self.cap = cv2.VideoCapture(rtsp_url)
        if not self.cap.isOpened():
            return "Failed to open RTSP stream"
        
        self.is_streaming = True
        self.stream_thread = threading.Thread(target=self._process_stream)
        self.stream_thread.daemon = True
        self.stream_thread.start()
        
        return "RTSP stream started"
    
    def stop_stream(self):
        """Stop the current stream"""
        self.is_streaming = False
        if self.stream_thread:
            self.stream_thread.join(timeout=1.0)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.stop_recording()
        return "Stream stopped"
    
    def start_recording(self):
        """Start recording the current stream"""
        if not self.is_streaming or self.recording:
            return "Cannot start recording"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.record_file = os.path.join(self.temp_dir, f"recording_{timestamp}.mp4")
        
        if self.cap and self.current_frame is not None:
            height, width = self.current_frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
            self.record_writer = cv2.VideoWriter(self.record_file, fourcc, fps, (width, height))
            self.recording = True
            return f"Recording started: {self.record_file}"
        
        return "Cannot start recording: No valid stream"
    
    def stop_recording(self):
        """Stop the current recording and analyze the video"""
        if not self.recording:
            return "Not recording"
        
        self.recording = False
        if self.record_writer:
            self.record_writer.release()
            self.record_writer = None
        
        return f"Recording stopped: {self.record_file}"
    
    def analyze_current_recording(self):
        """Analyze the current recording file"""
        if not self.record_file or not os.path.exists(self.record_file):
            return "No recording available to analyze"
        
        return self.analyzer.analyze_file(self.record_file)
    
    def get_current_frame(self):
        """Get the current frame from the stream"""
        if self.current_frame is not None:
            return self.current_frame
        return np.zeros((480, 640, 3), dtype=np.uint8)
    
    def _process_stream(self):
        """Process frames from the video stream"""
        while self.is_streaming and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to read frame")
                break
            
            self.current_frame = frame
            
            # Save frame if recording
            if self.recording and self.record_writer:
                self.record_writer.write(frame)
            
            time.sleep(0.01)  # Small delay to prevent high CPU usage

def create_gradio_interface():
    """Create Gradio interface for the video analyzer"""
    analyzer = VideoAnalyzer(credentials_path=GOOGLE_CREDENTIALS_PATH)
    processor = StreamProcessor(analyzer)
    
    with gr.Blocks(title="PTSD Trigger Video Analyzer") as app:
        gr.Markdown("# PTSD Trigger Video Analyzer")
        gr.Markdown("Upload a video file or connect to a stream to analyze for potential PTSD triggers")
        
        with gr.Tab("Video File Analysis"):
            with gr.Row():
                file_input = gr.File(label="Upload Video File")
                analyze_btn = gr.Button("Analyze Video")
            
            with gr.Row():
                results_output = gr.JSON(label="Analysis Results")
        
        with gr.Tab("Live Stream Analysis"):
            with gr.Row():
                with gr.Column():
                    webcam_btn = gr.Button("Start Webcam")
                    rtsp_input = gr.Textbox(label="RTSP URL", placeholder="rtsp://username:password@192.168.1.100:554/stream")
                    rtsp_btn = gr.Button("Connect to RTSP")
                    stop_btn = gr.Button("Stop Stream")
                    
                    with gr.Row():
                        record_btn = gr.Button("Start Recording")
                        stop_record_btn = gr.Button("Stop Recording")
                        analyze_record_btn = gr.Button("Analyze Recording")
                    
                stream_output = gr.Image(label="Live Stream")
            
            stream_status = gr.Textbox(label="Stream Status")
            stream_results = gr.JSON(label="Stream Analysis Results")
        
        # Define update function for the video stream
        def update_stream():
            return processor.get_current_frame()
        
        # Set up event handlers
        analyze_btn.click(
            fn=lambda f: analyzer.analyze_file(f.name) if f else "No file selected",
            inputs=file_input,
            outputs=results_output
        )
        
        webcam_btn.click(
            fn=processor.start_webcam,
            inputs=[],
            outputs=stream_status
        )
        
        rtsp_btn.click(
            fn=processor.start_rtsp,
            inputs=rtsp_input,
            outputs=stream_status
        )
        
        stop_btn.click(
            fn=processor.stop_stream,
            inputs=[],
            outputs=stream_status
        )
        
        record_btn.click(
            fn=processor.start_recording,
            inputs=[],
            outputs=stream_status
        )
        
        stop_record_btn.click(
            fn=processor.stop_recording,
            inputs=[],
            outputs=stream_status
        )
        
        analyze_record_btn.click(
            fn=processor.analyze_current_recording,
            inputs=[],
            outputs=stream_results
        )
        
        # Update the stream display
        app.load(lambda: None, None, None)
        stream_output.update(update_stream, every=0.1)
    
    return app

if __name__ == "__main__":
    # Check if credentials are set
    if not GOOGLE_CREDENTIALS_PATH:
        print("Warning: GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        print("Please set it to your Google Cloud service account key JSON file.")
    
    # Create and launch the Gradio interface
    app = create_gradio_interface()
    app.launch(share=True)