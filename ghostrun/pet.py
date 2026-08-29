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

    # Sizing without awkward extra padding so mouse never exits window when reaching for the X
    total_w = target_w
    total_h = target_h

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

    # Position at bottom right-center (nestled beside chat input & terminal)
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    # Offset further left into the workspace area (e.g. ~420px from right edge)
    pos_x = max(50, screen_w - total_w - 420)
    pos_y = max(50, screen_h - total_h - 75)
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
        "leave_job": None,
    }
    image_item = canvas.create_image(
        0, 0, anchor="nw", image=tk_frames[current_state["anim"]][0]
    )

    # Hover Close Button (X)
    btn_r = 10
    btn_cx, btn_cy = total_w - 14, 14
    close_btn_bg = canvas.create_oval(
        btn_cx - btn_r, btn_cy - btn_r, btn_cx + btn_r, btn_cy + btn_r,
        fill="#e53e3e", outline="#ffffff", width=1, state="hidden", tags="close_tag"
    )
    close_btn_text = canvas.create_text(
        btn_cx, btn_cy, text="✕", fill="#ffffff", font=("Segoe UI", 9, "bold"), state="hidden", tags="close_tag"
    )

    # Retain references on root to prevent Python/Tcl memory deallocation race
    root._tk_frames = tk_frames
    root._is_running = True

    def do_close(event=None):
        if not getattr(root, "_is_running", False):
            return
        root._is_running = False
        if current_state.get("anim_job"):
            try:
                root.after_cancel(current_state["anim_job"])
            except Exception:
                pass
        if current_state.get("leave_job"):
            try:
                root.after_cancel(current_state["leave_job"])
            except Exception:
                pass
        try:
            root.withdraw()
            root.quit()
        except Exception:
            pass

    # Direct click on the close button widget tag
    canvas.tag_bind("close_tag", "<Button-1>", do_close)

    drag_data = {"x": 0, "y": 0}

    def start_drag(event):
        drag_data["x"] = event.x
        drag_data["y"] = event.y

    def on_drag(event):
        new_x = root.winfo_x() + (event.x - drag_data["x"])
        new_y = root.winfo_y() + (event.y - drag_data["y"])
        root.geometry(f"+{new_x}+{new_y}")

    # Custom frame intervals per animation state matching preview.html
    ANIM_SPEEDS = {
        "idle": 120,
        "running-right": 110,
        "running-left": 110,
        "waving": 120,
        "jumping": 100,
        "failed": 150,
        "waiting": 120,
        "running": 80,
        "thinking": 70,
        "review": 90,
    }

    # Normalize aliases
    if initial_anim == "thinking":
        initial_anim = "running"

    def on_canvas_click(event):
        # Generous bounding box check for top-right close area
        if event.x >= total_w - 28 and event.y <= 28:
            do_close()
            return

        # Cycle all 9 animation states on pet click
        anim_cycle = [
            "idle",
            "running-right",
            "running-left",
            "jumping",
            "waving",
            "review",
            "running",
            "waiting",
            "failed",
        ]
        curr = current_state["anim"]
        next_idx = (anim_cycle.index(curr) + 1) % len(anim_cycle) if curr in anim_cycle else 0
        current_state["anim"] = anim_cycle[next_idx]
        current_state["frame_idx"] = 0

    def show_close_btn(event=None):
        if not getattr(root, "_is_running", False):
            return
        if current_state["leave_job"]:
            root.after_cancel(current_state["leave_job"])
            current_state["leave_job"] = None
        current_state["hover"] = True
        canvas.itemconfig(close_btn_bg, state="normal")
        canvas.itemconfig(close_btn_text, state="normal")

    def hide_close_btn():
        if not getattr(root, "_is_running", False):
            return
        current_state["hover"] = False
        canvas.itemconfig(close_btn_bg, state="hidden")
        canvas.itemconfig(close_btn_text, state="hidden")

    def on_hover_leave(event=None):
        if not getattr(root, "_is_running", False):
            return
        if current_state["leave_job"]:
            root.after_cancel(current_state["leave_job"])
        current_state["leave_job"] = root.after(500, hide_close_btn)

    canvas.bind("<Button-1>", on_canvas_click)
    canvas.bind("<Button-3>", do_close)  # Right click also closes instantly
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonPress-1>", start_drag)
    canvas.bind("<Enter>", show_close_btn)
    canvas.bind("<Leave>", on_hover_leave)
    canvas.bind("<Motion>", show_close_btn)

    def update_frame():
        if not getattr(root, "_is_running", False):
            return
        anim = current_state["anim"]
        idx = current_state["frame_idx"]
        frames = tk_frames.get(anim, tk_frames.get("running" if anim == "thinking" else "idle"))

        canvas.itemconfig(image_item, image=frames[idx % len(frames)])
        current_state["frame_idx"] = (idx + 1) % len(frames)

        # Smooth physical desktop locomotion when running!
        if not drag_data.get("dragging", False):
            curr_x = root.winfo_x()
            curr_y = root.winfo_y()
            step_px = 6  # Smooth pixels per frame

            if anim in ("running-right", "running"):
                new_x = curr_x + step_px
                # Bounce or wrap around if reaching right edge
                if new_x > screen_w - total_w - 20:
                    current_state["anim"] = "running-left"
                else:
                    root.geometry(f"+{new_x}+{curr_y}")
            elif anim == "running-left":
                new_x = curr_x - step_px
                # Bounce if reaching left edge
                if new_x < 20:
                    current_state["anim"] = "running-right"
                else:
                    root.geometry(f"+{new_x}+{curr_y}")
        
        speed = ANIM_SPEEDS.get(anim, 100)
        current_state["anim_job"] = root.after(speed, update_frame)

    print("\n👻 GhostRun Desktop Pet is active!")
    print("- Hover: Click the red '✕' button to close")
    print("- Left Click: Cycle through all 9 tactical animations")
    print("- Left Drag: Move pet anywhere on your screen\n")

    update_frame()

    if auto_close_ms:
        root.after(auto_close_ms, do_close)

    root.mainloop()


def spawn_pet_async(
    anim: str = "jumping",
    auto_close_ms: int = 3500,
    width: int = 96,
) -> None:
    """Spawn the floating pet in a non-blocking background daemon subprocess."""
    if os.environ.get("GHOSTRUN_NO_PET") or os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        return

    try:
        import subprocess
        cmd = [
            sys.executable,
            "-m",
            "ghostrun.pet",
            "--width",
            str(width),
            "--anim",
            anim,
            "--auto-close",
            str(auto_close_ms),
        ]
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=96)
    parser.add_argument("--anim", default="idle")
    parser.add_argument("--auto-close", type=int, default=None)
    args = parser.parse_args()
    try:
        run_pet(width=args.width, initial_anim=args.anim, auto_close_ms=args.auto_close)
    except KeyboardInterrupt:
        pass
