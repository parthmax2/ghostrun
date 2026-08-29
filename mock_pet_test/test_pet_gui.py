"""Mock test for Option B: Python transparent floating sprite animation engine.

Tests slicing frames from ghostrun-pet/spritesheet.png and rendering a borderless,
always-on-top transparent animated character.
"""

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from PIL import Image, ImageTk

def main():
    pet_dir = Path(__file__).parent.parent / "ghostrun-pet"
    spritesheet_path = pet_dir / "spritesheet.png"
    pet_json_path = pet_dir / "pet.json"

    if not spritesheet_path.exists() or not pet_json_path.exists():
        print(f"Error: Missing assets in {pet_dir}")
        return

    with open(pet_json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    frame_w = meta["frames"]["width"]
    frame_h = meta["frames"]["height"]
    animations = meta["animations"]

    print(f"[OK] Loaded pet metadata: {meta['name']} (Frame: {frame_w}x{frame_h})")
    print(f"[OK] Available animations: {list(animations.keys())}")

    # Load and slice spritesheet using PIL
    sheet_img = Image.open(spritesheet_path).convert("RGBA")
    
    # Compact, cozy desk size (e.g. 96px width)
    target_w, target_h = 96, int(96 * (frame_h / frame_w))

    frames_by_anim = {}
    for anim_name, anim_info in animations.items():
        row = anim_info["row"]
        frame_count = anim_info["frames"]
        frames = []
        for col in range(frame_count):
            box = (col * frame_w, row * frame_h, (col + 1) * frame_w, (row + 1) * frame_h)
            cropped = sheet_img.crop(box)
            # High-quality anti-aliased downsampling for crisp outlines
            resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
            frames.append(resized)
        frames_by_anim[anim_name] = frames

    print(f"[OK] Sliced {len(frames_by_anim)} animation states with total {sum(len(f) for f in frames_by_anim.values())} frames!")

    # Set up Tkinter floating window (Extra 22px top margin for the hover close button)
    total_w = target_w + 10
    total_h = target_h + 24

    root = tk.Tk()
    root.title("GhostRun Desktop Pet")
    root.overrideredirect(True)      # Borderless window
    root.wm_attributes("-topmost", True)  # Always on top

    # Windows transparent background keying
    TRANS_COLOR = "#000001"
    root.config(bg=TRANS_COLOR)
    root.wm_attributes("-transparentcolor", TRANS_COLOR)

    # Position at bottom-right corner of screen (just above taskbar)
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    pos_x = screen_w - total_w - 40
    pos_y = screen_h - total_h - 70
    root.geometry(f"{total_w}x{total_h}+{pos_x}+{pos_y}")

    # Canvas for rendering
    canvas = tk.Canvas(
        root,
        width=total_w,
        height=total_h,
        bg=TRANS_COLOR,
        highlightthickness=0,
        bd=0
    )
    canvas.pack(fill="both", expand=True)

    # Pre-render PhotoImages for Tkinter
    tk_frames = {}
    for anim_name, pil_frames in frames_by_anim.items():
        tk_frames[anim_name] = [ImageTk.PhotoImage(f) for f in pil_frames]

    current_state = {"anim": "idle", "frame_idx": 0, "hover": False}
    sprite_y_offset = 20
    image_item = canvas.create_image(5, sprite_y_offset, anchor="nw", image=tk_frames["idle"][0])

    # Hover Close Button (X)
    close_btn_bg = canvas.create_oval(total_w - 20, 2, total_w - 2, 20, fill="#e53e3e", outline="#ffffff", width=1, state="hidden")
    close_btn_text = canvas.create_text(total_w - 11, 10, text="✕", fill="#ffffff", font=("Segoe UI", 9, "bold"), state="hidden")

    # Allow dragging the pet anywhere on screen
    drag_data = {"x": 0, "y": 0}

    def start_drag(event):
        drag_data["x"] = event.x
        drag_data["y"] = event.y

    def on_drag(event):
        new_x = root.winfo_x() + (event.x - drag_data["x"])
        new_y = root.winfo_y() + (event.y - drag_data["y"])
        root.geometry(f"+{new_x}+{new_y}")

    def on_click(event):
        # Check if close button clicked
        if total_w - 24 <= event.x <= total_w and 0 <= event.y <= 24:
            print("GhostRun pet closed.")
            root.destroy()
            return

        # Cycle animation on click: idle -> running-right -> jumping -> waving -> review -> failed
        anim_cycle = ["idle", "running-right", "jumping", "waving", "review", "failed"]
        curr = current_state["anim"]
        next_idx = (anim_cycle.index(curr) + 1) % len(anim_cycle) if curr in anim_cycle else 0
        current_state["anim"] = anim_cycle[next_idx]
        current_state["frame_idx"] = 0

    def on_hover_enter(event):
        current_state["hover"] = True
        canvas.itemconfig(close_btn_bg, state="normal")
        canvas.itemconfig(close_btn_text, state="normal")

    def on_hover_leave(event):
        current_state["hover"] = False
        canvas.itemconfig(close_btn_bg, state="hidden")
        canvas.itemconfig(close_btn_text, state="hidden")

    canvas.bind("<Button-1>", on_click)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonPress-1>", start_drag)
    canvas.bind("<Enter>", on_hover_enter)
    canvas.bind("<Leave>", on_hover_leave)

    # 60 FPS animation loop (~100ms per frame for smooth game walk)
    def update_frame():
        anim = current_state["anim"]
        idx = current_state["frame_idx"]
        frames = tk_frames[anim]
        
        canvas.itemconfig(image_item, image=frames[idx])
        current_state["frame_idx"] = (idx + 1) % len(frames)
        root.after(100, update_frame)

    print("\nGhostRun Pet (Compact) is running!")
    print("- Hover: Shows red '✕' close button")
    print("- Left Click on pet: Cycles animations")
    print("- Left Drag: Move pet anywhere on your screen")

    update_frame()

    if "--auto-close" in sys.argv:
        root.after(4000, root.destroy)

    root.mainloop()

if __name__ == "__main__":
    main()
