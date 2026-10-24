from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGridLayout, QLineEdit
)
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtCore import Qt


class ManualMatrixInputDialog(QDialog):
    """Окно ручного ввода матрицы 3х3 и вектора смещения осей с поддержкой языков"""

    def __init__(self, lang: str = "Russian", parent=None):
        super().__init__(parent)
        self.lang = "Russian" if lang.startswith(("Rus", "rus")) else "English"
        self.matrix_data = None
        self.offset_data = None

        # Локализация
        self.loc = {
            "Russian": {
                "title": "Ввод коэффициентов",
                "header": "Введите примененные матрицу преобразования и вектор смещения осей:",
                "matrix_lbl": "Матрица преобразования (3x3):",
                "offset_lbl": "Вектор смещения осей (Offset X, Y, Z):",
                "btn_ok": "Ок", "btn_cancel": "Отмена"
            },
            "English": {
                "title": "Enter Coefficients",
                "header": "Enter the applied transformation matrix and axis offset vector:",
                "matrix_lbl": "Transformation matrix (3x3):",
                "offset_lbl": "Axis offset vector (Offset X, Y, Z):",
                "btn_ok": "Ok", "btn_cancel": "Cancel"
            }
        }
        self.lp = self.loc[self.lang]
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(self.lp["title"])
        self.resize(450, 320)
        layout = QVBoxLayout(self)

        title = QLabel(self.lp["header"])
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        float_validator = QDoubleValidator(self)
        float_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        layout.addWidget(QLabel(self.lp["matrix_lbl"]))
        matrix_grid = QGridLayout()
        self.matrix_cells = []
        for row in range(3):
            row_cells = []
            for col in range(3):
                cell = QLineEdit()
                cell.setPlaceholderText(f"M[{row}][{col}]")
                cell.setValidator(float_validator)
                cell.setStyleSheet("background-color: #2c2c2c; color: white; padding: 4px;")
                matrix_grid.addWidget(cell, row, col)
                row_cells.append(cell)
            self.matrix_cells.append(row_cells)
        layout.addLayout(matrix_grid)

        layout.addWidget(QLabel(self.lp["offset_lbl"]))
        offset_layout = QHBoxLayout()
        self.offset_cells = []
        labels = ["X:", "Y:", "Z:"]
        for i in range(3):
            offset_layout.addWidget(QLabel(labels[i]))
            cell = QLineEdit()
            cell.setPlaceholderText("0.0")
            cell.setValidator(float_validator)
            cell.setStyleSheet("background-color: #2c2c2c; color: white; padding: 4px;")
            offset_layout.addWidget(cell)
            self.offset_cells.append(cell)
        layout.addLayout(offset_layout)

        layout.addSpacing(15)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_ok = QPushButton(self.lp["btn_ok"])
        self.btn_cancel = QPushButton(self.lp["btn_cancel"])
        bottom_layout.addWidget(self.btn_cancel)
        bottom_layout.addWidget(self.btn_ok)
        layout.addLayout(bottom_layout)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.validate_and_accept)

    def validate_and_accept(self):
        all_valid = True
        error_style = "background-color: #ffcccc; color: black; padding: 4px;"
        normal_style = "background-color: #2c2c2c; color: white; padding: 4px;"

        matrix = []
        for row in range(3):
            row_vals = []
            for col in range(3):
                cell = self.matrix_cells[row][col]
                text = cell.text().strip().replace(',', '.')
                try:
                    val = float(text)
                    cell.setStyleSheet(normal_style)
                    row_vals.append(val)
                except ValueError:
                    cell.setStyleSheet(error_style)
                    all_valid = False
            matrix.append(row_vals)

        offset = []
        for cell in self.offset_cells:
            text = cell.text().strip().replace(',', '.')
            try:
                val = float(text)
                cell.setStyleSheet(normal_style)
                offset.append(val)
            except ValueError:
                cell.setStyleSheet(error_style)
                all_valid = False

        if not all_valid:
            return

        self.matrix_data = matrix
        self.offset_data = offset
        self.accept()
