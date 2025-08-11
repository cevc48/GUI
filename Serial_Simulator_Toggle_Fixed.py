
import time
import random
import serial
import os

# Adjust to your virtual COM port
SIM_PORT = 'COM5'
BAUD_RATE = 9600

gps_points = [
    (41.002381, -8.638930),
    (41.003073, -8.638234),
    (41.003070, -8.636365),
    (41.001082, -8.636363),
    (41.001154, -8.638493),
    (41.002130, -8.638588)
]

def is_simulation_mode_enabled():
    return os.path.exists("sim_mode.flag")

flight_modes = ['MANUAL', 'STABILIZATION', 'LOITER', 'NAVIGATION', 'RTH']

try:
    ser = serial.Serial(SIM_PORT, BAUD_RATE)
    print(f"Simulador serial ativo em {SIM_PORT} a {BAUD_RATE} baud.")
    index = 0

    while True:
        if not is_simulation_mode_enabled():
            lat, lon = gps_points[index % len(gps_points)]
            heading = random.uniform(0, 360)
            altitude = 100 + random.uniform(-5, 5)
            speed = 70 + random.uniform(-3, 3)
            battery = 15.8 + random.uniform(-2.0, 0.5)
            roll = random.uniform(-25, 25)
            pitch = random.uniform(-15, 15)

            data_string = f"{lat:.6f},{lon:.6f},{heading:.1f},{altitude:.1f},{speed:.1f},{battery:.2f},{roll:.1f},{pitch:.1f}\n"
            ser.write(data_string.encode())
            ser.flush()
            index += 1
        time.sleep(1.0)
except Exception as e:
    print(f"Erro ao iniciar simulador: {e}")
