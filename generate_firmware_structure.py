import os
import sys
import csv
import shutil
from PIL import Image

def load_grid(generation, pitch_name):
    """Loads the binary grid from the generation's pixel math folder."""
    if generation == "G4":
        filename = os.path.join("G4", "g4 pixel math", f"g4-{pitch_name}.txt")
        if not os.path.exists(filename):
            print(f"Warning: Math file {filename} not found.")
            return None
        
        grid = []
        with open(filename, 'r') as f:
            for line in f:
                row = [int(x) for x in line.split()]
                if row:
                    grid.append(row)
        return grid
    elif generation == "G3":
        # Format: Cam Finder Math - G3 - 20mm.csv
        filename = os.path.join("G3", "g3 pixel math", f"Cam Finder Math - G3 - {pitch_name}.csv")
        if not os.path.exists(filename):
            print(f"Warning: Math file {filename} not found.")
            return None
        
        return load_csv_grid(filename)
    elif generation == "G2":
        # Format: Cam Finder Math - G2 - 20mm.csv
        filename = os.path.join("G2", "g2 cam math", f"Cam Finder Math - G2 - {pitch_name}.csv")
        if not os.path.exists(filename):
            print(f"Warning: Math file {filename} not found.")
            return None
        
        return load_csv_grid(filename)
    elif generation == "G1":
        # Format: Cam Finder Math - G1 - 20mm.csv
        filename = os.path.join("G1", "g1 cam math", f"Cam Finder Math - G1 - {pitch_name}.csv")
        if not os.path.exists(filename):
            print(f"Warning: Math file {filename} not found.")
            return None
        
        return load_csv_grid(filename)
    return None

def load_csv_grid(filename):
    """Parses a CSV grid file."""
    grid = []
    with open(filename, 'r', newline='') as f:
        reader = csv.reader(f)
        # Skip header row
        next(reader)
        for row in reader:
            # Row starts with row index, so skip it
            data = row[1:]
            numeric_row = []
            for val in data:
                if val.strip():
                    numeric_row.append(int(val))
            if numeric_row:
                grid.append(numeric_row)
    return grid

def generate_module_tile(module_w, module_h, grid, pitch_name, generation):
    """Generates a single module tile based on grid values."""
    img = Image.new('RGB', (module_w, module_h), color=(0, 0, 0))
    pixels = img.load()

    if not grid:
        return img

    grid_h = len(grid)
    for y in range(min(grid_h, module_h)):
        current_row_w = len(grid[y])
        for x in range(min(current_row_w, module_w)):
            val = grid[y][x]
            if val == 1:
                # 1 is Red
                pixels[x, y] = (255, 0, 0)
            elif val == 2:
                # 2 is White
                pixels[x, y] = (255, 255, 255)
            elif val == 0:
                # 0 is Black
                pixels[x, y] = (0, 0, 0)
    
    # Fallback/Consistency logic for G4 style math if needed
    if generation == "G4":
        has_two = any(2 in row for row in grid)
        if not has_two and pitch_name != "9mm":
            # Fallback for old style math files: ensure white dots
            for y in range(min(grid_h, module_h)):
                for x in range(min(len(grid[y]), module_w)):
                    if grid[y][x] == 1:
                        pixels[x, y] = (255, 255, 255)
            # Red Border
            for x in range(module_w):
                pixels[x, 0] = (255, 0, 0)
                pixels[x, module_h - 1] = (255, 0, 0)
            for y in range(module_h):
                pixels[0, y] = (255, 0, 0)
                pixels[module_w - 1, y] = (255, 0, 0)

    return img

def generate_firmware_structure():
    """Generates a nested directory structure and tiled wallpaper images."""
    generations = {
        "G1": {
            "20mm": (16, 16),
            "15mm": (20, 20),
            "10mm": (32, 32)
        },
        "G2": {
            "20mm": (16, 8),
            "15mm": (20, 10),
            "10mm": (32, 16),
            "6mm": (48, 24)
        },
        "G3": {
            "20mm": (15, 15),
            "15mm": (20, 20),
            "10mm": (30, 30),
            "6mm": (50, 50)
        },
        "G4": {
            "4mm": (64, 64),
            "6mm": (48, 48),
            "9mm": (32, 32),
            "15mm": (20, 20)
        }
    }

    print("Starting firmware generation with TALL x WIDE naming...")
    
    # Optional: Wipe old folders to ensure clean structure
    for gen in ["G1", "G2", "G3", "G4"]:
        for d in os.listdir(gen):
            if d.endswith("mm"):
                shutil.rmtree(os.path.join(gen, d))

    for gen_name, pitches in generations.items():
        print(f"\nProcessing {gen_name}...")
        for pitch_name, module_size in pitches.items():
            module_w, module_h = module_size
            print(f"  - {pitch_name} ({module_w}x{module_h})")
            
            grid = load_grid(gen_name, pitch_name)
            module_tile = generate_module_tile(module_w, module_h, grid, pitch_name, gen_name)
            
            for cols in range(1, 21):
                for rows in range(1, 21):
                    total_w = cols * module_w
                    total_h = rows * module_h
                    
                    # New Naming: TALL x WIDE (Rows x Cols_Height x Width)
                    target_path = os.path.join(gen_name, pitch_name, f"{rows}x{cols}_{total_h}x{total_w}")
                    os.makedirs(target_path, exist_ok=True)

                    # 1. boot.png
                    source_logo_path = "Impact Logo.png"
                    if os.path.exists(source_logo_path):
                        boot_path = os.path.join(target_path, "boot.png")
                        try:
                            source_logo = Image.open(source_logo_path).convert("RGBA")
                            bg = Image.new('RGB', (total_w, total_h), color=(0, 0, 0))
                            src_w, src_h = source_logo.size
                            ratio = min(total_w / src_w, total_h / src_h)
                            new_w, new_h = int(src_w * ratio), int(src_h * ratio)
                            resized_logo = source_logo.resize((new_w, new_h), Image.Resampling.LANCZOS)
                            offset_x, offset_y = (total_w - new_w) // 2, (total_h - new_h) // 2
                            bg.paste(resized_logo, (offset_x, offset_y), resized_logo)
                            bg.save(boot_path, "PNG")
                        except Exception as e:
                            print(f"Error processing boot screen for {target_path}: {e}")

                    # 2. wallpaper.png
                    wallpaper_path = os.path.join(target_path, "wallpaper.png")
                    try:
                        full_wallpaper = Image.new('RGB', (total_w, total_h), color=(0, 0, 0))
                        for c in range(cols):
                            for r in range(rows):
                                full_wallpaper.paste(module_tile, (c * module_w, r * module_h))
                        full_wallpaper.save(wallpaper_path, "PNG")
                    except Exception as e:
                        print(f"Failed to save wallpaper: {e}")

    print("\nGeneration complete!")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    generate_firmware_structure()
