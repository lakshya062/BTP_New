# ui/add_exercise_dialog.py

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QMessageBox
from PySide6.QtCore import Qt


class AddExerciseDialog(QDialog):
    def __init__(self, available_cams, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Exercise")
        self.setModal(True)
        self.setFixedSize(400, 300)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Camera Selection
        cam_layout = QHBoxLayout()
        cam_label = QLabel("Select Camera:")
        self.cam_combo = QComboBox()
        self.cam_combo.addItems([f"cam_{cam}" for cam in available_cams])
        cam_layout.addWidget(cam_label)
        cam_layout.addWidget(self.cam_combo)

        # Exercise Selection
        exercise_layout = QHBoxLayout()
        exercise_label = QLabel("Select Exercise:")
        self.exercise_combo = QComboBox()
        # Populate with available exercises from config or predefined list
        self.exercise_combo.addItems(["Bicep Curls", "Squats", "Deadlifts", "Bench Press"])  # Example exercises
        exercise_layout.addWidget(exercise_label)
        exercise_layout.addWidget(self.exercise_combo)

        # User Selection
        user_layout = QHBoxLayout()
        user_label = QLabel("Select User:")
        self.user_combo = QComboBox()
        # Populate with existing users from local DB
        if parent:
            members = parent.db_handler.get_all_members_local()
            self.user_combo.addItems([member['username'] for member in members])
        user_layout.addWidget(user_label)
        user_layout.addWidget(self.user_combo)

        # Buttons
        buttons_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.ok_button)
        buttons_layout.addWidget(self.cancel_button)

        self.layout.addLayout(cam_layout)
        self.layout.addLayout(exercise_layout)
        self.layout.addLayout(user_layout)
        self.layout.addStretch()
        self.layout.addLayout(buttons_layout)

        # Connect Buttons
        self.ok_button.clicked.connect(self.validate_and_accept)
        self.cancel_button.clicked.connect(self.reject)

    def validate_and_accept(self):
        """Validate selections before accepting the dialog."""
        if not self.cam_combo.currentText():
            QMessageBox.warning(self, "Input Error", "Please select a camera.")
            return
        if not self.exercise_combo.currentText():
            QMessageBox.warning(self, "Input Error", "Please select an exercise.")
            return
        if not self.user_combo.currentText():
            QMessageBox.warning(self, "Input Error", "Please select a user.")
            return
        self.accept()

    def get_selection(self):
        """Return the selected camera, exercise, and user."""
        cam_text = self.cam_combo.currentText()
        exercise = self.exercise_combo.currentText()
        user = self.user_combo.currentText()
        return cam_text, exercise, user
