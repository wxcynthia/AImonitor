#!/usr/bin/env python3
from dotenv import load_dotenv
load_dotenv()

# Suppress warnings with stderr redirection
import os
import sys
import io
import time
import argparse
import threading
import queue
import cv2
import numpy as np
from datetime import datetime
from PIL import ImageGrab
import google.generativeai as genai

# Create null device to discard stderr output
class NullIO(io.IOBase):
    def write(self, *args, **kwargs):
        pass

# Redirect stderr
original_stderr = sys.stderr
sys.stderr = NullIO()
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'
os.environ['GRPC_POLL_STRATEGY'] = 'poll'
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
sys.stderr = original_stderr

# Suppress other warnings
import logging
logging.basicConfig(level=logging.ERROR)
import warnings
warnings.filterwarnings("ignore")

# Constants
ANALYSIS_INTERVAL = 2  # Seconds
RECORDING_COOLDOWN = 5  # Seconds

class PTSDTriggerMonitor:
    def __init__(self, model_name="gemini-2.0-flash", recording_path=None):
        self.model = genai.GenerativeModel(model_name)
        self.result_queue = queue.Queue()
        self.recording = False
        self.recorded_frames = []
        self.last_trigger_time = 0
        
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
            # Redirect stderr during API calls
            old_stderr = sys.stderr
            sys.stderr = NullIO()
            
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
            
            # Restore stderr
            sys.stderr = old_stderr
            
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
            # Restore stderr in case of exception
            sys.stderr = old_stderr
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

    def monitor_screen_region(self, x1, y1, x2, y2, user_prompt, display_video=False):
        """Monitor a specific region of the screen"""
        # Start result printer thread
        printer_thread = threading.Thread(target=self._result_printer, daemon=True)
        printer_thread.start()

        last_analysis_time = 0
        analysis_thread = None
        frames_processed = 0
        start_time = time.time()

        try:
            while self.running:
                # Capture the screen region
                screenshot = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                frame = np.array(screenshot)
                # Convert RGB to BGR for OpenCV
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                frames_processed += 1
                
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

                # Check if it's time for a new analysis (every ANALYSIS_INTERVAL seconds)
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

                time.sleep(0.1)  # 10fps to reduce CPU load

        except KeyboardInterrupt:
            print("\nExiting program via KeyboardInterrupt.")
        finally:
            self.running = False
            if analysis_thread is not None and analysis_thread.is_alive():
                analysis_thread.join(timeout=2)
                
            if display_video:
                cv2.destroyAllWindows()
                
            # Report statistics
            end_time = time.time()
            elapsed = end_time - start_time
            print(f"\nScreen region monitoring stopped.")
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
    parser = argparse.ArgumentParser(description="macOS PTSD Trigger Detection - Screen Monitor")
    parser.add_argument("--region", help="Screen region to capture as x1,y1,x2,y2", default="0,0,1200,800")
    parser.add_argument("--display", action="store_true", help="Display video while processing")
    parser.add_argument("--output", help="Directory to save recorded videos")
    args = parser.parse_args()
    
    # Parse region coordinates
    try:
        x1, y1, x2, y2 = map(int, args.region.split(','))
    except ValueError:
        print("Error: Region should be specified as x1,y1,x2,y2 (e.g., 0,0,1200,800)")
        return
    
    user_prompt = input("Please describe the scenario that might trigger PTSD: ")
    
    print(f"Monitoring screen region ({x1},{y1}) to ({x2},{y2})")
    print("Press Ctrl+C to exit")
    
    monitor = PTSDTriggerMonitor(recording_path=args.output)
    monitor.monitor_screen_region(x1, y1, x2, y2, user_prompt, display_video=args.display)

if __name__ == "__main__":
    main() 