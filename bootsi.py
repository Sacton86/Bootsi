import sys
import os
import shutil
import platform
import subprocess
import psutil
import ctypes
from PIL import Image
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QLabel, QComboBox, QPushButton, QMessageBox, QProgressBar,
    QStatusBar, QFileDialog, QFrame, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QFont, QIcon

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        # Compiled exe — assets live next to the exe, not in PyInstaller's temp dir
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class FormatCopyWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, drive, fs_type, source_path, custom_logo=None, skip_format=False, duplicate_logo_as_wallpaper=False):
        super().__init__()
        self.drive = drive
        self.fs_type = fs_type
        self.source_path = source_path
        self.custom_logo = custom_logo
        self.skip_format = skip_format
        self.duplicate_logo_as_wallpaper = duplicate_logo_as_wallpaper

    def run(self):
        temp_mount = None
        try:
            device = self.drive.split()[0]
            
            # 1. Handle Formatting or Preparation
            if platform.system() == "Windows":
                drive_letter = device.rstrip("\\")
                if not self.skip_format:
                    self.status.emit(f"Formatting {drive_letter} as {self.fs_type}...")
                    self.progress.emit(10)
                    cmd = ["format", drive_letter, "/FS:" + self.fs_type, "/Q", "/V:BOOTSI", "/Y"]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise Exception(f"Format failed: {result.stderr}")
                else:
                    self.status.emit(f"Using existing FAT32 system on {drive_letter}...")
                    self.progress.emit(10)
            else:
                # Linux/Unix unmount logic
                self.status.emit(f"Unmounting all partitions on {device}...")
                try:
                    # Find any partition or the device itself that is mounted
                    lsblk_partitions = subprocess.run(
                        ["lsblk", "-n", "-l", "-o", "MOUNTPOINT", "-p", device],
                        capture_output=True, text=True
                    ).stdout.strip().split("\n")
                    for mount_point in lsblk_partitions:
                        mount_point = mount_point.strip()
                        if mount_point and mount_point.startswith("/"):
                            self.status.emit(f"Unmounting {mount_point}...")
                            subprocess.run(["sudo", "umount", "-l", mount_point], capture_output=True)
                except Exception as e:
                    print(f"Error during unmount: {e}")

                if not self.skip_format:
                    self.status.emit(f"Wiping signatures on {device}...")
                    subprocess.run(["sudo", "wipefs", "-a", device], capture_output=True)
                    
                    self.status.emit(f"Formatting {device}...")
                    self.progress.emit(10)
                    # -I is needed to format the raw device without partitions
                    cmd = ["sudo", "mkfs.vfat", "-I", "-F", "32", "-n", "BOOTSI", device]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise Exception(f"Format failed: {result.stderr}")
                    
                    self.status.emit("Settling device...")
                    subprocess.run(["sudo", "partprobe", device], capture_output=True)
                    subprocess.run(["sudo", "udevadm", "settle"], capture_output=True)
                    import time
                    time.sleep(2)
                else:
                    self.status.emit(f"Using existing FAT32 system on {device}...")
                    self.progress.emit(10)

            # 2. Setup target mount
            target_mount = ""
            if platform.system() == "Windows":
                target_mount = device if device.endswith("\\") else device + "\\"
            else:
                import tempfile
                temp_mount = tempfile.mkdtemp(prefix="bootsi_")
                
                # Attempt to mount with multiple options
                self.status.emit(f"Mounting {device}...")
                mount_success = False
                last_error = ""

                # Try 1: Explicit vfat with common options
                mount_cmd = ["sudo", "mount", "-t", "vfat", "-o", "rw,flush,umask=000", device, temp_mount]
                result = subprocess.run(mount_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    mount_success = True
                else:
                    last_error = result.stderr
                    # Try 2: Simple mount
                    mount_cmd = ["sudo", "mount", device, temp_mount]
                    result = subprocess.run(mount_cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        mount_success = True
                    else:
                        last_error = result.stderr

                if not mount_success:
                    os.rmdir(temp_mount)
                    raise Exception(f"Failed to mount {device}: {last_error}")
                
                target_mount = temp_mount

            # 3. Clear existing files if skipping format
            if self.skip_format:
                self.status.emit("Deleting existing files from USB...")
                if platform.system() != "Windows":
                    subprocess.run(["sudo", "sync"])
                for item in os.listdir(target_mount):
                    item_path = os.path.join(target_mount, item)
                    try:
                        if platform.system() == "Windows":
                            if os.path.isfile(item_path) or os.path.islink(item_path):
                                os.remove(item_path)
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                        else:
                            if os.path.isfile(item_path) or os.path.islink(item_path):
                                subprocess.run(["sudo", "rm", "-f", item_path])
                            elif os.path.isdir(item_path):
                                subprocess.run(["sudo", "rm", "-rf", item_path])
                    except Exception as e:
                        print(f"Failed to delete {item_path}: {e}")
                self.progress.emit(30)

            target_dir = os.path.join(target_mount, "FACTORY-CUSTOMIZATION")
            self.status.emit(f"Copying assets to {target_dir}...")
            self.progress.emit(50)

            if platform.system() == "Windows":
                os.makedirs(target_dir, exist_ok=True)
                shutil.copytree(self.source_path, target_dir, dirs_exist_ok=True)
            else:
                subprocess.run(["sudo", "mkdir", "-p", target_dir])
                cmd = ["sudo", "cp", "-r", os.path.join(self.source_path, "."), target_dir]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"Copy failed: {result.stderr}")


            # 3. Handle Custom Logo and/or Duplicate as Wallpaper
            if self.custom_logo and os.path.exists(self.custom_logo):
                self.status.emit("Applying custom logo...")
                folder_name = os.path.basename(self.source_path)
                if "_" in folder_name:
                    res_part = folder_name.split("_")[-1]
                    if "x" in res_part:
                        try:
                            tw, th = map(int, res_part.split("x"))
                            boot_path = os.path.join(target_dir, "boot.png")
                            logo_img = Image.open(self.custom_logo).convert("RGBA")
                            bg = Image.new('RGB', (tw, th), color=(0, 0, 0))
                            lw, lh = logo_img.size
                            ratio = min(tw / lw, th / lh)
                            nw, nh = int(lw * ratio), int(lh * ratio)
                            resized_logo = logo_img.resize((nw, nh), Image.Resampling.LANCZOS)
                            ox, oy = (tw - nw) // 2, (th - nh) // 2
                            bg.paste(resized_logo, (ox, oy), resized_logo)
                            bg.save(boot_path, "PNG")
                            if self.duplicate_logo_as_wallpaper:
                                bg.save(os.path.join(target_dir, "wallpaper.png"), "PNG")
                        except Exception as e:
                            print(f"Failed to apply custom logo: {e}")
            elif self.duplicate_logo_as_wallpaper:
                boot_path = os.path.join(target_dir, "boot.png")
                if os.path.exists(boot_path):
                    shutil.copy2(boot_path, os.path.join(target_dir, "wallpaper.png"))

            if platform.system() != "Windows":
                self.status.emit("Flushing buffers...")
                subprocess.run(["sync"])

            self.progress.emit(100)
            self.status.emit("Finished!")
            self.finished.emit(True, "Process completed successfully.")

        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            if temp_mount and os.path.exists(temp_mount):
                subprocess.run(["sudo", "umount", temp_mount], capture_output=True)
                try: os.rmdir(temp_mount)
                except: pass

class BootsiApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bootsi - Custom Firmware USB Tool")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.setWindowIcon(QIcon(get_resource_path("kirbyicon.png")))

        self.base_dir = get_resource_path("")
        self.custom_logo_path = None
        self.default_logo_path = get_resource_path("Impact Logo.png")
        
        if not self.is_admin():
            QMessageBox.warning(self, "Permissions", "Admin/Root privileges may be required.")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_h_layout = QHBoxLayout(central_widget)

        # LEFT COLUMN: CONTROLS
        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        main_h_layout.addWidget(controls_panel, 1)

        # Branding
        branding_label = QLabel("Bootsi")
        branding_label.setStyleSheet("font-size: 28px; font-weight: bold; color: white; margin-bottom: 20px; border: none;")
        controls_layout.addWidget(branding_label)

        # Apply a dark theme to the entire window
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
            }
            QLabel {
                color: #e0e0e0;
                border: none;
            }
            QComboBox, QPushButton {
                background-color: #333;
                border: 1px solid #555;
                padding: 5px;
                color: white;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QPushButton#start_button {
                background-color: #27ae60;
                border: none;
            }
            QProgressBar {
                border: 1px solid #555;
                text-align: center;
                background-color: #333;
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
            }
            QFrame {
                border: none;
            }
            QCheckBox {
                color: #e0e0e0;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #333;
                border: 1px solid #555;
            }
            QCheckBox::indicator:checked {
                background-color: #27ae60;
                border: 1px solid #27ae60;
            }
        """)

        # Product Line
        controls_layout.addWidget(QLabel("Product Line:"))
        self.gen_combo = QComboBox()
        self.gen_combo.addItem("G1", "G1")
        self.gen_combo.addItem("G2", "G2")
        self.gen_combo.addItem("G3", "G3")
        self.gen_combo.addItem("G4", "G4")
        self.gen_combo.currentIndexChanged.connect(self.populate_pitches)
        controls_layout.addWidget(self.gen_combo)

        # Pitch
        controls_layout.addWidget(QLabel("Module Pitch:"))
        self.pitch_combo = QComboBox()
        self.pitch_combo.currentIndexChanged.connect(self.populate_sizes)
        controls_layout.addWidget(self.pitch_combo)

        # Size
        controls_layout.addWidget(QLabel("EMC Size (Tall x Wide):"))
        self.size_combo = QComboBox()
        self.size_combo.currentIndexChanged.connect(self.update_previews)
        controls_layout.addWidget(self.size_combo)

        # Logo Selection
        controls_layout.addSpacing(20)
        self.change_logo_button = QPushButton("Change Boot Logo")
        self.change_logo_button.clicked.connect(self.select_custom_logo)
        controls_layout.addWidget(self.change_logo_button)
        
        self.reset_logo_button = QPushButton("Reset to Default Logo")
        self.reset_logo_button.clicked.connect(self.reset_logo)
        controls_layout.addWidget(self.reset_logo_button)

        self.dup_logo_wallpaper_check = QCheckBox("Duplicate Logo as Wallpaper")
        self.dup_logo_wallpaper_check.stateChanged.connect(self.update_previews)
        controls_layout.addWidget(self.dup_logo_wallpaper_check)

        # USB
        controls_layout.addStretch()
        controls_layout.addWidget(QLabel("USB Drive:"))
        usb_h = QHBoxLayout()
        self.usb_combo = QComboBox()
        self.refresh_usb_button = QPushButton("Refresh")
        self.refresh_usb_button.clicked.connect(self.populate_usbs)
        usb_h.addWidget(self.usb_combo, 1)
        usb_h.addWidget(self.refresh_usb_button)
        controls_layout.addLayout(usb_h)

        self.start_button = QPushButton("Start Process")
        self.start_button.setObjectName("start_button")
        self.start_button.setMinimumHeight(60)
        self.start_button.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 16px; border: none;")
        self.start_button.clicked.connect(self.start_process)
        controls_layout.addWidget(self.start_button)

        self.progress_bar = QProgressBar()
        controls_layout.addWidget(self.progress_bar)

        # RIGHT COLUMN: PREVIEWS
        preview_panel = QFrame()
        preview_layout = QVBoxLayout(preview_panel)
        main_h_layout.addWidget(preview_panel, 2)

        preview_layout.addWidget(QLabel("<b>Asset Previews</b>"))
        
        preview_layout.addWidget(QLabel("Boot Screen (boot.png):"))
        self.boot_preview = QLabel("Select size to preview")
        self.boot_preview.setAlignment(Qt.AlignCenter)
        self.boot_preview.setStyleSheet("background-color: #000; border: 1px solid #444;")
        self.boot_preview.setMinimumHeight(200)
        self.boot_preview.setScaledContents(False)
        preview_layout.addWidget(self.boot_preview)

        preview_layout.addWidget(QLabel("Wallpaper (wallpaper.png):"))
        self.wall_preview = QLabel("Select size to preview")
        self.wall_preview.setAlignment(Qt.AlignCenter)
        self.wall_preview.setStyleSheet("background-color: #000; border: 1px solid #444;")
        self.wall_preview.setMinimumHeight(200)
        self.wall_preview.setScaledContents(False)
        preview_layout.addWidget(self.wall_preview)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Init
        self.gen_combo.setCurrentIndex(3) # G4
        self.populate_pitches()
        self.populate_usbs()

    def get_usb_fs(self, device):
        """ Returns (fstype, best_device_to_mount) """
        if platform.system() == "Windows":
            clean_device = device.replace("\\", "").upper()
            for p in psutil.disk_partitions():
                if p.device.replace("\\", "").upper() == clean_device:
                    return p.fstype, device
        else:
            try:
                # Use -l for list format which is easier to parse
                result = subprocess.run(["lsblk", "-n", "-l", "-o", "NAME,FSTYPE", "-p", device], capture_output=True, text=True)
                lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
                
                # First check if any entry is FAT32/vfat
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        name, fstype = parts[0], parts[1]
                        if fstype.lower() in ["vfat", "fat32"]:
                            return fstype.lower(), name
                
                # If no FAT found, return the first one with a filesystem
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1], parts[0]
                
                return "unknown", device
            except: pass
        return "unknown", device

    def is_admin(self):
        try:
            if platform.system() == "Windows":
                return (ctypes.windll.shell32.IsUserAnAdmin() != 0)
            else:
                return (os.getuid() == 0)
        except: return False

    def select_custom_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.custom_logo_path = file_path
            self.update_previews()

    def reset_logo(self):
        self.custom_logo_path = None
        self.update_previews()

    def populate_pitches(self):
        self.pitch_combo.blockSignals(True)
        self.pitch_combo.clear()
        gen = self.gen_combo.currentData()
        path = os.path.join(self.base_dir, gen)
        if os.path.exists(path):
            pitches = []
            for d in os.listdir(path):
                if os.path.isdir(os.path.join(path, d)) and d.endswith("mm"):
                    pitches.append(d)
            pitches.sort(key=lambda x: int(x.replace("mm","")))
            self.pitch_combo.addItems(pitches)
        self.pitch_combo.blockSignals(False)
        self.populate_sizes()

    def populate_sizes(self):
        self.size_combo.blockSignals(True)
        self.size_combo.clear()
        gen = self.gen_combo.currentData()
        pitch = self.pitch_combo.currentText()
        if not gen or not pitch:
            self.size_combo.blockSignals(False)
            return

        path = os.path.join(self.base_dir, gen, pitch)
        if os.path.exists(path):
            sizes = []
            for d in os.listdir(path):
                if os.path.isdir(os.path.join(path, d)) and "_" in d:
                    display = d.split("_")[0]
                    if "x" in display:
                        parts = display.split("x")
                        if all(p.isdigit() for p in parts):
                            sizes.append((display, d))
            
            # Sort by numeric tall x wide
            try:
                sizes.sort(key=lambda x: [int(v) for v in x[0].split("x")])
            except Exception as e:
                print(f"Sorting error: {e}")
            
            for d, a in sizes:
                self.size_combo.addItem(d, a)
        
        self.size_combo.blockSignals(False)
        self.update_previews()

    def update_previews(self):
        gen = self.gen_combo.currentData()
        pitch = self.pitch_combo.currentText()
        size_actual = self.size_combo.currentData()

        if not gen or not pitch or not size_actual:
            self.wall_preview.setPixmap(QPixmap())
            self.wall_preview.setText("Select size to preview")
            self.boot_preview.setPixmap(QPixmap())
            self.boot_preview.setText("Select size to preview")
            return

        folder_path = os.path.join(self.base_dir, gen, pitch, size_actual)
        logo_to_use = self.custom_logo_path if self.custom_logo_path else self.default_logo_path
        dup_as_wall = self.dup_logo_wallpaper_check.isChecked()

        # Boot logo preview
        if os.path.exists(logo_to_use):
            try:
                pix = QPixmap(logo_to_use)
                scaled_pix = pix.scaled(self.boot_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.boot_preview.setPixmap(scaled_pix)
            except:
                self.boot_preview.setText("Error loading logo")
        else:
            self.boot_preview.clear()
            self.boot_preview.setText("Logo not found")

        # Wallpaper preview — show logo when checkbox is checked
        if dup_as_wall:
            if os.path.exists(logo_to_use):
                try:
                    pix = QPixmap(logo_to_use)
                    scaled_pix = pix.scaled(self.wall_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.wall_preview.setPixmap(scaled_pix)
                except:
                    self.wall_preview.setText("Error loading logo")
            else:
                self.wall_preview.clear()
                self.wall_preview.setText("Logo not found")
        else:
            wall_path = os.path.join(folder_path, "wallpaper.png")
            if os.path.exists(wall_path):
                pix = QPixmap(wall_path)
                scaled_pix = pix.scaled(self.wall_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.wall_preview.setPixmap(scaled_pix)
            else:
                self.wall_preview.clear()
                self.wall_preview.setText("Wallpaper not found")

    def populate_usbs(self):
        self.usb_combo.clear()
        if platform.system() == "Linux":
            try:
                result = subprocess.run(["lsblk", "-d", "-n", "-p", "-o", "NAME,TRAN,MOUNTPOINT,SIZE,MODEL"], capture_output=True, text=True)
                for line in result.stdout.strip().split("\n"):
                    if not line: continue
                    parts = line.split()
                    if len(parts) >= 3 and parts[1] == "usb":
                        self.usb_combo.addItem(f"{parts[0]} ({parts[3]})", parts[0])
            except: pass
        else:
            for p in psutil.disk_partitions():
                if 'removable' in p.opts: self.usb_combo.addItem(f"{p.device} ({p.mountpoint})", p.device)
        if self.usb_combo.count() == 0: self.usb_combo.addItem("No USB detected", None)

    def start_process(self):
        gen = self.gen_combo.currentData()
        pitch = self.pitch_combo.currentText()
        size_actual = self.size_combo.currentData()
        usb_base = self.usb_combo.currentData()
        if not usb_base or not size_actual:
            QMessageBox.warning(self, "Warning", "Please ensure all selections are made.")
            return

        source = os.path.join(self.base_dir, gen, pitch, size_actual)
        
        # Check current File System
        fs_type, mount_device = self.get_usb_fs(usb_base)
        is_fat32 = False
        if platform.system() == "Windows":
            is_fat32 = (fs_type.upper() == "FAT32")
        else:
            is_fat32 = (fs_type.lower() in ["vfat", "fat32"])

        skip_format = False
        target_device = usb_base # Default to base disk if formatting
        
        if is_fat32:
            # Case 1: Already FAT32, just confirm file replacement
            confirm = QMessageBox.question(self, "Confirm", 
                f"USB Drive {mount_device} is already FAT32.\n\n"
                f"Reformatting is not required.\n"
                f"ALL EXISTING FILES WILL BE DELETED from the USB,\n"
                f"and the new firmware for {gen}/{pitch}/{size_actual} will be copied.\n\n"
                f"Proceed?")
            if confirm == QMessageBox.Yes:
                skip_format = True
                target_device = mount_device # Use the partition if skipping format
            else:
                return
        else:
            # Case 2: Not FAT32, ask to format
            confirm = QMessageBox.question(self, "Format Required", 
                f"USB Drive {usb_base} is not FAT32 (Found: {fs_type}).\n\n"
                f"It must be formatted to FAT32 to continue.\n"
                f"ALL DATA ON THE USB WILL BE LOST.\n\n"
                f"Format to FAT32 and proceed?")
            if confirm == QMessageBox.Yes:
                skip_format = False
                target_device = usb_base # Format the base disk
            else:
                return

        self.start_button.setEnabled(False)
        self.worker = FormatCopyWorker(target_device, "FAT32", source, self.custom_logo_path, skip_format=skip_format, duplicate_logo_as_wallpaper=self.dup_logo_wallpaper_check.isChecked())
        self.worker.progress.connect(self.progress_bar.setValue)
        self.status_bar.showMessage("Starting...")
        self.worker.status.connect(self.status_bar.showMessage)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success, msg):
        self.start_button.setEnabled(True)
        if success: QMessageBox.information(self, "Success", msg)
        else: QMessageBox.critical(self, "Error", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BootsiApp()
    window.show()
    sys.exit(app.exec())
