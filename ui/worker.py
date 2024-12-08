# ui/worker.py

from datetime import datetime
import time
import cv2
import face_recognition
import mediapipe as mp
import numpy as np
import os
import uuid
import logging
from PySide6.QtCore import QThread, Signal, Slot
from core.database import DatabaseHandler
from core.aruco_detection import ArucoDetector
from core.pose_analysis import ExerciseAnalyzer
from core.face_recognition import FaceRecognizer
from core.config import exercise_config

# Configure logging
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
    unknown_user_detected = Signal()  # Signal emitted when stable unknown detected
    data_updated = Signal()  # Signal to notify data update

    def __init__(self, db_handler, camera_index, exercise_choice='bicep_curl', face_recognizer=None, parent=None):
        super().__init__(parent)
        self.db_handler = db_handler  # Shared DatabaseHandler with thread-local connections
        self.exercise_choice = exercise_choice
        self.face_recognizer = face_recognizer
        self.stop_requested = False
        self.camera_index = camera_index

        # Unknown user handling
        self.unknown_frames = 0
        self.UNKNOWN_FRAME_THRESHOLD = 50
        self.new_user_name = None
        self.new_user_encodings = []
        self.capturing_new_user_data = False
        self.frames_to_capture = 100  # Number of frames to capture for new user

        # State flags
        self.face_recognition_active = True
        self.exercise_analysis_active = False
        self.exercise_analyzer = None
        self.current_user_info = None

    def request_stop(self):
        """Request the thread to stop."""
        self.stop_requested = True
        logging.info("Stop requested for ExerciseWorker.")

    def start_record_new_user(self, user_name):
        """
        Called by ExercisePage after main_window obtains user name.
        Start capturing frames for this new user.
        """
        self.new_user_name = user_name
        self.new_user_encodings = []
        self.capturing_new_user_data = True
        self.status_signal.emit(f"Capturing face data for {user_name}. Please wait...")
        logging.info(f"Started capturing face data for new user: {user_name}")

    def run(self):
        """Main loop of the worker."""
        cap = None
        mp_pose_solution = None
    
        aruco_detector = ArucoDetector(dict_type="DICT_5X5_100")
        exercises = list(exercise_config.keys())
        if self.exercise_choice not in exercises:
            self.status_signal.emit(f"Exercise '{self.exercise_choice}' not configured. Selecting default exercise.")
            logging.warning(f"Exercise '{self.exercise_choice}' not configured. Selecting default.")
            self.exercise_choice = exercises[0] if exercises else None

        if not self.exercise_choice:
            self.status_signal.emit("No exercises configured.")
            logging.error("No exercises configured. Worker is terminating.")
            return

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.status_signal.emit(f"Error: Could not open camera {self.camera_index}.")
            logging.error(f"Could not open camera {self.camera_index}.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        logging.info(f"Camera {self.camera_index} initialized with resolution 1280x720.")

        mp_pose_solution = mp_pose.Pose(min_detection_confidence=0.5,
                                        min_tracking_confidence=0.5,
                                        model_complexity=1)

        unknown_stable_detected = False
        last_face_recognized_time = None
        recognized_face_duration_threshold = 1.0  # Seconds
        occlusion_timeout = 3.0  # Seconds

        while not self.stop_requested:
            ret, frame = cap.read()
            if not ret:
                self.status_signal.emit("Failed to capture frame from camera.")
                logging.error("Failed to capture frame from camera.")
                break

            display_frame = frame.copy()

            if self.face_recognition_active and not self.capturing_new_user_data:
                # Face Recognition Mode
                face_recognition_result = self.face_recognizer.recognize_faces(frame)
                frame_face_processed, face_locations, face_names = face_recognition_result

                # Draw boxes around faces
                for ((top, right, bottom, left), name) in zip(face_locations, face_names):
                    top *= 4
                    right *= 4
                    bottom *= 4
                    left *= 4
                    cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.rectangle(display_frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)
                    font = cv2.FONT_HERSHEY_DUPLEX
                    cv2.putText(display_frame, name, (left + 6, bottom - 6), font, 0.8, (255, 255, 255), 1)

                if all(n == "Unknown" for n in face_names) and face_locations:
                    self.unknown_frames += 1
                    if self.unknown_frames >= self.UNKNOWN_FRAME_THRESHOLD and not unknown_stable_detected:
                        # Stable unknown detected, notify main UI
                        self.status_signal.emit("Stable unknown user detected. Prompting for user name...")
                        logging.info("Stable unknown user detected.")
                        self.unknown_user_detected.emit()
                        unknown_stable_detected = True
                else:
                    self.unknown_frames = 0
                    unknown_stable_detected = False

                # If a known user is recognized for enough duration
                if face_locations and not all(n == "Unknown" for n in face_names):
                    if last_face_recognized_time is None:
                        last_face_recognized_time = time.time()
                        logging.debug("Known user detected, starting timer.")
                    elif time.time() - last_face_recognized_time >= recognized_face_duration_threshold:
                        self.face_recognition_active = False
                        username = [n for n in face_names if n != "Unknown"][0]
                        logging.info(f"User recognized: {username}")
                        user_info = self.db_handler.get_member_info(username)
                        if user_info:
                            self.user_recognized_signal.emit(user_info)
                            self.status_signal.emit(f"Face recognized as {username}, starting exercise analysis.")
                            logging.info(f"Starting exercise analysis for user: {username}")
                            self.current_user_info = user_info
                            # Initialize ExerciseAnalyzer with valid user_id
                            self.exercise_analyzer = ExerciseAnalyzer(
                                self.exercise_choice,
                                aruco_detector,
                                self.db_handler,
                                user_id=user_info.get("user_id")
                            )
                            # self.exercise_analyzer.start_analysis()
                            self.exercise_analysis_active = True
                        else:
                            self.status_signal.emit(f"Face recognized as {username}, but no member info found.")
                            logging.warning(f"User info not found for recognized user: {username}")
                else:
                    last_face_recognized_time = None

                self.frame_signal.emit(display_frame)
                thumb = cv2.resize(display_frame, (160, 90), interpolation=cv2.INTER_AREA)
                self.thumbnail_frame_signal.emit(thumb)

            elif self.capturing_new_user_data:
                # New User Registration Mode
                face_locations = face_recognition.face_locations(
                    cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                )
                encodings = face_recognition.face_encodings(
                    cv2.resize(frame, (0, 0), fx=0.25, fy=0.25),
                    face_locations
                )
                self.new_user_encodings.extend(encodings)
                logging.debug(f"Captured {len(self.new_user_encodings)} face encodings for new user.")

                if len(self.new_user_encodings) >= self.frames_to_capture:
                    # Register the new user
                    self.status_signal.emit(f"Registering user {self.new_user_name}...")
                    logging.info(f"Registering new user: {self.new_user_name}")
                    registration_success = self.face_recognizer.register_new_user(
                        self.new_user_name,
                        self.new_user_encodings
                    )
                    if registration_success:
                        self.status_signal.emit(f"User {self.new_user_name} registered successfully.")
                        logging.info(f"User {self.new_user_name} registered successfully.")
                        # Insert into local DB
                        member_info = {
                            "user_id": str(uuid.uuid4()),
                            "username": self.new_user_name,
                            "email": "NA",
                            "membership": "NA",
                            "joined_on": datetime.utcnow().strftime('%Y-%m-%d')
                        }
                        insert_success = self.db_handler.insert_member_local(member_info)
                        if insert_success:
                            self.status_signal.emit(f"User {self.new_user_name} added to local database.")
                            logging.info(f"User {self.new_user_name} added to local database.")
                        else:
                            self.status_signal.emit(f"Failed to add user {self.new_user_name} to local database.")
                            logging.error(f"Failed to add user {self.new_user_name} to local database.")
                        self.data_updated.emit()  # Emit signal to sync data if needed
                    else:
                        self.status_signal.emit(f"Failed to register user {self.new_user_name}.")
                        logging.error(f"Failed to register user {self.new_user_name}.")
                    self.new_user_name = None
                    self.new_user_encodings = []
                    self.capturing_new_user_data = False
                    self.face_recognition_active = True

                # Display the frame while capturing
                self.frame_signal.emit(display_frame)
                thumb = cv2.resize(display_frame, (160, 90), interpolation=cv2.INTER_AREA)
                self.thumbnail_frame_signal.emit(thumb)

            elif self.exercise_analysis_active and self.exercise_analyzer:
                # Exercise Analysis Mode
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = mp_pose_solution.process(frame_rgb)
                    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

                    if results.pose_landmarks:
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

                        frame_landmarks = np.zeros_like(frame_bgr)
                        mp_drawing.draw_landmarks(
                            frame_landmarks,
                            results.pose_landmarks,
                            mp_pose.POSE_CONNECTIONS,
                            mp_drawing.DrawingSpec(color=connection_color, thickness=3, circle_radius=2),
                            mp_drawing.DrawingSpec(color=landmark_color, thickness=2, circle_radius=2)
                        )

                        overlay = cv2.addWeighted(frame_bgr, 0.5, frame_landmarks, 0.5, 0)

                        for i, text in enumerate(feedback_texts):
                            color = (0, 255, 0)
                            if "Warning" in text:
                                color = (0, 0, 255)
                            cv2.putText(frame_landmarks, text, (10, 30 + (i * 30)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                        rep_set_text = f"Reps: {self.exercise_analyzer.rep_count} | Sets: {self.exercise_analyzer.set_count}"
                        cv2.putText(frame_landmarks, rep_set_text, (10, 470),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                        final_frame = cv2.addWeighted(overlay, 0.8, frame_landmarks, 1.0, 0)
                        self.frame_signal.emit(final_frame)
                        thumb = cv2.resize(final_frame, (160, 90), interpolation=cv2.INTER_AREA)
                        self.thumbnail_frame_signal.emit(thumb)
                        self.counters_signal.emit(self.exercise_analyzer.rep_count,
                                                  self.exercise_analyzer.set_count)
                    else:
                        self.exercise_analyzer.no_pose_frames += 1
                        if self.exercise_analyzer.no_pose_frames >= occlusion_timeout:
                            self.status_signal.emit("Person exited the frame, updating database...")
                            logging.info("Person exited the frame. Updating database.")
                            record = self.exercise_analyzer.update_data()
                            if record:
                                insert_success = self.db_handler.insert_exercise_data_local(record)  # Correct method
                                if insert_success:
                                    self.status_signal.emit("Exercise data saved locally.")
                                    logging.info("Exercise data saved locally.")
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
                            blank_frame = np.zeros_like(frame)
                            self.frame_signal.emit(blank_frame)
                            blank_thumb = np.zeros((90, 160, 3), dtype=np.uint8)
                            self.thumbnail_frame_signal.emit(blank_thumb)

                except Exception as e:
                    self.status_signal.emit(f"Exercise analysis error: {e}")
                    logging.error(f"Exercise analysis error: {e}")
                    # Continue running without stopping the worker

            else:
                # No active mode, display the frame
                self.frame_signal.emit(display_frame)
                thumb = cv2.resize(display_frame, (160, 90), interpolation=cv2.INTER_AREA)
                self.thumbnail_frame_signal.emit(thumb)

            self.msleep(10)

        def cleanup(self):
            """Cleanup resources when thread is stopping."""
            if self.exercise_analyzer:
                try:
                    record = self.exercise_analyzer.update_data()
                    if record:
                        insert_success = self.db_handler.insert_exercise_data_local(record)
                        if insert_success:
                            logging.info("Exercise data saved locally during cleanup.")
                        else:
                            logging.error("Failed to save exercise data locally during cleanup.")
                except Exception as e:
                    self.status_signal.emit(f"Error updating exercise data during cleanup: {e}")
                    logging.error(f"Error updating exercise data during cleanup: {e}")
            self.data_updated.emit()
