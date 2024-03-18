import os
import cv2
import numpy as np
import logging
import subprocess
import shlex
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)

# Get current timestamp
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# Function to detect red color in a region of interest
def detect_color(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    # Define lower and upper bounds for red hue
    lower_red = np.array([0, 100, 100])
    upper_red = np.array([30, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red, upper_red)

    lower_red = np.array([150, 100, 100])
    upper_red = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower_red, upper_red)

    # Combine masks to detect red color in both ranges
    mask = mask1 + mask2

    # Calculate the percentage of red pixels in the ROI
    total_pixels = np.prod(roi.shape[:2])
    red_pixels = np.count_nonzero(mask)
    red_percentage = (red_pixels / total_pixels) * 100

    return red_percentage

# Function to convert frame index to SMPTE format
def frame_index_to_smpte(frame_index, frame_rate, timecode_offset):
    total_frames = int(frame_index + timecode_offset * frame_rate)
    hours = total_frames // (3600 * frame_rate)
    minutes = (total_frames % (3600 * frame_rate)) // (60 * frame_rate)
    seconds = (total_frames % (60 * frame_rate)) // frame_rate
    frames = total_frames % frame_rate
    return "{:02d}:{:02d}:{:02d}:{:02d}".format(int(hours), int(minutes), int(seconds), int(frames))

# Prompt for the video file path
video_path = input("Enter the path to the video file: ").strip()

# Check if the file exists
if not os.path.isfile(video_path):
    # If the file doesn't exist, check if the path contains escaped spaces and adjust accordingly
    if "\\ " in video_path:
        video_path = video_path.replace("\\ ", " ")
        
    # Check again if the adjusted file path exists
    if not os.path.isfile(video_path):
        logging.error("Video file not found. Please provide a valid path.")
        exit()

# Quote the path to handle spaces
video_path = video_path.strip("'\"")  # Remove surrounding quotes if present

# Open the video file
cap = cv2.VideoCapture(video_path)
frame_rate = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# Get the video file name and directory
video_file_name = os.path.basename(video_path)
video_directory = os.path.dirname(video_path)
video_file_name_without_ext = os.path.splitext(video_file_name)[0]

# Get starting timecode using ffprobe
ffprobe_command = [
    'ffprobe', '-v', 'error', '-select_streams', 'v:0',
    '-show_entries', 'stream_tags=timecode', '-of',
    'default=noprint_wrappers=1:nokey=1', video_path
]
output = subprocess.check_output(ffprobe_command, stderr=subprocess.STDOUT)
starting_timecode_ffprobe = output.decode('utf-8').strip()

# Convert the starting timecode from ffprobe to seconds
def timecode_to_seconds(timecode, frame_rate):
    time_parts = timecode.split(':')
    hours = int(time_parts[0])
    minutes = int(time_parts[1])
    seconds = int(time_parts[2])
    frames = int(time_parts[3])
    total_frames = (hours * 3600 + minutes * 60 + seconds) * frame_rate + frames
    return total_frames / frame_rate

# Calculate the timecode offset
timecode_offset = timecode_to_seconds(starting_timecode_ffprobe, frame_rate)

# Define ROI coordinates for each camera's tally border
# Format: (x1, y1, x2, y2)
roi_coords = [
    (1, 612, 2, 614),     # First camera
    (481, 612, 482, 614), # Second camera
    (960, 612, 961, 614), # Third camera
    (1440, 612, 1441, 614), # Fourth camera
    (1, 811, 2, 813) # Fifth Camera
]

# Initialize variables for tracking camera changes
prev_camera_number = None
cut_number = 1

# Define the EDL file path
edl_file_name = os.path.join(video_directory, f"{video_file_name_without_ext}_{timestamp}.edl")

# Open the EDL file for writing
with open(edl_file_name, 'w') as edl_file:
    # Write EDL header
    edl_file.write(f"TITLE: EDL {video_file_name}\n")
    edl_file.write("FCM: NON-DROP FRAME\n")

    # Main loop
    with open(edl_file_name, 'w') as edl_file:
        # Write EDL header
        edl_file.write(f"TITLE: EDL {video_file_name} {starting_timecode_ffprobe}\n")
        edl_file.write("FCM: NON-DROP FRAME\n")

        # Prompt for the video file paths for each camera
        camera_file_names = []
        for i in range(1, 6):
            camera_file_name = input(f"Enter the file name for Camera {i}: ").strip()
            camera_file_names.append(camera_file_name)

        # Iterate over each frame
        for frame_index in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                logging.info("End of video reached. Exiting loop.")
                break

            # Iterate over each ROI
            for i, coords in enumerate(roi_coords):
                x1, y1, x2, y2 = coords
                roi = frame[y1:y2, x1:x2]

                # Detect red color in ROI
                red_percentage = detect_color(roi)

                # Check if red color is detected (assuming red percentage threshold is 1%)
                if red_percentage > 1:
                    camera_number = i + 1
                    if camera_number != prev_camera_number:
                        # Output EDL line for the previous camera
                        if prev_camera_number is not None:
                            edl_file.write(f"{cut_number:03d} AX       V     C        {frame_index_to_smpte(prev_frame_index, frame_rate, timecode_offset)} {frame_index_to_smpte(frame_index, frame_rate, timecode_offset)} {frame_index_to_smpte(prev_frame_index, frame_rate, timecode_offset)} {frame_index_to_smpte(frame_index, frame_rate, timecode_offset)}\n")
                            cut_number += 1
                            edl_file.write(f"* FROM CLIP NAME: {camera_file_names[prev_camera_number - 1]}\n")
                        # Update previous camera number and frame index
                        prev_camera_number = camera_number
                        prev_frame_index = frame_index

            # Update progress bar
            progress = (frame_index + 1) / total_frames
            progress_bar_width = 50
            progress_bar = '[' + '#' * int(progress * progress_bar_width) + ' ' * (progress_bar_width - int(progress * progress_bar_width)) + ']'
            print(f"\rProcessing: {progress_bar} {frame_index + 1}/{total_frames}", end='')

        # Write the last camera change
        if prev_camera_number is not None:
            edl_file.write(f"{cut_number:03d} AX       V     C        {frame_index_to_smpte(prev_frame_index, frame_rate, timecode_offset)} {frame_index_to_smpte(frame_index, frame_rate, timecode_offset)} {frame_index_to_smpte(prev_frame_index, frame_rate, timecode_offset)} {frame_index_to_smpte(frame_index, frame_rate, timecode_offset)}\n")
            cut_number += 1
            edl_file.write(f"* FROM CLIP NAME: {camera_file_names[prev_camera_number - 1]}\n")

    # Release the video capture and close any OpenCV windows
    cap.release()
    cv2.destroyAllWindows()

    logging.info(f"EDL file '{edl_file_name}' has been created.")
