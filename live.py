#!/usr/bin/env python3
"""
Live Streaming Version for Meta Glasses
--------------------------------------
This script implements a streaming version that can work with live video
from Meta glasses using Google Cloud Video Intelligence Streaming API.
"""

import os
import sys
import time
import argparse
import json
import threading
import queue
from datetime import datetime
import subprocess

# For AIStreamer integration
import google.cloud.videointelligence as videointelligence
from google.cloud import storage

# Import our cursor recorder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from integration import CursorRecorder

class MetaGlassesStreamer:
    def __init__(self, 
                 rtsp_stream_url=None,
                 cursor_path='/Users/wenxin/Desktop/AI/sensor',
                 output_dir=None,
                 pipe_name='meta_glasses_pipe',
                 trigger_objects=None,
                 confidence_threshold=0.7,
                 recording_duration=5):
        """
        Initialize the Meta Glasses streamer for PTSD monitoring.
        
        Args:
            rtsp_stream_url: RTSP URL of the Meta glasses stream
            cursor_path: Path to the cursor device
            output_dir: Directory to save all output files
            pipe_name: Name of the named pipe for AIStreamer
            trigger_objects: List of objects to detect as triggers
            confidence_threshold: Minimum confidence for trigger detection
            recording_duration: Duration in seconds for each brain wave recording
        """
        self.rtsp_stream_url = rtsp_stream_url
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
        
        # Pipe configuration
        self.pipe_path = os.path.join(self.session_dir, pipe_name)
        
        # Trigger settings
        self.trigger_objects = trigger_objects or ["car", "vehicle", "truck", "automobile", "traffic"]
        self.confidence_threshold = confidence_threshold
        self.recording_duration = recording_duration
        
        # Create subdirectories
        self.recordings_dir = os.path.join(self.session_dir, "recordings")
        self.analysis_dir = os.path.join(self.session_dir, "analysis")
        os.makedirs(self.recordings_dir, exist_ok=True)
        os.makedirs(self.analysis_dir, exist_ok=True)
        
        # Initialize recorder
        self.recorder = None
        
        # Queue for communication between detector and recorder
        self.trigger_queue = queue.Queue()
        
        # Tracking variables
        self.running = False
        self.aistreamer_process = None
        self.gstreamer_process = None
        
        print(f"Meta Glasses Streaming Session {self.session_id} initialized")
        print(f"Output directory: {self.session_dir}")
        print(f"Monitoring for triggers: {', '.join(self.trigger_objects)}")
    
    def setup_named_pipe(self):
        """Create the named pipe for communication with AIStreamer."""
        try:
            # Remove pipe if it already exists
            if os.path.exists(self.pipe_path):
                os.unlink(self.pipe_path)
            
            # Create the named pipe
            os.mkfifo(self.pipe_path)
            print(f"Created named pipe at {self.pipe_path}")
            return True
        except Exception as e:
            print(f"Error creating named pipe: {e}")
            return False
    
    def start_aistreamer(self):
        """Start the AIStreamer ingestion proxy."""
        # Construct the AIStreamer command
        # This is based on the documentation for the AIStreamer client
        cmd = [
            "./streaming_client_main",  # Path to the AIStreamer binary
            "--alsologtostderr",
            "--endpoint", "dns:///alpha-videointelligence.googleapis.com:443",
            "--video_path", self.pipe_path,
            "--use_pipe=true",
            "--config", "./config.json",  # Path to your config file
            "--timeout", "3600"  # 1 hour timeout
        ]
        
        try:
            # Set environment variables
            env = os.environ.copy()
            
            # Start AIStreamer process
            self.aistreamer_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            print("AIStreamer process started")
            return True
        except Exception as e:
            print(f"Error starting AIStreamer: {e}")
            return False
    
    def start_gstreamer(self):
        """Start the GStreamer pipeline for RTSP streaming."""
        if not self.rtsp_stream_url:
            print("No RTSP stream URL provided")
            return False
            
        # Construct GStreamer command for RTSP
        cmd = [
            "gst-launch-1.0",
            "-v",
            "rtspsrc",
            f"location={self.rtsp_stream_url}",
            "!",
            "rtpjitterbuffer",
            "!",
            "rtph264depay",
            "!",
            "h264parse",
            "!",
            "flvmux",
            "!",
            "filesink",
            f"location={self.pipe_path}"
        ]
        
        try:
            # Start GStreamer process
            self.gstreamer_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            print("GStreamer process started")
            return True
        except Exception as e:
            print(f"Error starting GStreamer: {e}")
            return False
    
    def initialize_components(self):
        """Initialize all components needed for streaming."""
        try:
            # Initialize the cursor recorder
            self.recorder = CursorRecorder(
                cursor_path=self.cursor_path,
                output_dir=self.recordings_dir
            )
            
            # Setup the named pipe
            if not self.setup_named_pipe():
                return False
            
            return True
            
        except Exception as e:
            print(f"Error initializing components: {e}")
            return False
    
    def handle_streaming_results(self):
        """Process streaming annotation results and trigger recordings."""
        # This is a placeholder for the streaming annotation processing
        # In a real implementation, you would:
        # 1. Parse the output from AIStreamer
        # 2. Check for car-related objects
        # 3. If found, add to the trigger queue
        
        # For demonstration, we'll simulate periodic trigger detection
        while self.running:
            try:
                # Check if AIStreamer process is still running
                if self.aistreamer_process and self.aistreamer_process.poll() is not None:
                    print("AIStreamer process terminated unexpectedly")
                    self.running = False
                    break
                
                # Read output from AIStreamer
                if self.aistreamer_process:
                    output = self.aistreamer_process.stdout.readline().decode('utf-8').strip()
                    if output:
                        print(f"AIStreamer output: {output}")
                        
                        # Check if output contains trigger objects
                        if any(trigger in output.lower() for trigger in self.trigger_objects):
                            description = f"Detected trigger in stream: {output}"
                            print(f"RECORD: {description}")
                            self.trigger_queue.put(description)
                
                # Sleep to avoid CPU overuse
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error processing streaming results: {e}")
                time.sleep(1)  # Wait before retrying
    
    def recorder_thread_func(self):
        """Thread function to process recording requests from the queue."""
        while self.running:
            try:
                # Get trigger description from queue with timeout
                description = self.trigger_queue.get(timeout=1)
                
                # Record brain wave data
                self.recorder.record(
                    duration=self.recording_duration,
                    description=description
                )
                
                # Mark task as done
                self.trigger_queue.task_done()
                
            except queue.Empty:
                # Queue timeout, just continue
                continue
            except Exception as e:
                print(f"Error in recorder thread: {e}")
    
    def run(self):
        """Run the streaming monitoring application."""
        if not self.initialize_components():
            print("Failed to initialize components. Exiting.")
            return False
        
        try:
            self.running = True
            
            # Start AIStreamer
            if not self.start_aistreamer():
                print("Failed to start AIStreamer. Exiting.")
                return False
            
            # Start GStreamer
            if not self.start_gstreamer():
                print("Failed to start GStreamer. Exiting.")
                self.stop_aistreamer()
                return False
            
            # Start the recorder thread
            recorder_thread = threading.Thread(target=self.recorder_thread_func)
            recorder_thread.daemon = True
            recorder_thread.start()
            
            # Start the streaming results handler
            results_thread = threading.Thread(target=self.handle_streaming_results)
            results_thread.daemon = True
            results_thread.start()
            
            print("Streaming and monitoring started. Press Ctrl+C to stop.")
            
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
            
            return True
            
        except KeyboardInterrupt:
            print("\nStreaming interrupted by user")
            self.running = False
            return False
            
        except Exception as e:
            print(f"Error during streaming: {e}")
            self.running = False
            return False
        
        finally:
            # Cleanup
            self.cleanup()
    
    def stop_aistreamer(self):
        """Stop the AIStreamer process."""
        if self.aistreamer_process:
            try:
                self.aistreamer_process.terminate()
                self.aistreamer_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.aistreamer_process.kill()
            self.aistreamer_process = None
    
    def stop_gstreamer(self):
        """Stop the GStreamer process."""
        if self.gstreamer_process:
            try:
                self.gstreamer_process.terminate()
                self.gstreamer_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.gstreamer_process.kill()
            self.gstreamer_process = None
    
    def cleanup(self):
        """Clean up resources."""
        print("Cleaning up resources...")
        
        # Stop processes
        self.stop_aistreamer()
        self.stop_gstreamer()
        
        # Signal threads to stop
        self.running = False
        
        # Remove the pipe
        if os.path.exists(self.pipe_path):
            try:
                os.unlink(self.pipe_path)
            except:
                pass
        
        print("Cleanup completed")

def main():
    parser = argparse.ArgumentParser(description='Meta Glasses Streaming for PTSD Monitoring')
    parser.add_argument('--rtsp-url', required=True, help='RTSP URL of the Meta glasses stream')
    parser.add_argument('--cursor-path', default='/Users/wenxin/Desktop/AI/sensor', 
                        help='Path to the cursor device')
    parser.add_argument('--output-dir', help='Directory to save all output files')
    parser.add_argument('--pipe-name', default='meta_glasses_pipe', 
                        help='Name of the named pipe for AIStreamer')
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
    
    # Create and run the streamer
    streamer = MetaGlassesStreamer(
        rtsp_stream_url=args.rtsp_url,
        cursor_path=args.cursor_path,
        output_dir=args.output_dir,
        pipe_name=args.pipe_name,
        trigger_objects=trigger_objects,
        confidence_threshold=args.confidence,
        recording_duration=args.duration
    )
    
    if streamer.run():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()