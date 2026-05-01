import tkinter as tk
from tkinter import ttk, messagebox
import math
import smc_mixer_control.windows_helpers as wh
import os
import json
import ctypes
import mido
import yaml
import webbrowser

try:
    myappid = 'degtev.smc_mixer_control.gui.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except:
    pass

class MixerGUI:
    def __init__(self, event_queue, update_queue, num_channels):
        self.event_queue = event_queue
        self.update_queue = update_queue
        self.num_channels = num_channels
        
        self.root = tk.Tk()
        self.root.title("SMC Mixer Control - Dashboard")
        self.root.geometry("1100x650")
        self.root.configure(bg='#121212')
        self.root.overrideredirect(True)
        
        def set_appwindow():
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            
            self.root.withdraw()
            self.root.after(10, self.root.deiconify)
        
        self.root.after(10, set_appwindow)
        
        self._is_maximized = False
        self._old_geom = "1100x650+100+100"

        try:
            from PIL import Image, ImageTk
            icon_path = os.path.join(wh.static_path(), "images", "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
                self.icon_img = ImageTk.PhotoImage(Image.open(icon_path).resize((16, 16), Image.LANCZOS))
        except:
            self.icon_img = None
        
        self.channels_data = {}
        self.apps_list = []
        self.current_peaks = [0.0] * 8
        
        self.setup_styles()
        self.create_widgets()
        
    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Mixer.TFrame", background="#121212")
        style.configure("Channel.TFrame", background="#1e1e1e", relief="raised")
        
    def create_widgets(self):
        self.title_bar = tk.Frame(self.root, bg='#121212', height=30)
        self.title_bar.pack(fill='x', side='top')
        
        if self.icon_img:
            tk.Label(self.title_bar, image=self.icon_img, bg='#121212').pack(side='left', padx=(10, 5))
            
        tk.Label(self.title_bar, text="SMC Mixer Control - Dashboard", fg='#888888', bg='#121212', font=('Segoe UI', 9)).pack(side='left')
        
        close_btn = tk.Label(self.title_bar, text="✕", fg='#ffffff', bg='#121212', font=('Segoe UI', 10), width=4)
        close_btn.pack(side='right', fill='y')
        close_btn.bind("<Button-1>", lambda e: self.root.withdraw())
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg='#e81123'))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg='#121212'))
        
        min_btn = tk.Label(self.title_bar, text="—", fg='#ffffff', bg='#121212', font=('Segoe UI', 10), width=4)
        min_btn.pack(side='right', fill='y')
        min_btn.bind("<Button-1>", lambda e: self.minimize_window())
        min_btn.bind("<Enter>", lambda e: min_btn.config(bg='#333333'))
        min_btn.bind("<Leave>", lambda e: min_btn.config(bg='#121212'))
        
        self.title_bar.bind("<Button-1>", self.start_move)
        self.title_bar.bind("<B1-Motion>", self.do_move)
        
        self.main_frame = tk.Frame(self.root, bg='#121212', padx=20, pady=20)
        self.main_frame.pack(fill='both', expand=True)
        
        header = tk.Frame(self.main_frame, bg='#121212', height=40)
        header.pack(fill='x', side='top', pady=(0, 10))
        
        tk.Label(header, text="SMC Mixer Control - Dashboard", fg='#00a2ff', bg='#121212', font=('Segoe UI Bold', 16)).pack(side='left')
        
        settings_btn = tk.Label(header, text="⚙ Settings", fg='#666666', bg='#121212', font=('Segoe UI', 10), cursor="hand2")
        settings_btn.pack(side='right', padx=(10, 20))
        settings_btn.bind("<Button-1>", lambda e: self.open_settings())
        settings_btn.bind("<Enter>", lambda e: settings_btn.config(fg='#ffffff'))
        settings_btn.bind("<Leave>", lambda e: settings_btn.config(fg='#666666'))

        update_btn = tk.Label(header, text="↻ Check for Updates", fg='#666666', bg='#121212', font=('Segoe UI', 10), cursor="hand2")
        update_btn.pack(side='right', padx=10)
        update_btn.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/degtev/smc_mixer_control"))
        update_btn.bind("<Enter>", lambda e: update_btn.config(fg='#00a2ff'))
        update_btn.bind("<Leave>", lambda e: update_btn.config(fg='#666666'))
        
        self.mixer_frame = tk.Frame(self.main_frame, bg='#121212')
        self.mixer_frame.pack(fill='both', expand=True)
        
        self.channel_strips = []
        for i in range(8):
            strip = self.create_channel_strip(self.mixer_frame, i)
            strip['frame'].pack(side='left', padx=5, fill='y', expand=True)
            self.channel_strips.append(strip)

        self.settings_frame = tk.Frame(self.main_frame, bg='#1e1e1e', pady=10, highlightbackground="#333333", highlightthickness=1)
        self.settings_frame.pack(fill='x', pady=(20, 0))
        
        tk.Label(self.settings_frame, text="LED animation:", fg='#666666', bg='#1e1e1e', font=('Segoe UI Bold', 9)).pack(side='left', padx=(20, 10))
        
        modes = ["None", "Chase Forward", "Chase Backward", "Blink", "Knight Rider", "Random Pulse", "Fill Horizontal", "Fill Vertical", "Crawl Horizontal", "Crawl Vertical", "Equalizer"]
        self.anim_var = tk.StringVar(value="None")
        self.anim_combo = ttk.Combobox(self.settings_frame, textvariable=self.anim_var, values=modes, state="readonly", width=18)
        self.anim_combo.pack(side='left', padx=10)
        self.anim_combo.bind("<<ComboboxSelected>>", self.on_anim_change)
        
        self.led_canvas = tk.Canvas(self.settings_frame, width=120, height=40, bg='#1e1e1e', highlightthickness=0)
        self.led_canvas.pack(side='left', padx=20)
        self.led_circles = []
        for y in range(4):
            row = []
            for x in range(8):
                c = self.led_canvas.create_oval(x*15+2, y*10+2, x*15+10, y*10+8, fill='#333333', outline='')
                row.append(c)
            self.led_circles.append(row)
        
        tk.Label(self.settings_frame, text="Speed:", fg='#666666', bg='#1e1e1e', font=('Segoe UI Bold', 9)).pack(side='left', padx=(20, 10))
        
        speeds = ["Very Slow", "Slow", "Normal", "Fast", "Very Fast", "Insane"]
        self.speed_var = tk.StringVar(value="Normal")
        self.speed_combo = ttk.Combobox(self.settings_frame, textvariable=self.speed_var, values=speeds, state="readonly", width=10)
        self.speed_combo.pack(side='left')
        self.speed_combo.bind("<<ComboboxSelected>>", self.on_speed_change)

    def on_anim_change(self, event):
        self.event_queue.put(("interface", {"action": "set_animation", "mode": self.anim_var.get()}))

    def on_speed_change(self, event):
        speed_map = {"Very Slow": 0.5, "Slow": 0.75, "Normal": 1.0, "Fast": 1.5, "Very Fast": 2.0, "Insane": 4.0}
        val = speed_map.get(self.speed_var.get(), 1.0)
        self.event_queue.put(("interface", {"action": "set_animation_speed", "speed": val, "name": self.speed_var.get()}))

    def create_channel_strip(self, parent, index):
        frame = tk.Frame(parent, bg='#1e1e1e', width=120, highlightbackground="#333333", highlightthickness=1)
        
        tk.Label(frame, text=f"CH {index+1}", fg='#666666', bg='#1e1e1e', font=('Segoe UI Bold', 8)).pack(pady=5)
        
        knob_canvas = tk.Canvas(frame, width=80, height=80, bg='#1e1e1e', highlightthickness=0, cursor="hand2")
        knob_canvas.pack(pady=5)
        self.draw_knob(knob_canvas, 0)
        knob_canvas.bind("<Button-1>", lambda e, i=index: self.open_app_picker(40+i))
        
        controls_frame = tk.Frame(frame, bg='#1e1e1e', cursor="hand2")
        controls_frame.pack(pady=10, fill='x', padx=5)
        controls_frame.bind("<Button-1>", lambda e, i=index: self.open_app_picker(i))
        
        h = 180
        fader_canvas = tk.Canvas(controls_frame, width=40, height=h, bg='#1e1e1e', highlightthickness=0, cursor="hand2")
        fader_canvas.pack(side='left')
        self.draw_fader(fader_canvas, 0, height=h)
        fader_canvas.bind("<Button-1>", lambda e, i=index: self.open_app_picker(i))
        
        vu_canvas = tk.Canvas(controls_frame, width=10, height=h, bg='#1e1e1e', highlightthickness=0)
        vu_canvas.pack(side='left', padx=(2, 5))
        self.draw_vu(vu_canvas, 0, height=h)
        
        btn_frame = tk.Frame(controls_frame, bg='#1e1e1e', height=h, width=32)
        btn_frame.pack(side='left', fill='y', padx=(5, 0))
        btn_frame.pack_propagate(False) 
        
        buttons = []
        symbols = ["M", "S", "R", "▢"]
        for r in range(4):
            btn = tk.Canvas(btn_frame, width=26, height=26, bg='#1e1e1e', highlightthickness=0, cursor="hand2")
            btn.pack(side='top', expand=True)
            self.draw_button(btn, False, text=symbols[r])
            
            cid = 8 + (r * 8) + index
            btn.bind("<Button-1>", lambda e, ci=cid: self.open_button_config(ci))
            buttons.append({"canvas": btn, "symbol": symbols[r]})
        
        app_label = tk.Label(
            frame, 
            text="Unassigned", 
            fg='#ffffff', 
            bg='#2d2d2d', 
            font=('Segoe UI', 8),
            width=15,
            cursor="hand2"
        )
        app_label.pack(pady=(0, 10), padx=5)
        app_label.bind("<Button-1>", lambda e, i=index: self.open_app_picker(i))
        
        return {
            "frame": frame,
            "knob": knob_canvas,
            "fader": fader_canvas,
            "vu": vu_canvas,
            "label": app_label,
            "buttons": buttons
        }

    def draw_knob(self, canvas, value):
        canvas.delete("all")
        cx, cy = 40, 40
        r = 25
        canvas.create_oval(cx-r+2, cy-r+2, cx+r+2, cy+r+2, fill='#000000', outline='')
        canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill='#2d2d2d', outline='#444444', width=2)
        start_angle = 135
        extent = (value / 127.0) * 270
        canvas.create_arc(cx-r+5, cy-r+5, cx+r-5, cy+r-5, start=-start_angle, extent=-extent, outline='#00a2ff', width=3, style='arc')
        angle = math.radians(135 + extent)
        ix = cx + math.cos(angle) * (r-8)
        iy = cy + math.sin(angle) * (r-8)
        canvas.create_line(cx, cy, ix, iy, fill='#ffffff', width=2)

    def draw_fader(self, canvas, value, height=180):
        canvas.delete("all")
        w = 40
        track_h = height - 20
        canvas.create_rectangle(18, 10, 22, height-10, fill='#000000', outline='#333333')

        for i in range(6):
            y = 10 + i * (track_h / 5)
            canvas.create_line(10, y, 15, y, fill='#444444')
            canvas.create_line(25, y, 30, y, fill='#444444')
            
        pos = (height-10) - (value / 127.0) * track_h
        canvas.create_rectangle(10, pos-6, 32, pos+10, fill='#000000', outline='')
        canvas.create_rectangle(8, pos-8, 30, pos+8, fill='#3a3a3a', outline='#666666', width=1)
        canvas.create_line(8, pos, 30, pos, fill='#00a2ff', width=2)

    def draw_vu(self, canvas, peak, height=180):
        canvas.delete("all")
        track_h = height - 20
        canvas.create_rectangle(2, 10, 8, height-10, fill='#000000', outline='#333333')

        scaled_peak = peak ** 0.6
        
        num_segments = 15
        for i in range(num_segments):
            y_bot = (height-10) - (i * track_h / num_segments)
            y_top = (height-10) - ((i+1) * track_h / num_segments)
            
            ratio = (i + 1) / num_segments
            if ratio < 0.6: color = '#005500' if ratio > scaled_peak else '#00ff00'
            elif ratio < 0.85: color = '#555500' if ratio > scaled_peak else '#ffff00'
            else: color = '#550000' if ratio > scaled_peak else '#ff0000'
            
            canvas.create_rectangle(3, y_top+1, 7, y_bot-1, fill=color, outline='')

    def draw_button(self, canvas, active, color='#00a2ff', text=""):
        canvas.delete("all")
        bg_color = '#2d2d2d'
        border_color = color if active else '#444444'
        glow_color = color if active else '#2d2d2d'
        
        canvas.create_rectangle(2, 2, 24, 24, fill=bg_color, outline=border_color, width=1)
        if active:
            canvas.create_rectangle(4, 4, 22, 22, fill=glow_color, outline='')
            canvas.create_text(13, 13, text=text, fill='#ffffff', font=('Segoe UI Bold', 8))
        else:
            canvas.create_text(13, 13, text=text, fill='#666666', font=('Segoe UI Bold', 8))

    def open_app_picker(self, cid):
        picker = tk.Toplevel(self.root)
        picker.title(f"Select Application (CID {cid})")
        picker.geometry("400x500")
        picker.configure(bg='#1e1e1e')
        self.center_window(picker)
        picker.transient(self.root)
        picker.grab_set()
        
        tk.Label(picker, text="ASSIGN APPLICATION", fg='#00a2ff', bg='#1e1e1e', font=('Segoe UI Bold', 12)).pack(pady=15)
        
        search_var = tk.StringVar()
        search_entry = tk.Entry(picker, textvariable=search_var, bg='#121212', fg='#ffffff', insertbackground='#ffffff', relief='flat', font=('Segoe UI', 10))
        search_entry.pack(fill='x', padx=30, pady=5)
        search_entry.insert(0, "Search...")
        search_entry.bind("<FocusIn>", lambda e: search_entry.delete(0, tk.END) if search_entry.get() == "Search..." else None)

        list_frame = tk.Frame(picker, bg='#1e1e1e')
        list_frame.pack(fill='both', expand=True, padx=30, pady=5)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        listbox = tk.Listbox(list_frame, bg='#121212', fg='#ffffff', selectbackground='#00a2ff', relief='flat', 
            highlightthickness=0, font=('Segoe UI', 9), yscrollcommand=scrollbar.set, selectmode=tk.EXTENDED)
        listbox.pack(fill='both', expand=True)
        scrollbar.config(command=listbox.yview)
        
        all_apps = sorted(list(set(["Master", "Unused"] + self.apps_list)))
        if "---" in all_apps: all_apps.remove("---")
        all_apps = ["Master", "Unused", "---"] + all_apps
        
        def update_list(*args):
            search = search_var.get().lower()
            if search == "search...": search = ""
            listbox.delete(0, tk.END)
            for app in all_apps:
                if search in app.lower():
                    listbox.insert(tk.END, app)

        search_var.trace("w", update_list)
        update_list()

        def on_select(event=None):
            selections = [listbox.get(i) for i in listbox.curselection()]
            if not selections:
                selections = [listbox.get(tk.ACTIVE)]
            valid = [s for s in selections if s != "---"]
            if valid:
                app_name = valid[0]
                self.event_queue.put(("interface", {"action": "assign", "app": app_name, "channel": cid}))
                
                for s in valid[1:]:
                    if s not in ["Master", "Unused"]:
                        self.event_queue.put(("interface", {"action": "add_app", "app": s, "channel": cid}))
                picker.destroy()

        listbox.bind("<Double-Button-1>", on_select)
        
        btn_frame = tk.Frame(picker, bg='#1e1e1e')
        btn_frame.pack(fill='x', pady=20)
        tk.Button(btn_frame, text="CANCEL", command=picker.destroy, bg='#333333', fg='white', relief='flat', padx=20).pack(side='right', padx=20)
        tk.Button(btn_frame, text="SAVE", command=on_select, bg='#00a2ff', fg='white', relief='flat', padx=30).pack(side='right')

    def open_button_config(self, cid):
        config_win = tk.Toplevel(self.root)
        config_win.title(f"Button CID {cid} Configuration")
        config_win.geometry("400x550")
        config_win.configure(bg='#1e1e1e')
        self.center_window(config_win)
        config_win.transient(self.root)
        config_win.grab_set()
        
        ch_data = self.channels_data.get(cid, {})
        current_func = ch_data.get("funcs", ["none"])[0]
        current_assigned = ch_data.get("target_apps", [])
        
        tk.Label(config_win, text="BUTTON CONFIGURATION", fg='#00a2ff', bg='#1e1e1e', font=('Segoe UI Bold', 12)).pack(pady=15)
        
        tk.Label(config_win, text="1. SELECT FUNCTION", fg='#888888', bg='#1e1e1e', font=('Segoe UI Bold', 9)).pack(pady=(10, 5), anchor='w', padx=30)
        funcs = ["mute", "status", "meter", "select", "none"]
        func_var = tk.StringVar(value=current_func)
        func_frame = tk.Frame(config_win, bg='#1e1e1e')
        func_frame.pack(fill='x', padx=30)
        for f in funcs:
            tk.Radiobutton(func_frame, text=f.capitalize(), variable=func_var, value=f,
                bg='#1e1e1e', fg='#ffffff', selectcolor='#333333',
                activebackground='#1e1e1e', activeforeground='#00a2ff', font=('Segoe UI', 9)
            ).pack(side='left', expand=True)

        tk.Label(config_win, text="2. SELECT APPLICATION", fg='#888888', bg='#1e1e1e', font=('Segoe UI Bold', 9)).pack(pady=(20, 5), anchor='w', padx=30)
        search_var = tk.StringVar()
        search_entry = tk.Entry(config_win, textvariable=search_var, bg='#121212', fg='#ffffff', insertbackground='#ffffff', relief='flat', font=('Segoe UI', 10))
        search_entry.pack(fill='x', padx=30, pady=5)
        search_entry.insert(0, "Search...")
        search_entry.bind("<FocusIn>", lambda e: search_entry.delete(0, tk.END) if search_entry.get() == "Search..." else None)

        list_frame = tk.Frame(config_win, bg='#1e1e1e')
        list_frame.pack(fill='both', expand=True, padx=30, pady=5)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        app_listbox = tk.Listbox(list_frame, bg='#121212', fg='#ffffff', selectbackground='#00a2ff', relief='flat', 
            highlightthickness=0, font=('Segoe UI', 9), yscrollcommand=scrollbar.set, selectmode=tk.EXTENDED)
        app_listbox.pack(fill='both', expand=True)
        scrollbar.config(command=app_listbox.yview)
        
        all_apps = sorted(list(set(["Master", "Unused"] + self.apps_list + current_assigned)))
        if "---" in all_apps: all_apps.remove("---")
        all_apps = ["Master", "Unused", "---"] + [c for c in all_apps if c not in ["Master", "Unused"]]
        
        def update_list(*args):
            search = search_var.get().lower()
            if search == "search...": search = ""
            app_listbox.delete(0, tk.END)
            for app in all_apps:
                if search in app.lower():
                    app_listbox.insert(tk.END, app)
                    if app in current_assigned:
                        app_listbox.select_set(tk.END)

        search_var.trace("w", update_list)
        update_list()
        
        def on_save():
            func = func_var.get()
            selections = [app_listbox.get(i) for i in app_listbox.curselection()]
            if not selections: selections = [app_listbox.get(tk.ACTIVE)]
            
            self.event_queue.put(("interface", {"action": "assign", "app": selections[0], "channel": cid}))
            for s in selections[1:]:
                if s not in ["Master", "Unused"]:
                    self.event_queue.put(("interface", {"action": "add_app", "app": s, "channel": cid}))
            self.event_queue.put(("interface", {"action": "assign_func", "channel": cid, "type": "button", "func": func}))
            config_win.destroy()
            
        tk.Button(config_win, text="SAVE", command=on_save, bg='#00a2ff', fg='white', relief='flat', font=('Segoe UI Bold', 10), pady=10).pack(fill='x', padx=30, pady=20)

    def get_config_path(self):
        abs_home = os.path.abspath(os.path.expanduser("~"))
        app_dir = os.path.join(abs_home, ".smc_mixer_control")
        if not os.path.exists(app_dir): os.makedirs(app_dir)
        return os.path.join(app_dir, "midi_config.json")

    def save_midi_config(self, config):
        with open(self.get_config_path(), 'w') as f:
            json.dump(config, f)

    def load_midi_config(self):
        path = self.get_config_path()
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Device Settings")
        settings_win.geometry("500x450")
        settings_win.configure(bg='#1e1e1e')
        settings_win.transient(self.root)
        settings_win.grab_set()
        self.center_window(settings_win)

        current_config = self.load_midi_config()

        tk.Label(settings_win, text="DEVICE SETTINGS", fg='#00a2ff', bg='#1e1e1e', font=('Segoe UI Bold', 12)).pack(pady=20)

        tk.Label(settings_win, text="MIDI INPUT:", fg='#888888', bg='#1e1e1e', font=('Segoe UI Bold', 9)).pack(padx=20, anchor='w')
        input_names = mido.get_input_names()
        in_var = tk.StringVar(value=current_config.get('input', ''))
        in_combo = ttk.Combobox(settings_win, textvariable=in_var, values=input_names, state="readonly", width=50)
        in_combo.pack(padx=20, pady=(5, 15))

        tk.Label(settings_win, text="MIDI OUTPUT:", fg='#888888', bg='#1e1e1e', font=('Segoe UI Bold', 9)).pack(padx=20, anchor='w')
        output_names = mido.get_output_names()
        out_var = tk.StringVar(value=current_config.get('output', ''))
        out_combo = ttk.Combobox(settings_win, textvariable=out_var, values=output_names, state="readonly", width=50)
        out_combo.pack(padx=20, pady=(5, 15))

        tk.Label(settings_win, text="HARDWARE PROFILE:", fg='#888888', bg='#1e1e1e', font=('Segoe UI Bold', 9)).pack(padx=20, anchor='w')
        
        devices_path = os.path.join(wh.static_path(), "devices")
        device_configs = [x for x in os.listdir(devices_path) if x.endswith(".yaml")]
        
        abs_home = os.path.abspath(os.path.expanduser("~"))
        custom_path = os.path.join(abs_home, ".smc_mixer_control", "custom")
        if os.path.exists(custom_path):
            device_configs += [f"custom/{x}" for x in os.listdir(custom_path) if x.endswith(".yaml")]

        conf_var = tk.StringVar(value=current_config.get('profile', ''))
        conf_combo = ttk.Combobox(settings_win, textvariable=conf_var, values=device_configs, state="readonly", width=50)
        conf_combo.pack(padx=20, pady=(5, 20))

        def on_save():
            config = {
                'input': in_var.get(),
                'output': out_var.get(),
                'profile': conf_var.get()
            }
            self.save_midi_config(config)
            messagebox.showinfo("Settings Saved", "Settings saved successfully!\nPlease restart the application to apply changes.")
            settings_win.destroy()

        tk.Button(settings_win, text="SAVE CONFIGURATION", command=on_save, bg='#00a2ff', fg='white', relief='flat', font=('Segoe UI Bold', 10), pady=10).pack(fill='x', padx=50, pady=20)

    def center_window(self, win):
        win.update_idletasks()
        width = win.winfo_width()
        height = win.winfo_height()
        x = (win.winfo_screenwidth() // 2) - (width // 2)
        y = (win.winfo_screenheight() // 2) - (height // 2)
        win.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        if not self._is_maximized:
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")

    def toggle_maximize(self, event=None):
        if self._is_maximized:
            self.root.geometry(self._old_geom)
            self._is_maximized = False
        else:
            self._old_geom = self.root.geometry()
            self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
            self._is_maximized = True

    def minimize_window(self):
        self.root.update_idletasks()
        self.root.state('withdrawn')
        self.root.overrideredirect(False)
        self.root.iconify()
        
        def on_map(event):
            self.root.overrideredirect(True)
            self.root.unbind("<Map>")
        self.root.bind("<Map>", on_map)

    def update_state(self):
        try:
            while not self.update_queue.empty():
                msg_type, data = self.update_queue.get_nowait()
                if msg_type == "state":
                    self.channels_data = data['channels']
                    for i in range(8):
                        if i in self.channels_data:
                            ch = self.channels_data[i]
                            strip = self.channel_strips[i]
                            
                            name = ch['name'] if ch['assigned'] else "Unassigned"
                            if name.endswith(".exe"): name = name[:-4]
                            strip['label'].config(text=name, fg='#00a2ff' if ch['assigned'] else '#ffffff')
                            
                            self.draw_fader(strip['fader'], ch.get('level', 0))
                            
                            knob_ch = self.channels_data.get(40+i, {})
                            self.draw_knob(strip['knob'], knob_ch.get('level', 0))
                            
                            new_peak = ch.get('peak', 0.0)
                            if new_peak > self.current_peaks[i]:
                                self.current_peaks[i] = new_peak
                            else:
                                self.current_peaks[i] *= 0.85
                                if self.current_peaks[i] < 0.01: self.current_peaks[i] = 0
                                
                            self.draw_vu(strip['vu'], self.current_peaks[i])
                            
                            for b_idx in range(4):
                                b_info = strip['buttons'][b_idx]
                                b_cid = 8 + (b_idx * 8) + i
                                b_data = self.channels_data.get(b_cid, {})
                                b_funcs = b_data.get("funcs", [])
                                
                                is_active = False
                                b_color = '#ffffff'
                                
                                if b_funcs:
                                    f = b_funcs[0]
                                    if b_idx == 0:
                                        is_active = ch.get('mute', False)
                                        b_color = '#ff8c00'
                                    elif b_idx == 1:
                                        is_active = ch.get('peak', 0) > 0.01
                                        b_color = '#00a2ff'
                                    elif b_idx == 2:
                                        is_active = False 
                                        b_color = '#444444'
                                    elif b_idx == 3:
                                        is_active = ch.get('has_sessions', False)
                                        b_color = '#ffffff'
                                
                                self.draw_button(b_info['canvas'], is_active, color=b_color, text=b_info['symbol'])
                    
                    if data.get("animation_mode"):
                        self.anim_var.set(data["animation_mode"])
                    if data.get("animation_speed_name"):
                        self.speed_var.set(data["animation_speed_name"])
                elif msg_type == "led_states":

                    for i, val in enumerate(data):
                        x = i % 8
                        y = i // 8
                        b = int((val / 127.0) * 200) + 55 if val > 0 else 51
                        color = f'#{b:02x}{b:02x}{b:02x}' if val > 0 else '#333333'

                        if val > 0:
                            ratio = val / 127.0
                            r = int(0 * ratio + 30 * (1-ratio))
                            g = int(162 * ratio + 30 * (1-ratio))
                            b = int(255 * ratio + 30 * (1-ratio))
                            color = f'#{r:02x}{g:02x}{b:02x}'
                        
                        self.led_canvas.itemconfig(self.led_circles[y][x], fill=color)
                elif msg_type == "show":
                    self.root.deiconify()
                    self.root.lift()
                    self.root.focus_force()
                elif msg_type == "apps":
                    self.apps_list = data
        except:
            pass
        self.root.after(100, self.update_state)

    def run(self):
        try:
            self.update_state()
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

def start(event_queue, update_queue, num_channels):
    gui = MixerGUI(event_queue, update_queue, num_channels)
    gui.run()
