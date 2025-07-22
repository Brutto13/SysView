# Built-in libraries

# External libraries
import wmi
import clr
import System
import psutil
import GPUtil
import subprocess

from statistics import mean
from textual.app import App, Screen, ComposeResult
from textual.widgets import Header, Label
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget

# Constants
TITLE = "SysView 0.0.0"

def get_cpu_name():
    try:
        output = subprocess.check_output(
            "wmic cpu get Name", shell=True
        ).decode(errors="ignore").split("\n")[1].strip()
        return output or "Unknown"
    except Exception:
        return "Not available"


def get_cpu_cache():
    c = wmi.WMI()
    result = [0]
    for cache in c.Win32_CacheMemory():
        level = {3: "L1", 4: "L2", 5: "L3"}.get(cache.Level, f"{cache.level}")
        size_kb = int(cache.MaxCacheSize)
        result.append(size_kb)
    return result


# def get_cpu_temperature():
#     try:
#         w = wmi.WMI(namespace="root\\WMI")
#         temperature_info = w.MSAcpi_ThermalZoneTemperature()
#         result = []
#         for temp in temperature_info:
#             # Temperature is given in tenths of Kelvin
#             celsius = (temp.CurrentTemperature / 10) - 273.15
#             # print(f"Temperature: {celsius:.1f} °C")
#             result.append(round(celsius, 1))
#         return result
#     except: return "Access Denied"

# def get_cpu_temperature():
#     clr.AddReference(r'P:\Python\SysView\dll-container\LibreHardwareMonitorLib.dll')
#     from LibreHardwareMonitor import Hardware
#     computer = Hardware.Computer()
#     computer.IsCpuEnabled = True
#     computer.IsGpuEnabled = True  # optional if you want GPU temps
#     computer.Open()
#
#     # Update all hardware once
#     computer.Hardware[0].Update()  # Usually Hardware[0] is CPU, but better to check
#
#     cpu_temps = {}
#
#     # Iterate through all hardware to find CPU(s)
#     for hardware in computer.Hardware:
#         if hardware.HardwareType == Hardware.HardwareType.Cpu:
#             hardware.Update()
#             for sensor in hardware.Sensors:
#                 if sensor.SensorType == Hardware.SensorType.Temperature:
#                     cpu_temps[sensor.Name] = sensor.Value
#
#     computer.Close()
#     print(cpu_temps)
#     return cpu_temps

def get_sensor_data():
    clr.AddReference(r'P:\Python\SysView\dll-container\LibreHardwareMonitorLib.dll')
    from LibreHardwareMonitor import Hardware
    computer = Hardware.Computer()
    computer.IsCpuEnabled = True
    computer.IsGpuEnabled = True
    computer.IsMotherboardEnabled = True
    computer.IsMemoryEnabled = True
    computer.IsStorageEnabled = False
    computer.Open()

    sensor_info = {}

    for hw in computer.Hardware:
        hw.Update()
        name = hw.Name
        sensor_info[name] = {}

        for sensor in hw.Sensors:
            stype = str(sensor.SensorType)
            sname = sensor.Name
            svalue = sensor.Value

            if sensor.SensorType in (
                Hardware.SensorType.Temperature,
                Hardware.SensorType.Voltage,
                Hardware.SensorType.Power,
                Hardware.SensorType.Clock,
                Hardware.SensorType.Fan
            ):
                sensor_info[name][f"{stype}: {sname}"] = svalue

        for sub in hw.SubHardware:
            sub.Update()
            for sensor in sub.Sensors:
                stype = str(sensor.SensorType)
                sname = sensor.Name
                svalue = sensor.Value

                if sensor.SensorType in (
                    Hardware.SensorType.Temperature,
                    Hardware.SensorType.Voltage,
                    Hardware.SensorType.Power,
                    Hardware.SensorType.Clock,
                    Hardware.SensorType.Fan
                ):
                    sensor_info[name][f"{stype}: {sname}"] = svalue

    computer.Close()
    return sensor_info

def get_ram_name():
    c = wmi.WMI()
    mem = c.Win32_PhysicalMemory()[0]
    return mem.Manufacturer

class TitledSection(Vertical):
    def __init__(self, title: str, content: Widget) -> None:
        super().__init__(
            content,
            classes='titled-section'
        )
        self.border_title = title
        self.classes = "titled-section"


# Main Screen
class MainScreen(Screen):
    def __init__(self):
        super().__init__()
        self.label_cpu_usage   = Label()
        self.label_cpu_tempC   = Label()
        self.label_cpu_power   = Label()
        self.label_cpu_voltage = Label()

        self.label_ram_usage = Label()
        self.label_ram_total = Label()

        self.label_gpu_temp  = Label()
        self.label_gpu_power = Label()
        self.label_gpu_clock = Label()
        self.label_gpu_fan_1 = Label()
        self.label_gpu_fan_2 = Label()
        self.label_gpu_fan_3 = Label()

        self.system_view = Vertical(
            Label(f"CPU Name: {CPU_NAME}"),
            Label(f"GPU Name: {GPU_NAME}"),
            Label(f"RAM Name: {RAM_NAME} (JEDEC ID)")
        )

        self.cpu_view = Vertical(
            self.label_cpu_usage,
            self.label_cpu_power,
            self.label_cpu_tempC,
            self.label_cpu_voltage,
            Label(f"Cache L1 Size: {CPU_CACHE[1]} KB"),
            Label(f"Cache L2 Size: {CPU_CACHE[2]} KB"),
            Label(f"Cache L3 Size: {CPU_CACHE[3]} KB")
        )

        self.ram_view = Vertical()

        self.gpu_view = Vertical(
            self.label_gpu_temp,
            self.label_gpu_power,
            self.label_gpu_clock,
            self.label_gpu_fan_1,
            self.label_gpu_fan_2,
            self.label_gpu_fan_3
        )

        self.set_interval(1, self.chk_val)

    # def on_screen_resume(self):


    def chk_val(self):
        sensor_data = get_sensor_data()
        cpu_data = sensor_data[CPU_NAME]
        gpu_data = sensor_data[GPU_NAME]

        self.label_cpu_usage.update(F"CPU Usage:       {psutil.cpu_percent()} %")
        self.label_cpu_power.update(F"CPU Power:       {round(cpu_data['Power: CPU Package'], 1)} W")
        self.label_cpu_tempC.update(F"CPU Temperature: {cpu_data['Temperature: CPU Package']} *C")
        self.label_cpu_voltage.update(F"CPU Voltage:     {round(cpu_data['Voltage: CPU Core'], 1)} V")

        self.label_gpu_temp.update (F"GPU Temperature: {gpu_data['Temperature: GPU Core']} *C")
        self.label_gpu_clock.update(F"GPU Core Clock:  {gpu_data['Clock: GPU Core']} MHz")
        self.label_gpu_power.update(F"GPU Power:       {round(gpu_data['Power: GPU Package'], 1)} W")

        # try update fans. "Not detected" Message fallback
        try: self.label_gpu_fan_1.update(F"GPU Fan 1 Speed: {gpu_data['Fan: GPU Fan 1']} RPM"),
        except KeyError: self.label_gpu_fan_1.update("[red]Not detected[/red]")

        try: self.label_gpu_fan_2.update(F"GPU Fan 2 Speed: {gpu_data['Fan: GPU Fan 2']} RPM"),
        except KeyError: self.label_gpu_fan_2.update("[red]Not detected[/red]")

        try: self.label_gpu_fan_3.update(F"GPU Fan 3 Speed: {gpu_data['Fan: GPU Fan 3']} RPM"),
        except KeyError: self.label_gpu_fan_3.update("GPU Fan 3 Speed: [red]Not detected[/red]")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(TitledSection("[cyan]System Overview[/cyan]", self.system_view), TitledSection(f"[green]{CPU_NAME}[/green]", self.cpu_view)),
            Horizontal(TitledSection("[yellow]RAM Information[/yellow]", self.ram_view), TitledSection(f"[purple]{GPU_NAME}[/purple]", self.gpu_view))
        )

class Launcher(App):
    CSS = """
    .titled-section {
        border: solid white;
        padding: 1 2;
        margin: 1;
        height: 1fr;
        background: $surface;
        color: white;
        width: 1fr;
    }
    
    .section-title {
        text-style: bold;
    }
    """
    # def on_show(self):
    #     self.app.push_screen(MainScreen())

    def on_mount(self):
        self.title = TITLE
        self.app.push_screen(MainScreen())

if __name__ == '__main__':
    # print(get_sensor_data())
    # quit()
    CPU_NAME = get_cpu_name()
    CPU_NAME = CPU_NAME[:CPU_NAME.find(" CPU")].replace("(R)", "").replace("(TM)", "")
    CPU_FREQ = psutil.cpu_freq()
    CPU_CACHE = get_cpu_cache()

    RAM_NAME = get_ram_name()
    RAM_DTCT = round(psutil.virtual_memory().total/(1024**3), 1)

    gpu_data = GPUtil.getGPUs()

    # GPU Name
    try: GPU_NAME = str(gpu_data[0].name)
    except: GPU_NAME = "Internal Graphics"

    # GPU VRAM total
    try: GPU_VRAM_TOTAL = gpu_data[0].memoryTotal
    except IndexError: GPU_VRAM_TOTAL = "[red]Not Available[/red]"

    Launcher().run()
