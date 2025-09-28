# System Overview
## System diagnostic tool
### Description
Application uses LibreHardwareMonitor.dll file with its dependencies allowing
access to information like CPU Usage, Temperatures, Voltages etc.

## External dependencies
This project requires an LibreHardwareMonitorLib (version 0.9.4.0) project in dll-container file.
If you are downloading release this is included by the installer.
This project requires to enable WMI service if Windows 11 is used.

### BIOS information
- Voltage on +3.3V, +5V, +12V lines
- CPU Core and I/O Voltage
- PCH (MB chipset) Voltage
- DRAM Voltage
- CPU MB sensor Temperature
- PCH (MB chipset) temperature
- PCIe x16 device temperature
- System #X temperatures

### CPU Information
Application shows following CPU Information (package and per-core)
+ CPU Usage
+ CPU Frequency
+ CPU Power
+ CPU Temperature (in Celsius)
+ CPU Core voltage

### GPU Information
Application shows following GPU data.
**Up to 2 GPUs are supported.**
**Integrated graphics is not supported!**
+ GPU Core and VRAM Usage
+ GPU Core and VRAM Temperature (VRAM temperature may not be available for GDDR5 memory type and older)
+ GPU Core and VRAM Clock
+ GPU Fan speeds

### Memory Information
Following information about memory are available:
+ RAM usage
+ SWAP memory usage (HDD space used by OS as RAM memory)
+ Disks usages (WMI)

**All data provided are updated every 0.5s**