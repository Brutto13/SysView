# Built-in libraries
import os
import sys
import asyncio
from typing import Iterable

# External libraries
import wmi
import clr
import System
import psutil
import GPUtil
import plotext as plt
import subprocess

from statistics import mean
from rich import print as rprint
from rich.console import Console
from textual.app import App, Screen, ComposeResult, SystemCommand
from textual.widgets import Header, Label, Footer, DataTable, Static
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.binding import Binding

# Fetch DLL
try:
    clr.AddReference(sys._MEIPASS + r'\dll-container\LibreHardwareMonitorLib.dll')
except AttributeError:
    clr.AddReference(os.getcwd() + r'\dll-container\LibreHardwareMonitorLib.dll')

from LibreHardwareMonitor import Hardware

computer = Hardware.Computer()
computer.IsCpuEnabled = True
computer.IsGpuEnabled = True
computer.IsMotherboardEnabled = False
computer.IsMemoryEnabled = False
computer.IsStorageEnabled = False
computer.Open()

# Constants
TITLE = "SysView 0.0.0"

# Global Variables
cpu_temps: list[float] = [0]


def get_color(value: float | int) -> str:
    if value >= 95: return "red"
    elif value >= 50: return "yellow"
    elif value >= 10: return "green"
    else: return "cyan"
    # else: return "blue"


def get_cpu_freq_color(value: float | int) -> str:
    if value >= 4900: return "red"
    elif value >= 4000: return "yellow"
    else: return "green"


def get_voltage_color(value: float | int) -> str:
    if value >= 1.3: return "red"
    elif value >= 1.2: return "yellow"
    else: return "green"


def get_gpu_fan_color(value: float | int) -> str:
    if value >= 2500: return "red"
    elif value >= 1500: return "yellow"
    else: return "green"


def get_gpu_clock_color(value: float | int) -> str:
    if value >= 1500: return "red"
    elif value >= 1000: return "yellow"
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


def get_sensor_data(computer):
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

    # computer.Close()
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
            Label(f"CPU Name: [green]{CPU_NAME}[/green]"),
            Label(f"GPU Name: [blue]{GPU_NAME}[/blue]"),
            Label(f"RAM Name: [yellow]{RAM_NAME}[/yellow] (JEDEC ID)")
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

        self.tick = self.set_interval(0.5, self.chk_val)

    def on_screen_suspend(self) -> None:
        self.tick.stop()

    def chk_val(self):
        ram_used = round(psutil.virtual_memory().used/(1024**3), 1)
        swap_used = round(psutil.swap_memory().used/(1024**3), 1)
        sensor_data = get_sensor_data(computer)
        cpu_data = sensor_data[CPU_NAME]

        try: gpu_data = sensor_data[GPU_NAME]
        except: gpu_data = None

        # Get colors for CPU data
        cpu_usage = psutil.cpu_percent()
        cpu_usage_color = get_color(cpu_usage)
        # cpu_freq = cpu_data["Clock: CPU Core #1"]
        cpu_freq = round(mean([cpu_data[f'Clock: CPU Core #{i+1}'] for i in range(os.cpu_count())]))
        cpu_freq_color = get_cpu_freq_color(cpu_freq)
        cpu_power = cpu_data['Power: CPU Package']
        cpu_power_color = get_color(cpu_power)
        cpu_temp = cpu_data['Temperature: CPU Package']
        cpu_temp_color = get_color(cpu_temp)
        cpu_volt = cpu_data['Voltage: CPU Core']
        cpu_volt_color = get_voltage_color(cpu_volt)

        # Get colors for GPU data (pass if not available)
        if gpu_data is not None:
            gpu_temp = gpu_data['Temperature: GPU Core']
            gpu_temp_color = get_color(gpu_temp)
            gpu_power = gpu_data['Power: GPU Package']
            gpu_power_color = get_color(gpu_power)
            gpu_clock = gpu_data['Clock: GPU Core']
            gpu_clock_color = get_gpu_clock_color(gpu_clock)

            # try fetch GPU Fans data (Not detected fallback if unavailable)
            try:
                gpu_fan_1 = gpu_data['Fan: GPU Fan 1']
                gpu_fan_1_color = get_gpu_fan_color(gpu_fan_1)
            except KeyError:
                gpu_fan_1 = f"Not Detected"
                gpu_fan_1_color = "red"

            try:
                gpu_fan_2 = gpu_data['Fan: GPU Fan 2']
                gpu_fan_2_color = get_gpu_fan_color(gpu_fan_2)
            except KeyError:
                gpu_fan_2 = f"Not Detected"
                gpu_fan_2_color = "red"

            try:
                gpu_fan_3 = gpu_data['Fan: GPU Fan 3']
                gpu_fan_3_color = get_gpu_fan_color(gpu_fan_3)
            except KeyError:
                gpu_fan_3 = f"Not Detected"
                gpu_fan_3_color = "red"


        # update Labels
        self.label_cpu_usage.update(F"CPU Usage:       [{cpu_usage_color}]{cpu_usage}[/{cpu_usage_color}] %")
        self.label_cpu_freqc.update(F"CPU Frequency    [{cpu_freq_color}]{round(cpu_freq, 1)}[/{cpu_freq_color}] MHz")
        self.label_cpu_power.update(F"CPU Power:       [{cpu_power_color}]{round(cpu_power, 1)}[/{cpu_power_color}] W")
        self.label_cpu_tempC.update(F"CPU Temperature: [{cpu_temp_color}]{cpu_temp}[/{cpu_temp_color}] *C")
        self.label_cpu_voltage.update(F"CPU Voltage:     [{cpu_volt_color}]{round(cpu_volt, 1)}[/{cpu_volt_color}] V")

        self.label_ram_status.update(F"RAM Memory Used:  {ram_used} / {RAM_DTCT} GB ({round((ram_used/RAM_DTCT)*100, 1)} %)")
        self.label_swp_status.update(F"SWAP Memory Used:  {swap_used} /  {SWP_DTCT} GB ({round((swap_used/SWP_DTCT)*100, 1)} %)")

        # Try to get GPU data. This data may not be available e.g. for internal graphics or on VM
        if gpu_data is not None:
            self.label_gpu_temp.update (F"GPU Temperature: [{gpu_temp_color}]{gpu_temp}[/{gpu_temp_color}] *C")
            self.label_gpu_clock.update(F"GPU Core Clock:  [{gpu_clock_color}]{gpu_clock}[/{gpu_clock_color}] MHz")
            self.label_gpu_power.update(F"GPU Power:       [{gpu_power_color}]{round(gpu_power, 1)}[/{gpu_power_color}] W")
            self.label_gpu_fan_1.update(F"GPU Fan 1 Speed: [{gpu_fan_1_color}]{gpu_fan_1}[/{gpu_fan_1_color}] RPM")
            self.label_gpu_fan_2.update(F"GPU Fan 2 Speed: [{gpu_fan_2_color}]{gpu_fan_2}[/{gpu_fan_2_color}] RPM")
            self.label_gpu_fan_3.update(F"GPU Fan 3 Speed: [{gpu_fan_3_color}]{gpu_fan_3}[/{gpu_fan_3_color}] RPM")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(TitledSection("[cyan]System Overview[/cyan]", self.system_view), TitledSection(f"[green]{CPU_NAME}[/green]", self.cpu_view)),
            Horizontal(TitledSection("[yellow]Memory Information[/yellow]", self.ram_view), TitledSection(f"[blue]{GPU_NAME}[/blue]", self.gpu_view))
        )
        yield Footer()


class CPUDetails(Screen):
    CSS = """
    Screen {
        background: black;
        color: white;
    }
    """

    def __init__(self):
        super().__init__()
        self.temps_table = DataTable(cursor_type='none')
        self.clock_table = DataTable(cursor_type='none')
        self.loads_table = DataTable(cursor_type='none')
        self.volts_table = DataTable(cursor_type='none')

        self.temps_container = Vertical(self.temps_table)
        self.clock_container = Vertical(self.clock_table)
        self.loads_container = Vertical(self.loads_table)
        self.volts_container = Vertical(self.volts_table)
        self.timer = self.set_interval(0.5, self.chk_vals)

    def chk_vals(self):
        global CPU_NAME
        # Fetch CPU Data
        cpu_data = get_sensor_data(computer)[CPU_NAME]
        cpu_count = os.cpu_count()
        cores_num = list(range(cpu_count))

        temp_rows = []
        clock_rows = []
        loads_rows = []
        volts_rows = []

        temp_data  = [cpu_data[f'Temperature: CPU Core #{i+1}'] for i in range(cpu_count)]
        clock_data = [round(cpu_data[f'Clock: CPU Core #{i+1}'], 1) for i in range(cpu_count)]
        loads_data = psutil.cpu_percent(0.5, percpu=True)
        volts_data = [round(cpu_data[f'Voltage: CPU Core #{i+1}'], 3) for i in range(cpu_count)]

        # Update rows
        for core in cores_num:
            temp = temp_data[core]
            temp_color = get_color(temp)
            clock = clock_data[core]
            clock_color = get_cpu_freq_color(clock)
            load = loads_data[core]
            load_color = get_color(load)
            volt = volts_data[core]
            volt_color = get_voltage_color(volt)

            temp_rows.append((F"CPU-{core}", F"[{temp_color}]{temp}[/{temp_color}] *C"))
            clock_rows.append((F"CPU-{core}", F"[{clock_color}]{clock}[/{clock_color}] MHz"))
            loads_rows.append((F"CPU-{core}", F"[{load_color}]{load}[/{load_color}] %"))
            volts_rows.append((F"CPU-{core}", F"[{volt_color}]{volt}[/{volt_color}] V"))

        # Handle temperatures table updating
        self.temps_table.clear(columns=True)
        self.temps_table.add_columns("CPU Core", "Temperature")
        for row in temp_rows: self.temps_table.add_row(*row)

        # Handle clock frequencies table updating
        self.clock_table.clear(columns=True)
        self.clock_table.add_columns("CPU Core", "Clock Frequency")
        for row in clock_rows: self.clock_table.add_row(*row)

        # Handle Core loads table updating
        self.loads_table.clear(columns=True)
        self.loads_table.add_columns("CPU Core", "Core load")
        for row in loads_rows: self.loads_table.add_row(*row)

        # Handle Core Voltages
        self.volts_table.clear(columns=True)
        self.volts_table.add_columns("CPU Core", "Core Voltage")
        for row in volts_rows: self.volts_table.add_row(*row)

    def on_screen_suspend(self): self.timer.stop()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(TitledSection("[green]CPU Temperatures[/green]", self.temps_container), TitledSection("[green]CPU Clocks[/green]", self.clock_container)),
            Horizontal(TitledSection("[green]CPU Core Loads[/green]", self.loads_container), TitledSection("[green]CPU Voltages[/green]", self.volts_container))
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
    # rprint(get_sensor_data(computer))
    # quit()
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

    computer.Open()
