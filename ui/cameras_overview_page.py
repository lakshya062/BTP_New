# ui/cameras_overview_page.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QGridLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
import numpy as np
import math


class CamerasOverviewPage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.inner_widget = QWidget()
        self.grid_layout = QGridLayout()
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

        label = QLabel(f"{exercise} (cam_{camera_index})")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("border: 1px solid #81A1C1; margin:5px; font-size:12pt;")
        label.setFixedSize(640, 360)  # Increased thumbnail size
        self.thumbnails[key] = label
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
        rgb_image = frame[..., ::-1].copy()
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        scaled_pix = pix.scaled(label.width(), label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled_pix)
