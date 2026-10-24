# Acc_axis_align/views/plot_view.py — Часть 1 из 3
import numpy as np
import pyqtgraph as pg
from pathlib import Path  # ИСПРАВЛЕНО: Добавлен импорт класса Path
from PyQt6 import QtCore
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QDialog, QTextEdit, QApplication
)


class AlignmentPlotView(QDialog):
    """Пассивный графический компонент (View) для интерактивного анализа выравнивания осей.

    Полностью управляется контроллером. Исключает утечки памяти при закрытии.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)

        # Настройка графического движка pyqtgraph
        pg.setConfigOption('background', '#1e1e1e')
        pg.setConfigOption('foreground', 'w')
        pg.setConfigOptions(antialias=True)

        # Жизненный цикл и коллбеки контроллера
        self.on_gyro_fix_callback = None
        self.on_unapply_callback = None
        self.on_load_matrix_callback = None
        self.on_finish_step1_callback = None
        self.on_finish_step2_callback = None
        self.on_save_callback = None

        self.selected_range = (0, 0)
        self.user_decision = 'reject'

        # Ссылки на элементы для очистки
        self.p_gyro = None
        self.region = None
        self.p_gyro_widget = None
        self.widget_before = None
        self.widget_after = None
        self.session_header_widget = None

        self._init_localization()

    def _init_localization(self):
        self.loc = {
            "Russian": {
                "window_title": "Интерактивный модуль выравнивания осей Акселерометра",
                "status_start": "Фиксация отсутствия вращения (Шаг 1)...",
                "status_step2": "Интервал выбран. Подготовьте данные к выравниванию (Шаг 2).",
                "status_done": "Выравнивание осей успешно завершено (SVD)!",
                "btn_gyro": "Задать ноль гироскопа",
                "btn_unapply": "Убрать примененную калибровку",
                "btn_apply": "Выбрать файл калибровки",
                "btn_finish": "Завершить этап",
                "btn_save_result": "Сохранить результат",
                "gyro_title": "Показания контролируемой оси гироскопа",
                "2d_before": "До коррекции (2D Проекции)",
                "2d_after": "После коррекции (2D Проекции)",
                "time_x_before": "До коррекции: Ось X vs Время",
                "time_x_after": "После коррекции: Ось X_corr vs Время",
                "time_yz_before": "До коррекции: Оси Y, Z vs Время",
                "time_yz_after": "После коррекции: Оси Y_corr, Z_corr vs Время",
                "range_lbl": "Выбранный интервал",
                "stage_1": "Этап 1: Фильтрация вращения",
                "stage_2": "Этап 2: Ортогонализация SVD"
            },
            "English": {
                "window_title": "Interactive SNQ Axis Alignment Module",
                "status_start": "Static Interval Selection (Step 1)...",
                "status_step2": "Interval selected. Prepare data for axis alignment (Step 2).",
                "status_done": "Axis alignment successfully completed (SVD)!",
                "btn_gyro": "Set Gyro Zero",
                "btn_unapply": "Remove Applied Calibration",
                "btn_apply": "Select Calibration File",
                "btn_finish": "Finish Stage",
                "btn_save_result": "Save Results",
                "gyro_title": "Monitored Gyro Axis Readings",
                "2d_before": "Before Correction (2D Projections)",
                "2d_after": "After Correction (2D Projections)",
                "time_x_before": "Before Correction: Axis X vs Time",
                "time_x_after": "After Correction: Axis X_corr vs Time",
                "time_yz_before": "Before Correction: Axes Y, Z vs Time",
                "time_yz_after": "After Correction: Axes Y_corr, Z_corr vs Time",
                "range_lbl": "Selected interval",
                "stage_1": "Stage 1: Gyro Filtration",
                "stage_2": "Stage 2: SVD Orthogonalization"
            }
        }

    def setup_ui(self, lang: str = "Russian") -> None:
        """Инициализирует базовую сетку оконного интерфейса."""
        self.lp = self.loc.get(lang, self.loc["English"])
        self.setWindowTitle(self.lp["window_title"])
        self.resize(1350, 850)

        self.main_layout = QHBoxLayout(self)

        # Боковая панель управления (сайдбар)
        self.sidebar_layout = QVBoxLayout()
        self.sidebar_layout.setSpacing(10)

        self.lbl_stage = QLabel(self.lp["stage_1"])
        self.lbl_stage.setStyleSheet("font-weight: bold; font-size: 14px; color: #3498db; margin-bottom: 5px;")
        self.sidebar_layout.addWidget(self.lbl_stage)

        self.lbl_status = QLabel(self.lp["status_start"])
        self.lbl_status.setWordWrap(True)
        self.sidebar_layout.addWidget(self.lbl_status)

        # Динамический контейнер для кнопок управления этапами
        self.btn_container = QWidget()
        self.btn_box = QVBoxLayout(self.btn_container)
        self.btn_box.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.addWidget(self.btn_container)

        self.sidebar_layout.addStretch()
        self.main_layout.addLayout(self.sidebar_layout, stretch=1)

        # Правая графическая панель
        self.right_layout = QVBoxLayout()

        # Область графиков
        self.graphs_layout = QHBoxLayout()
        self.right_layout.addLayout(self.graphs_layout, stretch=4)

        # Окно терминального вывода логов математики
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas; font-size: 11px; border: 1px solid #333;"
        )
        self.log_output.setFixedHeight(110)
        self.right_layout.addWidget(self.log_output, stretch=0)

        self.main_layout.addLayout(self.right_layout, stretch=4)

        self.set_stage1_ui()
        self._center_window()

    # Acc_axis_align/views/plot_view.py — Часть 2 из 3

    def set_stage1_ui(self) -> None:
        """Переключает боковую панель в режим выбора интервала гироскопа."""
        self._clear_btn_box()
        self.lbl_stage.setText(self.lp["stage_1"])
        self.lbl_status.setText(self.lp["status_start"])

        self.btn_gyro = QPushButton(self.lp["btn_gyro"])
        self.btn_gyro.setMinimumHeight(45)
        self.btn_gyro.clicked.connect(self._on_gyro_clicked)
        self.btn_box.addWidget(self.btn_gyro)

        self.lbl_range = QLabel(f"{self.lp['range_lbl']}: --")
        self.btn_box.addWidget(self.lbl_range)

        self.btn_finish1 = QPushButton(self.lp["btn_finish"])
        self.btn_finish1.setMinimumHeight(38)
        self.btn_finish1.setVisible(False)
        self.btn_finish1.clicked.connect(self._on_finish1_clicked)
        self.btn_box.addWidget(self.btn_finish1)

    def set_stage2_ui(self) -> None:
        """Переключает боковую панель в режим подготовки данных калибровки."""
        self._clear_btn_box()
        self.lbl_stage.setText(self.lp["stage_2"])
        self.lbl_status.setText(self.lp["status_step2"])

        self.btn_unapply = QPushButton(self.lp["btn_unapply"])
        self.btn_unapply.setMinimumHeight(38)
        self.btn_unapply.clicked.connect(self._on_unapply_clicked)
        self.btn_box.addWidget(self.btn_unapply)

        self.btn_apply = QPushButton(self.lp["btn_apply"])
        self.btn_apply.setMinimumHeight(38)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        self.btn_box.addWidget(self.btn_apply)

        self.btn_finish2 = QPushButton(self.lp["btn_finish"])
        self.btn_finish2.setMinimumHeight(38)
        self.btn_finish2.setVisible(False)
        self.btn_finish2.clicked.connect(self._on_finish2_clicked)
        self.btn_box.addWidget(self.btn_finish2)

    def set_final_ui(self) -> None:
        """Переключает боковую панель в режим сохранения финальных результатов."""
        self._clear_btn_box()
        self.lbl_status.setText(self.lp["status_done"])

        self.btn_save = QPushButton(self.lp["btn_save_result"])
        self.btn_save.setMinimumHeight(45)
        self.btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px;")
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_box.addWidget(self.btn_save)

    def display_gyro_plot(self, gyro_data: np.ndarray) -> None:
        """Отрисовывает интерактивный график гироскопа с ползунком выбора диапазона."""
        self._clear_graphs_layout()

        self.p_gyro_widget = pg.PlotWidget()
        self.p_gyro = self.p_gyro_widget.getPlotItem()
        self.p_gyro.setTitle(self.lp["gyro_title"])
        self.p_gyro.showGrid(x=True, y=True)
        self.graphs_layout.addWidget(self.p_gyro_widget)

        self.p_gyro.plot(gyro_data, pen=pg.mkPen('#3498db', width=1.5))

        self.region = pg.LinearRegionItem(
            brush=(230, 126, 34, 50), movable=True,
            pen=pg.mkPen('#e67e22', width=1.5), hoverPen=pg.mkPen('#f1c40f', width=3.0)
        )
        self.region.setBounds([0, len(gyro_data)])
        self.region.setRegion([0, max(100, len(gyro_data) // 10)])
        self.p_gyro.addItem(self.region)
        self.region.sigRegionChanged.connect(self._on_region_changed)
        self._on_region_changed()

    # Acc_axis_align/views/plot_view.py — Часть 3 из 3

    def display_calibration_plots(self, step1_data: np.ndarray, corrected_data: np.ndarray = None,
                                  mask: np.ndarray = None) -> None:
        """Строит 2D-проекции и временные тренды 'до/после' выравнивания SVD."""
        self._clear_graphs_layout()

        # Создаем контейнер под графики 'До'
        self.widget_before = pg.GraphicsLayoutWidget()
        self.graphs_layout.addWidget(self.widget_before, stretch=1)

        p_2d_b = self.widget_before.addPlot(row=0, col=0, title=self.lp["2d_before"])
        p_x_b = self.widget_before.addPlot(row=1, col=0, title=self.lp["time_x_before"])
        p_yz_b = self.widget_before.addPlot(row=2, col=0, title=self.lp["time_yz_before"])
        p_yz_b.setXLink(p_x_b)

        # Отрисовка левых графиков (До коррекции)
        p_2d_b.showGrid(x=True, y=True)
        p_2d_b.plot(step1_data[:, 0], step1_data[:, 1], pen=None, symbol='o', symbolSize=3, symbolBrush='r')
        p_2d_b.plot(step1_data[:, 0], step1_data[:, 2], pen=None, symbol='o', symbolSize=3, symbolBrush='g')

        t_vector = np.arange(len(step1_data))
        p_x_b.showGrid(x=True, y=True)
        p_x_b.plot(t_vector, step1_data[:, 0], pen=pg.mkPen('#54a0ff', width=2))
        p_yz_b.showGrid(x=True, y=True)
        p_yz_b.plot(t_vector, step1_data[:, 1], pen=pg.mkPen('r', width=2))
        p_yz_b.plot(t_vector, step1_data[:, 2], pen=pg.mkPen('#ff69b4', width=2))

        # Настройка диапазонов шкал
        max_val_y = np.max(np.abs(step1_data[:, 1:3]))
        if corrected_data is not None:
            max_val_y = max(max_val_y, np.max(np.abs(corrected_data[:, 1:3])))
        rounded_limit_y = int(np.ceil(max_val_y / 1000.0) * 1000.0)

        p_2d_b.setYRange(-rounded_limit_y, rounded_limit_y, padding=0)
        p_yz_b.setYRange(-rounded_limit_y, rounded_limit_y, padding=0)

        # Если есть результаты выравнивания — выводим вторую панель графиков 'После'
        if corrected_data is not None:
            self.widget_after = pg.GraphicsLayoutWidget()
            self.graphs_layout.addWidget(self.widget_after, stretch=1)

            p_2d_a = self.widget_after.addPlot(row=0, col=0, title=self.lp["2d_after"])
            p_x_a = self.widget_after.addPlot(row=1, col=0, title=self.lp["time_x_after"])
            p_yz_a = self.widget_after.addPlot(row=2, col=0, title=self.lp["time_yz_after"])
            p_yz_a.setXLink(p_x_a)

            p_2d_a.showGrid(x=True, y=True)
            p_2d_a.plot(corrected_data[:, 0], corrected_data[:, 1], pen=None, symbol='o', symbolSize=3, symbolBrush='r')
            p_2d_a.plot(corrected_data[:, 0], corrected_data[:, 2], pen=None, symbol='o', symbolSize=3, symbolBrush='g')

            t_after = t_vector[mask] if mask is not None else np.arange(len(corrected_data))
            p_x_a.showGrid(x=True, y=True)
            p_x_a.plot(t_after, corrected_data[:, 0], pen=pg.mkPen('#54a0ff', width=2))
            p_yz_a.showGrid(x=True, y=True)
            p_yz_a.plot(t_after, corrected_data[:, 1], pen=pg.mkPen('r', width=2))
            p_yz_a.plot(t_after, corrected_data[:, 2], pen=pg.mkPen('#ff69b4', width=2))

            p_2d_a.setYRange(-rounded_limit_y, rounded_limit_y, padding=0)
            p_yz_a.setYRange(-rounded_limit_y, rounded_limit_y, padding=0)

    def display_session_header(self, device_number: str, file_path: Path) -> None:
        """Отрисовывает над графиками жирный номер прибора и ссылку на JSON-файл сессии.

        ИСПРАВЛЕНО: Текст маркера изменен на "Файл калибровки:" / "Calibration file:"
        """
        # Если шапка уже была создана ранее, удаляем её, чтобы избежать дублирования в right_layout
        if hasattr(self, 'session_header_widget') and self.session_header_widget:
            self.right_layout.removeWidget(self.session_header_widget)
            self.session_header_widget.setParent(None)
            self.session_header_widget.deleteLater()
            self.session_header_widget = None

        abs_path = Path(file_path).resolve()
        filename_only = abs_path.name

        # ИСПРАВЛЕНО: Текстовые маркеры согласно новым требованиям
        lbl_text = "Файл калибровки:" if self.lp == self.loc["Russian"] else "Calibration file:"
        dev_lbl_text = "Номер прибора:" if self.lp == self.loc["Russian"] else "Device Number:"

        # Создаем контейнер-виджет в горизонтальном формате
        self.session_header_widget = QWidget()
        header_hbox = QHBoxLayout(self.session_header_widget)
        header_hbox.setContentsMargins(5, 5, 5, 5)
        header_hbox.setSpacing(25)  # Комфортный отступ между прибором и ссылкой

        # 1. ТЕКСТ НОМЕРА ПРИБОРА: Стилизация под заголовок h2 с цветом номера #1A237E
        lbl_device = QLabel(f"<h2>{dev_lbl_text} <span style='color: #1A237E;'>{device_number}</span></h2>")
        header_hbox.addWidget(lbl_device)

        # 2. ССЫЛКА НА ФАЙЛ: Изменен маркер на Calibration file / Файл калибровки
        lbl_file_link = QLabel(
            f"<span style='font-size: 13px;'><b>{lbl_text}</b> <a href='#' style='color: #3498db;'>{filename_only}</a></span>")
        lbl_file_link.setOpenExternalLinks(False)

        # Локальная функция для открытия содержащей папки результатов в проводнике ОС
        def open_folder_containing_json():
            folder_path = abs_path.parent
            if folder_path.exists():
                import sys, subprocess, os
                if sys.platform == "win32":
                    os.startfile(folder_path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", folder_path])
                else:
                    subprocess.Popen(["xdg-open", folder_path])

        lbl_file_link.linkActivated.connect(open_folder_containing_json)
        header_hbox.addWidget(lbl_file_link)

        # Заполняем оставшееся пространство справа, прижимая элементы к левому краю над графиками
        header_hbox.addStretch()

        # Вставляем готовый виджет шапки на самую верхнюю позицию (индекс 0) правой панели, над графиками
        self.right_layout.insertWidget(0, self.session_header_widget)

    def _clear_session_header(self) -> None:
        """Безопасно удаляет виджет шапки прибора из интерфейса, если выбор файла был аннулирован."""
        if hasattr(self, 'session_header_widget') and self.session_header_widget:
            try:
                self.right_layout.removeWidget(self.session_header_widget)
                self.session_header_widget.setParent(None)
                self.session_header_widget.deleteLater()
            except Exception:
                pass
            self.session_header_widget = None
        QApplication.processEvents()

    def append_log(self, text: str) -> None:
        self.log_output.append(f"ℹ️ {text}")
        QApplication.processEvents()

    def append_error(self, text: str) -> None:
        self.log_output.append(f'<span style="color:#ff4d4d; font-weight:bold;">⚠️ {text}</span>')
        QApplication.processEvents()

    def show_finish1_btn(self, visible: bool = True) -> None:
        if hasattr(self, 'btn_finish1') and self.btn_finish1:
            self.btn_finish1.setVisible(visible)

    def show_finish2_btn(self, visible: bool = True) -> None:
        if hasattr(self, 'btn_finish2') and self.btn_finish2:
            self.btn_finish2.setVisible(visible)

    def remove_unapply_btn(self) -> None:
        if hasattr(self, 'btn_unapply') and self.btn_unapply:
            self.btn_unapply.setParent(None)
            self.btn_unapply.deleteLater()
            self.btn_unapply = None

    def _clear_btn_box(self) -> None:
        for i in reversed(range(self.btn_box.count())):
            w = self.btn_box.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _clear_graphs_layout(self) -> None:
        for i in reversed(range(self.graphs_layout.count())):
            w = self.graphs_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        if hasattr(self, 'session_header_widget') and self.session_header_widget:
            self.session_header_widget.setParent(None)
            self.session_header_widget.deleteLater()
            self.session_header_widget = None

    def _on_region_changed(self) -> None:
        if self.region:
            min_x, max_x = self.region.getRegion()
            self.selected_range = (int(max(0, min_x)), int(max_x))
            if hasattr(self, 'lbl_range') and self.lbl_range:
                start, end = self.selected_range
                self.lbl_range.setText(f"{self.lp['range_lbl']}: {{{start}:{end}}}")

    def _on_gyro_clicked(self):
        if self.on_gyro_fix_callback:
            self.on_gyro_fix_callback()

    def _on_finish1_clicked(self):
        if self.on_finish_step1_callback:
            self.on_finish_step1_callback()

    def _on_unapply_clicked(self):
        if self.on_unapply_callback:
            self.on_unapply_callback()

    def _on_apply_clicked(self):
        if self.on_load_matrix_callback:
            self.on_load_matrix_callback()

    def _on_finish2_clicked(self):
        if self.on_finish_step2_callback:
            self.on_finish_step2_callback()

    def _on_save_clicked(self):
        if self.on_save_callback:
            self.on_save_callback()

    def _center_window(self) -> None:
        app = QApplication.instance()
        screen = app.primaryScreen().geometry() if app else None
        if screen:
            self.move((screen.width() - self.width()) // 2, (screen.height() - self.height()) // 2)

    def closeEvent(self, event) -> None:
        """Безопасное закрытие окна без принудительного удаления разрушенных C++ объектов."""
        # Разрываем ссылки на коллбеки контроллера, чтобы избежать утечек памяти
        self.on_gyro_fix_callback = None
        self.on_unapply_callback = None
        self.on_load_matrix_callback = None
        self.on_finish_step1_callback = None
        self.on_finish_step2_callback = None
        self.on_save_callback = None

        if self.p_gyro:
            self.p_gyro.clear()
            self.p_gyro = None

        if self.region:
            self.region = None

        # ИСПРАВЛЕНО: Убран вызов self._clear_graphs_layout(),
        # так как флаг WA_DeleteOnClose сам автоматически и безопасно зачистит C++ память.
        super().closeEvent(event)
