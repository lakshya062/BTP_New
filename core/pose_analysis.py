# core/pose_analysis.py

import os
import cv2
import mediapipe as mp
import numpy as np
import time
import json
from datetime import datetime
import uuid

from .utils import calculate_joint_angle, calculate_bend_angle
from .config import exercise_config

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

ARUCO_DICT = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
}

arucoDict = cv2.aruco.Dictionary_get(ARUCO_DICT["DICT_5X5_100"])
arucoParams = cv2.aruco.DetectorParameters_create()

class ExerciseAnalyzer:
    def __init__(self, exercise, aruco_detector, database_handler, user_id=None):
        """
        Initialize the ExerciseAnalyzer with specific exercise settings.

        Args:
            exercise (str): The type of exercise to analyze.
            aruco_detector: ArucoDetector instance.
            database_handler: DatabaseHandler instance.
            user_id (str): Unique user ID for this user.
        """
        self.exercise = exercise
        self.aruco_detector = aruco_detector
        self.database_handler = database_handler
        self.user_id = user_id
        self.reset_counters()

    def reset_counters(self):
        """Reset all counters and flags."""
        self.rep_count = 0
        self.set_count = 0
        self.stable_start_detected = False
        self.stable_frames = 0
        self.sets_reps = []
        self.rep_data = []
        self.rep_start_angle = None
        self.rep_end_angle = None
        self.current_weight = 0
        self.bend_warning_displayed = False
        self.person_in_frame = False
        self.no_pose_frames = 0

        # State machine for counting reps reliably
        # 0 = waiting for stable start + down
        # 1 = down detected, waiting for up
        # 2 = up detected, waiting to return down to count rep
        self.rep_state = 0

        # Timestamp for the current exercise session
        self.exercise_start_time = None

    def detect_bend(self, landmarks):
        try:
            left_shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                             landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
            right_shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x,
                              landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
            left_hip = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x,
                        landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
            right_hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x,
                         landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]

            angle_left = calculate_bend_angle(left_shoulder, left_hip)
            angle_right = calculate_bend_angle(right_shoulder, right_hip)
            angle = (angle_left + angle_right) / 2
            tolerance = 3
            if angle > tolerance:
                return True, 'back'
            elif angle < -tolerance:
                return True, 'front'
            else:
                return False, None
        except Exception as e:
            print(f"Error in detect_bend: {e}")
            return False, None

    def analyze_exercise_form(self, landmarks, frame):
        feedback_texts = []

        if exercise_config[self.exercise].get('bend_detection'):
            bend_detected, bend_type = self.detect_bend(landmarks)
            if bend_detected:
                if bend_type == 'back':
                    feedback_texts.append("Warning: Keep your back straight!")
                elif bend_type == 'front':
                    feedback_texts.append("Warning: Do not bend forward!")
                self.bend_warning_displayed = True
            else:
                self.bend_warning_displayed = False

        for angle_name, points in exercise_config[self.exercise]['angles'].items():
            try:
                p1 = [landmarks[points[0].value].x, landmarks[points[0].value].y]
                p2 = [landmarks[points[1].value].x, landmarks[points[1].value].y]
                p3 = [landmarks[points[2].value].x, landmarks[points[2].value].y]
                angle = calculate_joint_angle(p1, p2, p3)
            except Exception as e:
                print(f"Error calculating angle for {angle_name}: {e}")
                angle = 0

            corners, ids, rejected = cv2.aruco.detectMarkers(frame, arucoDict, parameters=arucoParams)
            if ids is not None:
                try:
                    self.current_weight = int(ids[0][0])
                except (IndexError, ValueError):
                    self.current_weight = 0
                    print("We are not at correct place")
            else:
                self.current_weight = 0

            # Stability detection with improved logic to prevent double counting
            if not self.stable_start_detected:
                down_min, down_max = exercise_config[self.exercise]['down_range']
                if down_min <= angle <= down_max:
                    self.stable_frames += 1
                    if self.stable_frames > 30:
                        self.stable_start_detected = True
                        self.exercise_start_time = datetime.utcnow().isoformat()
                        feedback_texts.append("Ready to start!")
                        self.rep_state = 1  # Now we wait for up after starting from down
                else:
                    self.stable_frames = max(0, self.stable_frames - 1)
                continue

            # Rep counting logic with state machine
            down_min, down_max = exercise_config[self.exercise]['down_range']
            up_min, up_max = exercise_config[self.exercise]['up_range']

            if self.rep_state == 1:
                # Waiting for up
                if up_min <= angle <= up_max:
                    self.rep_state = 2
                    self.rep_start_angle = angle  # Starting angle of rep
            elif self.rep_state == 2:
                # Waiting to return down
                if down_min <= angle <= down_max:
                    self.rep_state = 1
                    self.rep_count += 1

                    # Capture ending angle
                    self.rep_end_angle = angle

                    # Record rep data with angles
                    rep_info = {
                        "start_angle": self.rep_start_angle,
                        "end_angle": self.rep_end_angle,
                        "weight": int(self.current_weight)
                    }
                    self.rep_data.append(rep_info)

                    # Log the rep
                    print(f"Rep {self.rep_count}: Start Angle = {self.rep_start_angle}, End Angle = {self.rep_end_angle}, Weight = {self.current_weight}")

            # Determine if a set is complete
            reps_per_set = exercise_config[self.exercise].get('reps_per_set', 12)
            if self.rep_count >= reps_per_set:
                self.sets_reps.append(self.rep_count)
                self.set_count += 1
                self.rep_count = 0
                self.last_update_time = time.time()

            feedback_text = f"{angle_name.replace('_', ' ').title()}: {int(angle)}°"
            feedback_texts.append(feedback_text)

        if self.current_weight > 0:
            feedback_texts.append(f"Detected Weight: {self.current_weight} lbs")

        return feedback_texts

    def update_data(self):
        """Prepare exercise data for saving to the local database."""
        try:
            if self.rep_count > 0:
                self.sets_reps.append(self.rep_count)
            data = {
                'set_count': self.set_count,
                'sets_reps': [int(rep) for rep in self.sets_reps],
                'rep_data': [{"start_angle": rep['start_angle'], "end_angle": rep['end_angle'], "weight": int(rep['weight'])} for rep in self.rep_data],
            }

            # Prepare the record
            record = {
                'id': str(uuid.uuid4()),
                'user_id': self.user_id,
                'exercise': self.exercise,
                'set_count': self.set_count,
                'sets_reps': data['sets_reps'],
                'rep_data': data['rep_data'],
                'timestamp': self.exercise_start_time,
                'date': datetime.utcnow().strftime('%Y-%m-%d')
            }

            # Reset counters after preparing data
            self.reset_counters()

            # Insert into the database
            insert_success = self.database_handler.insert_exercise_data_local(record)

            if insert_success:
                return record
            else:
                return None

        except Exception as e:
            print(f"Error updating exercise data: {e}")
            return None
