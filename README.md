# Bootsi - Custom Firmware USB Tool

## Project Overview
Bootsi is a cross-platform (Windows/Linux) utility designed to automate the provisioning of LED Sign Controllers. It handles the generation of custom system assets (boot screens and wallpapers) based on specific hardware module math and provides a one-click interface to format and prepare USB drives for "Factory Customization".

## Completed Features

### 1. Asset Generation Engine (`generate_firmware_structure.py`)
- **Directory Nesting:** Automatically builds a structure for multiple pixel pitches (4mm, 6mm, 9mm, 15mm) and sign sizes (1x1 modules up to 20x20).
- **Custom Boot Screens (`boot.png`):** 
  - Centered high-quality logo (Impact Logo) on a pure black background.
  - Dynamically scaled to match the specific EMC resolution.
- **Tiled Wallpapers (`wallpaper.png`):**
  - **Pixel Math Integration:** Reads binary grids from the `g4 pixel math` folder.
  - **Specific 9mm Mapping:** Implements a multi-color mapping:
    - `0`: Black background.
    - `1`: Red (typically used for per-module perimeters).
    - `2`: White (typically used for cam/internal markers).
  - **Automatic Tiling:** Efficiently tiles the single-module math across the entire resolution of the sign.
  - **Fallback Logic:** Ensures older math styles still receive a mandatory red border and white inner dots.

### 2. Bootsi UI Application (`bootsi.py`)
- **Professional UI:** Built with Python and PySide6 (Qt).
- **Dynamic Configuration:**
  - Hardcoded to "4th Generation" EMCs.
  - Auto-scans local folders to populate "Module Pitch" and "EMC Size" dropdowns.
- **Robust USB Handling:**
  - **Detection:** Uses `psutil` and `lsblk` (on Linux) to find removable drives even if they are currently unmounted.
  - **Safety:** Includes a confirmation dialog before any formatting occurs.
  - **Permissions:** Checks for Administrative/Root privileges and warns the user if they are missing.
- **Automation Logic:**
  - **Linux:** Automatically unmounts all partitions, wipes filesystem signatures using `wipefs`, formats to FAT32, mounts to a temporary directory, copies assets to a `FACTORY-CUSTOMIZATION` folder, and syncs data to disk.
  - **Windows:** Uses the native `format` command with quick-format flags for fast preparation.

## How the Program Was Built

### Tech Stack
- **Language:** Python 3.12+
- **UI Framework:** PySide6 (Qt for Python)
- **Imaging:** Pillow (PIL) for high-performance pixel-level manipulation.
- **System Utils:** `psutil` for hardware monitoring and `subprocess` for platform-specific system commands.

### Key Logic Patterns
- **Multithreading:** The formatting and copying operations are offloaded to a `QThread` (`FormatCopyWorker`). This prevents the UI from freezing during the formatting process and allows for real-time progress/status updates.
- **Abstraction:** Path handling uses absolute script directory resolution (`self.base_dir`), allowing the program to be run from any terminal location without breaking folder lookups.
- **Platform Specificity:** The app detects the host OS and switches between Windows-native commands and Linux-native tools (`lsblk`, `mkfs.vfat`, `mount`, `wipefs`) seamlessly.

## Usage Instructions

### Installation
Ensure you have the required dependencies installed in a virtual environment:
```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### Running the App
The application requires administrative privileges to format physical disks.

**Linux:**
```bash
sudo -E ./venv/bin/python3 bootsi.py
```
*Note: The `-E` flag is recommended to preserve your display environment variables for the GUI.*

**Windows:**
Run your terminal (PowerShell or CMD) as **Administrator**, then:
```powershell
python bootsi.py
```

### Regenerating Assets
If the pixel math files or the source logo change, run the generator:
```bash
./venv/bin/python3 generate_firmware_structure.py
```
