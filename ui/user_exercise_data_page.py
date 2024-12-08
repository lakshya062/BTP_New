# ui/user_exercise_data_page.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QMessageBox, QStackedWidget
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
from datetime import datetime


class UserExerciseDataPage(QWidget):
    def __init__(self, db_handler, user_id, embedded=False):
        super().__init__()
        self.db_handler = db_handler
        self.user_id = user_id
        self.embedded = embedded

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.header = QLabel("Exercise Data")
        self.header.setFont(QFont("Arial", 16, QFont.Bold))
        self.header.setAlignment(Qt.AlignCenter)

        # Initialize Stacked Widget
        self.stacked = QStackedWidget()

        # Initialize Pages
        self.init_exercises_page()
        self.init_sessions_page()
        self.init_rep_details_page()

        self.stacked.setCurrentWidget(self.exercises_page)

        self.layout.addWidget(self.header)
        self.layout.addWidget(self.stacked)

    def init_exercises_page(self):
        """Initialize the Exercises List Page."""
        self.exercises_page = QWidget()
        layout = QVBoxLayout()
        self.exercises_page.setLayout(layout)

        label = QLabel("Select an Exercise:")
        label.setFont(QFont("Arial", 14))
        layout.addWidget(label)

        self.exercises_table = QTableWidget()
        self.exercises_table.setColumnCount(1)
        self.exercises_table.setHorizontalHeaderLabels(["Exercise"])
        self.exercises_table.horizontalHeader().setStretchLastSection(True)
        self.exercises_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.exercises_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.exercises_table.setAlternatingRowColors(True)
        self.exercises_table.cellDoubleClicked.connect(self.on_exercise_double_clicked)
        layout.addWidget(self.exercises_table)

        # Back Button (Visible only when embedded)
        if self.embedded:
            self.back_button = QPushButton("Back to Members")
            self.back_button.clicked.connect(self.go_back)
            layout.addWidget(self.back_button, alignment=Qt.AlignRight)

        layout.addStretch()

        self.stacked.addWidget(self.exercises_page)

    def init_sessions_page(self):
        """Initialize the Sessions List Page."""
        self.sessions_page = QWidget()
        layout = QVBoxLayout()
        self.sessions_page.setLayout(layout)

        label = QLabel("Select a Session:")
        label.setFont(QFont("Arial", 14))
        layout.addWidget(label)

        self.sessions_table = QTableWidget()
        # Updated columns: Exercise Name, Sets, Reps, Date, Timestamp
        self.sessions_table.setColumnCount(5)
        self.sessions_table.setHorizontalHeaderLabels(["Exercise Name", "Sets", "Reps", "Date", "Timestamp"])
        self.sessions_table.horizontalHeader().setStretchLastSection(True)
        self.sessions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sessions_table.setAlternatingRowColors(True)
        self.sessions_table.cellDoubleClicked.connect(self.on_session_double_clicked)
        layout.addWidget(self.sessions_table)

        # Hidden column for Session ID
        self.sessions_table.setColumnCount(6)  # 5 visible + 1 hidden
        self.sessions_table.setHorizontalHeaderLabels(["Exercise Name", "Sets", "Reps", "Date", "Timestamp", "Session ID"])
        self.sessions_table.setColumnHidden(5, True)  # Hide the Session ID column

        # Back Button
        self.back_to_exercises_button = QPushButton("Back to Exercises")
        self.back_to_exercises_button.clicked.connect(self.back_to_exercises)
        layout.addWidget(self.back_to_exercises_button, alignment=Qt.AlignRight)

        layout.addStretch()

        self.stacked.addWidget(self.sessions_page)

    def init_rep_details_page(self):
        """Initialize the Rep Details Page."""
        self.rep_details_page = QWidget()
        layout = QVBoxLayout()
        self.rep_details_page.setLayout(layout)

        label = QLabel("Rep Details:")
        label.setFont(QFont("Arial", 14))
        layout.addWidget(label)

        self.rep_table = QTableWidget()
        # Updated columns: Rep Number, Start Angle (°), End Angle (°), Weight (lbs)
        self.rep_table.setColumnCount(4)
        self.rep_table.setHorizontalHeaderLabels(["Rep Number", "Start Angle (°)", "End Angle (°)", "Weight (lbs)"])
        self.rep_table.horizontalHeader().setStretchLastSection(True)
        self.rep_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rep_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rep_table.setAlternatingRowColors(True)
        layout.addWidget(self.rep_table)

        # Back Button
        self.back_to_sessions_button = QPushButton("Back to Sessions")
        self.back_to_sessions_button.clicked.connect(self.back_to_sessions)
        layout.addWidget(self.back_to_sessions_button, alignment=Qt.AlignRight)

        layout.addStretch()

        self.stacked.addWidget(self.rep_details_page)

    def load_exercises(self):
        """Load and display the list of exercises performed by the user."""
        self.exercises_table.setRowCount(0)
        data = self.db_handler.get_exercise_data_for_user(self.user_id)
        # Extract unique exercises
        exercises = sorted(list(set([entry['exercise'] for entry in data])))
        for exercise in exercises:
            row = self.exercises_table.rowCount()
            self.exercises_table.insertRow(row)
            self.exercises_table.setItem(row, 0, QTableWidgetItem(exercise))
        self.exercises_table.resizeColumnsToContents()

    @Slot(int, int)
    def on_exercise_double_clicked(self, row, column):
        """Handle double-click on an exercise to show its sessions."""
        exercise_item = self.exercises_table.item(row, 0)
        if exercise_item:
            self.selected_exercise = exercise_item.text()
            self.load_sessions(self.selected_exercise)
            self.stacked.setCurrentWidget(self.sessions_page)

    def load_sessions(self, exercise):
        """Load and display all sessions for the selected exercise."""
        self.sessions_table.setRowCount(0)
        data = self.db_handler.get_exercise_data_for_user(self.user_id)
        # Filter sessions for the selected exercise
        sessions = [entry for entry in data if entry['exercise'] == exercise]
        # Sort sessions by timestamp descending
        sessions_sorted = sorted(sessions, key=lambda x: x['timestamp'], reverse=True)
        for session in sessions_sorted:
            row = self.sessions_table.rowCount()
            self.sessions_table.insertRow(row)
            self.sessions_table.setItem(row, 0, QTableWidgetItem(session['exercise']))
            self.sessions_table.setItem(row, 1, QTableWidgetItem(str(session['set_count'])))
            # Calculate total reps
            total_reps = sum(session['sets_reps']) if session['sets_reps'] else 0
            self.sessions_table.setItem(row, 2, QTableWidgetItem(str(total_reps)))
            self.sessions_table.setItem(row, 3, QTableWidgetItem(session['date']))
            self.sessions_table.setItem(row, 4, QTableWidgetItem(session['timestamp']))
            # Store session ID in hidden column
            self.sessions_table.setItem(row, 5, QTableWidgetItem(session['id']))
        self.sessions_table.resizeColumnsToContents()

    @Slot(int, int)
    def on_session_double_clicked(self, row, column):
        """Handle double-click on a session to show rep details."""
        session_id_item = self.sessions_table.item(row, 5)  # Hidden ID column
        if session_id_item:
            self.selected_session_id = session_id_item.text()
            self.load_rep_details(self.selected_session_id)
            self.stacked.setCurrentWidget(self.rep_details_page)

    def load_rep_details(self, session_id):
        """Load and display rep details for the selected session."""
        self.rep_table.setRowCount(0)
        data = self.db_handler.get_exercise_data_for_user(self.user_id)
        # Find the session with the given ID
        session = next((entry for entry in data if entry['id'] == session_id), None)
        if not session:
            QMessageBox.warning(self, "Error", "Session data not found.")
            return
        rep_data = session.get('rep_data', [])
        for idx, rep in enumerate(rep_data, start=1):
            row = self.rep_table.rowCount()
            self.rep_table.insertRow(row)
            self.rep_table.setItem(row, 0, QTableWidgetItem(str(idx)))
            self.rep_table.setItem(row, 1, QTableWidgetItem(str(rep.get('start_angle', 'N/A'))))
            self.rep_table.setItem(row, 2, QTableWidgetItem(str(rep.get('end_angle', 'N/A'))))
            self.rep_table.setItem(row, 3, QTableWidgetItem(str(rep.get('weight', 'N/A'))))
        self.rep_table.resizeColumnsToContents()

    def back_to_exercises(self):
        """Navigate back to the Exercises List Page."""
        self.stacked.setCurrentWidget(self.exercises_page)

    def back_to_sessions(self):
        """Navigate back to the Sessions List Page."""
        self.stacked.setCurrentWidget(self.sessions_page)

    def go_back(self):
        """Navigate back to the Members List Page."""
        self.parent().go_back_to_members() if self.embedded else self.close()

    def showEvent(self, event):
        """Override showEvent to load exercises when the page is shown."""
        self.load_exercises()
        super().showEvent(event)
