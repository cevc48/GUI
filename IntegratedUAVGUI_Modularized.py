# === Imports ===
import tkinter as tk
from tkinter import ttk
from tkinter.constants import GROOVE
from tkinter import filedialog
from tkintermapview import TkinterMapView
import math
import serial
import threading
import random
import time
import json

# === Constants ===
SERIAL_PORT = 'COM6'
LOW_BATTERY_THRESHOLD = 15.0
BAUD_RATE = 9600

# === UAV GUI Class ===
class IntegratedUAVGUI:
    def __init__(self, root):
        self.root = root
        root.title("Estação Terrestre UAV")
        root.geometry("1200x600")
        root.configure(background='light grey')
        self.root.maxsize(1200, 600)

        self.flight_data = {'altitude': 50.0, 'speed': 50.0, 'battery': 16.8, 'roll': 0.0, 'pitch': 0.0}
        self.current_heading = 0
        self.simulation_mode = tk.BooleanVar(value=False)

        # Layout frames
        main_frame = ttk.Frame(root,borderwidth=2,relief='groove')
        main_frame.grid(row=0,column=0,padx=1,pady=1,sticky='n')

        # Notebook with combined Compass+Horizon and Map
        self.notebook = ttk.Notebook(main_frame,height=600,width=800,padding=(1,1,1,1),takefocus=True)

        self.notebook.grid(row=0,column=0,sticky='nw')

        # Compass + Horizon Tab
        instrument_tab = ttk.Frame(self.notebook)
        self.canvas = tk.Canvas(instrument_tab, width=380, height=380, relief='groove', borderwidth=3,
                                border="1", highlightbackground="light grey")

        self.canvas.grid(row=0,column=2,padx=1,pady=1)
        self.heading_text = self.canvas.create_text(200, 50, text="Heading: 0°", font=("Arial", 12))
        self.compass_needle = self.canvas.create_line(150, 150, 150, 80, width=3, fill='red', arrow='last', smooth=True)
        self.draw_heading_marks()

        self.horizon_canvas = tk.Canvas(instrument_tab, width=400, height=300, bg="black", relief='groove', border="2",
                                        borderwidth=1)
        self.horizon_canvas.grid(row=0,column=0,sticky='nw',pady=40)
        self.sky = self.horizon_canvas.create_rectangle(0, 0, 200, 150, fill="skyblue", width=1)
        self.ground = self.horizon_canvas.create_rectangle(0, 150, 200, 300, fill="saddlebrown", width=1)
        self.horizon_line = self.horizon_canvas.create_line(0, 150, 400, 150, fill="yellow", width=3, smooth=True)
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
        self.map_widget = TkinterMapView(map_tab, width=800, height=600, corner_radius=1)
        self.map_widget.grid(row=0,column=0)
        self.map_widget.set_position(41.002381, -8.638930)
        self.map_widget.set_zoom(16)
        self.marker = None
        self.route_line = None
        self.route_points = []
        self.notebook.add(map_tab, text="Mapa")

        # Vertical Gauges
        self.alt_gauge = tk.Canvas(main_frame, width=50, height=220, bg='black')
        self.alt_gauge.grid(row=0,column=3,sticky='n',pady=1)
        self.alt_label = ttk.Label(main_frame, text="ALT:\n0 m", font=('Arial', 10), background='yellow',
                                   anchor="center", width=10)
        self.alt_label.grid(row=0,column=3,sticky='n',pady=230)

        self.speed_gauge = tk.Canvas(main_frame, width=50, height=220, bg='black')
        self.speed_gauge.grid(row=0,column=3,sticky='n',pady=270)
        self.speed_label = ttk.Label(main_frame, text="VEL:\n0 km/h", font=('Arial', 10), background='lightgreen',
                                     anchor="center", width=10)
        self.speed_label.grid(row=0,column=3,sticky='s',pady=230)

        self.battery_label = ttk.Label(main_frame, text="BAT:\n0.0 V", font=('Arial', 10), background='lightblue',
                                       anchor="center", width=10)
        self.battery_label.grid(row=0,column=2,sticky='n',pady=80)

        self.battery_alert = ttk.Label(main_frame, text="Bat!", font=('Arial', 10), background='red',
                                       foreground= 'black', width=10,anchor='n')
        self.battery_alert.grid(row=0,column=2,sticky='n',pady=5)
        self.flightmode_label = ttk.Label(main_frame, text="Modo: ---", font=('Arial', 10), background='cyan'
                                        , width=10)
        self.flightmode_label.grid(row=0,column=2,sticky='n',pady=30)
        self.rssi_label = ttk.Label(main_frame, text="RSSI: ---%", font=('Arial', 10), background='pink',
                                    anchor="n", width=10)
        self.rssi_label.grid(row=0,column=2,sticky='n',pady=55)

        # Simulation toggle
        self.sim_toggle = ttk.Checkbutton(main_frame, text="Modo Simulação", variable=self.simulation_mode,
                                          command=self.toggle_mode)
        self.sim_toggle.grid(row=0,column=1,sticky='e')
        # Waypoint buttons
        self.wp_create_button = ttk.Button(main_frame, text="Criar Waypoint", command=self.add_current_waypoint,
                                           width=20)
        self.wp_create_button.grid(row=0,column=1,padx=5,pady=25,sticky='n')

        self.wp_send_button = ttk.Button(main_frame, text="Enviar Waypoints", command=self.send_waypoints, width=20)
        self.wp_send_button.grid(row=0,column=1,padx=50,sticky='n',pady=75)
        self.wp_save_button = ttk.Button(main_frame, text="Gravar Waypoints", command=self.save_waypoints, width=20)
        self.wp_save_button.grid(row=0,column=1,sticky='n',pady=150)

        self.wp_load_button = ttk.Button(main_frame,text="Carregar Waypoints", command=self.load_waypoints, width=20)
        self.wp_load_button.grid(row=0,column=1,sticky='n',padx=5,pady=5)
        self.rth_button = ttk.Button(main_frame, text="Gerar RTH", command=self.generate_rth_path, width=20)
        self.rth_button.grid(row=0,column=1,sticky='n',padx=5,pady=50)
        self.edit_wp_button = ttk.Button(main_frame, text="Editar Último WP", command=self.edit_last_waypoint,
                                         width=20)
        self.edit_wp_button.grid(row=0,column=1,sticky='n',padx=5,pady=100)

        self.del_wp_button = ttk.Button(main_frame, text="Apagar Último WP", command=self.delete_last_waypoint,
                                        width=20)
        self.del_wp_button.grid(row=0,column=1,sticky='n',pady=125)

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
        self.alt_label.config(text=f"ALT: \n{alt:.0f} m")

        self.speed_gauge.delete("all")
        for i in range(-5, 12):
            value = spd + i * 10
            y = center_y - i * 10
            self.speed_gauge.create_line(0, y, 30, y, fill='white')
            self.speed_gauge.create_text(50, y, text=f"{value:.0f}", fill='white', anchor="e")
        self.speed_gauge.create_line(0, center_y, 60, center_y, fill='red', width=2)
        self.speed_label.config(text=f"VEL:\n{spd:.0f} km/h")

        self.battery_label.config(text=f"BAT: \n{bat:.1f} V")
        if bat < LOW_BATTERY_THRESHOLD:
            self.battery_alert.config(text="Bateria!", foreground='black')
        else:
            self.battery_alert.config(text="")

        self.root.after(300, self.update_gauges)

    def update_status_labels(self, flightmode='STABILIZATION', rssi=90):
        self.flightmode_label.config(text=f"Modo: {flightmode}")
        self.rssi_label.config(text=f"RSSI: {rssi}%")
        # Auto-RTH logic based on flight mode or position
        if hasattr(self, 'last_mode') and self.last_mode != flightmode:
            if flightmode == "RTH":
                print("Modo RTH ativado - rota de retorno mantida.")
        self.last_mode = flightmode

        if self.route_points and self.marker:
            dist_to_last_wp = ((self.marker.position[0] - self.route_points[-1][0]) ** 2 + (
                    self.marker.position[1] - self.route_points[-1][1]) ** 2) ** 0.5
            if dist_to_last_wp < 0.0001:
                print("UAV próximo ao último waypoint. RTH será gerado.")
                self.generate_rth_path()

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
            (40.971958, -8.646664),
            (40.972388, -8.646764),
            (40.972549, -8.647595),
            (40.972021, -8.648246),
            (40.971531, -8.647407),
            (40.972080, -8.646701)
        ] # ACCV
        while self.running:
            lat, lon = gps_points[index % len(gps_points)]
            self.current_heading = random.uniform(0, 359)
            self.flight_data['altitude'] = 50 + random.uniform(-10, 10)
            self.flight_data['speed'] = 50 + random.uniform(-5, 5)
            self.flight_data['battery'] = 15.0 + random.uniform(-2.0, 0.5)
            self.flight_data['roll'] = random.uniform(-30, 30)
            self.flight_data['pitch'] = random.uniform(-20, 20)
            mode = random.choice(['MAN', 'LOI', 'NAV', 'RTH'])
            rssi = random.randint(60, 100)
            self.root.after(0, self.update_status_labels, mode, rssi)
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

    def save_waypoints(self):
        if not self.route_points:
            print("Nenhum waypoint para salvar.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "w") as f:
                json.dump(self.route_points, f)
            print(f"Waypoints salvos em {file_path}")

    def load_waypoints(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if file_path:
            try:
                with open(file_path, "r") as f:
                    points = json.load(f)
                self.route_points.clear()
                self.map_widget.delete_all_marker()
                for idx, (lat, lon) in enumerate(points):
                    marker = self.map_widget.set_marker(lat, lon, text=f"WP{idx + 1}")
                    self.route_points.append((lat, lon))
                if len(self.route_points) > 1:
                    self.route_line = self.map_widget.set_path(self.route_points)
                print("Waypoints carregados.")
            except Exception as e:
                print(f"Erro ao carregar waypoints: {e}")

    def edit_last_waypoint(self):
        if not self.route_points:
            print("Nenhum waypoint para editar.")
            return
        lat = self.marker.position[0] if self.marker else self.route_points[-1][0]
        lon = self.marker.position[1] if self.marker else self.route_points[-1][1]
        self.route_points[-1] = (lat, lon)
        self.map_widget.delete_all_marker()
        rth_point = self.route_points[0]
        if self.route_points[-1] != rth_point:
            self.route_points.append(rth_point)
        for idx, (lat, lon) in enumerate(self.route_points):
            self.map_widget.set_marker(lat, lon, text=f"WP{idx + 1}")
        if self.route_line:
            self.map_widget.delete(self.route_line)
        if len(self.route_points) > 1:
            self.route_line = self.map_widget.set_path(self.route_points)
        print("Último waypoint editado.")

    def delete_last_waypoint(self):
        if self.route_points:
            self.route_points.pop()
            self.map_widget.delete_all_marker()
            rth_point = self.route_points[0]
        if self.route_points[-1] != rth_point:
            self.route_points.append(rth_point)
        for idx, (lat, lon) in enumerate(self.route_points):
            self.map_widget.set_marker(lat, lon, text=f"WP{idx + 1}")
        if self.route_line:
            self.map_widget.delete(self.route_line)
            if len(self.route_points) > 1:
                self.route_line = self.map_widget.set_path(self.route_points)
            else:
                self.route_line = None
            print("Último waypoint removido.")

    def generate_rth_path(self):
        if not self.route_points or not self.marker:
            return
        home = self.route_points[0]
        current = self.marker.position
        self.route_points.append(home)
        self.map_widget.set_path(self.route_points)
        print("RTH path gerado.")

    def add_current_waypoint(self):
        lat = self.marker.position[0] if self.marker else 41.002381
        lon = self.marker.position[1] if self.marker else -8.638930
        marker = self.map_widget.set_marker(lat, lon, text=f"WP{len(self.route_points) + 1}")
        self.route_points.append((lat, lon))
        if self.route_line:
            self.map_widget.delete(self.route_line)
        if len(self.route_points) > 1:
            self.route_line = self.map_widget.set_path(self.route_points)

    def send_waypoints(self):
        if not self.route_points:
            print("Nenhum waypoint definido.")
            return
        try:
            with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
                rth_point = self.route_points[0]
            if self.route_points[-1] != rth_point:
                self.route_points.append(rth_point)
            for idx, (lat, lon) in enumerate(self.route_points):
                msg = f"WP,{idx + 1},{lat:.6f},{lon:.6f}\n"
                ser.write(msg.encode())
                ser.flush()
                time.sleep(0.1)
            print("Waypoints enviados.")
        except Exception as e:
            print(f"Erro ao enviar waypoints: {e}")


# === Main ===
if __name__ == "__main__":
    root = tk.Tk()
    app = IntegratedUAVGUI(root)
    root.mainloop()