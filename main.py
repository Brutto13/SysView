# Built-in libraries
import datetime
import json
import os
import sys
import shutil
from typing import Iterable

# External libraries
import wmi
import clr
import win32com.client
import psutil
import GPUtil
import subprocess

from statistics import mean
from rich import print as rprint
from rich.console import Console
from textual.app import App, Screen, ComposeResult, SystemCommand
from textual.widgets import Header, Label, Footer, DataTable, Input, Select, Button
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.binding import Binding

# Constants
TITLE = "SysView 1.1.0"

# Handle PyInstaller Splash Image
try:
    import pyi_splash
except ImportError: pass

# Fetch DLL
rprint("[cyan]INFO: Loading drivers...[/]")
try:
    clr.AddReference(sys._MEIPASS + r'\dll-container\LibreHardwareMonitorLib.dll')
except AttributeError:
    clr.AddReference(os.getcwd() + r'\dll-container\LibreHardwareMonitorLib.dll')

# Configure DLL
from LibreHardwareMonitor import Hardware

rprint("[cyan]INFO: Configuring drivers...[/]")
computer = Hardware.Computer()
computer.IsCpuEnabled = True
computer.IsGpuEnabled = True
computer.IsMotherboardEnabled = False
computeremoryEnabled = False
computer.IsStorageEnabled = False
computer.Open()


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

# Getting colors for data
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


def get_disk_info():
    c = wmi.WMI()
    fso = win32com.client.Dispatch("Scripting.FileSystemObject")

    disk_info = []

    for physical_disk in c.Win32_DiskDrive():
        # Find partitions
        for partition in physical_disk.associators("Win32_DiskDriveToDiskPartition"):
            for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
                letter = logical_disk.DeviceID  # np. "C:"
                usage = psutil.disk_usage(letter + "\\")

                try:
                    volume = fso.GetDrive(letter)
                    label = volume.VolumeName
                except:
                    label = ""

                disk_info.append({
                    "Name": physical_disk.Model,
                    "Letter": letter,
                    "SATA": physical_disk.SCSIPort,
                    "Free": round(usage.free / (1024 ** 3), 2),
                    "Used": round(usage.used / (1024 ** 3), 2),
                    "Total": round(usage.total / (1024 ** 3), 2),
                })

    return disk_info


def get_cpu_name():
    for hardware in computer.Hardware:
        if str(hardware.HardwareType) == 'Cpu':
            return hardware.Name


def get_gpu_name(computer):
    gpu_names = []
    for hardware in computer.Hardware:
        hw_type = str(hardware.HardwareType)
        if hw_type in ('GpuNvidia', 'GpuAmd'):
            gpu_names.append(hardware.Name)
    return gpu_names



def get_cpu_cache():
    c = wmi.WMI()
    result = [0]
    for cache in c.Win32_CacheMemory():
        level = {3: "L1", 4: "L2", 5: "L3"}.get(cache.Level, f"{cache.level}")
        size_kb = int(cache.MaxCacheSize)
        result.append(size_kb)
    return result


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
        self.bus_clock = Label()

        self.label_cpu_usage   = Label()
        self.label_cpu_freqc   = Label()
        self.label_cpu_tempC   = Label()
        self.label_cpu_power   = Label()
        self.label_cpu_voltage = Label()

        # self.label_ram_status = Label()
        # self.label_swp_status = Label()

        self.hdd_table = DataTable(cursor_type='none')

        self.label_gpu0_used  = Label()
        self.label_gpu0_temp  = Label()
        self.label_gpu0_power = Label()
        self.label_gpu0_clock = Label()
        self.label_gpu0_vram  = Label()
        self.label_gpu0_fan_1 = Label()
        self.label_gpu0_fan_2 = Label()
        self.label_gpu0_fan_3 = Label()

        self.label_gpu1_used  = Label()
        self.label_gpu1_temp  = Label()
        self.label_gpu1_power = Label()
        self.label_gpu1_clock = Label()
        self.label_gpu1_vram  = Label()
        self.label_gpu1_fan_1 = Label()
        self.label_gpu1_fan_2 = Label()
        self.label_gpu1_fan_3 = Label()

        self.system_view = Vertical(
            Label(f"CPU Name:    [green]{CPU_NAME}[/green]"),
            Label(f"RAM Name:    [yellow]{RAM_NAME}[/yellow] (JEDEC ID)"),
            Label(f"BOOT TIME:   [cyan]{BOOT_TIME}[/cyan]"),
            self.bus_clock,
            Label(f"GPU #0 Name: [purple]{GPU_NAME0}[/purple]"),
            Label(f"GPU #1 Name: [blue]{GPU_NAME1}[/blue]")
        )

        self.cpu_view = Vertical(
            self.label_cpu_usage,
            self.label_cpu_freqc,
            self.label_cpu_power,
            self.label_cpu_tempC,
            self.label_cpu_voltage
        )

        self.hdd_view = Vertical(
            self.hdd_table
        )

        self.gpu0_view = Vertical(
            self.label_gpu0_used,
            self.label_gpu0_temp,
            self.label_gpu0_power,
            self.label_gpu0_clock,
            self.label_gpu0_vram,
            self.label_gpu0_fan_1,
            self.label_gpu0_fan_2,
            self.label_gpu0_fan_3
        )

        self.gpu1_view = Vertical(
            self.label_gpu1_used,
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

        cpu_usage = psutil.cpu_percent()
        cpu_usage_color = get_color(cpu_usage)
        try: cpu_freq = round(mean([cpu_data[f'Clock: CPU Core #{i+1}'] for i in range(os.cpu_count())]))
        except KeyError: cpu_freq = round(cpu_data['Clock: CPU Core #1'])
        cpu_freq_color = get_cpu_freq_color(cpu_freq)
        cpu_power = cpu_data['Power: CPU Package']
        cpu_power_color = get_color(cpu_power)
        cpu_temp = cpu_data['Temperature: CPU Package']
        cpu_temp_color = get_color(cpu_temp)
        cpu_volt = cpu_data['Voltage: CPU Core']
        cpu_volt_color = get_voltage_color(cpu_volt)

        # Get colors for GPU-0 data (pass if not available)
        if gpu0_data is not None:
            gpu0_used = round(gpu_data[0].load*100, 1)
            gpu0_used_color = get_color(gpu0_used)
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
            gpu1_used = round(gpu_data[1].load*100, 1)
            gpu1_used_color = get_color(gpu1_used)
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
                    gpu1_fan_1 = gpu1_data['Fan: GPU Fan']
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
        self.bus_clock.update(F"Bus Clock:   [cyan]{round(cpu_data['Clock: Bus Speed'], 2)}[/cyan] MHz")

        self.label_cpu_usage.update(F"CPU Usage:       [{cpu_usage_color}]{cpu_usage}[/{cpu_usage_color}] %")
        self.label_cpu_freqc.update(F"CPU Frequency    [{cpu_freq_color}]{round(cpu_freq, 1)}[/{cpu_freq_color}] MHz")
        self.label_cpu_power.update(F"CPU Power:       [{cpu_power_color}]{round(cpu_power, 1)}[/{cpu_power_color}] W")
        self.label_cpu_tempC.update(F"CPU Temperature: [{cpu_temp_color}]{cpu_temp}[/{cpu_temp_color}] *C")
        self.label_cpu_voltage.update(F"CPU Voltage:     [{cpu_volt_color}]{round(cpu_volt, 3)}[/{cpu_volt_color}] V")

        # self.label_ram_status.update(F"RAM Memory Used:  {ram_used} / {RAM_DTCT} GB ({round((ram_used/RAM_DTCT)*100, 1)} %)")
        # self.label_swp_status.update(F"SWAP Memory Used:  {swap_used} /  {SWP_DTCT} GB ({round((swap_used/SWP_DTCT)*100, 1)} %)")

        # Try to get GPU data. This data may not be available e.g. for internal graphics or on VM
        if gpu0_data is not None:
            self.label_gpu0_used.update(F"GPU Core Load:   [{gpu0_used_color}]{gpu0_used}[/{gpu0_used_color}] %")
            self.label_gpu0_temp.update(F"GPU Temperature: [{gpu0_temp_color}]{gpu0_temp}[/{gpu0_temp_color}] *C")
            self.label_gpu0_clock.update(F"GPU Core Clock:  [{gpu0_clock_color}]{gpu0_clock}[/{gpu0_clock_color}] MHz")
            self.label_gpu0_power.update(F"GPU Power:       [{gpu0_power_color}]{round(gpu0_power, 1)}[/{gpu0_power_color}] W")
            self.label_gpu0_vram.update(F"GPU VRAM Usage:  [{gpu0_vram_color}]{gpu0_vram_used} / {gpu0_vram_total} MB ({gpu0_vram_percent} %)[/{gpu0_vram_color}]")
            self.label_gpu0_fan_1.update(F"GPU Fan 1 Speed: [{gpu0_fan_1_color}]{gpu0_fan_1}[/{gpu0_fan_1_color}] RPM")
            self.label_gpu0_fan_2.update(F"GPU Fan 2 Speed: [{gpu0_fan_2_color}]{gpu0_fan_2}[/{gpu0_fan_2_color}] RPM")
            self.label_gpu0_fan_3.update(F"GPU Fan 3 Speed: [{gpu0_fan_3_color}]{gpu0_fan_3}[/{gpu0_fan_3_color}] RPM")
        else: self.label_gpu0_temp.update("[red]Internal GPU is not supported[/red]")

        # Try to get second GPU data (this is not available if user has only one GPU)
        if gpu1_data is not None:
            self.label_gpu1_used.update(F"GPU Core Load:   [{gpu1_used_color}]{gpu1_used}[/{gpu1_used_color}] %")
            self.label_gpu1_temp.update(F"GPU Temperature: [{gpu1_temp_color}]{gpu1_temp}[/{gpu1_temp_color}] *C")
            self.label_gpu1_clock.update(F"GPU Core Clock:  [{gpu1_clock_color}]{gpu1_clock}[/{gpu1_clock_color}] MHz")
            self.label_gpu1_power.update(F"GPU Power:       [{gpu1_power_color}]{round(gpu1_power, 1)}[/{gpu1_power_color}] W")
            self.label_gpu1_vram.update(F"GPU VRAM Usage:  [{gpu1_vram_color}]{gpu1_vram_used} / {gpu1_vram_total} MB ({gpu1_vram_percent} %)[/{gpu1_vram_color}]")
            self.label_gpu1_fan_1.update(F"GPU Fan 1 Speed: [{gpu1_fan_1_color}]{gpu1_fan_1}[/{gpu1_fan_1_color}] RPM")
            self.label_gpu1_fan_2.update(F"GPU Fan 2 Speed: [{gpu1_fan_2_color}]{gpu1_fan_2}[/{gpu1_fan_2_color}] RPM")
            self.label_gpu1_fan_3.update(F"GPU Fan 3 Speed: [{gpu1_fan_3_color}]{gpu1_fan_3}[/{gpu1_fan_3_color}] RPM")
        else: self.label_gpu1_temp.update("[red]Not Detected[/red]")

        # Get HDD info
        hdd_rows = []
        # re-check available disks.
        DRIVES = [p.device for p in psutil.disk_partitions()]
        self.hdd_table.clear(columns=True)
        self.hdd_table.add_columns("Drive", "Used space", "Free Space", "Usage")
        for drive in DRIVES:
            total, used, free = shutil.disk_usage(drive)
            hdd_rows.append(
                (f"{drive}", f"{round(used/(1024**3), 1)} GB", f"{round(free/(1024**3), 1)} GB", f"{round(used*100/total, 1)} %")
            )

        for row in hdd_rows:
            self.hdd_table.add_row(*row)

    def compose(self) -> ComposeResult:
        yield Header()
        # Show SysOverview, CPU data and Disk Info on top, both GPU on bottom (if possible)
        if GPU_NAME1 != "[red]Not Detected[/red]":
            yield Container(
                Horizontal(TitledSection("[cyan]System Overview[/cyan]", self.system_view), TitledSection(f"[green]{CPU_NAME}[/green]", self.cpu_view), TitledSection("[yellow]Disk drives Information[/yellow]", self.hdd_view)),
                Horizontal(TitledSection(f"[purple]{GPU_NAME0}[/purple]", self.gpu0_view), TitledSection(f"[blue]{GPU_NAME1}[/blue]", self.gpu1_view))
            )

        # Show SysOverview, CPU data on top, Disk Info and only GPU on bottom
        else:
            yield Container(
                Horizontal(TitledSection("[cyan]System Overview[/cyan]", self.system_view), TitledSection(f"[green]{CPU_NAME}[/green]", self.cpu_view)),
                Horizontal(TitledSection(f"[blue]{GPU_NAME0}[/blue]", self.gpu0_view), TitledSection(f"[yellow]Disk drives Information[/yellow]", self.hdd_view))
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

        cpu_count = psutil.cpu_count(logical=False)
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

#
# class DiskDetails(Screen):
#     def __init__(self):
#         self.

class SaveScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Input(placeholder="Enter save path", id='path'),
            Select([("TXT File", "txt"), ("JSON data", "json")], prompt="Select file format", id='fs'),
            Horizontal(Button("Save", variant='success', id='save'), Button("Cancel", variant='error', id='back')),
            id='dialog'
        )
        yield Footer()

    def on_button_pressed(self, event):
        selector = self.query_one("#fs", Select)
        pathholder = self.query_one("#path", Input)

        mode = selector.value
        filepath = pathholder.value
        data = get_sensor_data(computer)
        if event.button.id == "save":
            if mode == "txt":
                content = f"""
------------------------------+ SysView Sensor Data Readout +------------------------------
============ CPU DATA ============
CPU Name:........ {CPU_NAME}
CPU Usage:....... {psutil.cpu_percent(0.1)} %
CPU Frequency:... {round(mean([data[CPU_NAME][f'Clock: CPU Core #{i+1}'] for i in range(os.cpu_count())]))} MHz
CPU Temperature:. {data[CPU_NAME]["Temperature: CPU Package"]} *C
CPU Power Usage:. {round(data[CPU_NAME]["Power: CPU Package"], 1)} W
CPU Core Voltage: {round(data[CPU_NAME]["Voltage: CPU Core"], 3)} V

============ RAM DATA ============
RAM Name:  {RAM_NAME}
RAM Used:  {psutil.virtual_memory().used} GB
RAM Total: {RAM_DTCT} GB
"""


            elif mode == "json":
                content = json.dumps(get_sensor_data(computer))

            try:
                with open(filepath, "x") as file:
                    file.write(content)
                    self.app.push_screen(FileSavedInfo())
            except FileExistsError:
                self.app.push_screen(FileExists())

        else: self.app.pop_screen()


class FileExists(Screen):
    def compose(self) -> ComposeResult:
        yield Container(
            Label("Error while saving file!"),
            Label("[red]FileExistsError[/]: [yellow]File already exists![/]"),
            Button("OK", variant='primary'),
            id='popup'
        )

    def on_button_pressed(self):
        self.app.pop_screen()


class FileSavedInfo(Screen):
    def compose(self):
        yield Container(
            Label("File Saved Successfully"),
            Button("OK"),
            id='popup'
        )

    def on_button_pressed(self, event):
        self.app.pop_screen()

class Launcher(App):
    CSS = """
    
    Screen {
        align: center middle;
    }
    
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
    
    
    Input {
        margin: 2;
    }
    
    Select {
        margin: 2;
    }
    
    Button {
        margin: 1;
        width: 1fr;
    }
    
    #dialog {
        align: center middle;
        border: solid white;
        width: 50%;
        height: 60%;
    }
    
    #popup {
        align: center middle;
        width: 50%;
        height: auto;
        border: round white;
        padding: 2 4;
        background: grey;
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
        yield SystemCommand("Save Report", "Save these data into file", lambda: self.push_screen(SaveScreen()))

    def on_mount(self):
        self.title = TITLE
        self.app.push_screen(MainScreen())


if __name__ == '__main__':
    rprint("BOOT: Entering program...")
    # rprint(get_sensor_data(computer))
    # quit()
    rprint("[cyan]INFO: Getting BOOT time...[/]")
    BOOT_TIME_TS = psutil.boot_time()
    BT = datetime.datetime.fromtimestamp(BOOT_TIME_TS)
    BOOT_TIME = F"{BT.day}/{BT.month}/{BT.year} {BT.hour}:{BT.minute}:{BT.second}"

    rprint("[cyan]INFO: Retrieving hardware information...[/]")
    CPU_NAME = get_cpu_name()
    CPU_FREQ = psutil.cpu_freq()
    CPU_CACHE = get_cpu_cache()

    RAM_NAME = get_ram_name()
    RAM_DTCT = round(psutil.virtual_memory().total/(1024**3), 1)

    SWP_DTCT = round(psutil.swap_memory().total/(1024**3), 1)

    rprint("[cyan]INFO: Retrieving GPU data...[/]")
    gpu_data = GPUtil.getGPUs()

    # GPU0 Name
    try:
        GPU_NAME0 = str(GPUtil.getGPUs()[0].name)
        GPU0_VRAM = gpu_data[0].memoryTotal
        rprint(f"[cyan]INFO: GPU0 found: {GPU_NAME0}[/]")
    except:
        # Internal Graphics is not supported (yet)
        GPU_NAME0 = "Internal Graphics"
        GPU0_VRAM = 0
        rprint("[yellow]WARN: GPU0 Data not available[/]")
        rprint("This IS expected if you are using Integrated Graphics.")
        rprint("This IS NOT expected if you are using external GPU")

    # Support For Second GPU!
    try:
        GPU_NAME1 = str(GPUtil.getGPUs()[1].name)
        GPU1_VRAM = gpu_data[1].memoryTotal
        rprint(F"[cyan]INFO: GPU1 Found: {GPU_NAME1}")
    except:
        GPU_NAME1 = "[red]Not Detected[/red]"
        GPU1_VRAM = 0

    # Get available Drives
    rprint("[cyan]INFO: Retrieving disk data...[/]")
    DRIVES = [p.device for p in psutil.disk_partitions()]
    rprint(f"[cyan]INFO: Detected {len(DRIVES)} drives")

    rprint("BOOT: Closing Splash...")
    try: pyi_splash.close()
    except NameError: pass
    rprint("[cyan]INFO: Lauching app...[/]")
    Launcher().run()
    rprint("[cyan]INFO: App closed![/]")
    # On CTRL+Q
    rprint("[cyan]INFO: Releasing drivers...")
    computer.Close()
    rprint("[green]DONE: Done![/]")
    rprint("Exit Code: 0")
