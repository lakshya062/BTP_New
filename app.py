# app.py
import sys
import os
from PySide6.QtWidgets import QApplication, QMessageBox
from ui.main_window import MainWindow
from PySide6.QtGui import QFont

def main():
    try:
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
        app = QApplication(sys.argv)
        app.setApplicationName("Smart Gym Client System")
        app.setOrganizationName("SmartGym")
        app.setOrganizationDomain("smartgym.com")

        # Increase font size
        font = QFont("Arial")
        font.setPointSize(14)
        app.setFont(font)

        stylesheet_path = os.path.join("resources", "styles.qss")
        if os.path.exists(stylesheet_path):
            with open(stylesheet_path, "r") as f:
                app.setStyleSheet(f.read())
        else:
            # Basic styling if no qss found
            app.setStyleSheet("""
            QWidget {
                background-color: #2E3440;
                color: #D8DEE9;
                font-family: Arial;
                font-size: 14pt;
            }
            QTabWidget::pane {
                border: 1px solid #81A1C1;
                background: #3B4252;
            }
            QTabBar::tab {
                background: #4C566A;
                color: #ECEFF4;
                padding: 8px;
                margin: 2px;
                font-size: 12pt;
            }
            QTabBar::tab:selected {
                background: #81A1C1;
                color: #2E3440;
            }
            QPushButton {
                background-color: #81A1C1;
                color: #2E3440;
                border-radius: 4px;
                padding: 8px 14px;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #88C0D0;
            }
            QGroupBox {
                border: 1px solid #81A1C1;
                border-radius: 5px;
                margin-top: 1em;
                font-weight: bold;
                background-color: #3B4252;
            }
            QLabel {
                color: #D8DEE9;
                font-size: 14pt;
            }
            QTableWidget {
                background-color: #434C5E;
                font-size: 12pt;
            }
            QHeaderView::section {
                background-color: #4C566A;
                color: #ECEFF4;
                font-size: 12pt;
                padding: 5px;
            }
            """)

        window = MainWindow()
        window.show()

        sys.exit(app.exec())
    
    except Exception as e:
        print(f"An error occurred: {e}")
        app = QApplication.instance()
        if app:
            QMessageBox.critical(None, "Error", f"An unexpected error occurred:\n{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
