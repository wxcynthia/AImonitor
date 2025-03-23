#!/usr/bin/env python3
from dotenv import load_dotenv
load_dotenv()

import os
import sys
import io
import subprocess
import time
import argparse
import threading
import queue
import cv2
import numpy as np
from datetime import datetime
from PIL import ImageGrab
import google.generativeai as genai

# Suppress warnings
class NullIO(io.IOBase):
    def write(self, *args, **kwargs):
        pass

sys.stderr = NullIO()
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'
os.environ['GRPC_POLL_STRATEGY'] = 'poll'
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
original_stderr = sys.stderr
sys.stderr = original_stderr

import logging
logging.basicConfig(level=logging.ERROR)
import warnings
warnings.filterwarnings("ignore")

# Constants
ANALYSIS_INTERVAL = 2  # Seconds
RECORDING_COOLDOWN = 5  # Seconds
MINIMUM_RECORDING_DURATION = 5  # Seconds - Minimum duration to record after a trigger

def capture_screen_area(x, y, width, height):
    """Capture a specific area of the screen"""
    try:
        # For Retina displays, we may need to adjust coordinates
        scale_factor = 1  # Try with 2 if you have a Retina display
        
        # Capture the entire screen
        screenshot = ImageGrab.grab()
        print(f"Full screenshot size: {screenshot.size}")
        
        # Crop to the desired area, adjusting for scale factor if needed
        area = screenshot.crop((x, y, x + width, y + height))
        
        # Convert to numpy array for OpenCV
        return np.array(area)
    except Exception as e:
        print(f"Error capturing screen area: {e}")
        return None

class PTSDTriggerMonitor:
    def __init__(self, model_name="gemini-2.0-flash", recording_path=None):
        self.model = genai.GenerativeModel(model_name)
        self.result_queue = queue.Queue()
        self.recording = False
        self.recorded_frames = []
        self.last_trigger_time = 0
        self.recording_start_time = 0
        self.recording_path = recording_path or os.path.join(os.path.expanduser("~"), "Desktop", "AI", "sensor", "recording")
        os.makedirs(self.recording_path, exist_ok=True)
        self.running = True
        self.total_analyzed_frames = 0
        self.total_triggers = 0

    def analyze_frame(self, frame, user_prompt):
        try:
            sys.stderr = NullIO()
            _, encoded_image = cv2.imencode('.jpg', frame)
            image_bytes = encoded_image.tobytes()
            image_part = {"mime_type": "image/jpeg", "data": image_bytes}
            prompt = f"""
            You are an AI assistant designed to detect PTSD triggers based on a user-provided description.
            User's prompt: "{user_prompt}".
            Analyze the image and determine if it contains a trigger. Respond with "Trigger: [explanation in 20 words]" or "No".
            """
            response = self.model.generate_content([prompt, image_part])
            result = response.text
            sys.stderr = original_stderr
            self.result_queue.put(result)
            self.total_analyzed_frames += 1
            if "Trigger:" in result:
                self.handle_trigger()
                self.total_triggers += 1
                return True
            self.handle_no_trigger()
            return False
        except Exception as e:
            sys.stderr = original_stderr
            print(f"Gemini API error: {e}")
            self.result_queue.put(f"Error: {e}")
            return False

    def handle_trigger(self):
        self.last_trigger_time = time.time()
        if not self.recording:
            self.recording = True
            self.recording_start_time = time.time()
            self.recorded_frames = []
            print("Trigger detected. Starting recording.")

    def handle_no_trigger(self):
        current_time = time.time()
        recording_elapsed = current_time - self.recording_start_time
        
        if self.recording and (current_time - self.last_trigger_time > RECORDING_COOLDOWN) and (recording_elapsed >= MINIMUM_RECORDING_DURATION):
            self.recording = False
            self.save_recorded_video()
            print(f"No trigger detected. Stopping recording after {recording_elapsed:.2f} seconds.")

    def save_recorded_video(self):
        if not self.recorded_frames:
            print("No frames to save")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Save both MP4 and AVI formats for better compatibility
        mp4_path = os.path.join(self.recording_path, f"trigger_{timestamp}.mp4")
        avi_path = os.path.join(self.recording_path, f"trigger_{timestamp}.avi")
        
        try:
            height, width, _ = self.recorded_frames[0].shape
            
            # Convert frames from RGB to BGR (OpenCV uses BGR)
            bgr_frames = [cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) for frame in self.recorded_frames]
            
            # Try H.264 codec for MP4
            fourcc_mp4 = cv2.VideoWriter_fourcc(*'avc1')  
            video_writer_mp4 = cv2.VideoWriter(mp4_path, fourcc_mp4, 20.0, (width, height))
            
            # Also save as AVI with MJPG codec which is more reliable
            fourcc_avi = cv2.VideoWriter_fourcc(*'MJPG')
            video_writer_avi = cv2.VideoWriter(avi_path, fourcc_avi, 20.0, (width, height))
            
            for frame in bgr_frames:
                video_writer_mp4.write(frame)
                video_writer_avi.write(frame)
            
            video_writer_mp4.release()
            video_writer_avi.release()
            
            print(f"Recorded videos saved to:\n- {mp4_path}\n- {avi_path}")
            
            # Also save a sample frame as a JPG for verification
            jpg_path = os.path.join(self.recording_path, f"sample_{timestamp}.jpg")
            cv2.imwrite(jpg_path, bgr_frames[0])
            print(f"Sample frame saved as {jpg_path}")
            
        except Exception as e:
            print(f"Error saving video: {e}")

    def process_screen_area(self, x, y, width, height, user_prompt, display_video=False):
        """Process a specific area of the screen"""
        printer_thread = threading.Thread(target=self._result_printer, daemon=True)
        printer_thread.start()
        frames_processed = 0
        start_time = time.time()

        try:
            next_capture_time = start_time
            while self.running:
                current_time = time.time()
                
                # Only capture a frame exactly every 2 seconds
                if current_time >= next_capture_time:
                    # Capture frame
                    frame = capture_screen_area(x, y, width, height)
                    if frame is None:
                        print("Could not capture screen area. Trying again...")
                        time.sleep(0.5)
                        continue
                    
                    frames_processed += 1
                    
                    # Display if requested
                    if display_video:
                        cv2.namedWindow('Captured Area', cv2.WINDOW_NORMAL)
                        cv2.moveWindow('Captured Area', 50, 50)
                        cv2.imshow('Captured Area', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    
                    # Store frame if recording
                    if self.recording:
                        self.recorded_frames.append(frame.copy())
                        
                    # Always analyze this frame
                    analysis_frame = frame.copy()
                    analysis_thread = threading.Thread(
                        target=self.analyze_frame,
                        args=(analysis_frame, user_prompt),
                        daemon=True
                    )
                    analysis_thread.start()
                    print(f"Starting analysis at {datetime.now().strftime('%H:%M:%S')}")
                    
                    # Set time for next capture
                    next_capture_time = next_capture_time + ANALYSIS_INTERVAL
                    
                # Brief sleep to prevent CPU overuse while waiting for next capture time
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nExiting via KeyboardInterrupt.")
        finally:
            self.running = False
            if display_video:
                cv2.destroyAllWindows()
            end_time = time.time()
            elapsed = end_time - start_time
            print(f"\nVideo processing stopped.")
            print(f"Statistics: Processed {frames_processed} frames in {elapsed:.2f} seconds")
            print(f"Analyzed {self.total_analyzed_frames} frames, detected {self.total_triggers} triggers")
            if self.recording and self.recorded_frames:
                print("Saving final recording...")
                self.save_recorded_video()

    def _result_printer(self):
        while self.running:
            try:
                result = self.result_queue.get(timeout=1)
                print(result)
            except queue.Empty:
                continue

def main():
    parser = argparse.ArgumentParser(description="macOS PTSD Trigger Detection - Screen Area Monitor")
    parser.add_argument("--window", help="Part of window name to capture (legacy option)")
    parser.add_argument("--region", help="Screen region to capture in format 'x,y,width,height'")
    parser.add_argument("--display", action="store_true", help="Display video while processing")
    parser.add_argument("--output", help="Directory to save recorded videos")
    args = parser.parse_args()
    
    # Interactive region selection if no region specified
    if not args.region:
        print("Please specify the screen region to capture in the format 'x,y,width,height'")
        region_input = input("Enter region (e.g., '100,100,800,600'): ")
        try:
            x, y, width, height = map(int, region_input.split(','))
        except:
            print("Invalid format. Using default region (0,0,800,600)")
            x, y, width, height = 0, 0, 800, 600
    else:
        try:
            x, y, width, height = map(int, args.region.split(','))
        except:
            print("Invalid region format. Using default region (0,0,800,600)")
            x, y, width, height = 0, 0, 800, 600
    
    print(f"Will capture screen area at ({x}, {y}) with size ({width}, {height})")
    user_prompt = input("Please describe the scenario that might trigger PTSD: ")
    monitor = PTSDTriggerMonitor(recording_path=args.output)
    monitor.process_screen_area(x, y, width, height, user_prompt, display_video=args.display)

if __name__ == "__main__":
    main()