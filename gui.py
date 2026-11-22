import inspect
import os
import threading
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image
from interact import ask_interact_llm

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class InteractLLMApp(ctk.CTk):
    def __init__(self, hw=None):
        super().__init__()
        self.title("InteractLLM — Offline Multimodal AI")
        self.geometry("840x640")

        self.hw = hw if hw else {"device": "cpu", "tier": "cpu", "vram_gb": 0.0}
        self.attached_image_path = None
        self.image_refs = []
        self.thumb_ref = None

        # ------------------------------------------------------------------
        # 1. Top Header Bar (Title, Hardware Badge, Clear Button)
        # ------------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(padx=16, pady=(12, 4), fill="x")

        title_lbl = ctk.CTkLabel(
            header,
            text="InteractLLM (Works Offline - FactChecked!)",
            font=("Segoe UI", 16, "bold"),
        )
        title_lbl.pack(side="left")

        clear_btn = ctk.CTkButton(
            header,
            text="Clear Chat",
            width=90,
            height=28,
            fg_color="#333333",
            hover_color="#444444",
            command=self.clear_chat,
        )
        clear_btn.pack(side="right", padx=(8, 0))

        if self.hw.get("tier") == "gpu":
            vram = self.hw.get("vram_gb", 0.0)
            badge_text = f"GPU-Mode ({vram} GB VRAM)"
            badge_color = "#1E4620"
            badge_text_color = "#7CE38B"
        else:
            badge_text = self.hw.get("label", "CPU / Snapdragon Dev")
            badge_color = "#3A301A"
            badge_text_color = "#F2CC60"

        self.hw_badge = ctk.CTkLabel(
            header,
            text=badge_text,
            font=("Segoe UI", 12, "bold"),
            fg_color=badge_color,
            text_color=badge_text_color,
            corner_radius=8,
            padx=10,
            pady=4,
        )
        self.hw_badge.pack(side="right")

        # ------------------------------------------------------------------
        # 2. Chat Display Box
        # ------------------------------------------------------------------
        self.chat_box = ctk.CTkTextbox(
            self, wrap="word", font=("Segoe UI", 14), state="disabled"
        )
        self.chat_box.pack(padx=16, pady=(8, 8), fill="both", expand=True)

        # ------------------------------------------------------------------
        # 3. Attached Image Preview Bar
        # ------------------------------------------------------------------
        self.preview_bar = ctk.CTkFrame(self, fg_color="#252526", corner_radius=8)
        self.preview_thumb_lbl = ctk.CTkLabel(self.preview_bar, text="")
        self.preview_thumb_lbl.pack(side="left", padx=(8, 6), pady=6)

        self.preview_name_lbl = ctk.CTkLabel(
            self.preview_bar, text="", font=("Segoe UI", 12), text_color="#CCCCCC"
        )
        self.preview_name_lbl.pack(side="left", padx=4)

        remove_img_btn = ctk.CTkButton(
            self.preview_bar,
            text="✕",
            width=26,
            height=24,
            fg_color="#442222",
            hover_color="#662222",
            command=self.clear_attached_image,
        )
        remove_img_btn.pack(side="right", padx=8, pady=6)

        # ------------------------------------------------------------------
        # 4. Bottom Input Bar
        # ------------------------------------------------------------------
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(padx=16, pady=(0, 16), fill="x")

        self.attach_btn = ctk.CTkButton(
            self.input_frame,
            text="+ Image",
            width=82,
            height=42,
            fg_color="#2D2D30",
            hover_color="#3E3E42",
            command=self.attach_image,
        )
        self.attach_btn.pack(side="left", padx=(0, 8))

        placeholder = (
            "Ask Wiki, solve math, attach an image, or type 'draw ...'..."
            if self.hw.get("tier") == "gpu"
            else "Ask a question, attach an image for vision/OCR, or test SQLite logging..."
        )
        self.entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text=placeholder,
            font=("Segoe UI", 14),
            height=42,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda _event: self.on_send())

        self.send_btn = ctk.CTkButton(
            self.input_frame, text="Send", width=95, height=42, command=self.on_send
        )
        self.send_btn.pack(side="right")

        self.append_text(
            f"InteractLLM ready ({badge_text}). Ask a question or attach an image.\n"
        )

    # ----------------------------------------------------------------------
    # UI Helper Methods
    # ----------------------------------------------------------------------
    def clear_chat(self):
        self.chat_box.configure(state="normal")
        self.chat_box.delete("1.0", "end")
        self.image_refs.clear()
        self.chat_box.insert("end", "Chat cleared.\n")
        self.chat_box.configure(state="disabled")

    def append_text(self, text: str):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", text)
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def append_image(self, image_path: str, max_width: int = 340):
        if not image_path or not os.path.exists(image_path):
            return
        try:
            with Image.open(image_path) as pil_img:
                img_copy = pil_img.copy()

            w, h = img_copy.size
            if w > max_width:
                ratio = max_width / float(w)
                new_size = (max_width, max(1, int(h * ratio)))
            else:
                new_size = (w, h)

            ctk_img = ctk.CTkImage(
                light_image=img_copy, dark_image=img_copy, size=new_size
            )
            self.image_refs.append(ctk_img)

            self.chat_box.configure(state="normal")
            self.chat_box.insert("end", "\n")
            img_label = ctk.CTkLabel(self.chat_box, image=ctk_img, text="")
            self.chat_box._textbox.window_create("end", window=img_label)
            self.chat_box.insert("end", "\n")
            self.chat_box.see("end")
            self.chat_box.configure(state="disabled")
        except Exception as e:
            self.append_text(f"\n[Could not render image preview: {e}]\n")

    def attach_image(self):
        file_path = filedialog.askopenfilename(
            title="Select an Image to Scan",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.bmp")],
        )
        if not file_path:
            return

        try:
            with Image.open(file_path) as pil_thumb:
                thumb_copy = pil_thumb.copy()
        except Exception as e:
            self.append_text(f"\n[Could not load attached image: {e}]\n")
            return

        self.attached_image_path = file_path
        filename = os.path.basename(file_path)

        self.thumb_ref = ctk.CTkImage(
            light_image=thumb_copy, dark_image=thumb_copy, size=(36, 36)
        )
        self.preview_thumb_lbl.configure(image=self.thumb_ref)
        self.preview_name_lbl.configure(text=f"Attached: {filename}")

        if not self.preview_bar.winfo_ismapped():
            self.preview_bar.pack(
                padx=16, pady=(0, 8), fill="x", before=self.input_frame
            )

    def clear_attached_image(self):
        self.attached_image_path = None
        self.thumb_ref = None
        self.preview_thumb_lbl.configure(image=None)
        if self.preview_bar.winfo_ismapped():
            self.preview_bar.pack_forget()

    # ----------------------------------------------------------------------
    # Message Dispatch & Background Inference
    # ----------------------------------------------------------------------
    def on_send(self):
        question = self.entry.get().strip()
        image_path = self.attached_image_path

        if not question and not image_path:
            return

        self.entry.delete(0, "end")
        self.clear_attached_image()
        self.send_btn.configure(state="disabled")
        self.attach_btn.configure(state="disabled")

        display_q = question if question else "[Scan Attached Image]"
        self.append_text(f"\nYou: {display_q}")
        if image_path:
            self.append_image(image_path, max_width=240)
        self.append_text("\nInteractLLM: ")

        threading.Thread(
            target=self.generate_response,
            args=(question, image_path),
            daemon=True,
        ).start()

    def _call_backend(self, question: str, image_path: str | None):
        kwargs = {
            "query": question,
            "stream_callback": lambda text: self.after(0, self.append_text, text),
            "image_path": image_path,
            "image_callback": lambda out_path: self.after(
                0, self.append_image, out_path
            ),
        }
        sig = inspect.signature(ask_interact_llm)
        if "hw" in sig.parameters:
            kwargs["hw"] = self.hw
        return ask_interact_llm(**kwargs)

    def generate_response(self, question: str, image_path: str | None):
        try:
            self._call_backend(question, image_path)
            self.after(0, self.append_text, "\n")
        except Exception as e:
            self.after(0, self.append_text, f"\n[Error: {e}]\n")
        finally:
            self.after(0, self._unlock_controls)

    def _unlock_controls(self):
        self.send_btn.configure(state="normal")
        self.attach_btn.configure(state="normal")


if __name__ == "__main__":
    app = InteractLLMApp(
        hw={"device": "qnn/cpu", "tier": "cpu", "vram_gb": 0.0, "label": "Snapdragon / Dev"}
    )
    app.mainloop()