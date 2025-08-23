# System Overview
## Description
Application uses LibreHardwareMonitor.dll file with its dependencies allowing
access to information like CPU Usage, Temperatures, Voltages etc.

## External dependencies
This project requires an LibreHardwareMonitorLib (version 0.9.4.0) project in dll-container file.
If you are downloading release this is included to application automatically

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
+ GPU Core Load
+ GPU Temperature
+ GPU Core Clock
+ VRAM Usage
+ Fan 1, 2 and 3 speeds

### Memory Information
Following information about memory are available:
+ RAM usage
+ SWAP memory usage
+ Disk usages

This data is updated with global tick update so if USB drive is inserted or removed
this table will change.