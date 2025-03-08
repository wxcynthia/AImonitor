#!/usr/bin/env python3
"""
Test Video Streaming with Google Cloud Video Intelligence API
------------------------------------------------------------
This script sets up a test environment for streaming video analysis
using Google Cloud Video Intelligence API's streaming capabilities.
"""

import os
import sys
import time
import subprocess
import tempfile

# Sample video path
SAMPLE_VIDEO = "/Users/wenxin/Downloads/sample.mp4"
# Verify credentials are exported
CREDENTIALS_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

def check_environment():
    """Check if the environment is properly set up"""
    print("Checking environment setup...")
    
    # Check if sample video exists
    if not os.path.exists(SAMPLE_VIDEO):
        print(f"Error: Sample video not found at {SAMPLE_VIDEO}")
        return False
    
    # Check if credentials are exported
    if not CREDENTIALS_PATH:
        print("Error: GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        return False
    
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"Error: Credentials file not found at {CREDENTIALS_PATH}")
        return False
    
    print(f"✓ Sample video: {SAMPLE_VIDEO}")
    print(f"✓ Credentials: {CREDENTIALS_PATH}")
    
    # Check for required tools
    try:
        # Check for GStreamer
        gst_version = subprocess.check_output(["gst-launch-1.0", "--version"], 
                                             stderr=subprocess.STDOUT, 
                                             universal_newlines=True)
        print(f"✓ GStreamer installed: {gst_version.split()[0]}")
    except (subprocess.SubprocessError, FileNotFoundError):
        print("Warning: GStreamer (gst-launch-1.0) not found. Required for streaming.")
        print("Install GStreamer on macOS with: brew install gstreamer gst-plugins-base gst-plugins-good")
        return False
    
    return True

def setup_named_pipe():
    """Create a named pipe for streaming"""
    temp_dir = tempfile.mkdtemp()
    pipe_path = os.path.join(temp_dir, "video_stream")
    
    print(f"Creating named pipe at: {pipe_path}")
    try:
        os.mkfifo(pipe_path)
        print(f"✓ Named pipe created successfully")
        return pipe_path
    except Exception as e:
        print(f"Error creating named pipe: {e}")
        return None

def start_gstreamer(pipe_path):
    """Start GStreamer pipeline to stream the video to the named pipe"""
    print("Starting GStreamer pipeline...")
    
    # Command to stream file to pipe
    gst_cmd = [
        "gst-launch-1.0", "-v",
        "filesrc", f"location={SAMPLE_VIDEO}", "!", 
        "decodebin", "!", 
        "videoconvert", "!",
        "x264enc", "!", 
        "flvmux", "!", 
        "filesink", f"location={pipe_path}"
    ]
    
    try:
        # Start process in background
        process = subprocess.Popen(
            gst_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        print("✓ GStreamer pipeline started")
        return process
    except Exception as e:
        print(f"Error starting GStreamer: {e}")
        return None

def run_aistreamer(pipe_path):
    """Run the AIStreamer ingestion client"""
    print("Looking for AIStreamer binary...")
    
    # Check if the binary exists in the aistreamer directory
    aistreamer_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aistreamer")
    
    # Try to find the binary
    aistreamer_bin = None
    possible_binary_paths = [
        os.path.join(aistreamer_base, "bin", "streaming_client_main"),
        os.path.join(aistreamer_base, "client", "cpp", "streaming_client_main"),
        os.path.join(aistreamer_base, "bazel-bin", "client", "cpp", "streaming_client_main")
    ]
    
    for path in possible_binary_paths:
        if os.path.exists(path):
            aistreamer_bin = path
            break
    
    if not aistreamer_bin:
        print("AIStreamer binary not found. Please build it first.")
        print("See: https://github.com/google/aistreamer/tree/master/ingestion")
        return None
    
    print(f"✓ Found AIStreamer binary at: {aistreamer_bin}")
    
    # Look for config file
    config_path = os.path.join(aistreamer_base, "client", "cpp", "config", "streaming_config.json")
    if not os.path.exists(config_path):
        print(f"Config file not found at {config_path}")
        print("Creating a basic config file...")
        
        # Create a basic config file
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            f.write('''
{
  "features": ["LABEL_DETECTION", "OBJECT_TRACKING"],
  "detection_config": {
    "confidence_threshold": 0.7
  }
}
''')
        print(f"✓ Created config file at: {config_path}")
    else:
        print(f"✓ Found config file at: {config_path}")
    
    # Run AIStreamer client
    print("Starting AIStreamer client...")
    
    aistreamer_cmd = [
        aistreamer_bin,
        "--alsologtostderr",
        "--endpoint", "dns:///alpha-videointelligence.googleapis.com",
        "--video_path", pipe_path,
        "--use_pipe", "true",
        "--config", config_path,
        "--timeout", "120"  # 2 minutes
    ]
    
    try:
        process = subprocess.Popen(
            aistreamer_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        print("✓ AIStreamer client started")
        return process
    except Exception as e:
        print(f"Error starting AIStreamer: {e}")
        return None

def alternative_test():
    """Alternative testing method if AIStreamer setup fails"""
    print("\nFalling back to alternative testing method...")
    print("Using Python client library for streaming analysis")
    
    # Try to import required libraries
    try:
        from google.cloud import videointelligence_v1p3beta1 as videointelligence
    except ImportError:
        print("Error: Google Cloud Video Intelligence library not installed")
        print("Install with: pip install google-cloud-videointelligence")
        return False
    
    # Use the existing video_monitor.py file if available
    if os.path.exists("video_monitor.py"):
        print("Found video_monitor.py, importing VideoAnalyzer...")
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        try:
            from video_monitor import VideoAnalyzer
            analyzer = VideoAnalyzer(CREDENTIALS_PATH)
            print("Testing video analysis with VideoAnalyzer...")
            results = analyzer.analyze_file(SAMPLE_VIDEO)
            print(f"Analysis complete! Found {len(results)} detections")
            for detection in results:
                print(f" - {detection.get('description', 'Unknown detection')}")
            return True
        except Exception as e:
            print(f"Error using VideoAnalyzer: {e}")
    
    # If that fails, use a direct approach
    print("Using direct API approach for testing...")
    
    client = videointelligence.StreamingVideoIntelligenceServiceClient()
    
    # Test a simple streaming request
    print(f"Reading video file: {SAMPLE_VIDEO}")
    
    # This is a simplified non-streaming test to verify API access
    video_client = videointelligence.VideoIntelligenceServiceClient()
    features = [videointelligence.Feature.LABEL_DETECTION]
    
    with open(SAMPLE_VIDEO, "rb") as file:
        input_content = file.read()
    
    print("Sending annotation request to Video Intelligence API...")
    operation = video_client.annotate_video(
        request={"features": features, "input_content": input_content}
    )
    print("Request sent! Waiting for response...")
    
    result = operation.result(timeout=120)
    print("Analysis complete!")
    
    for annotation_result in result.annotation_results:
        for segment_label in annotation_result.segment_label_annotations:
            print(f"Label: {segment_label.entity.description}")
    
    return True

def main():
    """Main function to test streaming video analysis"""
    if not check_environment():
        print("\nEnvironment check failed. Please fix the issues above before continuing.")
        if alternative_test():
            print("\nAlternative test completed successfully!")
        return
    
    pipe_path = setup_named_pipe()
    if not pipe_path:
        print("Failed to create named pipe. Exiting.")
        return
    
    print("\n" + "="*50)
    print("STARTING STREAMING TEST")
    print("="*50)
    
    # First start the AIStreamer client
    aistreamer_process = run_aistreamer(pipe_path)
    if not aistreamer_process:
        print("Failed to start AIStreamer client. Trying alternative test...")
        alternative_test()
        return
    
    # Wait a bit for AIStreamer to initialize
    time.sleep(2)
    
    # Then start GStreamer to feed the pipe
    gstreamer_process = start_gstreamer(pipe_path)
    if not gstreamer_process:
        print("Failed to start GStreamer pipeline. Cleaning up...")
        aistreamer_process.terminate()
        return
    
    print("\nBoth processes started. Streaming test in progress...")
    print("Press Ctrl+C to stop the test")
    
    try:
        # Monitor both processes
        while True:
            aistreamer_out = aistreamer_process.stdout.readline()
            if aistreamer_out:
                print(f"AIStreamer: {aistreamer_out.strip()}")
            
            gstreamer_out = gstreamer_process.stdout.readline()
            if gstreamer_out:
                print(f"GStreamer: {gstreamer_out.strip()}")
            
            # Check if processes are still running
            if aistreamer_process.poll() is not None:
                print("AIStreamer process has terminated")
                break
            
            if gstreamer_process.poll() is not None:
                print("GStreamer process has terminated")
                break
            
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        print("Cleaning up...")
        if aistreamer_process and aistreamer_process.poll() is None:
            aistreamer_process.terminate()
        
        if gstreamer_process and gstreamer_process.poll() is None:
            gstreamer_process.terminate()
        
        # Clean up the named pipe
        try:
            os.unlink(pipe_path)
            os.rmdir(os.path.dirname(pipe_path))
            print("Cleanup complete")
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    print("\nStreaming test completed")

if __name__ == "__main__":
    main()