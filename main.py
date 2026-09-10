import time
import Hinge_angle
from image_viewer import LidImageViewer

sensor = Hinge_angle.LidAngleSensor()
viewer = LidImageViewer(image_folder="images")

print("\nStarting Duosition - Hinge Angle Monitor with Image Skew Viewer...")

try:
    while viewer.is_running:
        reading = sensor.get_angle()

        if isinstance(reading, (tuple, list)):
            status, angle = reading[0], reading[1] if len(reading) > 1 else None
        else:
            status = 0
            angle = reading

        if status == 0 and angle is not None:
            print(f"Returned Angle: {angle:.2f}°")
            active = viewer.update(angle)
            if not active:
                break
        else:
            print(f"Sensor did not return an angle (Status: {status}). Exiting.")
            break

        time.sleep(0.05)
except KeyboardInterrupt:
    pass
finally:
    viewer.close()
    sensor.close()