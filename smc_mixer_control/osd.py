import tkinter as tk
from tkinter import ttk
import time
import win32gui
import win32con
import ctypes

class VolumeOSD:
    def __init__(self, queue):
        self.queue = queue
        self.root = None
        self.visible = False
        self.fade_timer = None
        self.alpha = 0.0
        self.target_alpha = 0.95
        self.color_active = '#00a2ff'
        self.color_mute = '#ff5555'
        self.color_bg = '#444444'
        
    def setup_ui(self):
        self.root = tk.Tk()
        self.root.title("SMC OSD")
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.0)
        self.root.overrideredirect(True)
        
        self.root.update()
        hwnd = self.root.winfo_id()
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        style |= win32con.WS_EX_TOOLWINDOW
        style |= win32con.WS_EX_TOPMOST
        style |= win32con.WS_EX_NOACTIVATE
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

        width = 240
        height = 65
        x = 20
        y = 20
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        self.outer_frame = tk.Frame(self.root, bg='#2d2d2d')
        self.outer_frame.pack(fill='both', expand=True)
        
        self.frame = tk.Frame(self.outer_frame, bg='#1e1e1e')
        self.frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        self.header_frame = tk.Frame(self.frame, bg='#1e1e1e')
        self.header_frame.pack(fill='x', padx=8, pady=(5, 0))
        
        self.app_name_label = tk.Label(
            self.header_frame, 
            text="Application", 
            fg='#ffffff', 
            bg='#1e1e1e', 
            font=('Segoe UI Semibold', 10),
            justify='left',
            wraplength=180 
        )
        self.app_name_label.pack(side='left', anchor='nw', pady=(2, 0))
        
        self.mute_label = tk.Label(
            self.header_frame,
            text="",
            fg='#ff5555',
            bg='#1e1e1e',
            font=('Segoe UI Bold', 9)
        )
        self.mute_label.pack(side='right')
        
        self.progress_container = tk.Frame(self.frame, bg='#1e1e1e')
        self.progress_container.pack(fill='x', padx=8, pady=(0, 5))
        
        self.canvas = tk.Canvas(
            self.progress_container, 
            width=170,
            height=4, 
            bg='#333333', 
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(side='left', pady=6)
        
        self.progress_bg = self.canvas.create_rectangle(0, 0, 170, 4, fill=self.color_bg, outline='')
        self.progress_bar = self.canvas.create_rectangle(0, 0, 0, 4, fill=self.color_active, outline='')
        
        self.volume_label = tk.Label(
            self.progress_container, 
            text="0%", 
            fg='#cccccc', 
            bg='#1e1e1e', 
            font=('Segoe UI', 8),
            width=5
        )
        self.volume_label.pack(side='right', padx=(10, 0))

    def update_osd(self, app_name, volume, mute):
        self.app_name_label.config(text=app_name)
        
        percent = int((volume / 127.0) * 100)
        self.volume_label.config(text=f"{percent}%")

        if mute:
            self.mute_label.config(text="MUTED")
        else:
            self.mute_label.config(text="")
            
        canvas_width = 170
        target_width = (volume / 127.0) * canvas_width
        
        self.canvas.coords(self.progress_bg, 0, 0, canvas_width, 4)
        self.canvas.coords(self.progress_bar, 0, 0, target_width, 4)
        self.canvas.itemconfig(self.progress_bar, fill=self.color_active)
        self.canvas.tag_raise(self.progress_bar)
        
        self.show()

    def show(self):
        if self.fade_timer:
            self.root.after_cancel(self.fade_timer)
        
        self.visible = True
        self.alpha = self.target_alpha
        self.root.attributes('-alpha', self.alpha)
        
        self.root.lift()
        self.root.attributes('-topmost', True)
        
        hwnd = self.root.winfo_id()
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
        
        self.fade_timer = self.root.after(2500, self.start_fade)

    def start_fade(self):
        if self.alpha > 0:
            self.alpha -= 0.05
            if self.alpha < 0: self.alpha = 0
            self.root.attributes('-alpha', self.alpha)
            self.fade_timer = self.root.after(20, self.start_fade)
        else:
            self.visible = False
            self.fade_timer = None

    def check_queue(self):
        try:
            while not self.queue.empty():
                msg_type, data = self.queue.get_nowait()
                if msg_type == "update":
                    self.update_osd(data['name'], data['volume'], data['mute'])
                elif msg_type == "quit":
                    self.root.destroy()
                    return
        except Exception:
            pass
        self.root.after(50, self.check_queue)

    def run(self):
        try:
            self.setup_ui()
            self.check_queue()
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"OSD Error: {e}")

def start(queue):
    osd = VolumeOSD(queue)
    osd.run()
