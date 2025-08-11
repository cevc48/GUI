#testado em 02/06/2025 em conjunto com o Serial_Simulator_Speed_Altitude
import tkinter as tk
from tkinter import ttk
from tkintermapview import TkinterMapView
import math
import serial
import threading
import random

SERIAL_PORT = 'COM7'
BAUD_RATE = 9600
LOW_BATTERY_THRESHOLD = 14.5


class IntegratedUAVGUI:
    def __init__(self, root):
        self.root = root
        root.title("Estação Terrestre UAV")
        root.geometry("1000x900")

        self.flight_data = {'altitude': 100.0, 'speed': 75.0, 'battery': 16.8, 'roll': 0.0, 'pitch': 0.0}
        self.current_heading = 0
        self.simulation_mode = tk.BooleanVar(value=False)

        # Layout frames
        main_frame = ttk.Frame(root)
        main_frame.pack(fill="both", expand=True)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True)

        right_frame = ttk.Frame(main_frame, width=100)
        right_frame.pack(side="right", fill="y")

        # Notebook with combined Compass+Horizon and Map
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill="both", expand=True)

        # Compass + Horizon Tab
        instrument_tab = ttk.Frame(self.notebook)
        self.canvas = tk.Canvas(instrument_tab, width=400, height=400, relief="groove", borderwidth=5,
                                border="1", highlightbackground="lightgrey")
        self.canvas.pack(pady=5)
        self.heading_text = self.canvas.create_text(200, 20, text="Heading: 0°", font=("Arial", 12))
        self.compass_needle = self.canvas.create_line(200, 200, 200, 80, width=3, fill='red', arrow='last')
        self.draw_heading_marks()

        self.horizon_canvas = tk.Canvas(instrument_tab, width=400, height=300, bg="black", relief="groove", border="1",
                                        borderwidth=1)
        self.horizon_canvas.pack(pady=50)
        self.sky = self.horizon_canvas.create_rectangle(0, 0, 400, 150, fill="skyblue", width=0)
        self.ground = self.horizon_canvas.create_rectangle(0, 150, 400, 300, fill="saddlebrown", width=0)
        self.horizon_line = self.horizon_canvas.create_line(0, 150, 400, 150, fill="white", width=2)
        self.pitch_text = self.horizon_canvas.create_text(200, 280, text="Pitch: 0.0°", fill="black",
                                                          font=("Arial", 10))
        self.roll_text = self.horizon_canvas.create_text(200, 20, text="Roll: 0.0°", fill="black", font=("Arial", 10))

        self.pitch_marks = []
        for i in range(-4, 5):
            y = 150 - i * 15
            pitch_value = i * 5
            line = self.horizon_canvas.create_line(180, y, 220, y, fill="black")
            label = self.horizon_canvas.create_text(170, y, text=f"{pitch_value:+}", fill="black", font=("Arial", 8),
                                                    anchor="e")
            self.pitch_marks.append((line, label))

        self.notebook.add(instrument_tab, text="Instrumentos")

        # Map Tab
        map_tab = ttk.Frame(self.notebook)
        self.map_widget = TkinterMapView(map_tab, width=800, height=600, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True)
        self.map_widget.set_position(41.002381, -8.638930)
        self.map_widget.set_zoom(16)
        self.marker = None
        self.route_line = None
        self.route_points = []
        self.notebook.add(map_tab, text="Mapa")

        # Vertical Gauges
        self.alt_gauge = tk.Canvas(right_frame, width=60, height=300, bg='black')
        self.alt_gauge.pack(pady=(20, 10))
        self.alt_label = ttk.Label(right_frame, text="ALT:\n0 m", font=('Arial', 10), background='yellow',
                                   anchor="center")
        self.alt_label.pack()

        self.speed_gauge = tk.Canvas(right_frame, width=60, height=300, bg='black')
        self.speed_gauge.pack(pady=(20, 10))
        self.speed_label = ttk.Label(right_frame, text="VEL:\n0 km/h", font=('Arial', 10), background='lightgreen',
                                     anchor="center")
        self.speed_label.pack()

        self.battery_label = ttk.Label(right_frame, text="BAT:\n0.0 V", font=('Arial', 10), background='lightblue',
                                       anchor="center")
        self.battery_label.pack(pady=(20, 10))

        self.battery_alert = ttk.Label(right_frame, text="", font=('Arial', 10), foreground='red')
        self.battery_alert.pack(pady=(5, 10))

        # Simulation toggle
        self.sim_toggle = ttk.Checkbutton(right_frame, text="Modo Simulação", variable=self.simulation_mode,
                                          command=self.toggle_mode)
        self.sim_toggle.pack(pady=10)

        # Start background threads
        self.running = True
        self.reader_thread = threading.Thread(target=self.data_loop, daemon=True)
        self.reader_thread.start()

        self.update_compass()
        self.update_gauges()
        self.update_horizon()

    def draw_heading_marks(self):
        self.canvas.create_oval(100, 100, 300, 300, outline='black', width=2)
        for angle in range(0, 360, 30):
            x = 200 + math.sin(math.radians(angle)) * 115
            y = 200 - math.cos(math.radians(angle)) * 115
            self.canvas.create_text(x, y, text=str(angle), font=("Arial", 10, "bold"))

    def update_compass(self):
        angle = math.radians(self.current_heading)
        x = 200 + math.sin(angle) * 100
        y = 200 - math.cos(angle) * 100
        self.canvas.coords(self.compass_needle, 200, 200, x, y)
        self.canvas.itemconfig(self.heading_text, text=f"Rumo: {self.current_heading:.1f}°")
        self.root.after(100, self.update_compass)

    def update_map_position(self, lat, lon):
        self.route_points.append((lat, lon))
        if self.marker is None:
            self.marker = self.map_widget.set_marker(lat, lon, text="UAV")
        else:
            self.marker.set_position(lat, lon)
        self.map_widget.set_position(lat, lon)
        if self.route_line:
            self.map_widget.delete(self.route_line)
        self.route_line = self.map_widget.set_path(self.route_points, color="blue", width=3)

    def update_gauges(self):
        alt = self.flight_data['altitude']
        spd = self.flight_data['speed']
        bat = self.flight_data['battery']
        center_y = 150

        self.alt_gauge.delete("all")
        for i in range(-5, 12):
            value = alt + i * 10
            y = center_y - i * 10
            self.alt_gauge.create_line(0, y, 30, y, fill='white')
            self.alt_gauge.create_text(50, y, text=f"{value:.0f}", fill='white', anchor="e")
        self.alt_gauge.create_line(0, center_y, 60, center_y, fill='red', width=2)
        self.alt_label.config(text=f"ALT:\n{alt:.0f} m")

        self.speed_gauge.delete("all")
        for i in range(-5, 12):
            value = spd + i * 10
            y = center_y - i * 10
            self.speed_gauge.create_line(0, y, 30, y, fill='white')
            self.speed_gauge.create_text(50, y, text=f"{value:.0f}", fill='white', anchor="e")
        self.speed_gauge.create_line(0, center_y, 60, center_y, fill='red', width=2)
        self.speed_label.config(text=f"SPD:\n{spd:.0f} km/h")

        self.battery_label.config(text=f"BAT:\n{bat:.1f} V")
        if bat < LOW_BATTERY_THRESHOLD:
            self.battery_alert.config(text="BATERIA BAIXA!", foreground='red')
        else:
            self.battery_alert.config(text="")

        self.root.after(300, self.update_gauges)

    def update_horizon(self):
        roll = self.flight_data['roll']
        pitch = self.flight_data['pitch']
        center_x, center_y = 200, 150
        offset = pitch * 2
        angle_rad = math.radians(roll)
        dx = math.cos(angle_rad) * 200
        dy = math.sin(angle_rad) * 200
        x1 = center_x - dx
        y1 = center_y - dy + offset
        x2 = center_x + dx
        y2 = center_y + dy + offset
        self.horizon_canvas.coords(self.horizon_line, x1, y1, x2, y2)
        self.horizon_canvas.coords(self.sky, 0, 0, 400, center_y + offset)
        self.horizon_canvas.coords(self.ground, 0, center_y + offset, 400, 300)
        self.horizon_canvas.itemconfig(self.pitch_text, text=f"Pitch: {pitch:.1f}°")
        self.horizon_canvas.itemconfig(self.roll_text, text=f"Roll: {roll:.1f}°")
        for i, (line, label) in enumerate(self.pitch_marks):
            y = center_y - (i - 4) * 15
            self.horizon_canvas.coords(line, 180, y, 220, y)
            self.horizon_canvas.coords(label, 170, y)
        self.root.after(100, self.update_horizon)

    def toggle_mode(self):
        print("Simulação ligada" if self.simulation_mode.get() else "Simulação desligada")

    def data_loop(self):
        if self.simulation_mode.get():
            self.simulation_loop()
        else:
            self.read_serial_data()

    def simulation_loop(self):
        index = 0
        gps_points = [
            (41.002381, -8.638930),
            (41.003073, -8.638234),
            (41.003070, -8.636365),
            (41.001082, -8.636363),
            (41.001154, -8.638493),
            (41.002130, -8.638588)
        ]
        while self.running:
            lat, lon = gps_points[index % len(gps_points)]
            self.current_heading = random.uniform(0, 359)
            self.flight_data['altitude'] = 100 + random.uniform(-10, 10)
            self.flight_data['speed'] = 70 + random.uniform(-5, 5)
            self.flight_data['battery'] = 16.0 + random.uniform(-2.0, 0.5)
            self.flight_data['roll'] = random.uniform(-30, 30)
            self.flight_data['pitch'] = random.uniform(-20, 20)
            self.root.after(0, self.update_map_position, lat, lon)
            index += 1
            self.root.after(1000)

    def read_serial_data(self):
        try:
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
                while True:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        try:
                            lat_str, lon_str, head_str, alt_str, spd_str, bat_str, roll_str, pitch_str = line.split(',')
                            lat = float(lat_str.strip())
                            lon = float(lon_str.strip())
                            heading = float(head_str.strip())
                            altitude = float(alt_str.strip())
                            speed = float(spd_str.strip())
                            battery = float(bat_str.strip())
                            roll = float(roll_str.strip())
                            pitch = float(pitch_str.strip())
                            self.current_heading = heading
                            self.flight_data['altitude'] = altitude
                            self.flight_data['speed'] = speed
                            self.flight_data['battery'] = battery
                            self.flight_data['roll'] = roll
                            self.flight_data['pitch'] = pitch
                            self.root.after(0, self.update_map_position, lat, lon)
                        except ValueError:
                            print(f"Ignored invalid line: {line}")
        except serial.SerialException as e:
            print(f"[Serial error] {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = IntegratedUAVGUI(root)
    root.mainloop()
