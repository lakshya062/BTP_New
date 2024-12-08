# ui/edit_member_dialog.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDateEdit, QPushButton, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QDate

class EditMemberDialog(QDialog):
    def __init__(self, current_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Member")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout()
        self.setLayout(layout)

        form_layout = QFormLayout()

        self.username_edit = QLineEdit(current_info.get("username", "N/A"))
        self.email_edit = QLineEdit(current_info.get("email", "N/A"))
        self.membership_combo = QComboBox()
        self.membership_combo.addItems(["Basic", "Premium", "VIP"])
        current_membership = current_info.get("membership", "Basic")
        idx = self.membership_combo.findText(current_membership)
        if idx >= 0:
            self.membership_combo.setCurrentIndex(idx)

        self.joined_edit = QDateEdit()
        self.joined_edit.setDisplayFormat("yyyy-MM-dd")
        joined_on = current_info.get("joined_on", "2023-01-01")
        try:
            jdate = QDate.fromString(joined_on, "yyyy-MM-dd")
            if not jdate.isValid():
                jdate = QDate.currentDate()
        except:
            jdate = QDate.currentDate()
        self.joined_edit.setDate(jdate)
        self.joined_edit.setCalendarPopup(True)

        form_layout.addRow(QLabel("<b>Username:</b>"), self.username_edit)
        form_layout.addRow(QLabel("<b>Email:</b>"), self.email_edit)
        form_layout.addRow(QLabel("<b>Membership:</b>"), self.membership_combo)
        form_layout.addRow(QLabel("<b>Joined On:</b>"), self.joined_edit)

        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
        self.cancel_button = QPushButton("Cancel")
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.cancel_button)

        layout.addLayout(buttons_layout)

        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_updated_info(self):
        return {
            "username": self.username_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "membership": self.membership_combo.currentText(),
            "joined_on": self.joined_edit.date().toString("yyyy-MM-dd"),
        }
