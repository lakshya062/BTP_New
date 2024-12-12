# ui/cameras_overview_page.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QGridLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
import cv2
import math
import logging

class CamerasOverviewPage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Header
        self.header = QLabel("Cameras Overview")
        self.header.setAlignment(Qt.AlignCenter)
        self.header.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        self.layout.addWidget(self.header)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.inner_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(15)
        self.inner_widget.setLayout(self.grid_layout)
        self.scroll_area.setWidget(self.inner_widget)
        self.layout.addWidget(self.scroll_area)

        self.thumbnails = {}
        self.grid_mode = 4  # Default to 4 screens (2x2)

    def set_grid_mode(self, screens):
        """Set the grid layout based on the number of screens."""
        self.grid_mode = screens
        self.relayout_thumbnails()

    def compute_rows_cols(self, count):
        """Compute number of rows and columns based on grid_mode."""
        if self.grid_mode == 2:
            rows = 1
            cols = 2
        elif self.grid_mode == 4:
            rows = 2
            cols = 2
        elif self.grid_mode == 8:
            rows = 2
            cols = 4
        elif self.grid_mode == 16:
            rows = 4
            cols = 4
        else:
            rows = int(math.ceil(math.sqrt(count)))
            cols = rows
        return rows, cols

    def add_camera_display(self, camera_index, exercise):
        """Add a camera thumbnail display."""
        key = (camera_index, exercise)
        if key in self.thumbnails:
            return  # Avoid adding duplicate thumbnails

        # Frame to hold thumbnail and label
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("background-color: #2E2E2E; border: 2px solid #007ACC; border-radius: 8px;")
        v_layout = QVBoxLayout()
        frame.setLayout(v_layout)

        # Thumbnail Label
        label = QLabel(f"{exercise} (cam_{camera_index})")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #FFFFFF; font-size: 12pt; margin-top: 5px;")
        label.setFixedHeight(30)

        # Initial Placeholder Image
        placeholder = QPixmap(320, 180)
        placeholder.fill(Qt.darkGray)
        label_pixmap = QLabel()
        label_pixmap.setPixmap(placeholder)
        label_pixmap.setFixedSize(320, 180)
        label_pixmap.setStyleSheet("border: 1px solid #555555; border-radius: 4px;")

        v_layout.addWidget(label_pixmap)
        v_layout.addWidget(label)

        self.thumbnails[key] = label_pixmap
        self.relayout_thumbnails()

    def remove_camera_display(self, camera_index, exercise):
        """Remove a camera thumbnail display."""
        key = (camera_index, exercise)
        if key in self.thumbnails:
            label = self.thumbnails[key]
            self.grid_layout.removeWidget(label)
            label.deleteLater()
            del self.thumbnails[key]
            self.relayout_thumbnails()

    def clear_thumbnails(self):
        """Clear all camera thumbnails."""
        for key, label in list(self.thumbnails.items()):
            self.grid_layout.removeWidget(label)
            label.deleteLater()
            del self.thumbnails[key]
        self.relayout_thumbnails()

    def relayout_thumbnails(self):
        """Rearrange thumbnails based on the current grid mode."""
        # Remove all widgets from the grid layout
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        count = len(self.thumbnails)
        if count == 0:
            return  # Nothing to layout

        rows, cols = self.compute_rows_cols(count)

        items = list(self.thumbnails.items())

        for idx, ((ci, ex), lbl) in enumerate(items):
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(lbl, row, col)

    def update_thumbnail(self, camera_index, exercise, frame):
        """Update the thumbnail with the latest frame."""
        key = (camera_index, exercise)
        if key not in self.thumbnails:
            return
        label = self.thumbnails[key]
        try:
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            scaled_pix = pix.scaled(label.width(), label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled_pix)
        except Exception as e:
            logging.error(f"Error updating thumbnail for cam_{camera_index}: {e}")
