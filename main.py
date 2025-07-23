# Built-in libraries
import os
import sys
import asyncio
from typing import Iterable

# External libraries
import wmi
import clr
# import System
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

        self.label_gpu0_temp  = Label()
        self.label_gpu0_power = Label()
        self.label_gpu0_clock = Label()
        self.label_gpu0_vram  = Label()
        self.label_gpu0_fan_1 = Label()
        self.label_gpu0_fan_2 = Label()
        self.label_gpu0_fan_3 = Label()

        self.label_gpu1_temp = Label()
        self.label_gpu1_power = Label()
        self.label_gpu1_clock = Label()
        self.label_gpu1_vram  = Label()
        self.label_gpu1_fan_1 = Label()
        self.label_gpu1_fan_2 = Label()
        self.label_gpu1_fan_3 = Label()

        self.system_view = Vertical(
            Label(f"CPU Name: [green]{CPU_NAME}[/green]"),
            Label(f"RAM Name: [yellow]{RAM_NAME}[/yellow] (JEDEC ID)"),
            Label(f"GPU #0 Name: [blue]{GPU_NAME0}[/blue]"),
            Label(f"GPU #1 Name: [blue]{GPU_NAME1}[/blue]"),
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

        self.gpu0_view = Vertical(
            self.label_gpu0_temp,
            self.label_gpu0_power,
            self.label_gpu0_clock,
            self.label_gpu0_vram,
            self.label_gpu0_fan_1,
            self.label_gpu0_fan_2,
            self.label_gpu0_fan_3
        )

        self.gpu1_view = Vertical(
            self.label_gpu1_temp,
            self.label_gpu1_power,
            self.label_gpu1_clock,
            self.label_gpu1_vram,
            self.label_gpu1_fan_1,
            self.label_gpu1_fan_2,
            self.label_gpu1_fan_3
        )


    def on_screen_resume(self) -> None:
        self.tick = self.set_interval(0.5, self.chk_val)

    def on_screen_suspend(self) -> None:
        self.tick.stop()

    def chk_val(self):
        gpu_data = GPUtil.getGPUs()
        ram_used = round(psutil.virtual_memory().used/(1024**3), 1)
        swap_used = round(psutil.swap_memory().used/(1024**3), 1)
        sensor_data = get_sensor_data(computer)
        cpu_data = sensor_data[CPU_NAME]

        try: gpu0_data = sensor_data[GPU_NAME0]
        except KeyError: gpu0_data = None

        try: gpu1_data = sensor_data[GPU_NAME1]
        except KeyError: gpu1_data = None

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

        # Get colors for GPU-0 data (pass if not available)
        if gpu0_data is not None:
            gpu0_temp = gpu0_data['Temperature: GPU Core']
            gpu0_temp_color = get_color(gpu0_temp)
            gpu0_power = gpu0_data['Power: GPU Package']
            gpu0_power_color = get_color(gpu0_power)
            gpu0_clock = gpu0_data['Clock: GPU Core']
            gpu0_clock_color = get_gpu_clock_color(gpu0_clock)
            gpu0_vram_used = gpu_data[0].memoryUsed
            gpu0_vram_total = gpu_data[0].memoryTotal
            gpu0_vram_percent = round((gpu0_vram_used/gpu0_vram_total)*100, 1)
            gpu0_vram_color = get_color(gpu0_vram_percent)

            # try fetch GPU Fans data (Not detected fallback if unavailable)
            try:
                gpu0_fan_1 = gpu0_data['Fan: GPU Fan 1']
                gpu0_fan_1_color = get_gpu_fan_color(gpu0_fan_1)
            except KeyError:
                try:
                    gpu0_fan_1 = gpu0_data['Fan: GPU Fan']
                    gpu0_fan_1_color = get_gpu_fan_color(gpu0_fan_1)
                except KeyError:
                    gpu0_fan_1 = f"Not Detected"
                    gpu0_fan_1_color = "red"

            try:
                gpu0_fan_2 = gpu0_data['Fan: GPU Fan 2']
                gpu0_fan_2_color = get_gpu_fan_color(gpu0_fan_2)
            except KeyError:
                gpu0_fan_2 = f"Not Detected"
                gpu0_fan_2_color = "red"

            try:
                gpu0_fan_3 = gpu0_data['Fan: GPU Fan 3']
                gpu0_fan_3_color = get_gpu_fan_color(gpu0_fan_3)
            except KeyError:
                gpu0_fan_3 = f"Not Detected"
                gpu0_fan_3_color = "red"

        # Support for second GPU (GPU-1)
        if gpu1_data is not None:
            gpu1_temp = gpu1_data['Temperature: GPU Core']
            gpu1_temp_color = get_color(gpu1_temp)
            gpu1_power = gpu1_data['Power: GPU Package']
            gpu1_power_color = get_color(gpu1_power)
            gpu1_clock = gpu1_data['Clock: GPU Core']
            gpu1_clock_color = get_gpu_clock_color(gpu1_clock)
            gpu1_vram_used = gpu_data[1].memoryUsed
            gpu1_vram_total = gpu_data[1].memoryTotal
            gpu1_vram_percent = round((gpu1_vram_used/gpu1_vram_total)*100, 1)
            gpu1_vram_color = get_color(gpu1_vram_percent)

            # Try fetch GPU fans data (Not detected message fallback)
            try:
                gpu1_fan_1 = gpu1_data['Fan: GPU Fan 1']
                gpu1_fan_1_color = get_gpu_fan_color(gpu1_fan_1)
            except KeyError:
                try:
                    gpu1_fan_1 = gpu1_data['Fan: GPU']
                    gpu1_fan_1_color = get_gpu_fan_color(gpu1_fan_1)
                except KeyError:
                    gpu1_fan_1 = f"Not Detected"
                    gpu1_fan_1_color = "red"

            try:
                gpu1_fan_2 = gpu1_data['Fan: GPU Fan 2']
                gpu1_fan_2_color = get_gpu_fan_color(gpu1_fan_2)
            except KeyError:
                gpu1_fan_2 = f"Not Detected"
                gpu1_fan_2_color = "red"

            try:
                gpu1_fan_3 = gpu1_data['Fan: GPU Fan 3']
                gpu1_fan_3_color = get_gpu_fan_color(gpu1_fan_3)
            except KeyError:
                gpu1_fan_3 = f"Not Detected"
                gpu1_fan_3_color = "red"

        # update Labels
        self.label_cpu_usage.update(F"CPU Usage:       [{cpu_usage_color}]{cpu_usage}[/{cpu_usage_color}] %")

        self.label_cpu_freqc.update(F"CPU Frequency    [{cpu_freq_color}]{round(cpu_freq, 1)}[/{cpu_freq_color}] MHz")
        self.label_cpu_power.update(F"CPU Power:       [{cpu_power_color}]{round(cpu_power, 1)}[/{cpu_power_color}] W")
        self.label_cpu_tempC.update(F"CPU Temperature: [{cpu_temp_color}]{cpu_temp}[/{cpu_temp_color}] *C")
        self.label_cpu_voltage.update(F"CPU Voltage:     [{cpu_volt_color}]{round(cpu_volt, 1)}[/{cpu_volt_color}] V")

        self.label_ram_status.update(F"RAM Memory Used:  {ram_used} / {RAM_DTCT} GB ({round((ram_used/RAM_DTCT)*100, 1)} %)")
        self.label_swp_status.update(F"SWAP Memory Used:  {swap_used} /  {SWP_DTCT} GB ({round((swap_used/SWP_DTCT)*100, 1)} %)")

        # Try to get GPU data. This data may not be available e.g. for internal graphics or on VM
        if gpu0_data is not None:
            self.label_gpu0_temp.update(F"GPU Temperature: [{gpu0_temp_color}]{gpu0_temp}[/{gpu0_temp_color}] *C")
            self.label_gpu0_clock.update(F"GPU Core Clock:  [{gpu0_clock_color}]{gpu0_clock}[/{gpu0_clock_color}] MHz")
            self.label_gpu0_power.update(F"GPU Power:       [{gpu0_power_color}]{round(gpu0_power, 1)}[/{gpu0_power_color}] W")
            self.label_gpu0_vram.update(F"GPU VRAM Usage:  [{gpu0_vram_color}]{gpu0_vram_used} / {gpu0_vram_total} MB ({gpu0_vram_percent} %)[/{gpu0_vram_color}]")
            self.label_gpu0_fan_1.update(F"GPU Fan 1 Speed: [{gpu0_fan_1_color}]{gpu0_fan_1}[/{gpu0_fan_1_color}] RPM")
            self.label_gpu0_fan_2.update(F"GPU Fan 2 Speed: [{gpu0_fan_2_color}]{gpu0_fan_2}[/{gpu0_fan_2_color}] RPM")
            self.label_gpu0_fan_3.update(F"GPU Fan 3 Speed: [{gpu0_fan_3_color}]{gpu0_fan_3}[/{gpu0_fan_3_color}] RPM")
        else: self.label_gpu0_temp.update("[red]Not Available[/red]")

        if gpu1_data is not None:
            self.label_gpu1_temp.update(F"GPU Temperature: [{gpu1_temp_color}]{gpu1_temp}[/{gpu1_temp_color}] *C")
            self.label_gpu1_clock.update(F"GPU Core Clock:  [{gpu1_clock_color}]{gpu1_clock}[/{gpu1_clock_color}] MHz")
            self.label_gpu1_power.update(F"GPU Power:       [{gpu1_power_color}]{round(gpu1_power, 1)}[/{gpu1_power_color}] W")
            self.label_gpu1_vram.update(F"GPU VRAM Usage:  [{gpu1_vram_color}]{gpu1_vram_used} / {gpu1_vram_total} MB ({gpu1_vram_percent} %)[/{gpu1_vram_color}]")
            self.label_gpu1_fan_1.update(F"GPU Fan 1 Speed: [{gpu1_fan_1_color}]{gpu1_fan_1}[/{gpu1_fan_1_color}] RPM")
            self.label_gpu1_fan_2.update(F"GPU Fan 2 Speed: [{gpu1_fan_2_color}]{gpu1_fan_2}[/{gpu1_fan_2_color}] RPM")
            self.label_gpu1_fan_3.update(F"GPU Fan 3 Speed: [{gpu1_fan_3_color}]{gpu1_fan_3}[/{gpu1_fan_3_color}] RPM")
        else: self.label_gpu1_temp.update("[red]Not Detected[/red]")

    def compose(self) -> ComposeResult:
        yield Header()
        if GPU_NAME1 != "Not Available":
            yield Container(
                Horizontal(TitledSection("[cyan]System Overview[/cyan]", self.system_view), TitledSection(f"[green]{CPU_NAME}[/green]", self.cpu_view)),
                Horizontal(TitledSection(f"[blue]{GPU_NAME0}[/blue]", self.gpu0_view), TitledSection(f"[blue]{GPU_NAME1}[/blue]", self.gpu1_view))
            )
        else:
            yield Container(
                Horizontal(TitledSection("[cyan]System Overview[/cyan]", self.system_view), TitledSection(f"[green]{CPU_NAME}[/green]", self.cpu_view)),
                Horizontal(TitledSection(f"[blue]{GPU_NAME0}[/blue]", self.gpu0_view), TitledSection(f"[yellow]Memory Information[/yellow]", self.ram_view))
            )
        yield Footer()

# CPU Details Window
# Display Per-Core information about voltage, load, temps and clock frequencies
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

    def on_screen_resume(self) -> None:
        self.timer = self.set_interval(0.5, self.chk_vals)

    def on_screen_suspend(self):
        self.timer.stop()

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

    # GPU0 Name
    try:
        GPU_NAME0 = str(gpu_data[0].name)
        GPU0_VRAM = gpu_data[0].memoryTotal
    except:
        GPU_NAME0 = "Internal Graphics"
        GPU0_VRAM = 0

    # Support For Second GPU!
    try:
        GPU_NAME1 = str(gpu_data[1].name)
        GPU1_VRAM = gpu_data[1].memoryTotal
    except:
        GPU_NAME1 = "[red]Not Detected[/red]"
        GPU1_VRAM = 0

    # # GPU VRAM total
    # try: GPU_VRAM_TOTAL = gpu_data[0].memoryTotal
    # except IndexError: GPU_VRAM_TOTAL = "[red]Not Available[/red]"

    Launcher().run()

    # On CTRL+Q
    computer.Close()
