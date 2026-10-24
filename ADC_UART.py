import serial
import csv
import time
import sys
import os
import struct  
from pyqtgraph.Qt import QtCore, QtWidgets
import pyqtgraph as pg

# === НАСТРОЙКИ ===
COM_PORT = 'COM3'         # Сверьте номер порта с Диспетчером устройств!
BAUD_RATE = 921600        # Скорость для USART2
MAX_PLOT_POINTS = 2000    # Сколько точек одновременно показывать на графике
# =================

# Автоматически создаем папку OutData рядом со скриптом
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(SCRIPT_DIR, 'OutData')
if not os.path.exists(OUT_DIR):
    os.makedirs(OUT_DIR)

is_recording = False
f = None
csv_writer = None
plot_data = []

# Глобальный счётчик времени для записи в файл
total_recorded_points = 0

try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=0.1)
    ser.reset_input_buffer()
except Exception as e:
    print(f"Ошибка подключения к {COM_PORT}: {e}")
    sys.exit()

app = QtWidgets.QApplication(sys.argv)
main_window = QtWidgets.QWidget()
main_window.setWindowTitle("STM32 ADC Бинарный Вольтметр (USART2 921600)")
main_window.resize(1000, 650)

btn_record = QtWidgets.QPushButton("Начать запись")
btn_record.setFixedHeight(40)
btn_record.setStyleSheet("QPushButton { background-color: #2ecc71; color: white; font-size: 14px; font-weight: bold; border-radius: 5px; } QPushButton:hover { background-color: #27ae60; }")

graph_widget = pg.GraphicsLayoutWidget()
plot = graph_widget.addPlot(title="График напряжения в реальном времени (USART2)")
plot.setLabel('left', 'Напряжение', units='V')
plot.setLabel('bottom', 'Точки (Время)')
plot.setYRange(0, 3.6)
curve = plot.plot(pen='g')

layout = QtWidgets.QVBoxLayout()
layout.addWidget(btn_record)
layout.addWidget(graph_widget)
main_window.setLayout(layout)
main_window.show()

def toggle_recording():
    global is_recording, f, csv_writer, total_recorded_points
    if not is_recording:
        try:
            # Обнуляем счётчик точек при каждом новом старте записи
            total_recorded_points = 0
            
            # Сохраняем строго в папку OutData с временным штампом в имени
            timestamp_str = time.strftime("%Y%m%d_%H%M%S")
            dynamic_csv_file = os.path.join(OUT_DIR, f"adc_data_{timestamp_str}.csv")
            
            f = open(dynamic_csv_file, mode='w', newline='', encoding='utf-8')
            csv_writer = csv.writer(f)
            # Шапка таблицы. Time_S — время в секундах от начала этой записи
            csv_writer.writerow(['Time_S', 'Raw_ADC', 'Voltage_V'])
            
            is_recording = True
            btn_record.setText(f"⏸ ИДЕТ ЗАПИСЬ -> OutData/{os.path.basename(dynamic_csv_file)}")
            btn_record.setStyleSheet("QPushButton { background-color: #e74c3c; color: white; font-size: 14px; font-weight: bold; border-radius: 5px; }")
            print(f"Запись запущена в: {dynamic_csv_file}")
        except Exception as e:
            print(f"Не удалось открыть файл: {e}")
    else:
        is_recording = False
        if f:
            f.close()
            f = None
            csv_writer = None
        btn_record.setText("Начать запись")
        btn_record.setStyleSheet("QPushButton { background-color: #2ecc71; color: white; font-size: 14px; font-weight: bold; border-radius: 5px; }")
        print("Запись остановлена. Файл сохранен.")

btn_record.clicked.connect(toggle_recording)

def update():
    global plot_data, total_recorded_points
    if not ser.is_open:
        try:
            ser.open()
            ser.reset_input_buffer()
            print("Соединение восстановлено!")
        except Exception:
            return

    try:
        if ser.in_waiting > 0:
            raw_bytes = ser.read(ser.in_waiting)
            if len(raw_bytes) % 2 != 0:
                raw_bytes = raw_bytes[:-1]
            if not raw_bytes:
                return

            new_voltages = []
            count = len(raw_bytes) // 2
            fmt = f"<{count}H"
            raw_values = struct.unpack(fmt, raw_bytes)

            for raw_val in raw_values:
                if 0 <= raw_val <= 4095:
                    voltage = (raw_val * 3.3) / 4095.0
                    new_voltages.append(voltage)
                    
                    if is_recording and csv_writer:
                        # Рассчитываем точное время от 0 с шагом строго 1 мс (0.001 сек)
                        relative_time = total_recorded_points * 0.001
                        # Записываем с точностью 3 знака (миллисекунды)
                        csv_writer.writerow([f"{relative_time:.3f}", raw_val, f"{voltage:.3f}"])
                        total_recorded_points += 1
            
            if new_voltages:
                plot_data.extend(new_voltages)
                if len(plot_data) > MAX_PLOT_POINTS:
                    plot_data = plot_data[-MAX_PLOT_POINTS:]
                curve.setData(plot_data)
                
    except (serial.SerialException, OSError):
        try:
            ser.close()
        except Exception:
            pass

timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(10)

main_window.closeEvent = lambda event: (f.close() if f else None, ser.close())

if __name__ == '__main__':
    QtWidgets.QApplication.instance().exec_()
