# System Overview
## Description
Application uses LibreHardwareMonitor.dll file with its dependencies allowing
access to information like CPU Usage, Temperatures, Voltages etc.

## External dependencies
This project requires an LibreHardwareMonitorLib (version 0.9.4.0) project in dll-container file.
If you are downloading release this is included by the installer.

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
+ GPU Core and VRAM Usage
+ GPU Core and VRAM Temperature (VRAM temperature may not be available for GDDR5 and older)
+ GPU Core and VRAM Clock
+ GPU Fan speeds

### Memory Information
Following information about memory are available:
+ RAM usage
+ SWAP memory usage (HDD space used by OS as RAM memory)
+ Disks usages

**All data provided are updated about every 0.5s**