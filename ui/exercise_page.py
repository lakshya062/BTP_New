# ui/exercise_page.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QGroupBox
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, Slot, Signal

from ui.worker import ExerciseWorker


class ExercisePage(QWidget):
    status_message = Signal(str)
    counters_update = Signal(int, int)
    user_recognized_signal = Signal(dict)
    unknown_user_detected = Signal(object)
    worker_started = Signal()

    def __init__(self, db_handler, camera_index, exercise_choice, face_recognizer, parent=None):
        super().__init__(parent)
        self.db_handler = db_handler
        self.camera_index = camera_index
        self.exercise_choice = exercise_choice
        self.face_recognizer = face_recognizer

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.video_label = QLabel("Video Feed")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setFixedSize(960, 540)
        self.video_label.setStyleSheet("background-color: #4C566A; border: 2px solid #81A1C1;")

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(self.start_button)
        self.button_layout.addWidget(self.stop_button)

        self.rep_label = QLabel("Reps: 0")
        self.set_label = QLabel("Sets: 0")
        self.rep_label.setStyleSheet("font-size: 14pt;")
        self.set_label.setStyleSheet("font-size: 14pt;")

        self.counters_layout = QHBoxLayout()
        self.counters_layout.addWidget(self.rep_label)
        self.counters_layout.addWidget(self.set_label)
        self.counters_layout.addStretch()

        self.controls_group = QGroupBox("Controls")
        self.controls_layout = QVBoxLayout()
        self.controls_layout.addLayout(self.button_layout)
        self.controls_layout.addLayout(self.counters_layout)
        self.controls_group.setLayout(self.controls_layout)
        self.controls_group.setStyleSheet("QGroupBox { border: 2px solid #81A1C1; border-radius: 8px; padding: 10px; }")

        self.layout.addWidget(self.video_label, alignment=Qt.AlignCenter)
        self.layout.addWidget(self.controls_group)
        self.layout.addStretch()

        self.worker = None

        self.start_button.clicked.connect(self.start_exercise)
        self.stop_button.clicked.connect(self.stop_exercise)

    def start_exercise(self):
        """Start exercise monitoring."""
        if not self.worker:
            self.worker = ExerciseWorker(
                db_handler=self.db_handler,
                camera_index=self.camera_index,
                exercise_choice=self.exercise_choice,
                face_recognizer=self.face_recognizer
            )
            self.worker.frame_signal.connect(self.update_frame)
            self.worker.status_signal.connect(self.emit_status_message)
            self.worker.counters_signal.connect(self.emit_counters_update)
            self.worker.user_recognized_signal.connect(self.user_recognized_signal.emit)
            self.worker.unknown_user_detected.connect(self.handle_unknown_user_detected)
            self.worker.data_updated.connect(self.handle_data_updated)
            self.worker.thumbnail_frame_signal.connect(self.handle_thumbnail_frame)
            self.worker.start()
            self.worker_started.emit()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_exercise(self):
        """Stop exercise monitoring."""
        if self.worker:
            try:
                self.worker.frame_signal.disconnect(self.update_frame)
                self.worker.status_signal.disconnect(self.emit_status_message)
                self.worker.counters_signal.disconnect(self.emit_counters_update)
                self.worker.user_recognized_signal.disconnect(self.user_recognized_signal.emit)
                self.worker.unknown_user_detected.disconnect(self.handle_unknown_user_detected)
                self.worker.data_updated.disconnect(self.handle_data_updated)
                self.worker.thumbnail_frame_signal.disconnect(self.handle_thumbnail_frame)
            except TypeError:
                pass
            self.worker.request_stop()
            self.worker.wait()
            self.worker = None

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        # Clear video display
        blank_pixmap = QPixmap(self.video_label.size())
        blank_pixmap.fill(Qt.black)
        self.video_label.setPixmap(blank_pixmap)

    def is_exercise_running(self):
        """Check if the exercise is currently running."""
        return self.worker is not None

    @Slot(object)
    def update_frame(self, frame):
        """Update the video display with the latest frame."""
        try:
            rgb_image = frame[..., ::-1].copy()
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            scaled_pix = pix.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.video_label.setPixmap(scaled_pix)
        except Exception as e:
            self.emit_status_message(f"Error updating frame: {e}")

    @Slot(str)
    def emit_status_message(self, message):
        """Emit status messages."""
        self.status_message.emit(message)

    @Slot(int, int)
    def emit_counters_update(self, reps, sets):
        """Update rep and set counters."""
        self.counters_update.emit(reps, sets)
        self.rep_label.setText(f"Reps: {reps}")
        self.set_label.setText(f"Sets: {sets}")

    @Slot(object)
    def handle_thumbnail_frame(self, frame):
        """Optional handling for thumbnails."""
        pass

    @Slot()
    def handle_unknown_user_detected(self):
        """
        Handle when the worker detects a stable unknown user.
        Emit a signal to main_window to prompt for user name.
        """
        self.unknown_user_detected.emit(self)

    @Slot()
    def handle_data_updated(self):
        """Handle the data_updated signal to notify MainWindow for syncing."""
        self.emit_status_message("Exercise data saved locally.")

    def start_user_registration(self, user_name):
        """
        Called by MainWindow after user name is provided.
        Instructs worker to start recording face data for the new user.
        """
        if self.worker:
            self.worker.start_record_new_user(user_name)
