import ctypes
import time
import sys

iokit = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/IOKit.framework/IOKit')
cf = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')

iokit.IOHIDManagerCreate.restype = ctypes.c_void_p
iokit.IOHIDManagerCopyDevices.restype = ctypes.c_void_p
iokit.IOHIDDeviceGetProperty.restype = ctypes.c_void_p
cf.CFStringCreateWithCString.restype = ctypes.c_void_p
cf.CFSetGetCount.restype = ctypes.c_long

class LidAngleSensor:
    def __init__(self):
        self.manager = iokit.IOHIDManagerCreate(None, 0)
        iokit.IOHIDManagerSetDeviceMatching(ctypes.c_void_p(self.manager), None)
        iokit.IOHIDManagerOpen(ctypes.c_void_p(self.manager), 0)
        
        time.sleep(0.1)
        
        self.target_device = None
        devices_set = iokit.IOHIDManagerCopyDevices(ctypes.c_void_p(self.manager))
        
        if devices_set:
            count = cf.CFSetGetCount(ctypes.c_void_p(devices_set))
            devices_array = (ctypes.c_void_p * count)()
            cf.CFSetGetValues(ctypes.c_void_p(devices_set), devices_array)
            
            vid_key = cf.CFStringCreateWithCString(None, b"VendorID", 0x08000100)
            pid_key = cf.CFStringCreateWithCString(None, b"ProductID", 0x08000100)
            
            for i in range(count):
                dev = devices_array[i]
                vid_prop = iokit.IOHIDDeviceGetProperty(ctypes.c_void_p(dev), ctypes.c_void_p(vid_key))
                pid_prop = iokit.IOHIDDeviceGetProperty(ctypes.c_void_p(dev), ctypes.c_void_p(pid_key))
                
                if vid_prop and pid_prop:
                    vid = ctypes.c_int32()
                    pid = ctypes.c_int32()
                    cf.CFNumberGetValue(ctypes.c_void_p(vid_prop), 3, ctypes.byref(vid))
                    cf.CFNumberGetValue(ctypes.c_void_p(pid_prop), 3, ctypes.byref(pid))
                    
                    if vid.value == 0x05AC and pid.value == 0x8104:
                        self.target_device = dev
                        break

    def get_angle(self):
        if not self.target_device:
            return -1, None
            
        report = (ctypes.c_uint8 * 3)()
        report_len = ctypes.c_long(3)
        res = iokit.IOHIDDeviceGetReport(ctypes.c_void_p(self.target_device), 2, 1, report, ctypes.byref(report_len))
        
        if res == 0:
            angle_raw = report[1] | (report[2] << 8)
            angle = angle_raw / 100.0
            calibrated_angle = (angle * 100.0) - 10.0
            return 0, calibrated_angle
        return res, None

    def close(self):
        if self.manager:
            iokit.IOHIDManagerClose(ctypes.c_void_p(self.manager), 0)

if __name__ == "__main__":
    sensor = LidAngleSensor()
    try:
        while True:
            status, angle = sensor.get_angle()
            
            if status == -1:
                sys.stdout.write("\rDebug Mode - Hardware sensor not found.                ")
                break
            elif status == 0:
                sys.stdout.write(f"\rDebug Mode - Current Lid Angle: {angle:.2f}°           ")
            else:
                sys.stdout.write(f"\rDebug Mode - Read blocked by macOS (Code: {hex(status)})")
                break
            
            sys.stdout.flush()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting debug mode...")
    finally:
        sensor.close()