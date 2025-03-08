#!/usr/bin/env python3
"""
Cursor Device Integration for PTSD Recording
-------------------------------------------
This script interfaces with a cursor device to record brain wave data
when triggers are detected from the video analysis.

Specific to the cursor device at: /Users/wenxin/Desktop/AI/sensor
"""

import os
import time
import subprocess
import argparse
import json
from datetime import datetime

class CursorRecorder:
    def __init__(self, cursor_path, output_dir=None):
        """
        Initialize the cursor recording device.
        
        Args:
            cursor_path: Path to the cursor device
            output_dir: Directory to save recordings
        """
        self.cursor_path = cursor_path
        self.output_dir = output_dir or os.path.join(os.path.dirname(cursor_path), "recordings")
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        # Check if cursor device exists
        if not os.path.exists(cursor_path):
            raise FileNotFoundError(f"Cursor device not found at {cursor_path}")
        
        print(f"Initialized cursor recorder at {cursor_path}")
        print(f"Recordings will be saved to {self.output_dir}")
    
    def record(self, duration=5, description=""):
        """
        Record brain wave data for the specified duration.
        
        Args:
            duration: Recording duration in seconds
            description: Description of the trigger event
        
        Returns:
            Path to the saved recording file
        """
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_description = description.replace(" ", "_").replace("/", "_")[:30]  # Clean and limit length
        filename = f"{timestamp}_{clean_description}.brainwave"
        output_path = os.path.join(self.output_dir, filename)
        
        # Log the recording start
        print(f"Starting brain wave recording: {description}")
        
        try:
            # Simulate sending command to cursor device
            # In a real implementation, this would communicate with the actual device
            # For example:
            # with open(self.cursor_path, 'w') as f:
            #     f.write(f"RECORD:{duration}\n")
            
            # Create metadata file with trigger information
            metadata = {
                "timestamp": timestamp,
                "duration": duration,
                "trigger_description": description,
                "device": "cursor"
            }
            
            metadata_path = os.path.join(self.output_dir, f"{timestamp}_{clean_description}.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Simulate recording for the duration
            time.sleep(duration)
            
            # Create an empty file to represent the recording
            # (In a real implementation, this would be actual data from the device)
            with open(output_path, 'w') as f:
                f.write(f"Simulated brain wave recording for trigger: {description}\n")
            
            print(f"Recording completed: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"Error during recording: {e}")
            return None

def main():
    parser = argparse.ArgumentParser(description='Cursor Brain Wave Recorder')
    parser.add_argument('--cursor-path', default='/Users/wenxin/Desktop/AI/sensor', 
                        help='Path to the cursor device')
    parser.add_argument('--output-dir', help='Directory to save recordings')
    parser.add_argument('--trigger-file', help='JSON file with trigger events to process')
    
    args = parser.parse_args()
    
    try:
        recorder = CursorRecorder(args.cursor_path, args.output_dir)
        
        # If a trigger file is provided, process all triggers
        if args.trigger_file and os.path.exists(args.trigger_file):
            with open(args.trigger_file, 'r') as f:
                triggers = json.load(f)
            
            for trigger in triggers:
                recorder.record(
                    duration=5,  # Default 5 seconds per trigger
                    description=trigger.get('description', 'Unknown trigger')
                )
        else:
            # Interactive mode for testing
            while True:
                description = input("Enter trigger description (or 'exit' to quit): ")
                if description.lower() == 'exit':
                    break
                
                duration = input("Enter recording duration in seconds (default 5): ")
                try:
                    duration = float(duration) if duration else 5
                except ValueError:
                    duration = 5
                
                recorder.record(duration, description)
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print(f"Please check that the cursor device exists at the specified path.")
    
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()