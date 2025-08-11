 

# PyQt6 UAV Ground Station with Compass and Artificial Horizon
import sys
import math
import random
import json
import serial
import threading
import time
import os

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QPushButton, QCheckBox, QFileDialog, QFrame, QGraphicsView, QGraphicsScene
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPen, QColor



SERIAL_PORT = 'COM7'
BAUD_RATE = 9600
LOW_BATTERY_THRESHOLD = 15.0

class VerticalGauge(QGraphicsView):
    def __init__(self, label_text, unit, color):
        super().__init__()
        self.label_text = label_text
        self.unit = unit
        self.color = color
        self.value = 0

        self.setFixedSize(80, 160)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)


    def update_value(self, val):
        self.value = val
        self.draw_gauge()

    def draw_gauge(self):
        self.scene.clear()
        center_y = 110
        for i in range(-5, 6):
            val = self.value + i * 10
            y = center_y - i * 10
            self.scene.addLine(0, y, 30, y, QPen(Qt.GlobalColor.white))
            self.scene.addText(f"{val:.0f}").setPos(35, y - 8)
        self.scene.addLine(0, center_y, 60, center_y, QPen(Qt.GlobalColor.red, 2))
        self.scene.addText(f"{self.label_text}: {self.value:.0f} {self.unit}").setPos(5, 140)


class CompassWidget(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setFixedSize(300, 300)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.heading = 0

    def update_heading(self, heading):
        self.heading = heading
        self.draw_compass()

    def draw_compass(self):
        self.scene.clear()
        center = 150
        radius = 100
        self.scene.addEllipse(center - radius, center - radius, 2*radius, 2*radius, QPen(Qt.GlobalColor.black))
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x = center + math.sin(rad) * radius
            y = center - math.cos(rad) * radius
            text = self.scene.addText(str(angle))
            text.setPos(x - 10, y - 10)
        needle_angle = math.radians(self.heading)
        x = center + math.sin(needle_angle) * (radius - 10)
        y = center - math.cos(needle_angle) * (radius - 10)
        self.scene.addLine(center, center, x, y, QPen(Qt.GlobalColor.red, 3))

class HorizonWidget(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setFixedSize(400, 300)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.draw_horizon()
        self.roll = 0
        self.pitch = 0

    def update_attitude(self, roll, pitch):
        self.roll = roll
        self.pitch = pitch
        self.draw_horizon()

    def draw_horizon(self):
        self.pitch = 0
        self.roll = 0
        self.scene.clear()
        center_x, center_y = 200, 150
        offset = self.pitch * 2
        angle_rad = math.radians(self.roll)
        dx = math.cos(angle_rad) * 200
        dy = math.sin(angle_rad) * 200
        x1 = center_x - dx
        y1 = center_y - dy + offset
        x2 = center_x + dx
        y2 = center_y + dy + offset
        self.scene.addRect(0, 0, 400, center_y + offset, QPen(), QColor("skyblue"))
        self.scene.addRect(0, center_y + offset, 400, 300 - (center_y + offset), QPen(), QColor("saddlebrown"))
        self.scene.addLine(x1, y1, x2, y2, QPen(Qt.GlobalColor.yellow, 3))
        for i in range(-4, 5):
            y = center_y - (i * 15)
            self.scene.addLine(180, y, 220, y, QPen(Qt.GlobalColor.black))
            self.scene.addText(f"{i*5:+}").setPos(160, y - 8)
        self.scene.addText(f"Roll: {self.roll:.1f}").setPos(10, 10)
        self.scene.addText(f"Pitch: {self.pitch:.1f}").setPos(10, 270)

class UAVGroundStation(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Estação Terrestre UAV - PyQt6")
        self.setFixedSize(1200, 600)

        self.flight_data = {'altitude': 50.0, 'speed': 50.0, 'battery': 16.8}
        self.simulation_mode = False
        self.running = True
        self.route_points = []

        main_layout = QHBoxLayout(self)

        # Tabs
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.instrument_tab = QWidget()
        self.map_tab = QWidget()
        self.tabs.addTab(self.instrument_tab, "Instrumentos")
        self.tabs.addTab(self.map_tab, "Mapa")

        # Instrument tab layout
        instr_layout = QHBoxLayout()
        self.instrument_tab.setLayout(instr_layout)

        # Placeholder for artificial horizon and compass
        self.horizon = HorizonWidget()
        instr_layout.addWidget(self.horizon)
        self.horizon.setFrameShape(QFrame.Shape.Box)
        self.horizon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.horizon.setFixedSize(400, 300)
        instr_layout.addWidget(self.horizon)

        self.compass = CompassWidget()
        instr_layout.addWidget(self.compass)
        self.compass.setFrameShape(QFrame.Shape.Box)
        self.compass.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compass.setFixedSize(300, 300)
        instr_layout.addWidget(self.compass)

        # Right-side gauges and controls
        right_panel = QVBoxLayout()

        self.alt_gauge = VerticalGauge("ALT", "m", QColor("yellow"))
        self.speed_gauge = VerticalGauge("VEL", "km/h", QColor("lightgreen"))
        right_panel.addWidget(self.alt_gauge)
        right_panel.addWidget(self.speed_gauge)

        self.battery_label = QLabel("BAT: 0.0 V")
        self.battery_label.setStyleSheet("background-color: lightblue")
        right_panel.addWidget(self.battery_label)

        self.battery_alert = QLabel("Bat!")
        self.battery_alert.setStyleSheet("background-color: red; color: black")
        right_panel.addWidget(self.battery_alert)

        self.flightmode_label = QLabel("Modo: ---")
        self.flightmode_label.setStyleSheet("background-color: cyan")
        right_panel.addWidget(self.flightmode_label)

        self.rssi_label = QLabel("RSSI: ---")
        self.rssi_label.setStyleSheet("background-color: pink")
        right_panel.addWidget(self.rssi_label)

        self.sim_toggle = QCheckBox("Modo Simulação")
        self.sim_toggle.stateChanged.connect(self.toggle_mode)
        right_panel.addWidget(self.sim_toggle)

        # Waypoint Buttons
        self.buttons = {}
        for label in ["Criar Waypoint", "Enviar Waypoints", "Gravar Waypoints",
                      "Carregar Waypoints", "Gerar RTH", "Editar Último WP", "Apagar Último WP"]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, b=label: self.handle_button(b))
            right_panel.addWidget(btn)
            self.buttons[label] = btn

        main_layout.addLayout(right_panel)

        # Timers
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_loop)
        self.timer.start(1000)

    def toggle_mode(self):
        self.simulation_mode = self.sim_toggle.isChecked()
        print("Simulação ligada" if self.simulation_mode else "Simulação desligada")
        if self.simulation_mode:
            open("sim_mode.flag", "w").close()
        else:
            if os.path.exists("sim_mode.flag"):
                os.remove("sim_mode.flag")

    def update_loop(self):
        if self.simulation_mode:
            self.simulate_step()
        else:
            self.read_serial_step()
        self.update_gauges()

    def update_gauges(self):
        self.alt_gauge.update_value(self.flight_data["altitude"])
        self.speed_gauge.update_value(self.flight_data["speed"])
        self.battery_label.setText(f"BAT: {self.flight_data['battery']:.1f} V")
        if self.flight_data["battery"] < LOW_BATTERY_THRESHOLD:
            self.battery_alert.setText("Bateria!")
        else:
            self.battery_alert.setText("")

    def simulate_step(self):
        self.flight_data['altitude'] = 50 + random.uniform(-10, 10)
        self.flight_data['speed'] = 50 + random.uniform(-5, 5)
        self.flight_data['battery'] = 15.0 + random.uniform(-2.0, 0.5)
        self.flightmode_label.setText("Modo: SIM")
        self.rssi_label.setText(f"RSSI: {random.randint(60, 100)}%")
        self.horizon.update_attitude(random.uniform(-30, 30), random.uniform(-20, 20))
        self.compass.update_heading(random.uniform(0, 360))

    def read_serial_step(self):
        try:
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
                line = ser.readline().decode("utf-8").strip()
                if line:
                    lat, lon, head, alt, spd, bat, roll, pitch = map(float, line.split(","))
                    self.flight_data['altitude'] = alt
                    self.flight_data['speed'] = spd
                    self.flight_data['battery'] = bat
                    self.flightmode_label.setText("Modo: NAV")
                    self.rssi_label.setText("RSSI: 90%")
        except:
            pass

    def handle_button(self, label):
        print(f"Botão '{label}' clicado (função ainda não implementada)")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UAVGroundStation()
    window.show()
    sys.exit(app.exec())
