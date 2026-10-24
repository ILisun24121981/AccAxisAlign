# Acc_axis_align/models/aligner.py
import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import Dict, Any, Tuple, Optional


class AccAligner:
    """Чистая математическая модель выравнивания осей акселерометра (ортогонализации).

    Не содержит элементов графического интерфейса, логгеров и файлового I/O.
    Работает со структурами данных в оперативной памяти.
    """

    def __init__(self):
        # Входные сырые буферы
        self.acc_data: Optional[np.ndarray] = None
        self.gyro_axis_data: Optional[np.ndarray] = None

        # Границы статического шума гироскопа
        self.gyro_limit_min: float = 0.0
        self.gyro_limit_max: float = 0.0

        # Калибровочные параметры первичной коррекции (SNQ)
        self.snq_matrix: np.ndarray = np.eye(3)
        self.snq_offset: np.ndarray = np.zeros(3)

    def set_data(self, acc_x: np.ndarray, acc_y: np.ndarray, acc_z: np.ndarray, gyro_axis: np.ndarray) -> None:
        """Безопасно инициализирует числовые матрицы в ОЗУ."""
        self.acc_data = np.column_stack((acc_x, acc_y, acc_z))
        self.gyro_axis_data = np.array(gyro_axis).flatten()

    def estimate_gyro_noise(self, start_idx: int, end_idx: int, safety_margin: float = 1.1) -> Tuple[float, float]:
        """Определяет границы шума гироскопа на усеченном внутреннем интервале покоя."""
        if self.gyro_axis_data is None:
            raise ValueError("Telemetry data not loaded in Aligner.")

        start_idx = max(0, start_idx)
        end_idx = min(len(self.gyro_axis_data) - 1, end_idx)

        if start_idx >= end_idx:
            raise ValueError("Invalid quiet interval indices.")

        total_length = end_idx - start_idx + 1
        edge_offset = int(total_length * 0.10)

        # Выделение стабильного центрального куска для фильтрации переходных процессов
        if total_length > 20:
            pure_start = start_idx + edge_offset
            pure_end = end_idx - edge_offset
        else:
            pure_start = start_idx
            pure_end = end_idx

        static_chunk = self.gyro_axis_data[pure_start:pure_end + 1]

        mean_val = np.mean(static_chunk)
        max_val = np.max(static_chunk)
        min_val = np.min(static_chunk)

        pos_delta = max_val - mean_val
        neg_delta = mean_val - min_val

        self.gyro_limit_max = mean_val + (pos_delta * safety_margin)
        self.gyro_limit_min = mean_val - (neg_delta * safety_margin)

        return self.gyro_limit_min, self.gyro_limit_max

    def filter_buffer_by_gyro(self) -> int:
        """Отсекает из буфера точки, в которых датчик находился в движении.

        Возвращает количество оставшихся статических точек.
        """
        if self.acc_data is None or self.gyro_axis_data is None:
            raise ValueError("Data buffers are uninitialized.")

        gyro_mask = (self.gyro_axis_data >= self.gyro_limit_min) & (self.gyro_axis_data <= self.gyro_limit_max)
        self.acc_data = np.copy(self.acc_data[gyro_mask])

        # Гироскоп больше не нужен, освобождаем ОЗУ
        self.gyro_axis_data = None
        return len(self.acc_data)

    def sync_snq_coefficients(self, matrix: list, offsets: list) -> None:
        """Загружает внешние калибровочные коэффициенты для предварительной коррекции."""
        self.snq_matrix = np.array(matrix, dtype=float)
        self.snq_offset = np.array(offsets, dtype=float)

    def remove_erroneous_coefficients(self, offset: list, matrix: list) -> None:
        """Инвертирует и устраняет некорректные калибровки из сырого буфера."""
        if self.acc_data is None:
            raise ValueError("Data buffer is empty.")

        offset_np = np.array(offset, dtype=float)
        matrix_np = np.array(matrix, dtype=float)

        try:
            inv_matrix_t = np.linalg.inv(matrix_np.T)
            self.acc_data = (self.acc_data @ inv_matrix_t) + offset_np
        except np.linalg.LinAlgError:
            raise ValueError("Provided calibration matrix is singular (determinant is 0).")

    def transform_buffer_with_snq(self) -> None:
        """Применяет матрицу SNQ и вектор смещения к текущему статическому буферу данных."""
        if self.acc_data is None:
            raise ValueError("Data buffer is empty.")
        self.acc_data = (self.acc_data - self.snq_offset) @ self.snq_matrix.T

    def calculate_3sigma_mask(self, data: np.ndarray) -> np.ndarray:
        """Статистический фильтр аномалий (3-Sigma критерий)."""
        means = np.mean(data, axis=0)
        stds = np.std(data, axis=0)
        return np.all(np.abs(data - means) <= 3.0 * stds, axis=1)

    def run_alignment(self) -> Dict[str, Any]:
        """Выполняет ортогонализацию методом SVD-аппроксимации на отфильтрованном облаке точек.

        Возвращает словарь с результатами расчетов и матрицами преобразования.
        """
        if self.acc_data is None or len(self.acc_data) == 0:
            raise ValueError("No static data points available for alignment.")

        step1_data = np.copy(self.acc_data)

        # Применяем фильтр 3-Сигма
        sigma_mask = self.calculate_3sigma_mask(step1_data)
        filtered_data = step1_data[sigma_mask] if np.sum(sigma_mask) > 10 else step1_data

        # Центрирование облака точек для SVD
        mean_vector = np.mean(filtered_data, axis=0)
        data_centered = filtered_data - mean_vector

        # Аппроксимация плоскости через сингулярное разложение
        _, _, vh = np.linalg.svd(data_centered, full_matrices=False)
        orto_vector_unit = vh[-1, :]

        if orto_vector_unit[0] < 0:
            orto_vector_unit = -orto_vector_unit

        target_vector_unit = np.array([1.0, 0.0, 0.0])

        v_cross = np.cross(orto_vector_unit, target_vector_unit)
        v_dot = np.dot(orto_vector_unit, target_vector_unit)
        v_cross_norm = np.linalg.norm(v_cross)

        # Вычисление корректирующей матрицы вращения
        if v_cross_norm < 1e-6:
            rot_matrix = np.eye(3)
        else:
            axis = v_cross / v_cross_norm
            angle = np.arccos(np.clip(v_dot, -1.0, 1.0))
            rot_matrix = R.from_rotvec(axis * angle).as_matrix()

        # Результирующие сквозные матрицы
        final_matrix = rot_matrix @ self.snq_matrix
        corrected_data = step1_data @ rot_matrix.T

        return {
            "step1_data": step1_data,
            "corrected_data": corrected_data,
            "sigma_mask": sigma_mask,
            "final_matrix": final_matrix,
            "final_offset": self.snq_offset,
            # Чистые числовые метрики для передачи во View/Контроллер
            "metrics": {
                "x_min_before": float(np.min(step1_data[:, 0])),
                "x_max_before": float(np.max(step1_data[:, 0])),
                "x_min_after": float(np.min(corrected_data[:, 0])),
                "x_max_after": float(np.max(corrected_data[:, 0])),
                "macro_min_before": float(np.min(step1_data[:, 1:3])),
                "macro_max_before": float(np.max(step1_data[:, 1:3])),
                "macro_min_after": float(np.min(corrected_data[:, 1:3])),
                "macro_max_after": float(np.max(corrected_data[:, 1:3]))
            }
        }

    def clear(self) -> None:
        """Принудительно очищает тяжелые массивы из оперативной памяти."""
        self.acc_data = None
        self.gyro_axis_data = None
