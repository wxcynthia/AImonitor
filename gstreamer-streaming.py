#!/usr/bin/env python3
"""
Real-time Video Streaming Analysis with GStreamer
------------------------------------------------
This script sets up a GStreamer pipeline to process video (either from a file or
streaming source) and feeds it to Google Cloud Video Intelligence Streaming API
for real-time analysis.

It can process sample.mp4 for testing and later be adapted for Meta glasses.
"""

import os
import sys
import time
import json
import argparse
import threading
import subprocess
import tempfile
from queue import Queue
from datetime import datetime
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
from google.cloud import videointelligence_v1p3beta1 as videointelligence

# Global variables
TRIGGER_TERMS = ["car", "vehicle", "truck", "automobile", "traffic", "bus", "motorcycle"]
PIPE_PATH = None
TEMP_DIR = None
running = True
frame_queue = Queue(maxsize=100)  # Queue to hold video frames for processing
result_queue = Queue()  # Queue to hold analysis results
main_loop = None  # GLib main loop

def setup_environment():
    """Setup environment and check dependencies."""
    print("Setting up environment...")
    
    # Check if GOOGLE_APPLICATION_CREDENTIALS is set
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/wenxin/Desktop/AI/sensor/credentials.json"
        print(f"Setting GOOGLE_APPLICATION_CREDENTIALS to default path")
    
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"Using credentials from: {credentials_path}")
    
    if not os.path.exists(credentials_path):
        print(f"Error: Credentials file not found at {credentials_path}")
        return False
    
    # Initialize GStreamer
    Gst.init(None)
    print("GStreamer initialized")
    
    # Create temporary directory for named pipes
    global TEMP_DIR, PIPE_PATH
    TEMP_DIR = tempfile.mkdtemp()
    PIPE_PATH = os.path.join(TEMP_DIR, "video_stream")
    
    # Create named pipe
    try:
        os.mkfifo(PIPE_PATH)
        print(f"Created named pipe at: {PIPE_PATH}")
    except Exception as e:
        print(f"Error creating named pipe: {e}")
        return False
    
    return True

def create_gstreamer_file_pipeline(input_file, pipe_path):
    """Create a GStreamer pipeline that processes a file and writes to a named pipe."""
    print(f"Creating GStreamer pipeline for file: {input_file}")
    
    # Check if file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file not found at {input_file}")
        return None
    
    # Create GStreamer pipeline
    pipeline = Gst.Pipeline.new("file-to-pipe-pipeline")
    
    # Create elements
    source = Gst.ElementFactory.make("filesrc", "file-source")
    decoder = Gst.ElementFactory.make("decodebin", "decoder")
    converter = Gst.ElementFactory.make("videoconvert", "converter")
    encoder = Gst.ElementFactory.make("x264enc", "encoder")
    muxer = Gst.ElementFactory.make("flvmux", "muxer")
    sink = Gst.ElementFactory.make("filesink", "file-sink")
    
    # Check if elements were created successfully
    elements = [source, decoder, converter, encoder, muxer, sink]
    for element in elements:
        if not element:
            print(f"Error: Could not create {element.get_name() if element else 'an element'}")
            return None
    
    # Set element properties
    source.set_property("location", input_file)
    sink.set_property("location", pipe_path)
    encoder.set_property("tune", "zerolatency")  # Optimize for low latency
    encoder.set_property("speed-preset", "ultrafast")  # Fastest encoding
    encoder.set_property("bitrate", 2000)  # Lower bitrate for faster processing
    
    # Add elements to pipeline
    for element in elements:
        pipeline.add(element)
    
    # Link elements (partial linking because decodebin has dynamic pads)
    if not Gst.Element.link(source, decoder):
        print("Error: Could not link source to decoder")
        return None
    
    if not Gst.Element.link_many(converter, encoder, muxer, sink):
        print("Error: Could not link converter -> encoder -> muxer -> sink")
        return None
    
    # Connect decoder's pad-added signal to handle dynamic pads
    def on_pad_added(element, pad):
        sink_pad = converter.get_static_pad("sink")
        if not sink_pad.is_linked():
            pad.link(sink_pad)
    
    decoder.connect("pad-added", on_pad_added)
    
    print("GStreamer pipeline created successfully")
    return pipeline

def create_gstreamer_rtsp_pipeline(rtsp_url, pipe_path):
    """Create a GStreamer pipeline that processes an RTSP stream and writes to a named pipe."""
    print(f"Creating GStreamer pipeline for RTSP stream: {rtsp_url}")
    
    # Create GStreamer pipeline
    pipeline = Gst.Pipeline.new("rtsp-to-pipe-pipeline")
    
    # Create elements
    source = Gst.ElementFactory.make("rtspsrc", "rtsp-source")
    depay = Gst.ElementFactory.make("rtph264depay", "depay")
    parse = Gst.ElementFactory.make("h264parse", "parse")
    muxer = Gst.ElementFactory.make("flvmux", "muxer")
    sink = Gst.ElementFactory.make("filesink", "file-sink")
    
    # Check if elements were created successfully
    elements = [source, depay, parse, muxer, sink]
    for element in elements:
        if not element:
            print(f"Error: Could not create {element.get_name() if element else 'an element'}")
            return None
    
    # Set element properties
    source.set_property("location", rtsp_url)
    source.set_property("latency", 0)  # Minimize latency
    source.set_property("buffer-mode", 0)  # Auto buffer mode
    source.set_property("drop-on-latency", True)  # Drop frames if necessary to maintain low latency
    sink.set_property("location", pipe_path)
    
    # Add elements to pipeline
    for element in elements:
        pipeline.add(element)
    
    # Link elements (partial linking because rtspsrc has dynamic pads)
    if not Gst.Element.link_many(depay, parse, muxer, sink):
        print("Error: Could not link depay -> parse -> muxer -> sink")
        return None
    
    # Connect source's pad-added signal to handle dynamic pads
    def on_pad_added(element, pad):
        sink_pad = depay.get_static_pad("sink")
        if not sink_pad.is_linked():
            pad.link(sink_pad)
    
    source.connect("pad-added", on_pad_added)
    
    print("GStreamer RTSP pipeline created successfully")
    return pipeline

def gstreamer_pipeline_thread(pipeline):
    """Run the GStreamer pipeline in a separate thread."""
    global running, main_loop
    
    print("Starting GStreamer pipeline thread...")
    
    # Create a GLib main loop to handle GStreamer events
    main_loop = GLib.MainLoop()
    
    # Set up bus to watch for messages on the pipeline
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    
    def on_message(bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            print("End of stream")
            main_loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}")
            main_loop.quit()
        
        return True
    
    bus.connect("message", on_message)
    
    # Start playing
    pipeline.set_state(Gst.State.PLAYING)
    print("Pipeline is now playing")
    
    try:
        main_loop.run()
    except Exception as e:
        print(f"Error in GStreamer pipeline: {e}")
    finally:
        # Clean up
        pipeline.set_state(Gst.State.NULL)
        print("Pipeline stopped")

def streaming_request_generator(pipe_path):
    """Generator function that yields streaming requests for the Video Intelligence API."""
    global running
    
    # First, yield the config request
    print("Setting up streaming config...")
    config = videointelligence.StreamingVideoConfig(
        feature=[
            videointelligence.StreamingFeature.STREAMING_LABEL_DETECTION,
            videointelligence.StreamingFeature.STREAMING_OBJECT_TRACKING,
            videointelligence.StreamingFeature.STREAMING_SHOT_CHANGE_DETECTION
        ],
        shot_change_detection_config=videointelligence.StreamingShotChangeDetectionConfig(
            min_shot_change_confidence=0.7
        ),
        label_detection_config=videointelligence.StreamingLabelDetectionConfig(
            label_detection_mode=videointelligence.LabelDetectionMode.SHOT_AND_FRAME_MODE,
            stationary_camera=False,
            min_confidence=0.7
        ),
        object_tracking_config=videointelligence.StreamingObjectTrackingConfig(
            min_confidence=0.7
        )
    )
    
    yield videointelligence.StreamingAnnotateVideoRequest(video_config=config)
    
    # Then, open the named pipe and read chunks to yield as content requests
    print(f"Opening named pipe for reading: {pipe_path}")
    
    # Wait for the pipe to be ready (GStreamer needs to start writing to it)
    time.sleep(2)
    
    try:
        with open(pipe_path, 'rb') as pipe:
            print("Pipe opened successfully, starting to read data")
            chunk_size = 65536  # 64KB chunks
            
            while running:
                chunk = pipe.read(chunk_size)
                if not chunk:
                    print("End of pipe data")
                    break
                
                yield videointelligence.StreamingAnnotateVideoRequest(input_content=chunk)
                
                # Add a small delay to simulate real-time processing
                time.sleep(0.05)
    
    except Exception as e:
        print(f"Error reading from pipe: {e}")
    
    print("Streaming request generator completed")

def process_streaming_responses(responses_iterator):
    """Process streaming responses from Video Intelligence API."""
    global running, result_queue
    
    print("Starting to process streaming responses...")
    
    current_scene_labels = []
    current_objects = []
    frame_count = 0
    shot_count = 0
    
    for response in responses_iterator:
        if not running:
            break
        
        if response.error.message:
            print(f"Error: {response.error.message}")
            running = False
            break
        
        # Process all annotations
        if response.annotation_results:
            frame_count += 1
            results = response.annotation_results
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            # Create result dictionary for this frame
            frame_result = {
                "timestamp": timestamp,
                "frame_number": frame_count,
                "shot_change": False,
                "labels": [],
                "objects": []
            }
            
            # Process shot changes
            if results.shot_annotations:
                for annotation in results.shot_annotations:
                    shot_count += 1
                    frame_result["shot_change"] = True
                    print(f"\n===== NEW SHOT {shot_count} DETECTED at {timestamp} =====")
                    current_scene_labels = []  # Reset scene labels on new shot
            
            # Process label annotations
            if results.label_annotations:
                for annotation in results.label_annotations:
                    if annotation.confidence >= 0.6:  # Only consider confident detections
                        label_info = {
                            "description": annotation.entity.description,
                            "confidence": annotation.confidence,
                            "is_trigger": any(term in annotation.entity.description.lower() for term in TRIGGER_TERMS)
                        }
                        frame_result["labels"].append(label_info)
                        
                        # Check if this is a new label for the current scene
                        if annotation.entity.description not in [l["description"] for l in current_scene_labels]:
                            current_scene_labels.append(label_info)
                            print(f"[{timestamp}] New label: {annotation.entity.description} ({annotation.confidence:.2f})")
                            
                            # Special alert for trigger terms
                            if label_info["is_trigger"]:
                                print(f"🚨 TRIGGER TERM DETECTED: {annotation.entity.description} ({annotation.confidence:.2f})")
            
            # Process object tracking
            if results.object_annotations:
                for annotation in results.object_annotations:
                    if annotation.confidence >= 0.6:  # Only consider confident detections
                        # Get bounding box if available
                        box_info = None
                        if annotation.normalized_bounding_box:
                            box = annotation.normalized_bounding_box
                            box_info = {
                                "left": box.left,
                                "top": box.top,
                                "right": box.right,
                                "bottom": box.bottom
                            }
                        
                        object_info = {
                            "description": annotation.entity.description,
                            "confidence": annotation.confidence,
                            "box": box_info,
                            "is_trigger": any(term in annotation.entity.description.lower() for term in TRIGGER_TERMS)
                        }
                        frame_result["objects"].append(object_info)
                        
                        # Check if this is a new object or position has changed significantly
                        is_new = True
                        for existing in current_objects:
                            if existing["description"] == annotation.entity.description:
                                is_new = False
                                break
                        
                        if is_new:
                            current_objects.append(object_info)
                            box_str = f" at position [{box_info}]" if box_info else ""
                            print(f"[{timestamp}] New object: {annotation.entity.description} ({annotation.confidence:.2f}){box_str}")
                            
                            # Special alert for trigger terms
                            if object_info["is_trigger"]:
                                print(f"🚨 TRIGGER OBJECT DETECTED: {annotation.entity.description} ({annotation.confidence:.2f})")
            
            # Add the frame result to the queue for further processing or visualization
            result_queue.put(frame_result)
            
            # Print a summary every few frames if there are new detections
            if frame_count % 10 == 0 and (frame_result["labels"] or frame_result["objects"]):
                print(f"\n--- Frame {frame_count} Summary ({timestamp}) ---")
                
                if frame_result["labels"]:
                    labels_str = ", ".join([f"{l['description']} ({l['confidence']:.2f})" 
                                          for l in frame_result["labels"]])
                    print(f"Labels: {labels_str}")
                
                if frame_result["objects"]:
                    objects_str = ", ".join([f"{o['description']} ({o['confidence']:.2f})" 
                                           for o in frame_result["objects"]])
                    print(f"Objects: {objects_str}")
    
    print("Finished processing streaming responses")

def run_streaming_analysis(pipe_path):
    """Run the streaming analysis using Video Intelligence API."""
    global running
    
    print("Setting up streaming video client...")
    client = videointelligence.StreamingVideoIntelligenceServiceClient()
    
    print("Starting streaming analysis...")
    try:
        # Start bidirectional streaming
        requests_iterator = streaming_request_generator(pipe_path)
        responses = client.streaming_annotate_video(requests_iterator)
        
        # Process responses
        process_streaming_responses(responses)
    
    except Exception as e:
        print(f"Error in streaming analysis: {e}")
        import traceback
        traceback.print_exc()
    
    print("Streaming analysis completed")

def cleanup():
    """Clean up resources."""
    global PIPE_PATH, TEMP_DIR, running, main_loop
    
    print("Cleaning up resources...")
    running = False
    
    # Stop the GStreamer main loop if it's running
    if main_loop and main_loop.is_running():
        main_loop.quit()
    
    # Remove named pipe and temp directory
    if PIPE_PATH and os.path.exists(PIPE_PATH):
        try:
            os.unlink(PIPE_PATH)
            print(f"Removed named pipe: {PIPE_PATH}")
        except Exception as e:
            print(f"Error removing named pipe: {e}")
    
    if TEMP_DIR and os.path.exists(TEMP_DIR):
        try:
            os.rmdir(TEMP_DIR)
            print(f"Removed temporary directory: {TEMP_DIR}")
        except Exception as e:
            print(f"Error removing temporary directory: {e}")

def main():
    """Main entry point."""
    global running
    
    parser = argparse.ArgumentParser(description='Real-time video streaming analysis.')
    parser.add_argument('--input', default='/Users/wenxin/Downloads/sample.mp4',
                        help='Input video file or RTSP URL')
    parser.add_argument('--rtsp', action='store_true',
                        help='Input is an RTSP URL instead of a file')
    
    args = parser.parse_args()
    
    if not setup_environment():
        print("Environment setup failed. Exiting.")
        return 1
    
    try:
        # Create the appropriate GStreamer pipeline based on input type
        if args.rtsp:
            pipeline = create_gstreamer_rtsp_pipeline(args.input, PIPE_PATH)
        else:
            pipeline = create_gstreamer_file_pipeline(args.input, PIPE_PATH)
        
        if not pipeline:
            print("Failed to create GStreamer pipeline. Exiting.")
            cleanup()
            return 1
        
        # Start the GStreamer pipeline in a separate thread
        gst_thread = threading.Thread(target=gstreamer_pipeline_thread, args=(pipeline,))
        gst_thread.daemon = True
        gst_thread.start()
        
        # Start the streaming analysis in the main thread
        run_streaming_analysis(PIPE_PATH)
        
        # Wait for the GStreamer thread to finish
        gst_thread.join(timeout=5.0)
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        running = False
        cleanup()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())