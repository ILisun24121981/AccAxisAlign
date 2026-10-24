# Acc_axis_align/controllers/alignment_controller.py — Часть 1 из 3
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QLineEdit, QMessageBox

# Импорты отказоустойчивого слоя менеджеров
from Acc_axis_align.models.Managers.settings_manager import SettingsManager
from Acc_axis_align.models.Managers.alignment_file_manager import AlignmentFileManager
from Acc_axis_align.models.Managers.alignment_session_manager import AlignmentSessionManager

# Импорты изолированного математического ядра и графических представлений
from Acc_axis_align.models.aligner import AccAligner
from Acc_axis_align.views.plot_view import AlignmentPlotView
from Acc_axis_align.views.errors import ErrorsDialog
from Acc_axis_align.views.ManualMatrixInputDialog import ManualMatrixInputDialog
from Acc_axis_align.views.SettingsDialog import SettingsDialog


class AlignmentController:
    """Центральный контроллер-дирижер.

    Полностью контролирует транзакции шагов, зависимости сессий и жизненный цикл окон.
    """

    def __init__(self, project_root: str = None):
        self.base_dir = Path(project_root) if project_root else Path(os.getcwd())

        # Инициализация менеджеров и математического движка
        self.settings_manager = SettingsManager(parent=QApplication.activeWindow())
        self.file_manager = AlignmentFileManager()
        self.session_manager = AlignmentSessionManager(self.settings_manager, self.file_manager)
        self.aligner = AccAligner()

        # Пассивные View компоненты
        self.view: Optional[AlignmentPlotView] = None

        # Буферы промежуточных результатов для GUI
        self._last_alignment_results: Optional[Dict[str, Any]] = None

    def handle_startup_session(self, force_settings: bool = False) -> bool:
        """Инициализирует окружение.

        Проверка цепочки сессии полностью удалена отсюда, так как рабочий
        JSON-файл выбирается пользователем только на Этапе 2.
        """
        active_win = QApplication.activeWindow()

        # Валидация файлов конфигурации среды
        if not self.settings_manager.validate_environment() or force_settings:
            self.show_settings_dialog()
            if force_settings:
                return False

        return True

    def show_settings_dialog(self) -> None:
        """Отображает глобальное окно конфигурации параметров среды."""
        current_data = {
            "Language": self.settings_manager.current_lang,
            "Acc Axis Align Calibration Result Folder": str(self.settings_manager.save_result_dir),
            "Acc Calibration Result Folder": str(self.settings_manager.load_calib_dir),
            "Norm Value": self.settings_manager.norm_value
        }

        active_win = QApplication.activeWindow()
        dialog = SettingsDialog(current_settings=current_data, parent=active_win)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_settings = dialog.get_configured_settings()
            raw_lang = new_settings["Language"].strip()
            lang_final = "Russian" if raw_lang.startswith(("Rus", "rus")) else "English"

            new_save_path = new_settings["Acc Axis Align Calibration Result Folder"]

            self.settings_manager.save_all_settings(
                lang_final, new_save_path,
                new_settings["Acc Calibration Result Folder"],
                new_settings["Norm Value"]
            )

    # Acc_axis_align/controllers/alignment_controller.py — Часть 2 из 3

    def run_full_cycle(self, data_dict: dict) -> None:
        """Инициализирует буферы данных и запускает основной графический цикл модуля."""
        self.aligner.set_data(
            acc_x=data_dict['acc_x'],
            acc_y=data_dict['acc_y'],
            acc_z=data_dict['acc_z'],
            gyro_axis=data_dict['gyro_axis']
        )

        active_win = QApplication.activeWindow()
        self.view = AlignmentPlotView(parent=active_win)
        self.view.setup_ui(lang=self.settings_manager.current_lang)

        self.view.on_gyro_fix_callback = self.handle_gyro_fix
        self.view.on_finish_step1_callback = self.handle_finish_stage1
        self.view.on_unapply_callback = self.handle_unapply_coefficients
        self.view.on_load_matrix_callback = self.handle_load_calibration_matrix
        self.view.on_finish_step2_callback = self.handle_finish_stage2
        self.view.on_save_callback = self.handle_save_results

        self.view.display_gyro_plot(self.aligner.gyro_axis_data)
        self.view.exec()

    def handle_gyro_fix(self) -> None:
        """Слот-коллбек: Расчет границ шума гироскопа на выделенном интервале."""
        start_idx, end_idx = self.view.selected_range
        try:
            g_min, g_max = self.aligner.estimate_gyro_noise(start_idx, end_idx)
            msg = (f"Шум зафиксирован. Границы покоя: [{g_min:.4f} : {g_max:.4f}]"
                   if self.settings_manager.current_lang == "Russian" else
                   f"Gyro noise fixed. Static limits: [{g_min:.4f} : {g_max:.4f}]")
            self.view.append_log(msg)
            self.view.show_finish1_btn(True)
        except Exception as e:
            self.view.append_error(f"Error: {e}")

    def handle_finish_stage1(self) -> None:
        """Слот-коллбек: Фильтрация динамических точек движения и переход на Этап 2."""
        try:
            remaining_points = self.aligner.filter_buffer_by_gyro()
            msg = (f"Успешно отфильтровано. Статических точек в буфере: {remaining_points}"
                   if self.settings_manager.current_lang == "Russian" else
                   f"Filtration complete. Static points remaining: {remaining_points}")
            self.view.append_log(msg)

            self.view.set_stage2_ui()
            self.view.display_calibration_plots(step1_data=self.aligner.acc_data)
        except Exception as e:
            self.view.append_error(f"Error: {e}")

    def handle_unapply_coefficients(self) -> None:
        """Слот-коллбек: Безопасное исключение старых калибровок из буфера."""
        is_ru = self.settings_manager.current_lang == "Russian"
        w_title = "Внимание" if is_ru else "Warning"
        w_text = ("Данный шаг выполняется, только если данные были собраны с примененными "
                  "по ошибке калибровочными коэффициентами.\n\nХотите продолжить?") if is_ru else \
            ("This step is performed only if the data was collected with erroneously "
             "applied calibration coefficients.\n\nDo you want to continue?")

        reply = QMessageBox.question(
            self.view, w_title, w_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        dialog = ManualMatrixInputDialog(lang=self.settings_manager.current_lang, parent=self.view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.aligner.remove_erroneous_coefficients(dialog.offset_data, dialog.matrix_data)
                self.view.append_log(
                    "Старые коэффициенты исключены из буфера." if is_ru else "Old coefficients removed from buffer.")
                self.view.display_calibration_plots(step1_data=self.aligner.acc_data)
                self.view.remove_unapply_btn()
            except Exception as e:
                self.view.append_error(str(e))

    def handle_load_calibration_matrix(self) -> None:
        """Слот-коллбек: Интерактивный выбор и валидация файла калибровочной сессии прибора."""
        is_ru = self.settings_manager.current_lang == "Russian"
        caption = "Выберите JSON файл калибровочной сессии" if is_ru else "Select Calibration Session JSON File"

        file_path, _ = QFileDialog.getOpenFileName(
            self.view, caption, str(self.settings_manager.load_calib_dir), "JSON Files (*.json)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        if not file_path:
            return

        target_path = Path(file_path).resolve()

        try:
            # Вызов циклической валидации через SessionManager
            session_data = self.session_manager.verify_and_load_session(target_path, parent=self.view)
            if not session_data:
                self.view.append_error(
                    "Выбор файла отменен: файл не соответствует технологической цепочке." if is_ru else "File selection canceled: file does not match workflow.")
                return

            matrix = session_data.get("acc", {}).get("calibration", {}).get("Result", {}).get("matrix")
            offsets = session_data.get("acc", {}).get("calibration", {}).get("Result", {}).get("offsets")

            if matrix is None or offsets is None:
                raise ValueError("В секции 'acc->calibration->Result' отсутствуют поля 'matrix' или 'offsets'.")

            self.aligner.sync_snq_coefficients(matrix, offsets)
            self.view.append_log(
                "Файл сессии успешно привязан. Коэффициенты базовой калибровки загружены." if is_ru else "Session file successfully linked. Baseline calibration coefficients loaded.")

            # Извлекаем номер прибора и отрисовываем жирную шапку над графиками
            dev_num = session_data.get("fileInfo", {}).get("device_number", "unknown")
            self.view.display_session_header(device_number=dev_num, file_path=target_path)

            # Активируем кнопку завершения Этапа 2
            self.view.show_finish2_btn(True)

        except Exception as e:
            self.view.append_error(f"Ошибка разбора структуры файла: {e}")

            # ИСПРАВЛЕНО: Безопасно скрываем кнопку Finish Stage, если произошел критический сбой структуры
            if self.view:
                self.view.show_finish2_btn(False)
                if hasattr(self.view, '_clear_session_header'):
                    self.view._clear_session_header()

            dev_num = str(target_path.name).split('_') if '_' in target_path.name else ["unknown"]
            dialog = ErrorsDialog(device_number=dev_num, result_path=target_path,
                                  lang=self.settings_manager.current_lang, parent=self.view)
            dialog.exec()

    def handle_finish_stage2(self) -> None:
        """Слот-коллбек: Применение SNQ, проведение SVD-ортогонализации и вывод графиков 'После'."""
        try:
            self.aligner.transform_buffer_with_snq()
            self._last_alignment_results = self.aligner.run_alignment()

            self.view.display_calibration_plots(
                step1_data=self._last_alignment_results["step1_data"],
                corrected_data=self._last_alignment_results["corrected_data"],
                mask=self._last_alignment_results["sigma_mask"]
            )

            m = self._last_alignment_results["metrics"]
            log_metrics = (
                f"Выравнивание SVD завершено.\n"
                f"  • Масштаб X (до/после): [{m['x_min_before']:.2f} : {m['x_max_before']:.2f}] -> [{m['x_min_after']:.2f} : {m['x_max_after']:.2f}]\n"
                f"  • Разброс YZ (до/после): [{m['macro_min_before']:.2f} : {m['macro_max_before']:.2f}] -> [{m['macro_min_after']:.2f} : {m['macro_max_after']:.2f}]"
            )
            self.view.append_log(log_metrics)
            self.view.set_final_ui()
        except Exception as e:
            self.view.append_error(f"Math Error: {e}")

    def handle_save_results(self) -> None:
        """Слот-коллбек: Автоматическое сохранение финальной матрицы сессии без ручного ввода номера прибора.

        ИСПРАВЛЕНО: Безопасная деструкция View до вызова диалога успеха хоста исключает
        ошибку "wrapped C/C++ object has been deleted". main.py не модифицируется.
        """
        if not self._last_alignment_results:
            return

        is_ru = self.settings_manager.current_lang == "Russian"

        try:
            # 1. Читаем текущее состояние файла сессии с диска
            file_data = self.file_manager.read_json(self.settings_manager.calibration_file_path, self.view)
            if not file_data:
                raise ValueError("Не удалось прочитать данные текущего файла калибровочной сессии.")

            # 2. Получаем номер прибора из заголовка fileInfo
            dev_num = file_data.get("fileInfo", {}).get("device_number", "unknown").strip()

            # 3. Переводим матрицы и смещения в списки Python для JSON
            matrix = self._last_alignment_results["final_matrix"].tolist()
            offsets = self._last_alignment_results["final_offset"].tolist()

            # 4. Фиксируем результаты SVD выравнивания в acc -> axesAlignment
            self.session_manager.save_final_alignment(matrix=matrix, offsets=offsets, parent=self.view)

            # 5. Формируем имя файла для отображения
            current_timestamp = file_data.get("fileInfo", {}).get("changeTimeStamp",
                                                                  datetime.now().strftime('%Y_%m_%d_%H_%M'))
            filename = f"{dev_num}_calibration_{current_timestamp}.json"

            log_msg = f"Результаты успешно зафиксированы в сессии прибора {dev_num}." if is_ru else f"Results successfully committed to device session {dev_num}."
            print(f"[Модуль] {log_msg}")

            # 6. ИСПРАВЛЕНО: Закрываем интерактивное окно модуля ДО вызова диалога хоста.
            # Это высвобождает C++ ресурсы plot_view и предотвращает коллизию указателей.
            if self.view:
                self.view.accept()
                self.view = None

            # 7. Импортируем и вызываем окно успешного сохранения из main,
            # передавая в качестве parent активное окно хост-приложения, а не удаленный view.
            from main import SaveSuccessDialog
            active_host_win = QApplication.activeWindow()

            success_dlg = SaveSuccessDialog(
                filename=filename,
                folder_path=str(self.settings_manager.save_result_dir),
                lang=self.settings_manager.current_lang,
                parent=active_host_win
            )
            success_dlg.exec()

        except Exception as e:
            if self.view:
                self.view.append_error(f"Save error: {e}")
            else:
                print(f"[Модуль] Критическая ошибка сохранения: {e}")

    def shutdown_session(self) -> None:
        """Безопасная деаллокация ресурсов и разрыв ссылок для исключения утечек памяти.

        ИСПРАВЛЕНО: Защита try-except предотвращает падение хоста при попытке
        очистки уже уничтоженного на крестик C++ объекта View.
        """
        if self.view:
            try:
                # Пытаемся безопасно разорвать связь с родителем, только если C++ объект еще жив
                self.view.setParent(None)
            except RuntimeError:
                # Если C++ объект уже удален ядром Qt при закрытии на крестик,
                # просто игнорируем это исключение и идем дальше
                pass
            self.view = None

        if self.aligner:
            try:
                self.aligner.clear()
            except Exception:
                pass
            self.aligner = None

        self.settings_manager = None
        self.file_manager = None
        self.session_manager = None
        self._last_alignment_results = None
        print("✨ [Изоляция ОЗУ] Сессия выравнивания осей успешно деаллоцирована, утечки исключены.")
