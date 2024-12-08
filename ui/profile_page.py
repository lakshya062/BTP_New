# ui/profile_page.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

class ProfilePage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.header = QLabel("Profile")
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet("font-size: 20px; font-weight: bold;")

        self.info_label = QLabel("No user recognized.")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("font-size: 16pt;")

        self.layout.addWidget(self.header)
        self.layout.addWidget(self.info_label)
        self.layout.addStretch()

    def update_profile(self, user_info):
        """Update the profile display with user information."""
        username = user_info.get("username", "Unknown")
        email = user_info.get("email", "Unknown")
        membership = user_info.get("membership", "Unknown")
        joined_on = user_info.get("joined_on", "Unknown")
        user_id = user_info.get("user_id", "Unknown")

        profile_text = (
            f"Username: {username}\n"
            f"Email: {email}\n"
            f"Membership: {membership}\n"
            f"Joined On: {joined_on}\n"
            f"User ID: {user_id}"
        )
        self.info_label.setText(profile_text)
