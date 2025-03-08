#!/usr/bin/env python3
"""
PTSD Trigger Detection System for Meta Glasses
---------------------------------------------
This script analyzes video streams from Meta glasses to detect triggers (specifically cars)
for PTSD patients. When triggers are detected, it sends a "record" signal.

Requirements:
- Google Cloud Video Intelligence API
- Google Cloud credentials configured
- PySerial for communicating with external recording device
"""

import os
import json
import time
import argparse
import serial
from google.cloud import videointelligence
from google.cloud import storage

# Configure your trigger objects here
TRIGGER_OBJECTS = ["car", "vehicle", "truck", "automobile", "traffic"]
CONFIDENCE_THRESHOLD = 0.7

class PTSDTriggerDetector:
    def __init__(self, input_video_path, serial_port=None, baud_rate=9600, gcs_bucket=None):
        """
        Initialize the PTSD trigger detector.
        
        Args:
            input_video_path: Path to video file (local or GCS URI)
            serial_port: Serial port for external recording device
            baud_rate: Baud rate for serial communication
            gcs_bucket: GCS bucket for storing video if needed
        """
        self.input_video_path = input_video_path
        self.gcs_uri = None
        self.gcs_bucket = gcs_bucket
        
        # Initialize Video Intelligence client
        self.video_client = videointelligence.VideoIntelligenceServiceClient()
        
        # Initialize serial communication for the recording device
        self.serial_conn = None
        if serial_port:
            try:
                self.serial_conn = serial.Serial(serial_port, baud_rate)
                print(f"Connected to recording device at {serial_port}")
            except Exception as e:
                print(f"Warning: Could not connect to recording device: {e}")
        
        # Check if the input is a local file and upload to GCS if needed
        if not input_video_path.startswith('gs://'):
            if gcs_bucket:
                self.gcs_uri = self._upload_to_gcs(input_video_path, gcs_bucket)
            else:
                raise ValueError("For local files, you must provide a GCS bucket for processing")
        else:
            self.gcs_uri = input_video_path

    def _upload_to_gcs(self, local_file_path, bucket_name):
        """Upload a local file to Google Cloud Storage."""
        filename = os.path.basename(local_file_path)
        destination_blob_name = f"ptsd_analysis/{int(time.time())}_{filename}"
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        
        print(f"Uploading {local_file_path} to GCS bucket {bucket_name}...")
        blob.upload_from_filename(local_file_path)
        
        gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
        print(f"File uploaded to {gcs_uri}")
        return gcs_uri
    
    def send_record_command(self, description):
        """Send a record command to the external device."""
        if self.serial_conn:
            command = f"RECORD;{description}\n"
            self.serial_conn.write(command.encode())
            print(f"Record command sent: {description}")
        else:
            print(f"Would send record command: {description}")
    
    def analyze_video(self):
        """Analyze video for objects and speech transcription."""
        features = [
            videointelligence.Feature.LABEL_DETECTION,
            videointelligence.Feature.OBJECT_TRACKING,
            videointelligence.Feature.SPEECH_TRANSCRIPTION
        ]
        
        # Configure speech transcription
        speech_config = videointelligence.SpeechTranscriptionConfig(
            language_code="en-US",
            enable_automatic_punctuation=True,
            filter_profanity=True
        )
        
        # Configure video context
        video_context = videointelligence.VideoContext(
            speech_transcription_config=speech_config
        )
        
        print(f"Starting video analysis on {self.gcs_uri}...")
        operation = self.video_client.annotate_video(
            request={
                "features": features,
                "input_uri": self.gcs_uri,
                "video_context": video_context,
            }
        )
        
        print("Video analysis in progress...")
        result = operation.result(timeout=600)  # Timeout after 10 minutes
        
        # Process the results
        print("Analysis complete. Processing results...")
        self._process_results(result)
        
        return result
    
    def _process_results(self, result):
        """Process video analysis results."""
        annotation_result = result.annotation_results[0]
        
        # Dictionary to track triggers with timestamps
        triggers = {}
        
        # Process object detections
        if hasattr(annotation_result, 'object_annotations'):
            for object_annotation in annotation_result.object_annotations:
                object_name = object_annotation.entity.description.lower()
                confidence = object_annotation.confidence
                
                # Check if the object is a trigger and meets confidence threshold
                if any(trigger in object_name for trigger in TRIGGER_OBJECTS) and confidence >= CONFIDENCE_THRESHOLD:
                    for track in object_annotation.frames:
                        timestamp = track.time_offset.seconds + track.time_offset.microseconds / 1000000
                        normalized_box = track.normalized_bounding_box
                        
                        box_info = {
                            'left': normalized_box.left,
                            'top': normalized_box.top,
                            'right': normalized_box.right,
                            'bottom': normalized_box.bottom
                        }
                        
                        description = f"Detected {object_name} (confidence: {confidence:.2f}) at timestamp {timestamp:.2f}s"
                        
                        if timestamp not in triggers:
                            triggers[timestamp] = []
                        
                        triggers[timestamp].append({
                            'type': 'object',
                            'name': object_name,
                            'confidence': confidence,
                            'box': box_info,
                            'description': description
                        })
        
        # Process label detections
        if hasattr(annotation_result, 'segment_label_annotations'):
            for label in annotation_result.segment_label_annotations:
                label_name = label.entity.description.lower()
                
                # Check if the label is a trigger
                if any(trigger in label_name for trigger in TRIGGER_OBJECTS):
                    for segment in label.segments:
                        confidence = segment.confidence
                        
                        if confidence >= CONFIDENCE_THRESHOLD:
                            start_time = segment.segment.start_time_offset.seconds + segment.segment.start_time_offset.microseconds / 1000000
                            end_time = segment.segment.end_time_offset.seconds + segment.segment.end_time_offset.microseconds / 1000000
                            
                            # Use the middle of the segment as the timestamp
                            timestamp = (start_time + end_time) / 2
                            
                            description = f"Detected {label_name} in scene (confidence: {confidence:.2f}) from {start_time:.2f}s to {end_time:.2f}s"
                            
                            if timestamp not in triggers:
                                triggers[timestamp] = []
                            
                            triggers[timestamp].append({
                                'type': 'label',
                                'name': label_name,
                                'confidence': confidence,
                                'start_time': start_time,
                                'end_time': end_time,
                                'description': description
                            })
        
        # Process speech transcriptions
        if hasattr(annotation_result, 'speech_transcriptions'):
            for transcription in annotation_result.speech_transcriptions:
                for alternative in transcription.alternatives:
                    transcript = alternative.transcript.lower()
                    
                    # Check if any trigger word is in the transcript
                    if any(trigger in transcript for trigger in TRIGGER_OBJECTS):
                        # Find the timestamp from the words
                        if alternative.words:
                            # Get the timestamp of the first word in the transcript
                            first_word = alternative.words[0]
                            timestamp = first_word.start_time.seconds + first_word.start_time.microseconds / 1000000
                            
                            description = f"Speech mentioned trigger word in: '{transcript}'"
                            
                            if timestamp not in triggers:
                                triggers[timestamp] = []
                            
                            triggers[timestamp].append({
                                'type': 'speech',
                                'transcript': transcript,
                                'confidence': alternative.confidence,
                                'description': description
                            })
        
        # Process and send record commands for all triggers
        if triggers:
            # Sort triggers by timestamp
            sorted_timestamps = sorted(triggers.keys())
            
            print(f"Found {len(sorted_timestamps)} trigger events")
            
            for timestamp in sorted_timestamps:
                trigger_events = triggers[timestamp]
                
                for event in trigger_events:
                    print(f"RECORD: {event['description']}")
                    self.send_record_command(event['description'])
                    
                    # Add a small delay to ensure separate recording events
                    time.sleep(0.5)
        else:
            print("No trigger events detected in the video")

def main():
    parser = argparse.ArgumentParser(description='PTSD Trigger Detection System')
    parser.add_argument('--video', required=True, help='Path to video file or GCS URI')
    parser.add_argument('--serial-port', help='Serial port for recording device (e.g., /dev/ttyUSB0)')
    parser.add_argument('--baud-rate', type=int, default=9600, help='Baud rate for serial communication')
    parser.add_argument('--gcs-bucket', help='GCS bucket name for uploading local video files')
    
    args = parser.parse_args()
    
    # Check if GOOGLE_APPLICATION_CREDENTIALS is set
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ:
        print("Warning: GOOGLE_APPLICATION_CREDENTIALS environment variable is not set.")
        print("Please set it to your Google Cloud service account key JSON file.")
    
    detector = PTSDTriggerDetector(
        input_video_path=args.video,
        serial_port=args.serial_port,
        baud_rate=args.baud_rate,
        gcs_bucket=args.gcs_bucket
    )
    
    detector.analyze_video()

if __name__ == "__main__":
    main()