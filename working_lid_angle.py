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

manager = iokit.IOHIDManagerCreate(None, 0)
iokit.IOHIDManagerSetDeviceMatching(ctypes.c_void_p(manager), None)
iokit.IOHIDManagerOpen(ctypes.c_void_p(manager), 0)

devices_set = iokit.IOHIDManagerCopyDevices(ctypes.c_void_p(manager))
count = cf.CFSetGetCount(ctypes.c_void_p(devices_set))
devices_array = (ctypes.c_void_p * count)()
cf.CFSetGetValues(ctypes.c_void_p(devices_set), devices_array)

vid_key = cf.CFStringCreateWithCString(None, b"VendorID", 0x08000100)
pid_key = cf.CFStringCreateWithCString(None, b"ProductID", 0x08000100)

target_device = None

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
            target_device = dev
            break

if target_device:
    try:
        while True:
            report = (ctypes.c_uint8 * 3)()
            report_len = ctypes.c_long(3)
            res = iokit.IOHIDDeviceGetReport(ctypes.c_void_p(target_device), 2, 1, report, ctypes.byref(report_len))
            
            if res == 0:
                angle_raw = report[1] | (report[2] << 8)
                angle = angle_raw / 100.0
                sys.stdout.write(f"\r {(angle * 100)-10}")
            else:
                sys.stdout.write(f"\rSensor read failed. Error: {hex(res)}   ")
                break
            sys.stdout.flush()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting monitoring mode...")
else:
    print("Error: Lid angle sensor not found.")