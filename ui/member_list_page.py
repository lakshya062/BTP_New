# ui/member_list_page.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QHBoxLayout, QLabel, QStackedWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from ui.user_exercise_data_page import UserExerciseDataPage


class MemberListPage(QWidget):
    def __init__(self, db_handler, face_recognizer):
        super().__init__()
        self.db_handler = db_handler
        self.face_recognizer = face_recognizer

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.header = QLabel("Members")
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet("font-size: 20px; font-weight: bold;")

        self.stacked = QStackedWidget()

        self.members_widget = QWidget()
        self.members_layout = QVBoxLayout()
        self.members_widget.setLayout(self.members_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Username", "Email", "Membership", "Joined On", "User ID"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_members)

        self.delete_button = QPushButton("Delete Member")
        self.delete_button.clicked.connect(self.delete_member)

        self.members_buttons_layout = QHBoxLayout()
        self.members_buttons_layout.addWidget(self.refresh_button)
        self.members_buttons_layout.addWidget(self.delete_button)
        self.members_buttons_layout.addStretch()

        self.members_layout.addWidget(self.header)
        self.members_layout.addWidget(self.table)
        self.members_layout.addLayout(self.members_buttons_layout)
        self.members_layout.addStretch()

        self.stacked.addWidget(self.members_widget)

        self.user_data_container = QWidget()
        self.user_data_layout = QVBoxLayout()
        self.user_data_container.setLayout(self.user_data_layout)
        self.stacked.addWidget(self.user_data_container)

        self.layout.addWidget(self.stacked)
        self.load_members()

    def load_members(self):
        """Load members from the database and populate the table."""
        members = self.db_handler.get_all_members()  # Ensure this calls the local method
        self.table.setRowCount(0)
        for m in members:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(m.get("username","N/A")))
            self.table.setItem(row, 1, QTableWidgetItem(m.get("email","NA")))
            self.table.setItem(row, 2, QTableWidgetItem(m.get("membership","NA")))
            self.table.setItem(row, 3, QTableWidgetItem(m.get("joined_on","N/A")))
            self.table.setItem(row, 4, QTableWidgetItem(m.get("user_id","")))
        self.table.resizeColumnsToContents()
        self.stacked.setCurrentIndex(0)

    def on_cell_double_clicked(self, row, column):
        """Show user exercise data in the same page using the stacked widget."""
        user_id = self.table.item(row,4).text()
        if user_id:
            for i in reversed(range(self.user_data_layout.count())):
                widget = self.user_data_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)

            user_data_page = UserExerciseDataPage(self.db_handler, user_id, embedded=True)
            # Connect the back_button signal to go_back_to_members
            if hasattr(user_data_page, 'back_button'):
                user_data_page.back_button.clicked.connect(self.go_back_to_members)
            else:
                # Handle the case where back_button might not be present
                pass
            self.user_data_layout.addWidget(user_data_page)

            self.stacked.setCurrentWidget(self.user_data_container)

    def go_back_to_members(self):
        """Navigate back to the Members List Page."""
        self.stacked.setCurrentIndex(0)

    def delete_member(self):
        """Delete the selected member(s) from DB and face recognition model."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Delete Member", "Please select a member to delete.")
            return

        reply = QMessageBox.question(
            self, "Delete Member", "Are you sure you want to delete the selected member(s)? This will also delete all associated exercise data.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for index in sorted(selected_rows, reverse=True):
                username = self.table.item(index.row(), 0).text()
                success = self.db_handler.delete_member_local(username)  # Ensure this calls the local method
                if success:
                    delete_success = self.face_recognizer.delete_user_from_model(username)
                    if delete_success:
                        QMessageBox.information(self, "Delete Member", f"Member '{username}' deleted successfully.")
                    else:
                        QMessageBox.warning(self, "Delete Member", f"Failed to delete member from face model: {username}")
                    self.table.removeRow(index.row())
                else:
                    QMessageBox.warning(self, "Delete Member", f"Failed to delete member: {username}")
            self.load_members()
