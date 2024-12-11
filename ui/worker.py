# worker.py

from datetime import datetime
import time
import cv2
import face_recognition as fr_lib  # Aliased to prevent conflicts
import mediapipe as mp
import numpy as np
import uuid
import logging
from PySide6.QtCore import QThread, Signal, Slot
from core.database import DatabaseHandler
from core.aruco_detection import ArucoDetector
from core.pose_analysis import ExerciseAnalyzer
from core.face_run import FaceRecognizer  # Updated import
from core.config import exercise_config

logging.basicConfig(level=logging.INFO, filename='worker.log',
                    format='%(asctime)s - %(levelname)s - %(message)s')

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose


class ExerciseWorker(QThread):
    frame_signal = Signal(object)
    thumbnail_frame_signal = Signal(object)
    status_signal = Signal(str)
    counters_signal = Signal(int, int)
    user_recognized_signal = Signal(dict)
    unknown_user_detected = Signal()
    data_updated = Signal()

    def __init__(self, db_handler, camera_index, exercise_choice='bicep_curl', face_recognizer=None, parent=None):
        super().__init__(parent)
        self.db_handler = db_handler
        self.exercise_choice = exercise_choice
        self.face_recognizer = face_recognizer
        self.stop_requested = False
        self.camera_index = camera_index

        # Thresholds adjusted for faster recognition
        self.unknown_frames = 0
        self.UNKNOWN_FRAME_THRESHOLD = 30  # Reduced from 50
        self.KNOWN_FRAME_THRESHOLD = 30    # Reduced from 50

        self.new_user_name = None
        self.new_user_encodings = []
        self.capturing_new_user_data = False
        self.frames_to_capture = 200  # Increased from 100

        self.face_recognition_active = True
        self.exercise_analysis_active = False
        self.exercise_analyzer = None
        self.current_user_info = None

        # Known user stable recognition
        self.known_frames = 0
        self.last_recognized_user = None
        self.unknown_stable_detected = False

    def request_stop(self):
        self.stop_requested = True
        logging.info("Stop requested for ExerciseWorker.")

    def start_record_new_user(self, user_name):
        self.new_user_name = user_name
        self.new_user_encodings = []
        self.capturing_new_user_data = True
        self.status_signal.emit(f"Capturing face data for {user_name}. Please wait...")
        logging.info(f"Started capturing face data for new user: {user_name}")

    def run(self):
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.status_signal.emit(f"Error: Could not open camera {self.camera_index}.")
            logging.error(f"Could not open camera {self.camera_index}.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        logging.info(f"Camera {self.camera_index} initialized.")

        mp_pose_solution = mp_pose.Pose(min_detection_confidence=0.5,
                                        min_tracking_confidence=0.5,
                                        model_complexity=1)
        aruco_detector = ArucoDetector(dict_type="DICT_5X5_100")

        if self.exercise_choice not in exercise_config:
            self.status_signal.emit(f"Exercise '{self.exercise_choice}' not configured. Using default if available.")
            logging.warning(f"Exercise '{self.exercise_choice}' not found in config.")
            if exercise_config:
                self.exercise_choice = list(exercise_config.keys())[0]
            else:
                self.status_signal.emit("No exercises configured.")
                logging.error("No exercises configured. Worker terminating.")
                cap.release()
                mp_pose_solution.close()
                return

        # Updated occlusion_timeout to represent number of frames (e.g., 300 frames for ~3 seconds at 100fps)
        # Adjusted based on actual frame rate
        occlusion_timeout = 90  # Approximately 3 seconds at 30 FPS

        while not self.stop_requested:
            ret, frame = cap.read()
            if not ret:
                self.status_signal.emit("Failed to capture frame.")
                logging.error("Failed to capture frame from camera.")
                break

            display_frame = frame.copy()
            thumb = cv2.resize(display_frame, (160, 90), interpolation=cv2.INTER_AREA)

            # If exercise analysis is active, skip face recognition to avoid interruptions
            if self.exercise_analysis_active and not self.capturing_new_user_data:
                # Exercise Analysis Mode
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = mp_pose_solution.process(frame_rgb)
                    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

                    if results.pose_landmarks:
                        # Reset no_pose_frames since pose is detected
                        self.exercise_analyzer.no_pose_frames = 0

                        landmarks = results.pose_landmarks.landmark
                        feedback_texts = self.exercise_analyzer.analyze_exercise_form(landmarks, frame_bgr)

                        if not self.exercise_analyzer.stable_start_detected:
                            connection_color = (255, 0, 0)
                            landmark_color = (255, 0, 0)
                        elif self.exercise_analyzer.bend_warning_displayed:
                            connection_color = (0, 0, 255)
                            landmark_color = (0, 0, 255)
                        else:
                            connection_color = (0, 255, 0)
                            landmark_color = (0, 255, 0)

                        mp_drawing.draw_landmarks(
                            frame_bgr,
                            results.pose_landmarks,
                            mp_pose.POSE_CONNECTIONS,
                            mp_drawing.DrawingSpec(color=connection_color, thickness=3, circle_radius=2),
                            mp_drawing.DrawingSpec(color=landmark_color, thickness=2, circle_radius=2)
                        )

                        for i, text in enumerate(feedback_texts):
                            color = (0, 255, 0)
                            if "Warning" in text:
                                color = (0, 0, 255)
                            cv2.putText(frame_bgr, text, (10, 30 + (i * 30)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                        rep_set_text = f"Reps: {self.exercise_analyzer.rep_count} | Sets: {self.exercise_analyzer.set_count}"
                        cv2.putText(frame_bgr, rep_set_text, (10, 470),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                        final_frame = frame_bgr
                        self.frame_signal.emit(final_frame)
                        self.thumbnail_frame_signal.emit(cv2.resize(final_frame, (160, 90), interpolation=cv2.INTER_AREA))
                        self.counters_signal.emit(self.exercise_analyzer.rep_count,
                                                  self.exercise_analyzer.set_count)
                    else:
                        self.exercise_analyzer.no_pose_frames += 1
                        logging.debug(f"No pose detected. no_pose_frames: {self.exercise_analyzer.no_pose_frames}")

                        if self.exercise_analyzer.no_pose_frames >= occlusion_timeout:
                            self.status_signal.emit("Person exited the frame, updating database...")
                            logging.info("Person exited frame. Updating database.")
                            record = self.exercise_analyzer.update_data()
                            if record:
                                insert_success = self.db_handler.insert_exercise_data_local(record)
                                if insert_success:
                                    self.status_signal.emit("Exercise data saved locally.")
                                    logging.info("Data saved locally.")
                                    self.data_updated.emit()
                                else:
                                    self.status_signal.emit("Failed to save exercise data locally.")
                                    logging.error("Failed to save exercise data locally.")
                            else:
                                self.status_signal.emit("No exercise data to save.")
                                logging.warning("No exercise data to save.")

                            self.exercise_analyzer.reset_counters()
                            self.exercise_analyzer = None
                            self.exercise_analysis_active = False
                            self.face_recognition_active = True
                            self.status_signal.emit("Returning to Face Recognition Mode.")
                            logging.info("Switched back to Face Recognition Mode.")

                    self.msleep(10)
                    continue
                except Exception as e:
                    self.status_signal.emit(f"Exercise analysis error: {e}")
                    logging.error(f"Exercise analysis error: {e}")
                    self.msleep(10)
                    continue

            if self.capturing_new_user_data:
                # New User Registration Mode
                try:
                    # Use the FaceRecognizer's internal methods if available
                    # Alternatively, use the aliased external library
                    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)  # Ensure correct color conversion

                    face_locations = fr_lib.face_locations(rgb_small_frame)
                    encodings = fr_lib.face_encodings(rgb_small_frame, face_locations)
                    self.new_user_encodings.extend(encodings)

                    self.frame_signal.emit(display_frame)
                    self.thumbnail_frame_signal.emit(thumb)

                    if len(self.new_user_encodings) >= self.frames_to_capture:
                        self.status_signal.emit(f"Registering user {self.new_user_name}...")
                        logging.info(f"Registering new user: {self.new_user_name}")
                        registration_success = self.face_recognizer.register_new_user(
                            self.new_user_name,
                            self.new_user_encodings
                        )
                        if registration_success:
                            self.status_signal.emit(f"User {self.new_user_name} registered successfully.")
                            logging.info(f"User {self.new_user_name} registered successfully.")
                        else:
                            self.status_signal.emit(f"Failed to register user {self.new_user_name}.")
                            logging.error(f"Failed to register user {self.new_user_name}.")

                        # Reset state after new user registration
                        self.new_user_name = None
                        self.new_user_encodings = []
                        self.capturing_new_user_data = False
                        # Reset face recognition states
                        self.face_recognition_active = True
                        self.unknown_stable_detected = False
                        self.unknown_frames = 0
                        self.known_frames = 0
                        self.last_recognized_user = None

                    self.msleep(10)
                    continue
                except Exception as e:
                    self.status_signal.emit(f"New user registration error: {e}")
                    logging.error(f"New user registration error: {e}")
                    self.msleep(10)
                    continue

            if self.face_recognition_active:
                # Face Recognition Mode
                try:
                    frame_face_processed, face_locations, face_names = self.face_recognizer.recognize_faces(frame)

                    # Draw boxes
                    for ((top, right, bottom, left), name) in zip(face_locations, face_names):
                        top *= 4
                        right *= 4
                        bottom *= 4
                        left *= 4
                        cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
                        cv2.rectangle(display_frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
                        font = cv2.FONT_HERSHEY_DUPLEX
                        cv2.putText(display_frame, name, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)

                    if len(face_names) > 0:
                        if all(n == "Unknown" for n in face_names):
                            self.unknown_frames += 1
                            self.known_frames = 0
                            if self.unknown_frames >= self.UNKNOWN_FRAME_THRESHOLD and not self.unknown_stable_detected:
                                self.status_signal.emit("Stable unknown user detected. Prompting for user name...")
                                logging.info("Stable unknown user detected.")
                                self.unknown_user_detected.emit()
                                self.unknown_stable_detected = True
                        else:
                            # Found a known user
                            self.unknown_frames = 0
                            self.unknown_stable_detected = False
                            recognized_user = [n for n in face_names if n != "Unknown"][0]
                            if recognized_user == self.last_recognized_user:
                                self.known_frames += 1
                            else:
                                self.last_recognized_user = recognized_user
                                self.known_frames = 1

                            if self.known_frames >= self.KNOWN_FRAME_THRESHOLD:
                                # Confirm recognized user
                                logging.info(f"User recognized: {recognized_user}")
                                user_info = self.db_handler.get_member_info(recognized_user)
                                if user_info:
                                    self.user_recognized_signal.emit(user_info)
                                    self.status_signal.emit(f"Face recognized as {recognized_user}, starting exercise analysis.")
                                    logging.info(f"Starting exercise analysis for user: {recognized_user}")
                                    self.current_user_info = user_info
                                    self.exercise_analyzer = ExerciseAnalyzer(
                                        self.exercise_choice,
                                        aruco_detector,
                                        self.db_handler,
                                        user_id=user_info.get("user_id")
                                    )
                                    self.exercise_analysis_active = True
                                    self.face_recognition_active = False
                                else:
                                    self.status_signal.emit(f"Face recognized as {recognized_user}, but no member info found.")
                                    logging.warning(f"No member info found for recognized user {recognized_user}.")
                    else:
                        # No face detected
                        self.unknown_frames = 0
                        self.known_frames = 0
                        self.last_recognized_user = None
                        self.unknown_stable_detected = False

                    self.frame_signal.emit(display_frame)
                    self.thumbnail_frame_signal.emit(thumb)
                except Exception as e:
                    self.status_signal.emit(f"Face recognition error: {e}")
                    logging.error(f"Face recognition error: {e}")

            self.msleep(10)

        # Cleanup method is already handled in the previous response
        def cleanup(self):
            """Handle cleanup operations when stopping the worker."""
            if self.exercise_analyzer:
                try:
                    record = self.exercise_analyzer.update_data()
                    if record:
                        insert_success = self.db_handler.insert_exercise_data_local(record)
                        if insert_success:
                            logging.info("Exercise data saved locally during cleanup.")
                        else:
                            logging.error("Failed to save exercise data locally during cleanup.")
                    else:
                        logging.warning("No exercise data to save during cleanup.")
                except Exception as e:
                    self.status_signal.emit(f"Error updating exercise data during cleanup: {e}")
                    logging.error(f"Error updating exercise data during cleanup: {e}")
            self.data_updated.emit()
