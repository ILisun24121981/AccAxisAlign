# main.py — Часть 1 из 2
import sys
import os
import json
import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox, QLabel, QLineEdit
)
from PyQt6.QtCore import Qt

# Подключение вашего интерактивного модуля калибровки
import Acc_axis_align

TARGET_GYRO_AXIS = 'CU_RPM'
CURRENT_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(CURRENT_PROJECT_ROOT, 'config.json')


class MockHostWindow(QMainWindow):
    """Имитация главного окна основного хост-приложения (Песочница)"""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Имитатор Хост-Приложения (Песочница)")
        self.resize(550, 260)

        # Главный контейнер
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Информационное поле
        self.info_label = QLabel(
            "<b>Модуль выравнивания осей подключен.</b><br>"
            "Выделите путь в поле ниже или скопируйте его стандартным сочетанием Ctrl+C."
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("font-size: 13px; color: #2c3e50; line-height: 1.4;")
        layout.addWidget(self.info_label)

        # ДОБАВЛЕНО: Интерактивная строка для просмотра и копирования пути к CSV-файлу
        path_layout = QVBoxLayout()
        path_title = QLabel("<b>Текущий файл телеметрии:</b>")
        path_title.setStyleSheet("font-size: 11px; color: #57606f;")
        path_layout.addWidget(path_title)

        self.le_current_path = QLineEdit()
        self.le_current_path.setReadOnly(True)  # Защита от редактирования, но копирование разрешено
        self.le_current_path.setPlaceholderText("Файл не выбран. Путь появится здесь...")
        self.le_current_path.setStyleSheet("""
            QLineEdit {
                background-color: #f1f2f6;
                color: #2f3542;
                font-family: 'Consolas', 'Courier New';
                font-size: 12px;
                border: 1px solid #ced6e0;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        path_layout.addWidget(self.le_current_path)
        layout.addLayout(path_layout)

        # Кнопка открытия файла
        self.btn_open = QPushButton("Открыть файл телеметрии (CSV)...")
        self.btn_open.setMinimumHeight(45)
        self.btn_open.setStyleSheet("""
            QPushButton {
                background-color: #2f3542;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #57606f; }
        """)
        self.btn_open.clicked.connect(self.handle_file_selection)
        layout.addWidget(self.btn_open)

        self.setCentralWidget(central_widget)

    def load_initial_dir(self) -> str:
        """Загружает сохраненный путь из config.json или возвращает пустую строку"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    saved_path = config.get('last_data_directory', '')
                    if os.path.isdir(saved_path):
                        return saved_path
            except Exception as e:
                print(f"[Хост] Не удалось прочитать config.json: {e}")
        return ''

    def save_current_dir(self, file_path: str):
        """Сохраняет директорию выбранного файла в config.json"""
        try:
            data_dir = os.path.dirname(file_path)
            config_data = {'last_data_directory': data_dir}
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print(f"[Хост] Путь '{data_dir}' сохранен в {CONFIG_FILE}")
        except Exception as e:
            print(f"[Хост] Не удалось записать config.json: {e}")

    # main.py — Часть 2 из 2

    def handle_file_selection(self):
        """Парсинг CSV-файла и запуск интерактивного модуля"""
        initial_dir = self.load_initial_dir()

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Хост: Открыть файл телеметрии", initial_dir, "CSV Files (*.csv)"
        )
        if not file_path:
            return

        try:
            self.save_current_dir(file_path)

            # ИСПРАВЛЕНО: Выводим полный абсолютный путь к открытому файлу в интерфейс для копирования
            abs_csv_path = os.path.abspath(file_path)
            self.le_current_path.setText(abs_csv_path)
            self.le_current_path.setSelection(0, len(abs_csv_path))  # Автовыделение для быстрого Ctrl+C
            self.le_current_path.setFocus()

            # Чтение файла телеметрии
            df = pd.read_csv(file_path)
            acc_cols = ['SNQ_x', 'SNQ_y', 'SNQ_z']

            # Валидация структуры данных
            if TARGET_GYRO_AXIS not in df.columns:
                QMessageBox.critical(
                    self, "Ошибка разбора",
                    f"В CSV файле отсутствует точный столбец '{TARGET_GYRO_AXIS}'!\n"
                    f"Доступные столбцы: {list(df.columns)}"
                )
                return

            if not all(col in df.columns for col in acc_cols):
                QMessageBox.critical(
                    self, "Ошибка структуры",
                    f"Файл должен содержать столбцы акселерометра: {acc_cols}"
                )
                return

            # Формируем входной словарь данных для калибровки
            input_data_dict = {
                'acc_x': df['SNQ_x'].to_numpy(),
                'acc_y': df['SNQ_y'].to_numpy(),
                'acc_z': df['SNQ_z'].to_numpy(),
                'gyro_axis': df[TARGET_GYRO_AXIS].to_numpy()
            }

            # Запуск новой сессии калибровки с явным пробросом корня хоста
            print(f"[Хост] Запуск интерактивной калибровки для файла: {os.path.basename(file_path)}")
            Acc_axis_align.start_interactive_calibration(
                input_data_dict,
                project_root=CURRENT_PROJECT_ROOT
            )

        except Exception as e:
            QMessageBox.critical(self, "Критическая ошибка", f"Не удалось обработать файл:\n{str(e)}")
            print(f"Критическая ошибка в Хост-скрипте: {str(e)}")


class SaveSuccessDialog(QDialog):
    """Кастомное окно успешного сохранения с поддержкой выделения и копирования пути"""

    def __init__(self, filename: str, folder_path: str, lang: str = "Russian", parent=None):
        super().__init__(parent)
        self.folder_path = os.path.abspath(folder_path)
        self.full_file_path = os.path.join(self.folder_path, filename)

        if lang == "Russian":
            self.setWindowTitle("Внимание")
            self.msg_text = "Результаты успешно сохранены в файл:"
            self.btn_open_text = "Открыть папку с результатом"
            self.btn_ok_text = "ОК"
        else:
            self.setWindowTitle("Attention")
            self.msg_text = "Results successfully saved to file:"
            self.btn_open_text = "Open Containing Folder"
            self.btn_ok_text = "OK"

        self.init_ui()

    def init_ui(self):
        self.resize(500, 160)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        lbl = QLabel(self.msg_text)
        layout.addWidget(lbl)

        # ИСПРАВЛЕНО: Заменяем обычный QLabel на QLineEdit в режиме ReadOnly, чтобы путь можно было копировать
        self.le_path_display = QLineEdit(self.full_file_path)
        self.le_path_display.setReadOnly(True)
        self.le_path_display.setStyleSheet("""
            QLineEdit {
                background-color: #f5f5f5;
                color: #333333;
                font-family: 'Consolas', 'Courier New';
                font-size: 11px;
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        layout.addWidget(self.le_path_display)

        btn_layout = QHBoxLayout()
        self.btn_open = QPushButton(self.btn_open_text)
        self.btn_ok = QPushButton(self.btn_ok_text)

        self.btn_open.setMinimumHeight(30)
        self.btn_ok.setMinimumHeight(30)
        self.btn_ok.setFixedWidth(80)

        btn_layout.addWidget(self.btn_open)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_open.clicked.connect(self.handle_open_folder)

        # Автоматически выделяем весь текст для мгновенного Ctrl+C при появлении окна
        self.le_path_display.setSelection(0, len(self.full_file_path))
        self.le_path_display.setFocus()

    def handle_open_folder(self):
        try:
            if os.path.exists(self.folder_path):
                if os.name == 'nt':
                    os.startfile(self.folder_path)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', self.folder_path])
                else:
                    subprocess.Popen(['xdg-open', self.folder_path])
        except Exception as e:
            print(f"[Модуль] Не удалось открыть папку: {e}")
        self.accept()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    host_window = MockHostWindow()
    host_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
