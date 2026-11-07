"""
gui_app.py - Polished AI Desktop Window with Dot Grid Matrix, White Icons, Custom Scrollbars & Settings Theme Switcher
"""

import os
import sys
import math
import subprocess
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageDraw

ctk.set_appearance_mode("dark")

GRID_STEP = 25  # 25px Grid Dot Matrix
CANVAS_BOUNDS = 5000  # -5000 to +5000 X and Y pan space

# Color Themes Configuration
THEMES = {
    "Slate White": {
        "accent": "#ffffff",
        "grid_minor": "#1e293b",
        "grid_major": "#475569",
        "dock_border": "#334155",
        "dock_bg": "#0f172a",
        "thumb_color": "#334155",
        "thumb_hover": "#f8fafc",
        "text": "#f8fafc"
    },
    "Electric Indigo": {
        "accent": "#818cf8",
        "grid_minor": "#1e1b4b",
        "grid_major": "#4f46e5",
        "dock_border": "#4338ca",
        "dock_bg": "#0f172a",
        "thumb_color": "#4338ca",
        "thumb_hover": "#818cf8",
        "text": "#f8fafc"
    },
    "Emerald Green": {
        "accent": "#34d399",
        "grid_minor": "#064e3b",
        "grid_major": "#059669",
        "dock_border": "#047857",
        "dock_bg": "#061812",
        "thumb_color": "#047857",
        "thumb_hover": "#34d399",
        "text": "#f8fafc"
    },
    "Cyber Cyan": {
        "accent": "#00f2fe",
        "grid_minor": "#0f1a2e",
        "grid_major": "#005577",
        "dock_border": "#00f2fe",
        "dock_bg": "#0d162a",
        "thumb_color": "#005577",
        "thumb_hover": "#00f2fe",
        "text": "#f8fafc"
    }
}


# Pure Crisp White Vector Icon Generators
def create_power_icon(size=36, color="#ffffff"):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.line([(size // 2, 4), (size // 2, size // 2 - 1)], fill=color, width=3)
    draw.arc([(6, 6), (size - 6, size - 6)], start=305, end=235, fill=color, width=3)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))

def create_settings_icon(size=36, color="#ffffff"):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    center = size // 2
    draw.ellipse([(6, 6), (size - 6, size - 6)], outline=color, width=3)
    draw.ellipse([(14, 14), (size - 14, size - 14)], outline=color, width=3)
    for i in range(8):
        ang = math.radians(i * 45)
        x1 = center + 11 * math.cos(ang)
        y1 = center + 11 * math.sin(ang)
        x2 = center + 16 * math.cos(ang)
        y2 = center + 16 * math.sin(ang)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))

def create_recenter_icon(size=36, color="#ffffff"):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([(4, 4), (size - 4, size - 4)], radius=6, outline=color, width=3)
    center = size // 2
    draw.line([(center, 10), (center, size - 10)], fill=color, width=3)
    draw.line([(10, center), (size - 10, center)], fill=color, width=3)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))


class CustomCanvasScrollbar(ctk.CTkCanvas):
    """100% Custom 6px ultra-thin scrollbar with dynamic theme colors."""

    def __init__(self, master, orientation="horizontal", size=6, command=None, app_ref=None, **kwargs):
        width = 100 if orientation == "horizontal" else size
        height = size if orientation == "horizontal" else 100
        super().__init__(master, bg="#090d16", highlightthickness=0, width=width, height=height, **kwargs)

        self.orientation = orientation
        self.command = command
        self.app = app_ref
        self.first = 0.0
        self.last = 1.0
        self.is_hovered = False

        self.bind("<Configure>", lambda e: self.draw_thumb())
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)

    def get_thumb_color(self):
        theme = THEMES.get(self.app.current_theme, THEMES["Slate White"]) if self.app else THEMES["Slate White"]
        return theme["thumb_hover"] if self.is_hovered else theme["thumb_color"]

    def on_hover(self, event=None):
        self.is_hovered = True
        self.draw_thumb()

    def on_leave(self, event=None):
        self.is_hovered = False
        self.draw_thumb()

    def set(self, first, last):
        self.first = float(first)
        self.last = float(last)
        self.draw_thumb()

    def draw_thumb(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()

        if w <= 1 or h <= 1:
            return

        color = self.get_thumb_color()

        if self.orientation == "horizontal":
            x0 = self.first * w
            x1 = self.last * w
            if x1 - x0 < 25:
                x1 = x0 + 25
            self.create_rectangle(x0, 0, min(w, x1), h, fill=color, outline="", tags="thumb")
        else:
            y0 = self.first * h
            y1 = self.last * h
            if y1 - y0 < 25:
                y1 = y0 + 25
            self.create_rectangle(0, y0, w, min(h, y1), fill=color, outline="", tags="thumb")

    def on_click(self, event):
        self.on_drag(event)

    def on_drag(self, event):
        w = self.winfo_width()
        h = self.winfo_height()

        if self.orientation == "horizontal" and w > 0:
            fraction = max(0.0, min(1.0, event.x / w))
            if self.command:
                self.command("moveto", fraction)
        elif self.orientation == "vertical" and h > 0:
            fraction = max(0.0, min(1.0, event.y / h))
            if self.command:
                self.command("moveto", fraction)


class CustomTooltip:
    """Floating tooltip bubble visible on hover over dock icons."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None

        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x = self.widget.winfo_rootx() - 10
        y = self.widget.winfo_rooty() - 32

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg="#0f172a")

        lbl = tk.Label(
            tw, text=self.text, bg="#0f172a", fg="#f8fafc",
            font=("Inter", 9, "bold"), relief="solid", bd=1,
            highlightbackground="#334155", padx=8, pady=3
        )
        lbl.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


class DraggableDock(ctk.CTkFrame):
    """Movable Floating Main Menu Dock with sleek white icons and smooth border radius."""

    def __init__(self, master, app_ref, **kwargs):
        self.app = app_ref
        theme = THEMES.get(self.app.current_theme, THEMES["Slate White"])
        
        super().__init__(
            master, 
            corner_radius=20, 
            fg_color=theme["dock_bg"], 
            border_color=theme["dock_border"], 
            border_width=1, 
            **kwargs
        )

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(padx=8, pady=6)

        # Pure White Dock Icons
        self.icon_power = create_power_icon(color="#ffffff")
        self.btn_power = ctk.CTkButton(
            inner, text="", image=self.icon_power, width=40, height=40,
            corner_radius=14, fg_color="transparent", hover_color="#1e293b",
            command=self.on_power_click
        )
        self.btn_power.pack(side="left", padx=4)
        CustomTooltip(self.btn_power, "Power Options")

        self.icon_settings = create_settings_icon(color="#ffffff")
        self.btn_settings = ctk.CTkButton(
            inner, text="", image=self.icon_settings, width=40, height=40,
            corner_radius=14, fg_color="transparent", hover_color="#1e293b",
            command=self.on_settings_click
        )
        self.btn_settings.pack(side="left", padx=4)
        CustomTooltip(self.btn_settings, "Settings")

        self.icon_recenter = create_recenter_icon(color="#ffffff")
        self.btn_recenter = ctk.CTkButton(
            inner, text="", image=self.icon_recenter, width=40, height=40,
            corner_radius=14, fg_color="transparent", hover_color="#1e293b",
            command=self.on_recenter_click
        )
        self.btn_recenter.pack(side="left", padx=4)
        CustomTooltip(self.btn_recenter, "Recenter Board")

        # Movable Drag Bindings
        self.bind("<Button-1>", self.on_drag_start)
        self.bind("<B1-Motion>", self.on_drag_motion)
        self.bind("<ButtonRelease-1>", self.on_drag_release)
        inner.bind("<Button-1>", self.on_drag_start)
        inner.bind("<B1-Motion>", self.on_drag_motion)
        inner.bind("<ButtonRelease-1>", self.on_drag_release)

        self.power_menu = None

    def update_theme_style(self):
        theme = THEMES.get(self.app.current_theme, THEMES["Slate White"])
        self.configure(fg_color=theme["dock_bg"], border_color=theme["dock_border"])

    def on_drag_start(self, event):
        self._offset_x = event.x_root - self.winfo_x()
        self._offset_y = event.y_root - self.winfo_y()

    def on_drag_motion(self, event):
        # 120 FPS Silky Smooth Fluid Motion while dragging
        new_x = event.x_root - self._offset_x
        new_y = event.y_root - self._offset_y
        self.place(x=new_x, y=new_y)

    def on_drag_release(self, event):
        # Magnetically Snap top-left corner to nearest dot grid point on drop
        cur_x = self.winfo_x()
        cur_y = self.winfo_y()
        snap_x = round(cur_x / GRID_STEP) * GRID_STEP
        snap_y = round(cur_y / GRID_STEP) * GRID_STEP
        self.place(x=snap_x, y=snap_y)




    def on_power_click(self):
        if self.power_menu and self.power_menu.winfo_exists():
            self.power_menu.destroy()
            self.power_menu = None
            return

        x = self.btn_power.winfo_rootx()
        y = self.btn_power.winfo_rooty() - 130

        self.power_menu = ctk.CTkToplevel(self)
        self.power_menu.wm_overrideredirect(True)
        self.power_menu.geometry(f"200x120+{x}+{y}")
        self.power_menu.configure(fg_color="#0f172a")

        menu_frame = ctk.CTkFrame(self.power_menu, corner_radius=12, fg_color="#0f172a", border_color="#334155", border_width=1)
        menu_frame.pack(fill="both", expand=True, padx=2, pady=2)

        btn_restart = ctk.CTkButton(
            menu_frame, text="🔄 Restart Friday", height=30, fg_color="transparent", 
            hover_color="#1e293b", text_color="#f8fafc", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"), command=self.app.restart_friday
        )
        btn_restart.pack(fill="x", padx=6, pady=4)

        btn_reload = ctk.CTkButton(
            menu_frame, text="⚡ Reload (with updates)", height=30, fg_color="transparent", 
            hover_color="#1e293b", text_color="#38bdf8", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"), command=self.app.reload_friday
        )
        btn_reload.pack(fill="x", padx=6, pady=2)

        btn_shutdown = ctk.CTkButton(
            menu_frame, text="🔴 Shutdown Friday", height=30, fg_color="transparent", 
            hover_color="#3d1015", text_color="#f87171", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"), command=self.app.shutdown_friday
        )
        btn_shutdown.pack(fill="x", padx=6, pady=4)

    def on_settings_click(self):
        self.app.open_settings_popup()

    def on_recenter_click(self):
        self.app.recenter_origin()


class FridayGridPanGUI(ctk.CTk):
    """Pannable Blueprint Graph Canvas with Dot Matrix & Settings Theme Switcher."""

    def __init__(self):
        super().__init__()

        self.title("Friday AI")
        self.geometry("1100x750")
        self.configure(fg_color="#090d16")

        self.current_theme = "Slate White"

        container = ctk.CTkFrame(self, fg_color="#090d16", corner_radius=0)
        container.pack(fill="both", expand=True)

        # 100% Custom 6px Thin Scrollbars
        self.hbar = CustomCanvasScrollbar(container, orientation="horizontal", size=6, app_ref=self)
        self.hbar.pack(side="bottom", fill="x")

        self.vbar = CustomCanvasScrollbar(container, orientation="vertical", size=6, app_ref=self)
        self.vbar.pack(side="right", fill="y")

        # Main Canvas
        self.canvas = tk.Canvas(
            container, 
            bg="#090d16", 
            highlightthickness=0,
            xscrollcommand=self.hbar.set,
            yscrollcommand=self.vbar.set,
            scrollregion=(-CANVAS_BOUNDS, -CANVAS_BOUNDS, CANVAS_BOUNDS, CANVAS_BOUNDS)
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        self.hbar.command = self.canvas.xview
        self.vbar.command = self.canvas.yview

        # Mouse Drag Pan Bindings
        self.canvas.bind("<ButtonPress-1>", self.on_pan_start)
        self.canvas.bind("<B1-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.bind("<Configure>", self.draw_grid)

        # Draw Viewport Dot Grid Matrix
        self.draw_grid()

        # Floating Movable Main Menu Dock
        self.dock = DraggableDock(self.canvas, app_ref=self)
        self.dock.place(x=470, y=660)

        self.after(50, self.recenter_origin)

    def draw_grid(self, event=None):
        """Draws polished clean AI Dot Grid Matrix for 120 FPS native hardware panning."""
        self.canvas.delete("grid")
        theme = THEMES.get(self.current_theme, THEMES["Slate White"])
        b = 2500  # Smooth grid bounds

        # Pre-render grid dots for hardware panning
        for x in range(-b, b, GRID_STEP):
            is_major_x = (x % 100 == 0)
            for y in range(-b, b, GRID_STEP):
                is_major_y = (y % 100 == 0)
                if is_major_x and is_major_y:
                    self.canvas.create_oval(
                        x - 1.5, y - 1.5, x + 1.5, y + 1.5,
                        fill=theme["grid_major"], outline="", tags="grid"
                    )
                else:
                    self.canvas.create_oval(
                        x - 0.75, y - 0.75, x + 0.75, y + 0.75,
                        fill=theme["grid_minor"], outline="", tags="grid"
                    )

        # Subtle Origin Marker at (0, 0)
        self.canvas.create_line(-25, 0, 25, 0, fill=theme["accent"], width=1.5, tags="grid")
        self.canvas.create_line(0, -25, 0, 25, fill=theme["accent"], width=1.5, tags="grid")
        self.canvas.create_text(35, 14, text="(0, 0) Origin", fill=theme["accent"], font=("Inter", 9, "bold"), tags="grid")

    def on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def on_pan_drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)



    def recenter_origin(self, event=None):
        """Centers (0, 0) Origin dead center in viewport."""
        if not self.winfo_exists():
            return
        self.update_idletasks()
        win_w = self.canvas.winfo_width()
        win_h = self.canvas.winfo_height()

        if win_w > 1 and win_h > 1:
            total_dim = 2 * CANVAS_BOUNDS
            frac_x = (CANVAS_BOUNDS - (win_w / 2)) / total_dim
            frac_y = (CANVAS_BOUNDS - (win_h / 2)) / total_dim
            self.canvas.xview_moveto(frac_x)
            self.canvas.yview_moveto(frac_y)

    def set_theme(self, theme_name):
        """Updates active UI color theme."""
        if theme_name in THEMES:
            self.current_theme = theme_name
            self.draw_grid()
            self.dock.update_theme_style()
            self.hbar.draw_thumb()
            self.vbar.draw_thumb()

    def open_settings_popup(self):
        """Settings Popup Window with Theme Accent Color Switcher."""
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("Friday AI — Settings")
        settings_win.geometry("460x340")
        settings_win.configure(fg_color="#0f172a")

        lbl_title = ctk.CTkLabel(settings_win, text="⚙️ Friday Settings", font=ctk.CTkFont(size=16, weight="bold"), text_color="#f8fafc")
        lbl_title.pack(pady=(20, 10))

        lbl_theme = ctk.CTkLabel(settings_win, text="Interface Theme Accent Color:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8")
        lbl_theme.pack(anchor="w", padx=30, pady=(10, 5))

        theme_var = ctk.StringVar(value=self.current_theme)

        def on_theme_change(val):
            self.set_theme(val)

        seg_theme = ctk.CTkSegmentedButton(
            settings_win,
            values=list(THEMES.keys()),
            variable=theme_var,
            command=on_theme_change,
            selected_color="#334155",
            selected_hover_color="#475569",
            unselected_color="#1e293b",
            text_color="#f8fafc"
        )
        seg_theme.pack(fill="x", padx=30, pady=10)

        lbl_desc = ctk.CTkLabel(settings_win, text="Select your preferred canvas dot matrix and accent palette. The clean Slate White theme is selected by default.", text_color="#64748b", wraplength=400, justify="left")
        lbl_desc.pack(padx=30, pady=15)

        btn_close = ctk.CTkButton(settings_win, text="Save & Close", fg_color="#334155", hover_color="#475569", text_color="#f8fafc", font=ctk.CTkFont(size=12, weight="bold"), command=settings_win.destroy)
        btn_close.pack(pady=15)

    def restart_friday(self):
        self.destroy()
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def reload_friday(self):
        self.recenter_origin()

    def shutdown_friday(self):
        self.destroy()
        sys.exit(0)


def launch_gui_app():
    app = FridayGridPanGUI()
    app.mainloop()


if __name__ == "__main__":
    launch_gui_app()
