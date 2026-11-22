import subprocess
import platform
import tkinter as tk
import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def detect_all_devices() -> list:
    """Detects all available Windows compute devices (NVIDIA GPUs, CPU)."""
    devices = []

    # 1. Check for NVIDIA Graphics Cards using nvidia-smi (supports multi-Card setups like NVLink or SLI setups)
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=index,name,memory.total", "--format=csv,noheader,nounits"],
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        )
        for line in output.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                idx, name, vram_mb = int(parts[0]), parts[1], int(parts[2])
                vram_gb = round(vram_mb / 1024, 1)
                devices.append({
                    "name": f"NVIDIA {name} ({vram_gb} GB VRAM)",
                    "device": "nvidia_gpu",
                    "tier": "gpu",
                    "vram_gb": vram_gb,
                    "index": idx
                })
    except Exception:
        pass

    # 2. Always include Windows CPU fallback
    devices.append({
        "name": "CPU-Only (Lightweight / Low Resource)",
        "device": "cpu",
        "tier": "cpu",
        "vram_gb": 0.0,
        "index": -1
    })

    return devices


def get_hardware_profile() -> dict:
    """Compatibility helper for gui.py to fetch the primary active hardware tier."""
    devices = detect_all_devices()
    for dev in devices:
        if dev["tier"] == "gpu":
            return dev
    return devices[-1]


class DeviceSelectorDialog(ctk.CTk):
    """Startup window allowing the user to select their preferred device and click Start."""
    def __init__(self, devices: list):
        super().__init__()
        self.title("InteractLLM — Hardware Selector")
        self.geometry("520x400")
        self.resizable(False, False)
        
        self.selected_device = None
        self.devices = devices

        # Header Title
        title_lbl = ctk.CTkLabel(
            self, text="Select Compute Device", font=("Segoe UI", 18, "bold")
        )
        title_lbl.pack(padx=20, pady=(24, 8), anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            self,
            text="Choose which hardware acceleration lane InteractLLM should use:",
            font=("Segoe UI", 13),
            text_color="#AAAAAA",
        )
        subtitle_lbl.pack(padx=20, pady=(0, 16), anchor="w")

        # Frame for Device Radio Buttons
        self.radio_var = tk.IntVar(value=0)
        
        frame = ctk.CTkScrollableFrame(self, width=480, height=200, fg_color="#1E1E1E")
        frame.pack(padx=20, pady=4, fill="both", expand=True)

        for i, dev in enumerate(devices):
            rb = ctk.CTkRadioButton(
                frame,
                text=dev["name"],
                variable=self.radio_var,
                value=i,
                font=("Segoe UI", 14),
                border_color="#3B82F6",
                hover_color="#1D4ED8",
            )
            rb.pack(padx=12, pady=10, anchor="w")

        # Start Button
        start_btn = ctk.CTkButton(
            self,
            text="Start InteractLLM",
            font=("Segoe UI", 15, "bold"),
            height=45,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.on_start,
        )
        start_btn.pack(padx=20, pady=(16, 24), fill="x")

    def on_start(self):
        idx = self.radio_var.get()
        self.selected_device = self.devices[idx]
        self.destroy()

        # Local import to avoid circular dependency with gui.py
        from gui import InteractLLMApp

        # Launch the main GUI and pass the selected hardware profile
        app = InteractLLMApp(hw=self.selected_device)
        app.mainloop()


def select_hardware_gui() -> dict:
    """Launches the hardware selection dialog and returns the chosen device config dictionary."""
    devices = detect_all_devices()
    
    # If only CPU is available, auto-launch the GUI directly without showing popup
    if len(devices) == 1:
        from gui import InteractLLMApp
        app = InteractLLMApp(hw=devices[0])
        app.mainloop()
        return devices[0]

    app = DeviceSelectorDialog(devices)
    app.mainloop()

    return app.selected_device if app.selected_device else devices[-1]


if __name__ == "__main__":
    select_hardware_gui()