#!/usr/bin/env python3
"""
PTSD Trigger Detection with GStreamer and Cloud Video Intelligence
-----------------------------------------------------------------
This script monitors video streams for potential PTSD triggers (specifically
vehicles and traffic scenes) using GStreamer for processing and Google Cloud
Video Intelligence API for analysis.

Compatible with Meta Glasses or any video source.
"""

import os
import sys
import time
import argparse
import json
import tempfile
import threading
from datetime import datetime

# Import GStreamer
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject

# Import Google Cloud libraries
from google.cloud import videointelligence
from google.cloud import storage

# Initialize GStreamer
Gst.init(None)

# PTSD trigger objects to detect
TRIGGER_OBJECTS = ["car", "vehicle", "truck", "automobile", "traffic", "bus", "motorcycle"]
CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence level to consider a detection valid

class PTSDTriggerMonitor:
    """Monitor video streams for PTSD triggers using GStreamer and Cloud Video Intelligence"""
    
    def __init__(self, credentials_path=None, gcs_bucket=None, serial_port=None):
        """
        Initialize the PTSD trigger monitor.
        
        Args:
            credentials_path: Path to Google Cloud credentials JSON file
            gcs_bucket: GCS bucket for temporary video storage
            serial_port: Serial port for external recording device (if needed)
        """
        # Set credentials
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
            print(f"Using credentials from: {credentials_path}")
        
        # Initialize clients
        self.video_client = videointelligence.VideoIntelligenceServiceClient()
        self.storage_client = storage.Client() if gcs_bucket else None
        self.gcs_bucket = gcs_bucket
        
        # Create a temporary directory for storing video segments
        self.temp_dir = tempfile.mkdtemp()
        print(f"Using temporary directory: {self.temp_dir}")
        
        # GStreamer pipeline
        self.pipeline = None
        self.loop = None
        self.bus = None
        
        # Serial communication for recording device (optional)
        self.serial_port = serial_port
        self.serial_conn = None
        if serial_port:
            try:
                import serial
                self.serial_conn = serial.Serial(serial_port, 9600)
                print(f"Connected to recording device at {serial_port}")
            except Exception as e:
                print(f"Warning: Could not connect to recording device: {e}")
                print("Continuing without recording device connection")
        
        # Trigger tracking
        self.detected_triggers = []
    
    def build_pipeline(self, video_source, output_path, show_video=True):
        """
        Build a GStreamer pipeline for processing a video source.
        
        Args:
            video_source: URL or path to the video source
            output_path: Path to save the processed video segment
            show_video: Whether to display the video while processing
        
        Returns:
            Gst.Pipeline: The constructed pipeline
        """
        # Determine source type from URL
        if video_source.startswith("rtsp://"):
            # RTSP stream
            source_element = f'rtspsrc location="{video_source}" ! rtpjitterbuffer ! rtph264depay ! h264parse'
        elif video_source.startswith("rtmp://"):
            # RTMP stream
            source_element = f'rtmpsrc location="{video_source}" ! flvdemux ! h264parse'
        elif video_source.startswith("http://") and video_source.endswith(".m3u8"):
            # HLS stream
            source_element = f'souphttpsrc location="{video_source}" ! hlsdemux ! h264parse'
        elif os.path.exists(video_source):
            # Local file
            file_ext = os.path.splitext(video_source)[1].lower()
            if file_ext in ['.mp4', '.mov', '.avi', '.mkv']:
                source_element = f'filesrc location="{video_source}" ! decodebin'
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")
        else:
            # Try using as a device (like webcam)
            if sys.platform == 'darwin':  # macOS
                # Use specific macOS video source
                try:
                    # If it's a number, use it as device-index
                    device_index = int(video_source)
                    source_element = f'avfvideosrc device-index={device_index}'
                except ValueError:
                    # Otherwise just use default device
                    source_element = 'avfvideosrc'
            else:  # Linux/Windows
                source_element = f'v4l2src device={video_source}'
        
        # Build the complete pipeline with proper format conversion
        if show_video:
            # For macOS camera source, we need to ensure proper format conversion
            if 'avfvideosrc' in source_element:
                pipeline_str = (
                    f"{source_element} ! "
                    f"videoconvert ! video/x-raw,format=I420 ! "
                    f"tee name=t ! queue ! "
                    f"videoconvert ! x264enc tune=zerolatency bitrate=500 ! mp4mux ! "
                    f"filesink location={output_path} "
                    f"t. ! queue ! videoconvert ! autovideosink"
                )
            else:
                pipeline_str = (
                    f"{source_element} ! "
                    f"videoconvert ! "
                    f"tee name=t ! queue ! "
                    f"videoconvert ! x264enc tune=zerolatency bitrate=500 ! mp4mux ! "
                    f"filesink location={output_path} "
                    f"t. ! queue ! videoconvert ! autovideosink"
                )
        else:
            if 'avfvideosrc' in source_element:
                pipeline_str = (
                    f"{source_element} ! "
                    f"videoconvert ! video/x-raw,format=I420 ! "
                    f"videoconvert ! x264enc tune=zerolatency bitrate=500 ! mp4mux ! "
                    f"filesink location={output_path}"
                )
            else:
                pipeline_str = (
                    f"{source_element} ! videoconvert ! "
                    f"x264enc tune=zerolatency bitrate=500 ! mp4mux ! "
                    f"filesink location={output_path}"
                )
        
        print(f"Creating pipeline: {pipeline_str}")
        return Gst.parse_launch(pipeline_str)
    
    def process_stream(self, video_source, duration=10, show_video=True):
        """
        Process a video stream and save a segment for analysis.
        
        Args:
            video_source: URL or path to the video source
            duration: Duration in seconds to record
            show_video: Whether to display the video while processing
            
        Returns:
            str: Path to the recorded segment
        """
        # Create output file path
        timestamp = int(time.time())
        output_path = os.path.join(self.temp_dir, f"segment_{timestamp}.mp4")
        
        # For macOS camera capture, use a more specific approach
        if sys.platform == 'darwin' and not (
            video_source.startswith(('rtsp://', 'rtmp://', 'http://')) or 
            os.path.exists(video_source)
        ):
            try:
                # Try to convert to int if it's a numeric string
                try:
                    device_index = int(video_source)
                except ValueError:
                    device_index = 0  # Default to first camera
                    
                print(f"Using macOS camera capture with device index: {device_index}")
                pipeline_str = (
                    f"avfvideosrc device-index={device_index} ! "
                    f"videoconvert ! video/x-raw,format=I420 ! "
                    f"tee name=t ! queue ! "
                    f"videoconvert ! x264enc tune=zerolatency bitrate=500 ! mp4mux ! "
                    f"filesink location={output_path} "
                    f"t. ! queue ! videoconvert ! autovideosink"
                )
                
                if not show_video:
                    pipeline_str = (
                        f"avfvideosrc device-index={device_index} ! "
                        f"videoconvert ! video/x-raw,format=I420 ! "
                        f"videoconvert ! x264enc tune=zerolatency bitrate=500 ! mp4mux ! "
                        f"filesink location={output_path}"
                    )
                    
                self.pipeline = Gst.parse_launch(pipeline_str)
            except Exception as e:
                print(f"Error setting up macOS camera pipeline: {e}")
                print("Falling back to generic pipeline...")
                self.pipeline = self.build_pipeline(video_source, output_path, show_video)
        else:
            # Use the regular pipeline for other sources
            self.pipeline = self.build_pipeline(video_source, output_path, show_video)
        
        # Start pipeline
        self.loop = GLib.MainLoop()
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self.on_message)
        
        # Start playing
        result = self.pipeline.set_state(Gst.State.PLAYING)
        if result != Gst.StateChangeReturn.SUCCESS:
            print(f"Warning: Pipeline state change returned {result}, but continuing anyway")
        
        print(f"Started recording {duration} seconds of video to {output_path}")
        
        # Wait a moment to ensure the pipeline starts properly
        time.sleep(1)
        
        # Create a timer to stop the pipeline after duration
        timer_thread = threading.Timer(duration, self.stop_pipeline)
        timer_thread.daemon = True
        timer_thread.start()
        
        # Run the loop
        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            # Make sure to wait for pipeline to finish writing
            self.pipeline.set_state(Gst.State.NULL)
            time.sleep(1)  # Give time for file to be finalized
        
        # Check if the file was created and has content
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"Successfully recorded video ({file_size_mb:.2f} MB) to {output_path}")
            return output_path
        else:
            print("Warning: Recorded file is empty or doesn't exist")
            if os.path.exists(output_path):
                print(f"File exists but size is {os.path.getsize(output_path)} bytes")
            else:
                print(f"File doesn't exist at {output_path}")
            
            # Try to use the sample file as fallback
            sample_path = "/Users/wenxin/Downloads/sample.mp4"
            if os.path.exists(sample_path):
                print(f"Using sample file as fallback: {sample_path}")
                return sample_path
            else:
                raise ValueError("Failed to record video and no fallback available")
    
    def on_message(self, bus, message):
        """Handle GStreamer bus messages"""
        t = message.type
        
        if t == Gst.MessageType.EOS:
            print("End of stream")
            self.stop_pipeline()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}")
            self.stop_pipeline()
    
    def stop_pipeline(self):
        """Stop the GStreamer pipeline and main loop"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        
        if self.loop and self.loop.is_running():
            self.loop.quit()
    
    def upload_to_gcs(self, local_file_path):
        """
        Upload a file to Google Cloud Storage.
        
        Args:
            local_file_path: Path to the local file
            
        Returns:
            str: GCS URI of the uploaded file
        """
        if not self.storage_client or not self.gcs_bucket:
            raise ValueError("GCS bucket and credentials must be configured for upload")
        
        # Use bucket() instead of get_bucket() and don't try to create it
        try:
            bucket = self.storage_client.bucket(self.gcs_bucket)
            # Check if bucket exists - this will fail if it doesn't or if no access
            if not bucket.exists():
                print(f"Warning: Bucket {self.gcs_bucket} doesn't exist or you don't have access to it.")
                print("Trying to continue anyway...")
            
            # Create a blob name based on the file name
            blob_name = f"ptsd_analysis/{os.path.basename(local_file_path)}"
            blob = bucket.blob(blob_name)
            
            # Upload the file
            print(f"Uploading {local_file_path} to gs://{self.gcs_bucket}/{blob_name}")
            blob.upload_from_filename(local_file_path)
            
            # Return the GCS URI
            return f"gs://{self.gcs_bucket}/{blob_name}"
        except Exception as e:
            print(f"Error uploading to bucket {self.gcs_bucket}: {e}")
            print("Trying to analyze directly using file content instead...")
            return None  # Signal to analyze_video to use input_content approach
    
    def analyze_video(self, video_path):
        """
        Analyze a video file for PTSD triggers using Google Cloud Video Intelligence API.
        
        Args:
            video_path: Local path or GCS URI to the video
            
        Returns:
            dict: Analysis results with detected triggers
        """
        # Check if we need to upload the file
        if not video_path.startswith("gs://"):
            if self.gcs_bucket:
                try:
                    gcs_uri = self.upload_to_gcs(video_path)
                    if gcs_uri:  # If upload succeeded
                        video_path = gcs_uri
                    else:  # If upload failed but returned None, try direct analysis
                        return self.analyze_video_content_from_file(video_path)
                except Exception as e:
                    print(f"GCS upload failed: {e}. Trying direct analysis...")
                    return self.analyze_video_content_from_file(video_path)
            else:
                # No bucket provided, try direct analysis
                return self.analyze_video_content_from_file(video_path)
        
        print(f"Starting video analysis on {video_path}")
        
        # Configure the analysis request
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
        
        # Create the request
        request = videointelligence.AnnotateVideoRequest(
            input_uri=video_path,
            features=features,
            video_context=video_context
        )
        
        # Make the API call
        print("Submitting video for analysis. This might take a few minutes...")
        operation = self.video_client.annotate_video(request=request)
        
        # Wait for the operation to complete
        print("Waiting for analysis to complete...")
        result = operation.result(timeout=300)  # 5-minute timeout
        
        # Process the results
        return self._process_results(result)
    
    def analyze_video_content(self, input_content):
        """
        Analyze video content directly without GCS upload.
        
        Args:
            input_content: Binary content of the video file
            
        Returns:
            dict: Analysis results with detected triggers
        """
        # Configure the analysis request
        features = [
            videointelligence.Feature.LABEL_DETECTION,
            videointelligence.Feature.OBJECT_TRACKING,
        ]
        
        # Create the request
        request = videointelligence.AnnotateVideoRequest(
            input_content=input_content,
            features=features
        )
        
        # Make the API call
        print("Submitting video content for analysis. This might take a few minutes...")
        operation = self.video_client.annotate_video(request=request)
        
        # Wait for the operation to complete
        print("Waiting for analysis to complete...")
        result = operation.result(timeout=300)  # 5-minute timeout
        
        # Process the results
        return self._process_results(result)
    
    def analyze_video_content_from_file(self, video_path):
        """
        Read file and analyze its content directly.
        
        Args:
            video_path: Path to local video file
            
        Returns:
            dict: Analysis results
        """
        try:
            file_size = os.path.getsize(video_path)
            if file_size < 10 * 1024 * 1024:  # Less than 10MB
                print(f"Reading file content for direct analysis (size: {file_size/1024/1024:.2f} MB)")
                with open(video_path, "rb") as video_file:
                    input_content = video_file.read()
                return self.analyze_video_content(input_content)
            else:
                raise ValueError(f"File is too large ({file_size/1024/1024:.2f} MB) for direct analysis. Either create/access GCS bucket or use a smaller file.")
        except Exception as e:
            raise ValueError(f"Error reading file content: {e}")
    
    def _process_results(self, result):
        """
        Process video analysis results and extract PTSD triggers.
        
        Args:
            result: The raw API result
            
        Returns:
            dict: Detected triggers
        """
        # Dictionary to track triggers with timestamps
        triggers = []
        
        annotation_result = result.annotation_results[0]
        
        # Process object detections
        if hasattr(annotation_result, 'object_annotations'):
            for object_annotation in annotation_result.object_annotations:
                object_name = object_annotation.entity.description.lower()
                confidence = object_annotation.confidence
                
                # Check if the object is a trigger and meets confidence threshold
                if any(trigger in object_name for trigger in TRIGGER_OBJECTS) and confidence >= CONFIDENCE_THRESHOLD:
                    timestamps = []
                    
                    for track in object_annotation.frames:
                        timestamp = track.time_offset.seconds + track.time_offset.microseconds / 1000000
                        normalized_box = track.normalized_bounding_box
                        
                        box_info = {
                            'left': normalized_box.left,
                            'top': normalized_box.top,
                            'right': normalized_box.right,
                            'bottom': normalized_box.bottom
                        }
                        
                        timestamps.append({
                            'time': timestamp,
                            'box': box_info
                        })
                    
                    # Sort timestamps
                    timestamps.sort(key=lambda x: x['time'])
                    
                    # Create trigger event
                    trigger_event = {
                        'type': 'object',
                        'name': object_name,
                        'confidence': confidence,
                        'first_appearance': timestamps[0]['time'] if timestamps else 0,
                        'last_appearance': timestamps[-1]['time'] if timestamps else 0,
                        'occurrences': len(timestamps),
                        'description': f"Detected {object_name} (confidence: {confidence:.2f})"
                    }
                    
                    triggers.append(trigger_event)
                    self.send_record_command(trigger_event['description'])
                    print(f"TRIGGER: {trigger_event['description']}")
        
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
                            
                            # Create trigger event
                            trigger_event = {
                                'type': 'label',
                                'name': label_name,
                                'confidence': confidence,
                                'start_time': start_time,
                                'end_time': end_time,
                                'description': f"Detected {label_name} in scene (confidence: {confidence:.2f}) from {start_time:.2f}s to {end_time:.2f}s"
                            }
                            
                            triggers.append(trigger_event)
                            self.send_record_command(trigger_event['description'])
                            print(f"TRIGGER: {trigger_event['description']}")
        
        # Process speech transcriptions
        if hasattr(annotation_result, 'speech_transcriptions'):
            for transcription in annotation_result.speech_transcriptions:
                for alternative in transcription.alternatives:
                    transcript = alternative.transcript.lower()
                    
                    # Check if any trigger word is in the transcript
                    if any(trigger in transcript for trigger in TRIGGER_OBJECTS):
                        timestamp = 0
                        
                        # Find the timestamp from the words
                        if alternative.words:
                            # Get the timestamp of the first word in the transcript
                            first_word = alternative.words[0]
                            timestamp = first_word.start_time.seconds + first_word.start_time.microseconds / 1000000
                        
                        # Create trigger event
                        trigger_event = {
                            'type': 'speech',
                            'transcript': transcript,
                            'confidence': alternative.confidence,
                            'timestamp': timestamp,
                            'description': f"Speech mentioned trigger word in: '{transcript}'"
                        }
                        
                        triggers.append(trigger_event)
                        self.send_record_command(trigger_event['description'])
                        print(f"TRIGGER: {trigger_event['description']}")
        
        # Store the triggers
        self.detected_triggers = triggers
        
        # Prepare and return the full results
        results = {
            'triggers': triggers,
            'summary': {
                'total_triggers': len(triggers),
                'trigger_types': {}
            }
        }
        
        # Count trigger types
        for trigger in triggers:
            trigger_type = trigger['type']
            if trigger_type not in results['summary']['trigger_types']:
                results['summary']['trigger_types'][trigger_type] = 1
            else:
                results['summary']['trigger_types'][trigger_type] += 1
        
        return results
    
    def send_record_command(self, description):
        """
        Send a record command to the external device if connected.
        
        Args:
            description: Description of the trigger event
        """
        if self.serial_conn:
            try:
                command = f"RECORD;{description}\n"
                self.serial_conn.write(command.encode())
                print(f"Record command sent: {description}")
            except Exception as e:
                print(f"Error sending record command: {e}")
        else:
            print(f"Would send record command (no device connected): {description}")

def main():
    parser = argparse.ArgumentParser(description="PTSD Trigger Detection System")
    parser.add_argument("--source", required=True, help="Video source URL, file path, or device")
    parser.add_argument("--credentials", help="Path to Google Cloud credentials JSON file")
    parser.add_argument("--bucket", help="GCS bucket name for temporary storage")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds to record (for streams)")
    parser.add_argument("--output", help="Path to save analysis results JSON")
    parser.add_argument("--no-display", action="store_true", help="Don't display video while processing")
    parser.add_argument("--serial-port", help="Serial port for external recording device")
    
    args = parser.parse_args()
    
    # Create monitor
    monitor = PTSDTriggerMonitor(
        credentials_path=args.credentials,
        gcs_bucket=args.bucket,
        serial_port=args.serial_port
    )
    
    try:
        # Check if source is a GCS URI
        if args.source.startswith("gs://"):
            # If it's a GCS URI, analyze it directly
            print(f"Analyzing GCS URI directly: {args.source}")
            results = monitor.analyze_video(args.source)
        else:
            # Process the video source
            if args.source.startswith(("rtsp://", "rtmp://", "http://")) or not os.path.exists(args.source):
                # Source is a stream or device
                print(f"Processing stream or device: {args.source}")
                video_path = monitor.process_stream(
                    args.source,
                    duration=args.duration,
                    show_video=not args.no_display
                )
            else:
                # Source is a local file
                video_path = args.source
                print(f"Using local video file: {video_path}")
            
            # Analyze the video
            results = monitor.analyze_video(video_path)
        
        # Print a summary
        print("\nAnalysis Results:")
        print(f"Total Triggers Detected: {results['summary']['total_triggers']}")
        
        for trigger_type, count in results['summary']['trigger_types'].items():
            print(f"  {trigger_type.capitalize()} triggers: {count}")
        
        # Save results to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {args.output}")
        
        # Return trigger count for programmatic use
        return results['summary']['total_triggers']
        
    except KeyboardInterrupt:
        print("Operation cancelled by user")
        return -1
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return -1

if __name__ == "__main__":
    main()