#!/usr/bin/env python3
from dotenv import load_dotenv
load_dotenv()

import os
import sys
import time
import argparse
import threading
import queue
import cv2
import numpy as np
from datetime import datetime
import google.generativeai as genai

# Constants
ANALYSIS_INTERVAL = 2  # Seconds
RECORDING_COOLDOWN = 5  # Seconds before stopping recording after last trigger

# Initialize Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

class PTSDTriggerMonitor:
    def __init__(self, model_name="gemini-2.0-flash", recording_path=None):
        self.model = genai.GenerativeModel(model_name)
        self.result_queue = queue.Queue()
        self.recording = False
        self.recorded_frames = []
        self.last_trigger_time = 0
        
        # Set default recording path if none provided
        if recording_path is None:
            self.recording_path = os.path.join(os.path.expanduser("~"), "Desktop", "AI", "sensor", "recording")
        else:
            self.recording_path = recording_path
            
        os.makedirs(self.recording_path, exist_ok=True)
        self.running = True
        self.total_analyzed_frames = 0
        self.total_triggers = 0

    def analyze_frame(self, frame, user_prompt):
        try:
            _, encoded_image = cv2.imencode('.jpg', frame)
            image_bytes = encoded_image.tobytes()

            image_part = {
                "mime_type": "image/jpeg",
                "data": image_bytes
            }

            prompt = f"""
            You are an AI assistant designed to detect PTSD triggers based on a user-provided description.
            The user has described a scenario that may trigger their PTSD.
            User's prompt/description: "{user_prompt}".

            Analyze the following image and determine if it contains a trigger *based on the user's description*.
            Respond with "Trigger: [explanation in 20 words]" or "No".
            """
            response = self.model.generate_content([prompt, image_part])
            result = response.text
            self.result_queue.put(result)
            
            self.total_analyzed_frames += 1
            
            if "Trigger:" in result:
                self.handle_trigger()
                self.total_triggers += 1
                return True
            else:
                self.handle_no_trigger()
                return False

        except Exception as e:
            error_msg = f"Gemini API error: {e}"
            print(error_msg)
            self.result_queue.put(f"Error: {e}")
            return False

    def handle_trigger(self):
        self.last_trigger_time = time.time()
        if not self.recording:
            self.recording = True
            self.recorded_frames = []
            print("Trigger detected. Starting recording.")

    def handle_no_trigger(self):
        if self.recording and time.time() - self.last_trigger_time > RECORDING_COOLDOWN:
            self.recording = False
            self.save_recorded_video()
            print("No trigger detected. Stopping recording.")

    def save_recorded_video(self):
        if not self.recorded_frames:
            print("No frames to save")
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.recording_path, f"recorded_video_{timestamp}.mp4")
        
        try:
            height, width, _ = self.recorded_frames[0].shape
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(output_path, fourcc, 20.0, (width, height))
            
            for frame in self.recorded_frames:
                video_writer.write(frame)
                
            video_writer.release()
            print(f"Recorded video saved to {output_path}")
        except Exception as e:
            print(f"Error saving video: {e}")

    def process_stream(self, video_source, user_prompt, display_video=False):
        if isinstance(video_source, str) and os.path.isfile(video_source):
            cap = cv2.VideoCapture(video_source)
            print(f"Reading from video file: {video_source}")
            
            # Get video properties for progress reporting
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps if fps > 0 else 0
            print(f"Video has {total_frames} frames, {fps:.2f} FPS, duration: {duration:.2f} seconds")
        else:
            try:
                camera_index = int(video_source)
                cap = cv2.VideoCapture(camera_index)
                print(f"Using camera with index: {camera_index}")
                total_frames = float('inf')  # Infinite for camera
            except ValueError:
                cap = cv2.VideoCapture(video_source)
                print(f"Using camera device: {video_source}")
                total_frames = float('inf')  # Infinite for camera

        if not cap.isOpened():
            print(f"Error: Could not open video source {video_source}")
            return

        # Start result printer thread
        printer_thread = threading.Thread(target=self._result_printer, daemon=True)
        printer_thread.start()

        last_analysis_time = 0
        analysis_thread = None
        frames_processed = 0
        start_time = time.time()

        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    print("No more frames to read. Exiting.")
                    break

                frames_processed += 1
                
                # Display progress for video files
                if isinstance(video_source, str) and os.path.isfile(video_source) and frames_processed % 30 == 0:
                    progress = (frames_processed / total_frames) * 100 if total_frames > 0 else 0
                    elapsed = time.time() - start_time
                    print(f"Progress: {progress:.1f}% ({frames_processed}/{total_frames} frames, {elapsed:.1f} seconds elapsed)")

                # Resize frame if needed
                height, width = frame.shape[:2]
                max_edge = max(height, width)
                if max_edge > 720:
                    scale = 720 / max_edge
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

                # Store frame if recording
                if self.recording:
                    self.recorded_frames.append(frame.copy())

                # Display video if requested
                if display_video:
                    cv2.imshow('PTSD Trigger Monitor', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("User requested exit")
                        break

                current_time = time.time()

                # Check if it's time for a new analysis AND no analysis is running
                if current_time - last_analysis_time >= ANALYSIS_INTERVAL and (analysis_thread is None or not analysis_thread.is_alive()):
                    last_analysis_time = current_time
                    analysis_frame = frame.copy()
                    analysis_thread = threading.Thread(
                        target=self.analyze_frame,
                        args=(analysis_frame, user_prompt),
                        daemon=True
                    )
                    analysis_thread.start()
                    print(f"Starting analysis at {datetime.now().strftime('%H:%M:%S')}")

                time.sleep(0.03)  # ~30fps processing rate

        except KeyboardInterrupt:
            print("\nExiting program via KeyboardInterrupt.")
        finally:
            self.running = False
            if analysis_thread is not None and analysis_thread.is_alive():
                analysis_thread.join(timeout=2)  # Wait for up to 2 seconds for analysis to finish
            
            cap.release()
            if display_video:
                cv2.destroyAllWindows()
                
            # Report statistics
            end_time = time.time()
            elapsed = end_time - start_time
            print(f"Video processing stopped.")
            print(f"Statistics: Processed {frames_processed} frames in {elapsed:.2f} seconds")
            print(f"Analyzed {self.total_analyzed_frames} frames, detected {self.total_triggers} triggers")
            
            # Save any remaining recording
            if self.recording and self.recorded_frames:
                print("Saving final recording...")
                self.save_recorded_video()

    def _result_printer(self):
        """Thread function to print analysis results"""
        while self.running:
            try:
                result = self.result_queue.get(timeout=1)
                print(result)
            except queue.Empty:
                continue


def main():
    parser = argparse.ArgumentParser(description="PTSD Trigger Detection System")
    parser.add_argument("--source", required=True, help="Video source: camera index (e.g., 0) or video file path")
    parser.add_argument("--display", action="store_true", help="Display video while processing")
    parser.add_argument("--output", help="Directory to save recorded videos")
    args = parser.parse_args()
    
    user_prompt = input("Please describe the scenario that might trigger PTSD: ")
    
    monitor = PTSDTriggerMonitor(recording_path=args.output)
    monitor.process_stream(args.source, user_prompt, display_video=args.display)

if __name__ == "__main__":
    main()