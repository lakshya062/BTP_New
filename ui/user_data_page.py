# ui/user_data_page.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal


class UserDataPage(QWidget):
    user_selected = Signal(str)  # Emit user_id when clicked

    def __init__(self, db_handler):
        super().__init__()
        self.db_handler = db_handler

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.header = QLabel("All Users")
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet("font-size: 20px; font-weight: bold;")

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Username", "User ID"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_data)

        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.addWidget(self.refresh_button)
        self.buttons_layout.addStretch()

        self.layout.addWidget(self.header)
        self.layout.addWidget(self.table)
        self.layout.addLayout(self.buttons_layout)
        self.layout.addStretch()

        self.load_data()

    def load_data(self):
        """Load all users from 'members' collection and populate the table."""
        members = self.db_handler.get_all_members()
        self.table.setRowCount(0)
        for member in members:
            user_id = member.get("user_id", "N/A")
            username = member.get("username", "Unknown")
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(username))
            self.table.setItem(row, 1, QTableWidgetItem(user_id))
        self.table.resizeColumnsToContents()

    def on_cell_double_clicked(self, row, column):
        """Open UserExerciseDataPage for the selected user."""
        user_id = self.table.item(row, 1).text()
        if user_id:
            self.user_selected.emit(user_id)
