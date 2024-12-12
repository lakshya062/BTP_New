# ui/main_window.py

import json
import os
import sys
import uuid
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QStatusBar, QPushButton, QHBoxLayout, QComboBox, QInputDialog, QDialog, QLabel
)
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt, QTimer, Slot, QSize
from core.database import DatabaseHandler
from core.face_recognition import FaceRecognizer
from ui.exercise_page import ExercisePage
from ui.profile_page import ProfilePage
from ui.member_list_page import MemberListPage
from ui.cameras_overview_page import CamerasOverviewPage
from ui.add_exercise_dialog import AddExerciseDialog
from ui.home_page import HomePage
import cv2
import logging
from datetime import datetime

def detect_available_cameras(max_cameras=10):
    available_cams = []
    for i in range(max_cameras):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cams.append(i)
            cap.release()
    return available_cams

class MainWindow(QMainWindow):
    CONFIG_FILE = "config.json"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Gym Client System")
        self.setMinimumSize(1600, 1000)
        font = QFont("Segoe UI", 10)
        self.setFont(font)

        # Central Widget and Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        # Database and Face Recognizer Initialization
        self.db_handler = DatabaseHandler()
        self.global_face_recognizer = FaceRecognizer()
        if not self.global_face_recognizer.known_face_encodings:
            QMessageBox.warning(
                self,
                "Face Recognition",
                "No known faces loaded. All detections will be unknown until users are registered."
            )

        self.sync_face_model_with_db()

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setTabsClosable(False)
        self.tabs.setMovable(True)
        self.tabs.setIconSize(QSize(24,24))  # Corrected

        # Initialize Pages
        self.home_page = HomePage(self.db_handler)
        self.profile_page = ProfilePage()
        self.member_list_page = MemberListPage(self.db_handler, self.global_face_recognizer)
        self.cameras_overview_page = CamerasOverviewPage()

        # Add Tabs with Icons
        self.tabs.addTab(self.home_page, QIcon(os.path.join("resources", "icons", "home.png")), "Home")
        self.tabs.addTab(self.profile_page, QIcon(os.path.join("resources", "icons", "profile.png")), "Profile")
        self.tabs.addTab(self.member_list_page, QIcon(os.path.join("resources", "icons", "members.png")), "Members")
        self.tabs.addTab(self.cameras_overview_page, QIcon(os.path.join("resources", "icons", "cameras.png")), "Cameras Overview")

        self.main_layout.addWidget(self.tabs)

        # Controls Layout
        self.controls_layout = QHBoxLayout()
        self.controls_layout.setSpacing(10)
        self.controls_layout.setContentsMargins(10, 10, 10, 10)

        self.add_exercise_button = QPushButton(QIcon(os.path.join("resources", "icons", "add.png")), "Add Exercise")
        self.add_exercise_button.setToolTip("Add a new exercise with a camera")
        self.delete_exercise_button = QPushButton(QIcon(os.path.join("resources", "icons", "delete.png")), "Delete Exercise")
        self.delete_exercise_button.setToolTip("Delete the selected exercise")
        self.start_all_button = QPushButton(QIcon(os.path.join("resources", "icons", "start.png")), "Start All")
        self.start_all_button.setToolTip("Start all exercises")
        self.layout_selector = QComboBox()
        self.layout_selector.addItems(["2 Screens", "4 Screens", "8 Screens", "16 Screens"])
        self.layout_selector.setCurrentIndex(1)
        self.layout_selector.setToolTip("Select Camera Layout")

        # Adding Widgets to Controls Layout
        self.controls_layout.addWidget(self.add_exercise_button)
        self.controls_layout.addWidget(self.delete_exercise_button)
        self.controls_layout.addWidget(self.start_all_button)
        self.controls_layout.addWidget(QLabel("Set Layout:"))
        self.controls_layout.addWidget(self.layout_selector)
        self.controls_layout.addStretch()

        self.main_layout.addLayout(self.controls_layout)

        # Connect Buttons
        self.add_exercise_button.clicked.connect(self.add_exercise_dialog)
        self.delete_exercise_button.clicked.connect(self.delete_current_exercise)
        self.start_all_button.clicked.connect(self.start_all_exercises)
        self.layout_selector.currentIndexChanged.connect(self.change_camera_layout)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Exercise Pages Tracking
        self.exercise_pages = []
        self.load_config()
        self.update_overview_tab()

        # Sync Timer
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_local_data_to_sqlite)
        self.sync_timer.start(60000)

    def sync_face_model_with_db(self):
        for name in self.global_face_recognizer.known_face_names:
            member = self.db_handler.get_member_info(name)
            if not member:
                joined_on = datetime.utcnow().strftime('%Y-%m-%d')
                member_info = {
                    "user_id": str(uuid.uuid4()),
                    "username": name,
                    "email": "NA",
                    "membership": "NA",
                    "joined_on": joined_on
                }
                success = self.db_handler.insert_member_local(member_info)
                if success:
                    logging.info(f"Added {name} to local db from face model.")
                else:
                    logging.error(f"Failed to add {name} to local db.")

    def load_config(self):
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                data = json.load(f)
            exercises = data.get("exercises", [])
            for ex in exercises:
                camera_index = ex["camera_index"]
                exercise = ex["exercise"]
                user_name = ex.get("user_name", None)
                self.add_exercise_page(camera_index, exercise, user_name=user_name, start_immediately=False)
        else:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({"exercises": []}, f, indent=4)

    def save_config(self):
        exercises = []
        for (page, cam_idx, ex, user) in self.exercise_pages:
            exercises.append({"camera_index": cam_idx, "exercise": ex, "user_name": user})
        data = {"exercises": exercises}
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def add_exercise_dialog(self):
        available_cams = detect_available_cameras(max_cameras=10)
        assigned_cams = [cam for (_, cam, _, _) in self.exercise_pages]
        available_cams = [cam for cam in available_cams if cam not in assigned_cams]

        if not available_cams:
            QMessageBox.warning(
                self,
                "No Available Cameras",
                "All available cameras are already assigned to exercises."
            )
            return

        dialog = AddExerciseDialog(available_cams, self)
        if dialog.exec() == QDialog.Accepted:
            cam_text, exercise, user_name = dialog.get_selection()
            camera_index = int(cam_text.replace("cam_", ""))
            self.add_exercise_page(camera_index, exercise, user_name=user_name)
            self.save_config()

    def add_exercise_page(self, camera_index, exercise, user_name=None, start_immediately=True):
        if user_name and user_name.strip():
            member = self.db_handler.get_member_info(user_name)
            if not member:
                joined_on = datetime.utcnow().strftime('%Y-%m-%d')
                member_info = {
                    "user_id": str(uuid.uuid4()),
                    "username": user_name,
                    "email": "NA",
                    "membership": "NA",
                    "joined_on": joined_on
                }
                success = self.db_handler.insert_member_local(member_info)
                if success:
                    self.status_bar.showMessage(f"Added {user_name} to local database.", 5000)
                else:
                    self.status_bar.showMessage(f"Failed to add {user_name} to local database.", 5000)

        exercise_page = ExercisePage(
            self.db_handler,
            camera_index,
            exercise,
            self.global_face_recognizer
        )
        exercise_page.status_message.connect(self.update_status)
        exercise_page.counters_update.connect(self.update_counters)
        exercise_page.user_recognized_signal.connect(self.handle_user_recognized)
        exercise_page.unknown_user_detected.connect(self.prompt_new_user_name)
        exercise_page.worker_started.connect(lambda: self.connect_data_updated_signal(exercise_page))

        tab_label = f"{exercise} (cam_{camera_index})"
        self.tabs.addTab(exercise_page, QIcon(os.path.join("resources", "icons", "exercise.png")), tab_label)
        self.exercise_pages.append((exercise_page, camera_index, exercise, user_name))

        if start_immediately:
            exercise_page.start_exercise()

        self.update_overview_tab()

    @Slot()
    def connect_data_updated_signal(self, exercise_page):
        if exercise_page.worker:
            exercise_page.worker.data_updated.connect(self.sync_local_data_to_sqlite)

    def prompt_new_user_name(self, exercise_page):
        username, ok = QInputDialog.getText(
            self, "New User Registration", "Enter username for the new user:"
        )
        if ok and username.strip():
            username = username.strip()
            exercise_page.start_user_registration(username)
            member_info = {
                "user_id": str(uuid.uuid4()),
                "username": username,
                "email": "NA",
                "membership": "NA",
                "joined_on": datetime.utcnow().strftime('%Y-%m-%d')
            }
            success = self.db_handler.insert_member_local(member_info)
            if success:
                self.status_bar.showMessage(f"Registered new user: {username}", 5000)
                self.global_face_recognizer.reload_model()
                self.member_list_page.load_members()
            else:
                self.status_bar.showMessage(f"Failed to register user: {username}", 5000)
                QMessageBox.warning(self, "Registration Failed", f"Could not register user: {username}")
        else:
            self.status_bar.showMessage("User registration canceled.", 5000)
            QMessageBox.warning(self, "Registration Canceled", "User was not registered.")

    def handle_user_recognized(self, user_info):
        username = user_info.get("username", "Unknown")
        if username != "Unknown":
            member = self.db_handler.get_member_info(username)
            if not member:
                member_info = {
                    "user_id": str(uuid.uuid4()),
                    "username": username,
                    "email": "NA",
                    "membership": "NA",
                    "joined_on": datetime.utcnow().strftime('%Y-%m-%d')
                }
                success = self.db_handler.insert_member_local(member_info)
                if success:
                    self.status_bar.showMessage(f"Added {username} to local database.", 5000)
                    self.global_face_recognizer.reload_model()
                    self.member_list_page.load_members()
                else:
                    self.status_bar.showMessage(f"Failed to add {username} to local database.", 5000)
                    QMessageBox.warning(self, "Registration Failed", f"Could not register user: {username}")
            self.profile_page.update_profile(user_info)

    def delete_current_exercise(self):
        current_idx = self.tabs.currentIndex()
        if current_idx < 4:  # Now first four tabs are Home, Profile, Members, Cameras
            QMessageBox.information(self, "Cannot Delete", "Cannot delete default tabs.")
            return

        reply = QMessageBox.question(
            self, "Delete Exercise",
            "Are you sure you want to delete this exercise?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            widget = self.tabs.widget(current_idx)
            for i, (page, cam_idx, ex, user) in enumerate(self.exercise_pages):
                if page == widget:
                    page.stop_exercise()
                    self.exercise_pages.pop(i)
                    break
            self.tabs.removeTab(current_idx)
            self.save_config()
            self.update_overview_tab()

    def start_all_exercises(self):
        available_cams = detect_available_cameras(max_cameras=10)
        missing = []
        for (page, cam_idx, ex, _) in self.exercise_pages:
            if cam_idx not in available_cams:
                missing.append((cam_idx, ex))

        if missing:
            msg = "Some cameras are not connected:\n"
            for (ci, ex) in missing:
                msg += f"cam_{ci} for exercise {ex}\n"
            msg += "The remaining cameras will be started."
            QMessageBox.warning(self, "Missing Cameras", msg)

        for (page, cam_idx, ex, _) in self.exercise_pages:
            if cam_idx in available_cams:
                if not page.is_exercise_running():
                    page.start_exercise()

        self.update_overview_tab()

    def change_camera_layout(self):
        selected = self.layout_selector.currentText()
        if selected == "2 Screens":
            self.cameras_overview_page.set_grid_mode(2)
        elif selected == "4 Screens":
            self.cameras_overview_page.set_grid_mode(4)
        elif selected == "8 Screens":
            self.cameras_overview_page.set_grid_mode(8)
        elif selected == "16 Screens":
            self.cameras_overview_page.set_grid_mode(16)
        else:
            self.cameras_overview_page.set_grid_mode(4)

    def update_overview_tab(self):
        self.cameras_overview_page.clear_thumbnails()
        for (page, cam_idx, ex, _) in self.exercise_pages:
            self.cameras_overview_page.add_camera_display(cam_idx, ex)
            if page.worker:
                page.worker.thumbnail_frame_signal.connect(
                    lambda frame, ci=cam_idx, exx=ex: self.cameras_overview_page.update_thumbnail(ci, exx, frame)
                )

    def update_status(self, message):
        self.status_bar.showMessage(message, 5000)

    def update_counters(self, reps, sets):
        pass

    def sync_local_data_to_sqlite(self):
        # Already saving directly to SQLite, no extra sync needed.
        pass

    def closeEvent(self, event):
        # Confirm exit
        reply = QMessageBox.question(
            self, 'Confirm Exit',
            "Are you sure you want to exit the application?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # Stop all exercise workers
            for (page, cam_idx, ex, _) in self.exercise_pages[:]:  # Iterate over a copy
                page.stop_exercise()
            # After all exercises have been stopped, proceed
            self.db_handler.close_connections()
            self.sync_local_data_to_sqlite()
            event.accept()
        else:
            event.ignore()
