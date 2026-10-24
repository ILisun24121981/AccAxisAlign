# Acc_axis_align/views/errors.py
import os
import sys
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class ErrorsDialog(QDialog):
    """Интерактивное окно блокировки технологической цепочки.

    Позволяет увидеть текущий файл, открыть папку сессии или выбрать другой файл.
    """

    def __init__(self, device_number: str, result_path: Path, lang: str = "Russian", parent=None):
        super().__init__(parent)
        self.result_mode = "close"  # Режим по умолчанию при закрытии окна
        self.selected_file_path = ""
        self.result_path = Path(result_path).resolve()
        self._device_number = device_number

        self.loc = {
            "Russian": {
                "title": "Предупреждение системы калибровки",
                "device_lbl": "Номер прибора:",
                "msg": "<br><b>Калибровка выравнивания осей (axesAlignment) заблокирована!</b><br><br>"
                       "В выбранном файле сессии отсутствует выполненная базовая калибровка акселерометра.<br>"
                       "Убедитесь, что модуль 'AccCalibration' завершил работу со статусом 'Completed'.",
                "btn_change": "Сменить файл калибровки",
                "btn_close": "Закрыть"  # ИСПРАВЛЕНО: Краткое название
            },
            "English": {
                "title": "Calibration System Warning",
                "device_lbl": "Device Number:",
                "msg": "<br><b>Axis alignment calibration (axesAlignment) is blocked!</b><br><br>"
                       "The selected session file lacks a completed baseline accelerometer calibration.<br>"
                       "Ensure that the 'AccCalibration' module has finished with 'Completed' status.",
                "btn_change": "Change Calibration File",
                "btn_close": "Close"  # ИСПРАВЛЕНО: Изменено с "Close Module" на "Close"
            }
        }

        self.lp = self.loc.get(lang, self.loc["English"])
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(self.lp["title"])
        self.setModal(True)
        self.resize(540, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # 1. Номер прибора по центру
        dev_layout = QHBoxLayout()
        dev_layout.addStretch()
        lbl_device = QLabel(
            f"<h2>{self.lp['device_lbl']} <span style='color: #1A237E;'>{self._device_number}</span></h2>")
        lbl_device.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_layout.addWidget(lbl_device)
        dev_layout.addStretch()
        layout.addLayout(dev_layout)

        # 2. Интерактивная ссылка на файл сессии
        filename_only = self.result_path.name if self.result_path.is_file() else "No file selected"
        lbl_link = QLabel(f"<center><a href='#'>{filename_only}</a></center>")
        lbl_link.setOpenExternalLinks(False)
        lbl_link.linkActivated.connect(self._open_containing_folder)
        layout.addWidget(lbl_link)

        # 3. Основной текст предупреждения
        lbl_msg = QLabel(self.lp["msg"])
        lbl_msg.setWordWrap(True)
        layout.addWidget(lbl_msg)

        layout.addSpacing(10)

        # 4. Панель кнопок управления
        btn_layout = QHBoxLayout()

        # Кнопка смены файла: на нее устанавливается дефолтный фокус
        self.btn_change = QPushButton(self.lp["btn_change"])
        self.btn_change.setStyleSheet("font-weight: bold; height: 32px; padding: 0 12px;")
        self.btn_change.setDefault(True)
        self.btn_change.clicked.connect(self._handle_change_file)
        btn_layout.addWidget(self.btn_change)

        btn_layout.addStretch()

        # Кнопка закрытия: стиль изменен на стандартный, убран красный фон
        self.btn_close = QPushButton(self.lp["btn_close"])
        self.btn_close.setStyleSheet("font-weight: bold; height: 32px; min-width: 120px;")
        self.btn_close.clicked.connect(self._handle_close)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def showEvent(self, event):
        """Гарантирует, что при открытии окна фокус принудительно встанет на кнопку смены файла."""
        super().showEvent(event)
        self.btn_change.setFocus()

    def _open_containing_folder(self):
        """Открывает папку с файлом сессии в проводнике операционной системы."""
        folder_path = self.result_path.parent
        if folder_path.exists():
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])

    def _handle_change_file(self) -> None:
        """Вызывает проводник для смены файла калибровочной сессии."""
        file_filter = "JSON Files (*.json)"
        caption = "Выберите файл калибровочной сессии" if self.lp == self.loc[
            "Russian"] else "Select Calibration Session File"

        selected_file, _ = QFileDialog.getOpenFileName(
            self, caption, str(self.result_path.parent), file_filter,
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if selected_file:
            self.selected_file_path = selected_file
            self.result_mode = "change"
            self.accept()

    def _handle_close(self) -> None:
        self.result_mode = "close"
        self.reject()
