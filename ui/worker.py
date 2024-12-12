# worker.py

from datetime import datetime
import cv2
import face_recognition as fr_lib
import mediapipe as mp
import logging
from PySide6.QtCore import QThread, Signal
from core.database import DatabaseHandler
from core.aruco_detection import ArucoDetector
from core.pose_analysis import ExerciseAnalyzer
from core.face_run import FaceRecognizer
from core.config import exercise_config
import math

logging.basicConfig(level=logging.INFO, filename='worker.log',
                    format='%(asctime)s - %(levelname)s - %(message)s')

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose


def draw_text_with_background(frame, text, position, font=cv2.FONT_HERSHEY_SIMPLEX,
                             font_scale=0.6, font_color=(255, 255, 255),
                             bg_color=(0, 0, 0), alpha=0.6, thickness=1):
    """
    Draws text with a semi-transparent background on the frame.

    Args:
        frame (ndarray): The video frame.
        text (str): The text to draw.
        position (tuple): Bottom-left corner of the text (x, y).
        font (int): Font type.
        font_scale (float): Font scale.
        font_color (tuple): Text color in BGR.
        bg_color (tuple): Background color in BGR.
        alpha (float): Transparency factor.
        thickness (int): Thickness of the text.
    """
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = position
    # Create the overlay
    overlay = frame.copy()
    # Define the rectangle coordinates
    cv2.rectangle(overlay, (x, y - text_height - baseline - 5),
                  (x + text_width + 10, y + 5), bg_color, -1)
    # Blend the overlay with the frame
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    # Put the text above the rectangle
    cv2.putText(frame, text, (x + 5, y - 2), font, font_scale, font_color, thickness, cv2.LINE_AA)


def draw_progress_bar(frame, label, current, total, position, bar_size=(200, 15), color=(0, 255, 0)):
    """
    Draws a progress bar on the frame.

    Args:
        frame (ndarray): The video frame.
        label (str): Label for the progress bar.
        current (int): Current progress value.
        total (int): Total value for the progress bar.
        position (tuple): Top-left corner of the progress bar (x, y).
        bar_size (tuple): Size of the progress bar (width, height).
        color (tuple): Color of the progress bar in BGR.
    """
    x, y = position
    width, height = bar_size
    # Draw the border
    cv2.rectangle(frame, (x, y), (x + width, y + height), (255, 255, 255), 1)
    # Calculate the filled width
    filled_width = int((current / total) * (width - 2))
    filled_width = min(filled_width, width - 2)  # Ensure it doesn't exceed
    # Draw the filled part
    cv2.rectangle(frame, (x + 1, y + 1), (x + 1 + filled_width, y + height - 1), color, -1)
    # Put the label above the progress bar
    draw_text_with_background(frame, label, (x, y - 5), font_scale=0.5, bg_color=(50, 50, 50))


class ExerciseWorker(QThread):
    frame_signal = Signal(object)
    thumbnail_frame_signal = Signal(object)
    status_signal = Signal(str)
    counters_signal = Signal(int, int)
    user_recognized_signal = Signal(dict)
    unknown_user_detected = Signal()
    data_updated = Signal()
    audio_feedback_signal = Signal(str)  # New signal for audio feedback

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
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = mp_pose_solution.process(frame_rgb)
                    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

                    if results.pose_landmarks:
                        self.exercise_analyzer.no_pose_frames = 0
                        landmarks = results.pose_landmarks.landmark
                        feedback_texts, _ = self.exercise_analyzer.analyze_exercise_form(landmarks, frame_bgr)

                        # Determine colors based on analysis
                        if not self.exercise_analyzer.stable_start_detected:
                            connection_color = (255, 0, 0)  # Blue
                            landmark_color = (255, 0, 0)
                        elif self.exercise_analyzer.bend_warning_displayed:
                            connection_color = (0, 0, 255)  # Red
                            landmark_color = (0, 0, 255)
                        else:
                            connection_color = (0, 255, 0)  # Green
                            landmark_color = (0, 255, 0)

                        mp_drawing.draw_landmarks(
                            frame_bgr,
                            results.pose_landmarks,
                            mp_pose.POSE_CONNECTIONS,
                            mp_drawing.DrawingSpec(color=connection_color, thickness=2, circle_radius=2),
                            mp_drawing.DrawingSpec(color=landmark_color, thickness=2, circle_radius=2)
                        )

                        # Draw feedback texts
                        for i, text in enumerate(feedback_texts):
                            # Position feedback texts at bottom-left
                            pos_x = 20
                            pos_y = frame_bgr.shape[0] - 100 + (i * 20)
                            if "Warning" in text:
                                color = (0, 0, 255)  # Red for warnings
                            elif "Set complete!" in text or "Ready to start!" in text:
                                color = (0, 255, 255)  # Yellow for encouragement
                            else:
                                color = (255, 255, 255)  # White for normal feedback
                            draw_text_with_background(
                                frame_bgr,
                                text,
                                (pos_x, pos_y),
                                font_scale=0.6,
                                font_color=color,
                                bg_color=(50, 50, 50),
                                alpha=0.6,
                                thickness=1
                            )

                            # Emit audio feedback based on feedback_texts
                            if "Warning" in text:
                                self.audio_feedback_signal.emit(text)  # e.g., "Warning: Incorrect form!"
                            elif "Set complete!" in text or "Ready to start!" in text:
                                self.audio_feedback_signal.emit(text)  # e.g., "Great job!"

                        # Draw rep and set counts at top-right with progress bars
                        reps_per_set = exercise_config[self.exercise_choice].get('reps_per_set', 12)
                        sets_per_session = exercise_config[self.exercise_choice].get('sets_per_session', 5)
                        rep_set_text = f"Reps: {self.exercise_analyzer.rep_count} / {reps_per_set}"
                        set_text = f"Sets: {self.exercise_analyzer.set_count} / {sets_per_session}"
                        frame_width = frame_bgr.shape[1]

                        draw_text_with_background(
                            frame_bgr,
                            rep_set_text,
                            (frame_width - 220, 30),
                            font_scale=0.6,
                            font_color=(255, 255, 255),
                            bg_color=(50, 50, 50),
                            alpha=0.6,
                            thickness=1
                        )
                        draw_text_with_background(
                            frame_bgr,
                            set_text,
                            (frame_width - 220, 60),
                            font_scale=0.6,
                            font_color=(255, 255, 255),
                            bg_color=(50, 50, 50),
                            alpha=0.6,
                            thickness=1
                        )

                        # Draw progress bars at top-right corner
                        # MARKER: Progress Bar Position
                        draw_progress_bar(
                            frame_bgr,
                            "Reps Progress",
                            self.exercise_analyzer.rep_count,
                            reps_per_set,
                            (frame_width - 220, 20),
                            bar_size=(200, 15),
                            color=(0, 255, 0)
                        )
                        draw_progress_bar(
                            frame_bgr,
                            "Sets Progress",
                            self.exercise_analyzer.set_count,
                            sets_per_session,
                            (frame_width - 220, 150),
                            bar_size=(200, 15),
                            color=(0, 255, 0)
                        )

                        # Encourage the user when halfway through a set
                        if self.exercise_analyzer.rep_count == reps_per_set // 2:
                            encouragement_text = "Great halfway mark! Keep going!"
                            draw_text_with_background(
                                frame_bgr,
                                encouragement_text,
                                (frame_width // 2 - 150, 30),
                                font_scale=0.6,
                                font_color=(0, 255, 255),  # Yellow
                                bg_color=(50, 50, 50),
                                alpha=0.6,
                                thickness=1
                            )
                            self.audio_feedback_signal.emit(encouragement_text)

                        # Encourage the user when a set is complete
                        if "Set complete!" in feedback_texts:
                            encouragement_text = "Excellent work! Take a short break."
                            draw_text_with_background(
                                frame_bgr,
                                encouragement_text,
                                (frame_width // 2 - 150, 60),
                                font_scale=0.6,
                                font_color=(0, 255, 255),  # Yellow
                                bg_color=(50, 50, 50),
                                alpha=0.6,
                                thickness=1
                            )
                            self.audio_feedback_signal.emit(encouragement_text)

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
                    self.status_signal.emit("Exercise analysis error.")
                    logging.error(f"Exercise analysis error: {e}")
                    self.msleep(10)
                    continue

            if self.capturing_new_user_data:
                try:
                    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

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
                    self.status_signal.emit("New user registration error.")
                    logging.error(f"New user registration error: {e}")
                    self.msleep(10)
                    continue

            if self.face_recognition_active:
                try:
                    frame_face_processed, face_locations, face_names = self.face_recognizer.recognize_faces(frame)

                    # Draw boxes and names
                    for ((top, right, bottom, left), name) in zip(face_locations, face_names):
                        top *= 4
                        right *= 4
                        bottom *= 4
                        left *= 4
                        cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
                        cv2.rectangle(display_frame, (left, bottom - 20), (right, bottom), (0, 255, 0), cv2.FILLED)
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        cv2.putText(display_frame, name, (left + 5, bottom - 5), font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

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
                    self.status_signal.emit("Face recognition error.")
                    logging.error(f"Face recognition error: {e}")

            self.msleep(10)

        # After loop ends
        self.cleanup()

    def cleanup(self):
        """Handle cleanup operations when stopping the worker."""
        try:
            if self.exercise_analyzer:
                record = self.exercise_analyzer.update_data()
                if record:
                    insert_success = self.db_handler.insert_exercise_data_local(record)
                    if insert_success:
                        logging.info("Exercise data saved locally during cleanup.")
                    else:
                        logging.error("Failed to save exercise data locally during cleanup.")
                else:
                    logging.warning("No exercise data to save during cleanup.")

            # Emit data_updated signal
            self.data_updated.emit()

            # Safely disconnect signals
            try:
                self.frame_signal.disconnect()
                self.thumbnail_frame_signal.disconnect()
                self.status_signal.disconnect()
                self.counters_signal.disconnect()
                self.user_recognized_signal.disconnect()
                self.unknown_user_detected.disconnect()
                self.data_updated.disconnect()
                self.audio_feedback_signal.disconnect()
                logging.info("Successfully disconnected all signals.")
            except TypeError as te:
                logging.error(f"Error disconnecting signals: {te}")
        except Exception as e:
            self.status_signal.emit("Error during cleanup.")
            logging.error(f"Error during cleanup: {e}")
