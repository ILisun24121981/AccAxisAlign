# Acc_axis_align/views/SettingsDialog.py
import os
from pathlib import Path
from typing import Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QPushButton, QFileDialog, QApplication
)


class SettingsDialog(QDialog):
    """Окно конфигурации параметров среды с раздельным выбором папок загрузки и сохранения.

    Поддерживает динамический перевод интерфейса на лету при изменении языка.
    """

    def __init__(self, current_settings: Dict[str, Any], parent=None):
        super().__init__(parent)

        # Полный словарь локализации окна настроек
        self.loc = {
            "Russian": {
                "title": "Настройки модуля выравнивания осей",
                "lbl_lang": "Язык интерфейса:",
                "lbl_save_path": "Папка сохранения результатов (Save Folder):",
                "lbl_load_path": "Папка исходных калибровок (Load Folder):",
                "lbl_norm": "Значение нормы (g_norm):",
                "btn_browse": "Обзор...",
                "btn_save": "Сохранить",
                "btn_cancel": "Отмена"
            },
            "English": {
                "title": "Calibration Module Settings",
                "lbl_lang": "Interface Language:",
                "lbl_save_path": "Result Save Directory:",
                "lbl_load_path": "Calibration Load Directory:",
                "lbl_norm": "Norm Value (g_norm):",
                "btn_browse": "Browse...",
                "btn_save": "Save Settings",
                "btn_cancel": "Cancel"
            }
        }

        # Начальное определение и валидация языка
        raw_lang = str(current_settings.get("Language", "Russian")).strip()
        self.lang = "Russian" if raw_lang.startswith(("Rus", "rus")) else "English"
        self.user_decision = "reject"

        self.resize(540, 310)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # 1. Выбор Языка
        self.lbl_lang = QLabel()
        layout.addWidget(self.lbl_lang)
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["English", "Russian"])
        self.combo_lang.setCurrentText("Russian" if self.lang == "Russian" else "English")
        self.combo_lang.currentTextChanged.connect(self._handle_language_change)
        layout.addWidget(self.combo_lang)

        # 2. Выбор Папки СОХРАНЕНИЯ результатов
        self.lbl_save_path = QLabel()
        layout.addWidget(self.lbl_save_path)
        save_layout = QHBoxLayout()
        self.le_save_path = QLineEdit(str(current_settings.get("Acc Axis Align Calibration Result Folder", "")))
        self.btn_browse_save = QPushButton()
        self.btn_browse_save.clicked.connect(self._handle_browse_save)
        save_layout.addWidget(self.le_save_path)
        save_layout.addWidget(self.btn_browse_save)
        layout.addLayout(save_layout)

        # 3. Выбор Папки ЗАГРУЗКИ исходных калибровок
        self.lbl_load_path = QLabel()
        layout.addWidget(self.lbl_load_path)
        load_layout = QHBoxLayout()
        self.le_load_path = QLineEdit(str(current_settings.get("Acc Calibration Result Folder", "")))
        self.btn_browse_load = QPushButton()
        self.btn_browse_load.clicked.connect(self._handle_browse_load)
        load_layout.addWidget(self.le_load_path)
        load_layout.addWidget(self.btn_browse_load)
        layout.addLayout(load_layout)

        # 4. Физическая Норма
        self.lbl_norm = QLabel()
        layout.addWidget(self.lbl_norm)
        self.le_norm = QLineEdit(str(current_settings.get("Norm Value", 1000.628)))
        layout.addWidget(self.le_norm)

        layout.addSpacing(10)

        # Кнопки Управления
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton()
        self.btn_save.setStyleSheet("background-color: #27ae60; font-weight: bold; height: 30px; color: white;")
        self.btn_save.clicked.connect(self._handle_save)

        self.btn_cancel = QPushButton()
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        # Вызываем первичную отрисовку текстов элементов интерфейса
        self._retranslate_ui()

        # Центрирование диалогового окна на экране
        app = QApplication.instance()
        screen = app.primaryScreen().geometry() if app else None
        if screen:
            self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def _retranslate_ui(self) -> None:
        """Динамически переводит текстовые метки интерфейса на выбранный язык."""
        lp = self.loc.get(self.lang, self.loc["English"])

        self.setWindowTitle(lp["title"])
        self.lbl_lang.setText(f"<b>{lp['lbl_lang']}</b>")
        self.lbl_save_path.setText(f"<b>{lp['lbl_save_path']}</b>")
        self.lbl_load_path.setText(f"<b>{lp['lbl_load_path']}</b>")
        self.lbl_norm.setText(f"<b>{lp['lbl_norm']}</b>")
        self.btn_browse_save.setText(lp["btn_browse"])
        self.btn_browse_load.setText(lp["btn_browse"])
        self.btn_save.setText(lp["btn_save"])
        self.btn_cancel.setText(lp["btn_cancel"])

    def _handle_language_change(self, selected_text: str) -> None:
        """Слот мгновенного перевода элементов формы при смене значения в комбобоксе."""
        self.lang = selected_text
        self._retranslate_ui()

    def _handle_browse_save(self) -> None:
        """Вызывает проводник ОС для выбора директории сохранения результатов."""
        raw_path = self.le_save_path.text()
        start_dir = raw_path if Path(raw_path).exists() else os.getcwd()

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            self.loc[self.lang]["lbl_save_path"],
            str(start_dir),
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if selected_dir:
            self.le_save_path.setText(str(Path(selected_dir).resolve()))

    def _handle_browse_load(self) -> None:
        """Вызывает проводник ОС для выбора директории загрузки исходных калибровок."""
        raw_path = self.le_load_path.text()
        start_dir = raw_path if Path(raw_path).exists() else os.getcwd()

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            self.loc[self.lang]["lbl_load_path"],
            str(start_dir),
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if selected_dir:
            self.le_load_path.setText(str(Path(selected_dir).resolve()))

    def _handle_save(self) -> None:
        self.user_decision = "accept"
        self.accept()

    def get_configured_settings(self) -> Dict[str, Any]:
        """Формирует итоговый словарь настроек для передачи в SettingsManager."""
        try:
            norm = float(self.le_norm.text().replace(',', '.'))
        except ValueError:
            norm = 1000.628

        return {
            "Language": self.combo_lang.currentText(),
            "Acc Axis Align Calibration Result Folder": self.le_save_path.text().strip(),
            "Acc Calibration Result Folder": self.le_load_path.text().strip(),
            "Norm Value": norm
        }
