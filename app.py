#!/usr/bin/env python3
"""
Main PTSD Monitoring Application
-------------------------------
This script integrates the Video Analysis and Cursor Recording components
to create a complete system for detecting PTSD triggers from Meta glasses video
and recording brain wave data when triggers are detected.
"""

import os
import sys
import argparse
import json
import time
from datetime import datetime
import threading
import queue

# Import our custom modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from trigger import PTSDTriggerDetector
from integration import CursorRecorder

class PTSDMonitoringApp:
    def __init__(self, 
                 video_path, 
                 cursor_path='/Users/wenxin/Desktop/AI/sensor',
                 output_dir=None,
                 gcs_bucket=None,
                 trigger_objects=None,
                 confidence_threshold=0.7,
                 recording_duration=5):
        """
        Initialize the PTSD monitoring application.
        
        Args:
            video_path: Path to the video file or GCS URI
            cursor_path: Path to the cursor device
            output_dir: Directory to save all output files
            gcs_bucket: GCS bucket for uploading/processing video
            trigger_objects: List of objects to detect as triggers
            confidence_threshold: Minimum confidence for trigger detection
            recording_duration: Duration in seconds for each brain wave recording
        """
        self.video_path = video_path
        self.cursor_path = cursor_path
        
        # Setup output directory
        self.output_dir = output_dir or os.path.join(os.getcwd(), "ptsd_monitoring_output")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Session information
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(self.output_dir, f"session_{self.session_id}")
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)
        
        # Trigger settings
        self.trigger_objects = trigger_objects or ["car", "vehicle", "truck", "automobile", "traffic"]
        self.confidence_threshold = confidence_threshold
        self.recording_duration = recording_duration
        
        # Create subdirectories
        self.recordings_dir = os.path.join(self.session_dir, "recordings")
        self.analysis_dir = os.path.join(self.session_dir, "analysis")
        os.makedirs(self.recordings_dir, exist_ok=True)
        os.makedirs(self.analysis_dir, exist_ok=True)
        
        # Initialize components
        self.detector = None
        self.recorder = None
        self.gcs_bucket = gcs_bucket
        
        # Queue for communication between detector and recorder
        self.trigger_queue = queue.Queue()
        
        print(f"PTSD Monitoring Session {self.session_id} initialized")
        print(f"Output directory: {self.session_dir}")
        print(f"Monitoring for triggers: {', '.join(self.trigger_objects)}")
        
    def initialize_components(self):
        """Initialize the detector and recorder components."""
        try:
            # Initialize the cursor recorder
            self.recorder = CursorRecorder(
                cursor_path=self.cursor_path,
                output_dir=self.recordings_dir
            )
            
            # Initialize the PTSD trigger detector with a callback function
            self.detector = PTSDTriggerDetector(
                input_video_path=self.video_path,
                gcs_bucket=self.gcs_bucket
            )
            
            # Override the send_record_command method to use our queue
            original_send_record = self.detector.send_record_command
            
            def new_send_record(description):
                # Call the original method for logging
                original_send_record(description)
                # Add to our queue for the recorder thread
                self.trigger_queue.put(description)
            
            self.detector.send_record_command = new_send_record
            
            return True
            
        except Exception as e:
            print(f"Error initializing components: {e}")
            return False
    
    def recorder_thread_func(self):
        """Thread function to process recording requests from the queue."""
        while True:
            try:
                # Get trigger description from queue (blocks until one is available)
                description = self.trigger_queue.get()
                
                # Special value to signal thread termination
                if description == "STOP":
                    break
                
                # Record brain wave data
                self.recorder.record(
                    duration=self.recording_duration,
                    description=description
                )
                
                # Mark task as done
                self.trigger_queue.task_done()
                
            except Exception as e:
                print(f"Error in recorder thread: {e}")
    
    def run(self):
        """Run the monitoring application."""
        if not self.initialize_components():
            print("Failed to initialize components. Exiting.")
            return False
        
        try:
            # Start the recorder thread
            recorder_thread = threading.Thread(target=self.recorder_thread_func)
            recorder_thread.daemon = True
            recorder_thread.start()
            
            print("Starting video analysis...")
            # Run the video analysis
            results = self.detector.analyze_video()
            
            # Save analysis results
            results_path = os.path.join(self.analysis_dir, f"analysis_results_{self.session_id}.json")
            
            # Wait for all recording tasks to complete
            self.trigger_queue.join()
            
            # Signal the recorder thread to stop
            self.trigger_queue.put("STOP")
            recorder_thread.join()
            
            print(f"Session {self.session_id} completed successfully")
            print(f"Results saved to {self.session_dir}")
            
            return True
            
        except KeyboardInterrupt:
            print("\nMonitoring interrupted by user")
            return False
            
        except Exception as e:
            print(f"Error during monitoring: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='PTSD Monitoring Application')
    parser.add_argument('--video', required=True, help='Path to video file or GCS URI')
    parser.add_argument('--cursor-path', default='/Users/wenxin/Desktop/AI/sensor', 
                        help='Path to the cursor device')
    parser.add_argument('--output-dir', help='Directory to save all output files')
    parser.add_argument('--gcs-bucket', help='GCS bucket for uploading/processing video')
    parser.add_argument('--triggers', help='Comma-separated list of trigger objects to detect')
    parser.add_argument('--confidence', type=float, default=0.7, 
                        help='Minimum confidence threshold for triggers')
    parser.add_argument('--duration', type=float, default=5,
                        help='Duration in seconds for each brain wave recording')
    
    args = parser.parse_args()
    
    # Parse trigger objects list if provided
    trigger_objects = None
    if args.triggers:
        trigger_objects = [t.strip().lower() for t in args.triggers.split(',')]
    
    # Create and run the application
    app = PTSDMonitoringApp(
        video_path=args.video,
        cursor_path=args.cursor_path,
        output_dir=args.output_dir,
        gcs_bucket=args.gcs_bucket,
        trigger_objects=trigger_objects,
        confidence_threshold=args.confidence,
        recording_duration=args.duration
    )
    
    if app.run():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()