#!/usr/bin/env python3
"""
Test Script for Sample Video Analysis
------------------------------------
This script analyzes a sample video to check if it contains car-related objects
that can be detected by Google Cloud Video Intelligence API.
"""

import os
import sys
import time
from google.cloud import videointelligence
from google.cloud import storage
import functools
print = functools.partial(print, flush=True)  # Make all print statements flush immediately

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

# List of car-related terms to search for
CAR_TERMS = ["car", "vehicle", "truck", "automobile", "traffic", "bus", "motorcycle"]

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
    """Analyze the video for labels and objects."""
    print(f"Starting analysis of video: {video_path}")
    start_time = time.time()
    
    # Create a client
    video_client = videointelligence.VideoIntelligenceServiceClient()
    
    features = [
        videointelligence.Feature.LABEL_DETECTION,
        videointelligence.Feature.OBJECT_TRACKING
    ]
    
    # Determine if we're using a GCS URI or local file
    is_gcs = video_path.startswith("gs://")
    
    if is_gcs:
        # Use the GCS URI directly
        operation = video_client.annotate_video(
            request={"features": features, "input_uri": video_path}
        )
    else:
        # For local files, read the content
        with open(video_path, "rb") as file:
            input_content = file.read()
        
        operation = video_client.annotate_video(
            request={"features": features, "input_content": input_content}
        )
    
    print("Processing video... This may take a few minutes.")
    result = operation.result(timeout=300)  # 5-minute timeout
    
    elapsed_time = time.time() - start_time
    print(f"Analysis completed in {elapsed_time:.2f} seconds")
    
    return result

def check_for_car_content(result):
    """Check if the video contains car-related content."""
    print("\n===== VIDEO CONTENT ANALYSIS =====")
    
    car_found = False
    
    # Dictionary to collect all findings
    findings = {
        "segment_labels": [],
        "shot_labels": [],
        "objects": []
    }
    
    # Process the first annotation result
    annotation_result = result.annotation_results[0]
    
    # Check segment label annotations
    if hasattr(annotation_result, 'segment_label_annotations'):
        print("\nSEGMENT LABELS (entire video):")
        
        for label in annotation_result.segment_label_annotations:
            label_name = label.entity.description.lower()
            confidence = label.segments[0].confidence
            
            print(f"- {label_name} (confidence: {confidence:.2f})")
            
            # Check if this is a car-related label
            if any(car_term in label_name for car_term in CAR_TERMS):
                car_found = True
                findings["segment_labels"].append({
                    "label": label_name,
                    "confidence": confidence
                })
                print(f"  *** CAR-RELATED CONTENT DETECTED: {label_name} ***")
    
    # Check shot label annotations (if available)
    if hasattr(annotation_result, 'shot_label_annotations'):
        print("\nSHOT LABELS (specific segments):")
        
        for label in annotation_result.shot_label_annotations:
            label_name = label.entity.description.lower()
            
            # Get the highest confidence segment
            segments = sorted(label.segments, key=lambda s: s.confidence, reverse=True)
            if segments:
                confidence = segments[0].confidence
                print(f"- {label_name} (confidence: {confidence:.2f})")
                
                # Check if this is a car-related label
                if any(car_term in label_name for car_term in CAR_TERMS):
                    car_found = True
                    findings["shot_labels"].append({
                        "label": label_name,
                        "confidence": confidence
                    })
                    print(f"  *** CAR-RELATED CONTENT DETECTED: {label_name} ***")
    
    # Check object annotations
    if hasattr(annotation_result, 'object_annotations'):
        print("\nOBJECT DETECTIONS:")
        
        for object_annotation in annotation_result.object_annotations:
            object_name = object_annotation.entity.description.lower()
            confidence = object_annotation.confidence
            
            print(f"- {object_name} (confidence: {confidence:.2f})")
            
            # Check if this is a car-related object
            if any(car_term in object_name for car_term in CAR_TERMS):
                car_found = True
                findings["objects"].append({
                    "object": object_name,
                    "confidence": confidence
                })
                print(f"  *** CAR-RELATED OBJECT DETECTED: {object_name} ***")
    
    # Summary of findings
    print("\n===== SUMMARY =====")
    if car_found:
        print("CAR-RELATED CONTENT WAS FOUND IN THE VIDEO!")
        
        if findings["segment_labels"]:
            print("\nCar-related segment labels:")
            for item in findings["segment_labels"]:
                print(f"- {item['label']} (confidence: {item['confidence']:.2f})")
        
        if findings["shot_labels"]:
            print("\nCar-related shot labels:")
            for item in findings["shot_labels"]:
                print(f"- {item['label']} (confidence: {item['confidence']:.2f})")
        
        if findings["objects"]:
            print("\nCar-related objects:")
            for item in findings["objects"]:
                print(f"- {item['object']} (confidence: {item['confidence']:.2f})")
        
        print("\nThis video is suitable for testing your PTSD monitoring application.")
    else:
        print("NO CAR-RELATED CONTENT WAS FOUND IN THE VIDEO.")
        print("This video may not be suitable for testing your PTSD monitoring application.")
        print("Consider using a different video that contains cars, vehicles, or traffic.")
    
    return car_found, findings

def main():
    """Main function to test the sample video."""
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
        if video_size_mb > 10:
            print("Video file is larger than 10MB, uploading to Google Cloud Storage...")
            gcs_uri = upload_to_gcs(VIDEO_PATH)
            if gcs_uri:
                video_path = gcs_uri
            else:
                print("Continuing with local file despite size (may cause issues)...")
                video_path = VIDEO_PATH
        else:
            video_path = VIDEO_PATH
        
        # Analyze the video
        result = analyze_video(video_path)
        
        # Check for car content
        car_found, findings = check_for_car_content(result)
        
    except Exception as e:
        print(f"Error analyzing video: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Script is being run directly")
    main()
    print("Script execution completed")