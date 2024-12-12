# ui/home_page.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QFrame, QMessageBox
from PySide6.QtGui import QFont, QIcon
from PySide6.QtCore import Qt
import os

class HomePage(QWidget):
    def __init__(self, db_handler, parent=None):
        super().__init__(parent)
        self.db_handler = db_handler
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Welcome Header
        welcome_label = QLabel("Welcome to Smart Gym Management System")
        welcome_label.setFont(QFont("Segoe UI", 20, QFont.Bold))
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_label.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(welcome_label)

        # Summary Statistics
        summary_frame = QFrame()
        summary_frame.setStyleSheet("background-color: #2E2E2E; border-radius: 8px;")
        summary_layout = QHBoxLayout()
        summary_frame.setLayout(summary_layout)

        # Total Members
        total_members = self.db_handler.get_total_members()
        members_label = QLabel("Total Members")
        members_label.setFont(QFont("Segoe UI", 14))
        members_label.setAlignment(Qt.AlignCenter)
        members_value = QLabel(str(total_members))
        members_value.setFont(QFont("Segoe UI", 16, QFont.Bold))
        members_value.setAlignment(Qt.AlignCenter)
        members_layout = QVBoxLayout()
        members_layout.addWidget(members_label)
        members_layout.addWidget(members_value)
        summary_layout.addLayout(members_layout)

        # Active Exercises
        active_exercises = self.db_handler.get_active_exercises()
        exercises_label = QLabel("Active Exercises")
        exercises_label.setFont(QFont("Segoe UI", 14))
        exercises_label.setAlignment(Qt.AlignCenter)
        exercises_value = QLabel(str(active_exercises))
        exercises_value.setFont(QFont("Segoe UI", 16, QFont.Bold))
        exercises_value.setAlignment(Qt.AlignCenter)
        exercises_layout = QVBoxLayout()
        exercises_layout.addWidget(exercises_label)
        exercises_layout.addWidget(exercises_value)
        summary_layout.addLayout(exercises_layout)

        # Total Sets
        total_sets = self.db_handler.get_total_sets()
        sets_label = QLabel("Total Sets")
        sets_label.setFont(QFont("Segoe UI", 14))
        sets_label.setAlignment(Qt.AlignCenter)
        sets_value = QLabel(str(total_sets))
        sets_value.setFont(QFont("Segoe UI", 16, QFont.Bold))
        sets_value.setAlignment(Qt.AlignCenter)
        sets_layout = QVBoxLayout()
        sets_layout.addWidget(sets_label)
        sets_layout.addWidget(sets_value)
        summary_layout.addLayout(sets_layout)

        # Total Reps
        total_reps = self.db_handler.get_total_reps()
        reps_label = QLabel("Total Reps")
        reps_label.setFont(QFont("Segoe UI", 14))
        reps_label.setAlignment(Qt.AlignCenter)
        reps_value = QLabel(str(total_reps))
        reps_value.setFont(QFont("Segoe UI", 16, QFont.Bold))
        reps_value.setAlignment(Qt.AlignCenter)
        reps_layout = QVBoxLayout()
        reps_layout.addWidget(reps_label)
        reps_layout.addWidget(reps_value)
        summary_layout.addLayout(reps_layout)

        layout.addWidget(summary_frame)

        # Recent Activities
        recent_activities_label = QLabel("Recent Activities")
        recent_activities_label.setFont(QFont("Segoe UI", 14))
        recent_activities_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(recent_activities_label)

        # Recent Activities Table
        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(4)
        self.recent_table.setHorizontalHeaderLabels(["Username", "Exercise", "Sets", "Reps", "Timestamp"])
        self.recent_table.horizontalHeader().setStretchLastSection(True)
        self.recent_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setStyleSheet("QTableWidget { background-color: #2E2E2E; color: #C5C6C7; }")
        self.load_recent_activities()
        layout.addWidget(self.recent_table)

        # Quick Actions
        quick_actions_label = QLabel("Quick Actions")
        quick_actions_label.setFont(QFont("Segoe UI", 14))
        quick_actions_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(quick_actions_label)

        quick_actions_layout = QHBoxLayout()

        # Add Member Button
        add_member_btn = QPushButton(QIcon(os.path.join("resources", "icons", "add_member.png")), "Add Member")
        add_member_btn.setToolTip("Add a new member")
        add_member_btn.setFixedSize(150, 50)
        add_member_btn.clicked.connect(self.add_member)
        quick_actions_layout.addWidget(add_member_btn)

        # Add Exercise Button
        add_exercise_btn = QPushButton(QIcon(os.path.join("resources", "icons", "add_exercise.png")), "Add Exercise")
        add_exercise_btn.setToolTip("Add a new exercise")
        add_exercise_btn.setFixedSize(150, 50)
        add_exercise_btn.clicked.connect(self.add_exercise)
        quick_actions_layout.addWidget(add_exercise_btn)

        # View Reports Button
        view_reports_btn = QPushButton(QIcon(os.path.join("resources", "icons", "reports.png")), "View Reports")
        view_reports_btn.setToolTip("View detailed reports")
        view_reports_btn.setFixedSize(150, 50)
        view_reports_btn.clicked.connect(self.view_reports)
        quick_actions_layout.addWidget(view_reports_btn)

        quick_actions_layout.addStretch()
        layout.addLayout(quick_actions_layout)

        layout.addStretch()

    def load_recent_activities(self):
        """Load recent activities from the database."""
        activities = self.db_handler.get_recent_activities(limit=5)
        self.recent_table.setRowCount(0)
        for activity in activities:
            row = self.recent_table.rowCount()
            self.recent_table.insertRow(row)
            self.recent_table.setItem(row, 0, QTableWidgetItem(activity.get("username", "N/A")))
            self.recent_table.setItem(row, 1, QTableWidgetItem(activity.get("exercise", "N/A").replace('_', ' ').title()))
            self.recent_table.setItem(row, 2, QTableWidgetItem(str(activity.get("set_count", 0))))
            self.recent_table.setItem(row, 3, QTableWidgetItem(str(len(activity.get("rep_data", [])))))
            self.recent_table.setItem(row, 4, QTableWidgetItem(activity.get("timestamp", "N/A")))
        self.recent_table.resizeColumnsToContents()

    def add_member(self):
        """Trigger adding a new member."""
        # This should emit a signal or interact with MainWindow to open Add Member dialog
        QMessageBox.information(self, "Add Member", "Add Member functionality is not implemented yet.")

    def add_exercise(self):
        """Trigger adding a new exercise."""
        # This should emit a signal or interact with MainWindow to open Add Exercise dialog
        QMessageBox.information(self, "Add Exercise", "Add Exercise functionality is not implemented yet.")

    def view_reports(self):
        """Trigger viewing reports."""
        # This should open a reports page or dialog
        QMessageBox.information(self, "View Reports", "View Reports functionality is not implemented yet.")
