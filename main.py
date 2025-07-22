# Built-in libraries
import os
import sys
from typing import Iterable

# External libraries
import wmi
import clr
import System
import psutil
import GPUtil
import subprocess

from statistics import mean
from textual.app import App, Screen, ComposeResult, SystemCommand
from textual.widgets import Header, Label, Footer, DataTable
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.binding import Binding

# Constants
TITLE = "SysView 0.0.0"


def get_color(value: float | int) -> str:
    if value >= 95: return "red"
    elif value >= 50: return "yellow"
    else: return "green"


def get_cpu_freq_color(value: float | int) -> str:
    if value >= 4900: return "red"
    elif value >= 4000: return "yellow"
    else: return "green"


def get_voltage_color(value: float | int) -> str:
    if value >= 1.3: return "red"
    elif value >= 1: return "yellow"
    else: return "green"


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


def get_sensor_data():
    try: clr.AddReference(sys._MEIPASS + r'\dll-container\LibreHardwareMonitorLib.dll')
    except AttributeError: clr.AddReference(os.getcwd() + r'\dll-container\LibreHardwareMonitorLib.dll')

    from LibreHardwareMonitor import Hardware
    computer = Hardware.Computer()
    computer.IsCpuEnabled = True
    computer.IsGpuEnabled = True
    computer.IsMotherboardEnabled = False
    computer.IsMemoryEnabled = False
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
        self.label_cpu_freqc   = Label()
        self.label_cpu_tempC   = Label()
        self.label_cpu_power   = Label()
        self.label_cpu_voltage = Label()

        self.label_ram_status = Label()
        self.label_swp_status = Label()

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
            self.label_cpu_freqc,
            self.label_cpu_power,
            self.label_cpu_tempC,
            self.label_cpu_voltage
        )

        self.ram_view = Vertical(
            self.label_ram_status,
            self.label_swp_status
        )

        self.gpu_view = Vertical(
            self.label_gpu_temp,
            self.label_gpu_power,
            self.label_gpu_clock,
            self.label_gpu_fan_1,
            self.label_gpu_fan_2,
            self.label_gpu_fan_3
        )

        self.tick = self.set_interval(1, self.chk_val)

    def on_screen_suspend(self) -> None:
        self.tick.stop()

    def chk_val(self):
        ram_used = round(psutil.virtual_memory().used/(1024**3), 1)
        swap_used = round(psutil.swap_memory().used/(1024**3), 1)
        sensor_data = get_sensor_data()
        cpu_data = sensor_data[CPU_NAME]
        try: gpu_data = sensor_data[GPU_NAME]
        except KeyError: gpu_data = None

        # Get colors for CPU data
        cpu_usage = psutil.cpu_percent()
        cpu_usage_color = get_color(cpu_usage)
        cpu_freq = cpu_data["Clock: CPU Core #1"]
        cpu_freq_color = get_cpu_freq_color(cpu_freq)
        cpu_power = cpu_data['Power: CPU Package']
        cpu_power_color = get_color(cpu_power)
        cpu_temp = cpu_data['Temperature: CPU Package']
        cpu_temp_color = get_color(cpu_temp)
        cpu_volt = cpu_data['Voltage: CPU Core']
        cpu_volt_color = get_voltage_color(cpu_volt)

        # Get colors for GPU data
        gpu_temp = gpu_data['Temperature: GPU Core']
        gpu_temp_color = get_color(gpu_temp)
        gpu_power = gpu_data['Power: GPU Package']
        gpu_power_color = get_color(gpu_power)


        # update Labels
        self.label_cpu_usage.update(F"CPU Usage:       [{cpu_usage_color}]{cpu_usage}[/{cpu_usage_color}] %")
        self.label_cpu_freqc.update(F"CPU Frequency    [{cpu_freq_color}]{round(cpu_freq, 1)}[/{cpu_freq_color}] MHz")
        self.label_cpu_power.update(F"CPU Power:       [{cpu_power_color}]{round(cpu_power, 1)}[/{cpu_power_color}] W")
        self.label_cpu_tempC.update(F"CPU Temperature: [{cpu_temp_color}]{cpu_temp}[/{cpu_temp_color}] *C")
        self.label_cpu_voltage.update(F"CPU Voltage:     [{cpu_volt_color}]{round(cpu_volt, 1)}[/{cpu_volt_color}] V")

        self.label_ram_status.update(F"RAM Memory Used:  {ram_used} / {RAM_DTCT} GB ({round((ram_used/RAM_DTCT)*100, 1)} %)")
        self.label_swp_status.update(F"SWAP Memory Used: {swap_used} / {SWP_DTCT} GB ({round((swap_used/SWP_DTCT)*100, 1)} %)")

        # Try to get GPU data. This data may not be available e.g. for internal graphics or on VM
        if gpu_data is not None:
            self.label_gpu_temp.update (F"GPU Temperature: [{gpu_temp_color}]{gpu_temp}[/{gpu_temp_color}] *C")
            self.label_gpu_clock.update(F"GPU Core Clock:  {gpu_data['Clock: GPU Core']} MHz")
            self.label_gpu_power.update(F"GPU Power:       [{gpu_power_color}]{round(gpu_power, 1)}[/{gpu_power_color}] W")

            # try update fans. "Not detected" Message fallback if GPU has less than 3 fans
            try: self.label_gpu_fan_1.update(F"GPU Fan 1 Speed: {gpu_data['Fan: GPU Fan 1']} RPM"),
            except KeyError: self.label_gpu_fan_1.update("[red][italic]Not detected[/italic][/red]")

            try: self.label_gpu_fan_2.update(F"GPU Fan 2 Speed: {gpu_data['Fan: GPU Fan 2']} RPM"),
            except KeyError: self.label_gpu_fan_2.update("[red][italic]Not detected[/italic][/red]")

            try: self.label_gpu_fan_3.update(F"GPU Fan 3 Speed: {gpu_data['Fan: GPU Fan 3']} RPM"),
            except KeyError: self.label_gpu_fan_3.update("GPU Fan 3 Speed: [red]Not detected[/red]")
        else: self.label_gpu_temp.update("[red][italic]Not detected[/italic][/red]")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(TitledSection("[cyan]System Overview[/cyan]", self.system_view), TitledSection(f"[green]{CPU_NAME}[/green]", self.cpu_view)),
            Horizontal(TitledSection("[yellow]RAM Information[/yellow]", self.ram_view), TitledSection(f"[purple]{GPU_NAME}[/purple]", self.gpu_view))
        )
        yield Footer()


# class CPUDetails(Screen):
#     def __init__(self):
#         super().__init__()
#         self.table = DataTable(cursor_type='none')
#         self.tick = self.set_interval(1, self.chk_val)
#
#     def chk_val(self):
#         rows = [
#             ("CPU Core", "Load", "Temperature", "Voltage", "Clock Frequency")
#         ]
#
#         # Add columns if they are not.
#         try:
#             for col in rows[0]:
#                 self.table.add_column(col, key=col)
#         except Exception: pass
#
#         sensors = get_sensor_data()
#         cpu_data = sensors[CPU_NAME]
#         cpu_usage = psutil.cpu_percent(0.5, percpu=True)
#
#         # update (clear and redraw)
#         self.table.clear(columns=False)
#         for i in range(os.cpu_count()):
#             rows.append(
#                 (F"CPU Core #{i}", F"{cpu_usage[i]}%", F"{cpu_data[F'Temperature: CPU Core #{i+1}']} *C", F"{round(cpu_data[F'Voltage: CPU Core #{i+1}'], 1)} V", F"{round(cpu_data[F'Clock: CPU Core #{i+1}'], 1)} MHz")
#             )
#
#         for row in rows[1:]:
#             self.table.add_row(*row)
#
#     def on_screen_suspend(self):
#         self.tick.stop()
#
#
#     def compose(self) -> ComposeResult:
#         yield Header()
#         yield TitledSection("[green]CPU Per-Core Details[/green]", self.table)
#         yield Footer()

class CPUDetails(Screen):
    def __init__(self):
        super().__init__()
        self.temps_container = Vertical()
        self.clock_container = Vertical()
        self.loads_container = Vertical()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(TitledSection("[green]CPU Temperatures[/green]", self.temps_container), TitledSection("[green]CPU Clocks[/green]", self.clock_container)),
            Horizontal(TitledSection("[green]CPU Core Loads[/green]", self.loads_container))
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

    BINDINGS = [
        Binding(
            key='ctrl+q',
            action='quit',
            description="Quit the app"
        )
    ]

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        yield SystemCommand("Quit", "Quit the app", sys.exit)
        yield SystemCommand("Main Screen", "Go to main screen", lambda: self.push_screen(MainScreen()))
        yield SystemCommand("CPU Info", "Detailed CPU Information", lambda: self.push_screen(CPUDetails()))

    def on_mount(self):
        self.title = TITLE
        self.app.push_screen(MainScreen())


if __name__ == '__main__':
    CPU_NAME = get_cpu_name()
    CPU_NAME = CPU_NAME[:CPU_NAME.find(" CPU")].replace("(R)", "").replace("(TM)", "")
    CPU_FREQ = psutil.cpu_freq()
    CPU_CACHE = get_cpu_cache()

    RAM_NAME = get_ram_name()
    RAM_DTCT = round(psutil.virtual_memory().total/(1024**3), 1)

    SWP_DTCT = round(psutil.swap_memory().total/(1024**3), 1)

    gpu_data = GPUtil.getGPUs()

    # GPU Name
    try: GPU_NAME = str(gpu_data[0].name)
    except: GPU_NAME = "Internal Graphics"

    # GPU VRAM total
    try: GPU_VRAM_TOTAL = gpu_data[0].memoryTotal
    except IndexError: GPU_VRAM_TOTAL = "[red]Not Available[/red]"

    Launcher().run()
