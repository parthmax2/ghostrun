"""GhostRun Desktop Pet: A lightweight, transparent, animated tactical skull companion.

Can be run standalone via `ghostrun pet`, or react to live pytest & craft execution.
"""

from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from pathlib import Path
from typing import Dict, List, Optional

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None


def get_asset_paths() -> tuple[Path, Path]:
    """Locate spritesheet.png and pet.json inside package assets or repository fallback."""
    pkg_assets = Path(__file__).parent / "assets"
    if (pkg_assets / "spritesheet.png").exists() and (pkg_assets / "pet.json").exists():
        return pkg_assets / "spritesheet.png", pkg_assets / "pet.json"

    # Fallback to repo directory if running from source tree
    repo_pet = Path(__file__).parent.parent / "ghostrun-pet"
    if (repo_pet / "spritesheet.png").exists() and (repo_pet / "pet.json").exists():
        return repo_pet / "spritesheet.png", repo_pet / "pet.json"

    raise FileNotFoundError("Could not locate GhostRun pet spritesheet assets.")


def run_pet(
    width: int = 96,
    auto_close_ms: Optional[int] = None,
    initial_anim: str = "idle",
) -> None:
    """Launch the floating transparent GhostRun mascot."""
    if Image is None or ImageTk is None:
        print(
            "ghostrun pet requires Pillow. Install it with: pip install pillow",
            file=sys.stderr,
        )
        sys.exit(1)

    spritesheet_path, pet_json_path = get_asset_paths()

    with open(pet_json_path, "r", encoding="utf-8") as fh:
        meta = json.load(fh)

    frame_w = meta["frames"]["width"]
    frame_h = meta["frames"]["height"]
    animations = meta["animations"]

    sheet_img = Image.open(spritesheet_path).convert("RGBA")
    target_w = width
    target_h = int(width * (frame_h / frame_w))

    # Slice frames for each animation state
    frames_by_anim: Dict[str, List[Image.Image]] = {}
    for anim_name, anim_info in animations.items():
        row = anim_info["row"]
        frame_count = anim_info["frames"]
        frames = []
        for col in range(frame_count):
            box = (col * frame_w, row * frame_h, (col + 1) * frame_w, (row + 1) * frame_h)
            cropped = sheet_img.crop(box)
            resized = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
            frames.append(resized)
        frames_by_anim[anim_name] = frames

    total_w = target_w + 10
    total_h = target_h + 24

    root = tk.Tk()
    root.title("GhostRun Pet")
    root.overrideredirect(True)
    root.wm_attributes("-topmost", True)

    TRANS_COLOR = "#000001"
    root.config(bg=TRANS_COLOR)
    try:
        root.wm_attributes("-transparentcolor", TRANS_COLOR)
    except tk.TclError:
        pass  # Non-Windows fallback

    # Position at bottom-right of primary display
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    pos_x = screen_w - total_w - 40
    pos_y = screen_h - total_h - 70
    root.geometry(f"{total_w}x{total_h}+{pos_x}+{pos_y}")

    canvas = tk.Canvas(
        root,
        width=total_w,
        height=total_h,
        bg=TRANS_COLOR,
        highlightthickness=0,
        bd=0,
    )
    canvas.pack(fill="both", expand=True)

    tk_frames: Dict[str, List[ImageTk.PhotoImage]] = {}
    for anim_name, pil_frames in frames_by_anim.items():
        tk_frames[anim_name] = [ImageTk.PhotoImage(f) for f in pil_frames]

    current_state = {
        "anim": initial_anim if initial_anim in tk_frames else "idle",
        "frame_idx": 0,
        "hover": False,
    }
    sprite_y_offset = 20
    image_item = canvas.create_image(
        5, sprite_y_offset, anchor="nw", image=tk_frames[current_state["anim"]][0]
    )

    # Hover Close Button (X)
    close_btn_bg = canvas.create_oval(
        total_w - 20, 2, total_w - 2, 20, fill="#e53e3e", outline="#ffffff", width=1, state="hidden"
    )
    close_btn_text = canvas.create_text(
        total_w - 11, 10, text="✕", fill="#ffffff", font=("Segoe UI", 9, "bold"), state="hidden"
    )

    drag_data = {"x": 0, "y": 0}

    def start_drag(event):
        drag_data["x"] = event.x
        drag_data["y"] = event.y

    def on_drag(event):
        new_x = root.winfo_x() + (event.x - drag_data["x"])
        new_y = root.winfo_y() + (event.y - drag_data["y"])
        root.geometry(f"+{new_x}+{new_y}")

    def on_click(event):
        # Clicked hover close button
        if total_w - 24 <= event.x <= total_w and 0 <= event.y <= 24:
            root.destroy()
            return

        # Cycle animation states on pet click
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

    def update_frame():
        anim = current_state["anim"]
        idx = current_state["frame_idx"]
        frames = tk_frames.get(anim, tk_frames["idle"])

        canvas.itemconfig(image_item, image=frames[idx % len(frames)])
        current_state["frame_idx"] = (idx + 1) % len(frames)
        root.after(100, update_frame)

    print("\n👻 GhostRun Desktop Pet is active!")
    print("- Hover: Click the red '✕' button to close")
    print("- Left Click: Cycle animations (idle / running / jumping / waving / review / failed)")
    print("- Left Drag: Move pet anywhere on your screen\n")

    update_frame()

    if auto_close_ms:
        root.after(auto_close_ms, root.destroy)

    root.mainloop()
