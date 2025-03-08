#!/usr/bin/env python3
"""
Simple Video Analysis
-------------------
This script analyzes a video using Google Cloud Video Intelligence API
and provides scene descriptions at specified time intervals.
Based on the working test_video_content.py approach.
"""

import os
import sys
import time
import functools
from google.cloud import videointelligence
from google.cloud import storage

# Make all print statements flush immediately
print = functools.partial(print, flush=True)

# Add debug print at the very beginning
print("Script starting...")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# Set Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/wenxin/Desktop/AI/sensor/credentials.json"
print(f"Credentials file path: {os.environ['GOOGLE_APPLICATION_CREDENTIALS']}")
print(f"Credentials file exists: {os.path.exists(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])}")

# Video path to test
VIDEO_PATH = "/Users/wenxin/Downloads/sample.mp4"
print(f"Video path: {VIDEO_PATH}")
print(f"Video file exists: {os.path.exists(VIDEO_PATH)}")

def upload_to_gcs(local_file_path, bucket_name="temp-video-bucket"):
    """Upload a local file to Google Cloud Storage and return the GCS URI."""
    try:
        print(f"Attempting to upload {local_file_path} to GCS bucket {bucket_name}...")
        
        # Create a storage client
        storage_client = storage.Client()
        
        # Check if the bucket exists, create it if not
        try:
            bucket = storage_client.get_bucket(bucket_name)
        except Exception:
            print(f"Bucket {bucket_name} not found, creating it...")
            bucket = storage_client.create_bucket(bucket_name)
        
        # Create a blob and upload the file
        blob_name = os.path.basename(local_file_path)
        blob = bucket.blob(blob_name)
        
        # Upload the file
        blob.upload_from_filename(local_file_path)
        
        # Get the GCS URI
        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        print(f"File uploaded successfully to {gcs_uri}")
        return gcs_uri
    
    except Exception as e:
        print(f"Error uploading to GCS: {e}")
        return None

def analyze_video(video_path):
    """Analyze the video for labels, objects and shot changes."""
    print(f"Starting analysis of video: {video_path}")
    start_time = time.time()
    
    # Create a client
    video_client = videointelligence.VideoIntelligenceServiceClient()
    
    features = [
        videointelligence.Feature.LABEL_DETECTION,
        videointelligence.Feature.OBJECT_TRACKING,
        videointelligence.Feature.SHOT_CHANGE_DETECTION  # Correct feature name
    ]
    
    # Create video context with settings
    video_context = videointelligence.VideoContext(
        label_detection_config=videointelligence.LabelDetectionConfig(
            label_detection_mode=videointelligence.LabelDetectionMode.SHOT_AND_FRAME_MODE,
            stationary_camera=False
        )
    )
    
    # Determine if we're using a GCS URI or local file
    is_gcs = video_path.startswith("gs://")
    
    if is_gcs:
        # Use the GCS URI directly
        operation = video_client.annotate_video(
            request={
                "features": features, 
                "input_uri": video_path,
                "video_context": video_context
            }
        )
    else:
        # For local files, read the content
        with open(video_path, "rb") as file:
            input_content = file.read()
        
        operation = video_client.annotate_video(
            request={
                "features": features, 
                "input_content": input_content,
                "video_context": video_context
            }
        )
    
    print("Processing video... This may take a few minutes.")
    result = operation.result(timeout=300)  # 5-minute timeout
    
    elapsed_time = time.time() - start_time
    print(f"Analysis completed in {elapsed_time:.2f} seconds")
    
    return result

def print_scene_descriptions(result):
    """Print detailed descriptions of the video scenes."""
    print("\n===== VIDEO CONTENT ANALYSIS =====")
    
    # Process the first annotation result
    annotation_result = result.annotation_results[0]
    
    # Get shot changes to break the video into scenes
    shot_changes = []
    if hasattr(annotation_result, 'shot_annotations'):
        print("\nSHOT CHANGES:")
        for i, shot in enumerate(annotation_result.shot_annotations):
            start_time = shot.start_time_offset.seconds + shot.start_time_offset.microseconds / 1000000
            end_time = shot.end_time_offset.seconds + shot.end_time_offset.microseconds / 1000000
            shot_changes.append((start_time, end_time))
            print(f"- Shot {i+1}: {start_time:.2f}s to {end_time:.2f}s (duration: {end_time - start_time:.2f}s)")
    
    # Print all segment labels
    if hasattr(annotation_result, 'segment_label_annotations'):
        print("\nSEGMENT LABELS (entire video):")
        
        for label in annotation_result.segment_label_annotations:
            label_name = label.entity.description
            confidence = label.segments[0].confidence
            
            print(f"- {label_name} (confidence: {confidence:.2f})")
    
    # Print all shot labels
    if hasattr(annotation_result, 'shot_label_annotations'):
        print("\nSHOT LABELS (specific segments):")
        
        for label in annotation_result.shot_label_annotations:
            label_name = label.entity.description
            
            # Print each segment this label appears in
            for segment in label.segments:
                confidence = segment.confidence
                start_time = segment.segment.start_time_offset.seconds + segment.segment.start_time_offset.microseconds / 1000000
                end_time = segment.segment.end_time_offset.seconds + segment.segment.end_time_offset.microseconds / 1000000
                
                print(f"- {label_name} (confidence: {confidence:.2f}) from {start_time:.2f}s to {end_time:.2f}s")
    
    # Print all objects with timestamps
    if hasattr(annotation_result, 'object_annotations'):
        print("\nOBJECT DETECTIONS:")
        
        for object_annotation in annotation_result.object_annotations:
            object_name = object_annotation.entity.description
            confidence = object_annotation.confidence
            
            # Get time range
            if object_annotation.frames:
                first_frame = object_annotation.frames[0]
                last_frame = object_annotation.frames[-1]
                
                start_time = first_frame.time_offset.seconds + first_frame.time_offset.microseconds / 1000000
                end_time = last_frame.time_offset.seconds + last_frame.time_offset.microseconds / 1000000
                
                print(f"- {object_name} (confidence: {confidence:.2f}) from {start_time:.2f}s to {end_time:.2f}s")
    
    # Create scene-by-scene breakdown
    if shot_changes:
        print("\n===== SCENE-BY-SCENE BREAKDOWN =====")
        
        for i, (start_time, end_time) in enumerate(shot_changes):
            print(f"\nSCENE {i+1}: {start_time:.2f}s - {end_time:.2f}s")
            
            # Find labels for this scene
            scene_labels = []
            if hasattr(annotation_result, 'shot_label_annotations'):
                for label in annotation_result.shot_label_annotations:
                    for segment in label.segments:
                        segment_start = segment.segment.start_time_offset.seconds + segment.segment.start_time_offset.microseconds / 1000000
                        segment_end = segment.segment.end_time_offset.seconds + segment.segment.end_time_offset.microseconds / 1000000
                        
                        # Check if there's overlap with this shot
                        if max(start_time, segment_start) < min(end_time, segment_end):
                            scene_labels.append((label.entity.description, segment.confidence))
            
            # Find objects for this scene
            scene_objects = []
            if hasattr(annotation_result, 'object_annotations'):
                for obj in annotation_result.object_annotations:
                    # Check if any frame falls within this shot
                    obj_in_scene = False
                    for frame in obj.frames:
                        frame_time = frame.time_offset.seconds + frame.time_offset.microseconds / 1000000
                        if start_time <= frame_time <= end_time:
                            obj_in_scene = True
                            break
                    
                    if obj_in_scene:
                        scene_objects.append((obj.entity.description, obj.confidence))
            
            # Print scene content
            if scene_labels:
                # Remove duplicates and get the highest confidence for each label
                unique_labels = {}
                for label, conf in scene_labels:
                    if label not in unique_labels or conf > unique_labels[label]:
                        unique_labels[label] = conf
                
                print("Labels: " + ", ".join([f"{label} ({conf:.2f})" 
                                           for label, conf in sorted(unique_labels.items(), 
                                                                    key=lambda x: x[1], 
                                                                    reverse=True)]))
            
            if scene_objects:
                # Remove duplicates and get the highest confidence for each object
                unique_objects = {}
                for obj, conf in scene_objects:
                    if obj not in unique_objects or conf > unique_objects[obj]:
                        unique_objects[obj] = conf
                
                print("Objects: " + ", ".join([f"{obj} ({conf:.2f})" 
                                            for obj, conf in sorted(unique_objects.items(), 
                                                                  key=lambda x: x[1], 
                                                                  reverse=True)]))
            
            if not scene_labels and not scene_objects:
                print("No specific content detected in this scene")

def main():
    """Main function to analyze the sample video."""
    print("Entering main function...")
    
    # Check if the video exists
    if not os.path.exists(VIDEO_PATH):
        print(f"Error: The video file does not exist at {VIDEO_PATH}")
        print("Please provide a valid video file path.")
        return
    
    try:
        # Get video file info
        video_size_mb = os.path.getsize(VIDEO_PATH) / (1024 * 1024)
        print(f"Video file: {VIDEO_PATH}")
        print(f"File size: {video_size_mb:.2f} MB")
        
        # For larger files, upload to GCS first
        video_path = VIDEO_PATH
        if video_size_mb > 10:
            print("Video file is larger than 10MB, uploading to Google Cloud Storage...")
            gcs_uri = upload_to_gcs(VIDEO_PATH)
            if gcs_uri:
                video_path = gcs_uri
            else:
                print("Continuing with local file despite size (may cause issues)...")
        
        # Analyze the video
        result = analyze_video(video_path)
        
        # Print scene descriptions
        print_scene_descriptions(result)
        
    except Exception as e:
        print(f"Error analyzing video: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Script is being run directly")
    main()
    print("Script execution completed")