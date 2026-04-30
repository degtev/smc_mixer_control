import yaml
import mido
import mido.backends.rtmidi
import smc_mixer_control.windows_helpers as wh
from smc_mixer_control.windows_helpers import get_application_names
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem
import os
from os import listdir
from os.path import isfile, join, dirname, realpath, exists, abspath, expanduser

def chooser(prompt, choices):
    print(prompt)
    for i,choice in enumerate(choices):
        print(f"{i}) {choice}")
    
    while True:
        try:
            selection = int(input(":"))
        except (ValueError, TypeError) as e:
            pass
        else:
            if 0 <= selection < len(choices):
                return choices[selection]
        print("Bad input, try again.")

def match_dev(name, dev_list):
    if name is None:
        return None
    for dev in dev_list:
        if name.lower() in dev.lower():
            return dev
    return None

def static_path():
    import sys
    base = getattr(sys, '_MEIPASS', dirname(dirname(realpath(__file__))))
    return join(base, "static")

def custom_device_files():
    abs_home = abspath(expanduser("~"))
    app_dir = join(abs_home, ".smc_mixer_control")
    old_dir = join(abs_home, ".havomi")

    if not exists(app_dir) and exists(old_dir):
        print(f"Migrating config from {old_dir} to {app_dir}")
        try:
            import os
            os.rename(old_dir, app_dir)
        except Exception as e:
            print(f"Migration failed: {e}")
            app_dir = old_dir
    custom_dev = join(app_dir, "custom")
    if exists(custom_dev):
        print("Found custom files:")
        return [(f"custom:{x}",join(custom_dev, x)) for x in listdir(custom_dev) if x.endswith(".yaml")]
    else:
        print(f"{custom_dev} does not exist")
        return []

def find_connected_device(inputs, outputs):
    devices_path = join(static_path(),"devices")
    device_configs = [(x,join(devices_path, x)) for x in listdir(devices_path) if x.endswith(".yaml")]
    device_configs += custom_device_files()

    dev_matches = {}
    for config_filename,config_path in device_configs:
        with open(config_path, 'r', encoding='utf-8') as config_file:
            config = yaml.safe_load(config_file.read())
        conf_input = config.get("device_names",{}).get("windows",{}).get("input")
        conf_output = config.get("device_names",{}).get("windows",{}).get("output")
        input_match = match_dev(conf_input, inputs)
        output_match = match_dev(conf_output, outputs)
        if input_match and output_match:
            dev_matches[config_filename] = [config_path, input_match, output_match]
    
    if len(dev_matches.keys()) > 1:
        chosen_device = chooser("Multiple devices detected; select one:", list(dev_matches.keys()))
        path, input_dev, output_dev = dev_matches[chosen_device]
    elif len(dev_matches.keys()) == 0:
        chosen_device_name, chosen_device_path = chooser("No devices detected; select a config:", device_configs)
        path = chosen_device_path
        input_dev = chooser("Choose your input device", inputs)
        output_dev = chooser("Choose your output device", outputs)
    else:
        chosen_device = list(dev_matches.keys())[0]
        path, input_dev, output_dev = dev_matches[chosen_device]
    
    return path, input_dev, output_dev

def get_config():
    """
    Prompts the user on the command-line for a device config file and, if necessary, input and
    output devices if the entries in the device config file don't match any connected midi devices.
    """
    inputs = mido.get_input_names()
    outputs = mido.get_output_names()

    device_filename, input_dev, output_dev = find_connected_device(inputs, outputs)

    return {
        "input": input_dev,
        "output": output_dev,
        "device": device_filename,
    }

def load_icon():
    icon_path = join(static_path(), "images", "icon.ico")
    if exists(icon_path):
        return Image.open(icon_path)
    
    width = 64
    height = 64
    color1 = "red"
    color2 = "black"
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 2, 0, width, height // 2), fill=color2)
    dc.rectangle((0, height // 2, width // 2, height), fill=color2)

    return image

def create_image():
    width = 64
    height = 64
    color1 = "red"
    color2 = "black"
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 2, 0, width, height // 2),
        fill=color2)
    dc.rectangle(
        (0, height // 2, width // 2, height),
        fill=color2)

    return image

class AppMenuItemAction(object):
    def __init__(self, app_name, cid, app_state):
        self.app_name = app_name
        self.cid = cid
        self.app_state = app_state
    
    def __call__(self, arg1=None, arg2=None, arg3=None):
        self.app_state.event_queue.put(("interface", {"action": "assign", "app": self.app_name, "channel": self.cid}))

class AppMenu(object):
    def __init__(self, cid, app_state):
        self.cid = cid
        self.app_state = app_state
    
    def __call__(self, arg1=None, arg2=None, arg3=None):
        applications = self.app_state.application_names
        menu = []
        for an in applications:
            menu.append(MenuItem(an, AppMenuItemAction(an, self.cid, self.app_state)))
        return menu

class AddAppMenuItemAction(object):
    def __init__(self, app_name, cid, app_state):
        self.app_name = app_name
        self.cid = cid
        self.app_state = app_state
    
    def __call__(self, arg1=None, arg2=None, arg3=None):
        self.app_state.event_queue.put(("interface", {"action": "add_app", "app": self.app_name, "channel": self.cid}))

class AddAppMenu(object):
    def __init__(self, cid, app_state):
        self.cid = cid
        self.app_state = app_state
    
    def __call__(self, arg1=None, arg2=None, arg3=None):
        applications = self.app_state.application_names
        menu = []
        for an in applications:
            menu.append(MenuItem(an, AddAppMenuItemAction(an, self.cid, self.app_state)))
        return menu

class AnimationMenuItemAction(object):
    def __init__(self, mode, app_state):
        self.mode = mode
        self.app_state = app_state
    
    def __call__(self, arg1=None, arg2=None, arg3=None):
        self.app_state.event_queue.put(("interface", {"action": "set_animation", "mode": self.mode}))

class AnimationMenu(object):
    def __init__(self, app_state):
        self.app_state = app_state
    
    def __call__(self, arg1=None, arg2=None, arg3=None):
        modes = ["None", "Chase Forward", "Chase Backward", "Blink", "Knight Rider", "Random Pulse", "Fill Horizontal", "Fill Vertical", "Crawl Horizontal", "Crawl Vertical", "Equalizer"]
        menu = []
        for m in modes:
            menu.append(MenuItem(m, AnimationMenuItemAction(m, self.app_state), 
                                 checked=lambda item, mode=m: mode == self.app_state.animation_mode))
        return menu

class AnimationSpeedMenuItemAction(object):
    def __init__(self, speed_name, speed_val, app_state):
        self.speed_name = speed_name
        self.speed_val = speed_val
        self.app_state = app_state
    
    def __call__(self, arg1=None, arg2=None, arg3=None):
        self.app_state.event_queue.put(("interface", {"action": "set_animation_speed", "speed": self.speed_val, "name": self.speed_name}))

class AnimationSpeedMenu(object):
    def __init__(self, app_state):
        self.app_state = app_state
    
    def __call__(self, arg1=None, arg2=None, arg3=None):
        speeds = [
            ("Very Slow", 0.5),
            ("Slow", 0.75),
            ("Normal", 1.0),
            ("Fast", 1.5),
            ("Very Fast", 2.0),
            ("Insane", 4.0)
        ]
        menu = []
        current_speed = getattr(self.app_state, "animation_speed_name", "Normal")
        for name, val in speeds:
            menu.append(MenuItem(name, AnimationSpeedMenuItemAction(name, val, self.app_state),
                                 checked=lambda item, n=name: n == current_speed))
        return menu

class AssignMenuItem(object):
    def __init__(self, cid, app_state):
        self.cid = cid
        self.app_state = app_state

    def __call__(self, arg1=None, arg2=None, arg3=None):
        if self.cid < 8: label = f"Fader {self.cid + 1}"
        elif self.cid < 16: label = f"Btn 1.{self.cid - 7} (Mute)"
        elif self.cid < 24: label = f"Btn 2.{self.cid - 15} (Level)"
        elif self.cid < 32: label = f"Btn 3.{self.cid - 23} (---)"
        elif self.cid < 40: label = f"Btn 4.{self.cid - 31} (Status/Focus)"
        elif self.cid < 48: label = f"Knob {self.cid - 39}"
        else: label = f"Unknown {self.cid}"
        return f"Assign {label}"

class FaderMenuItem(object):
    def __init__(self, cid, app_state):
        self.cid = cid
        self.app_state = app_state

    def __call__(self, arg1=None, arg2=None, arg3=None):
        if self.cid < 8: label = f"Fader {self.cid + 1}"
        elif self.cid < 16: label = f"Btn 1.{self.cid - 7} (Mute)"
        elif self.cid < 24: label = f"Btn 2.{self.cid - 15} (Level)"
        elif self.cid < 32: label = f"Btn 3.{self.cid - 23} (---)"
        elif self.cid < 40: label = f"Btn 4.{self.cid - 31} (Status/Focus)"
        elif self.cid < 48: label = f"Knob {self.cid - 39}"
        else: label = f"Unknown {self.cid}"
        
        if self.app_state.channels.get(self.cid, {}).get("assigned"):
            app_name = self.app_state.channels[self.cid]["name"]
            return f"{label}: {app_name}"
        else:
            return label

class UnassignAction(object):
    def __init__(self, cid, app_state):
        self.cid = cid
        self.app_state = app_state

    def __call__(self, arg1=None, arg2=None, arg3=None):
        self.app_state.event_queue.put(("interface", {"action": "unassign", "channel": self.cid}))

class MenuItems(object):
    def __init__(self, app_state):
        self.app_state = app_state

    def __call__(self, arg1=None, arg2=None, arg3=None):
        mi = []
        
        mi.append(MenuItem("SMC Mixer Control", lambda: None, enabled=False))
        mi.append(MenuItem("---", lambda: None))

        faders_menu = []
        for i in range(8):
            if i < self.app_state.num_channels:
                faders_menu.append(MenuItem(FaderMenuItem(i, self.app_state), Menu(
                    MenuItem(AssignMenuItem(i, self.app_state), Menu(AppMenu(i, self.app_state))),
                    MenuItem("Add application...", Menu(AddAppMenu(i, self.app_state))),
                    MenuItem("Unassign", UnassignAction(i, self.app_state))
                )))
        mi.append(MenuItem("Faders", Menu(*faders_menu)))

        buttons_menu = []
        for i in range(8, 40):
            if i < self.app_state.num_channels:
                buttons_menu.append(MenuItem(FaderMenuItem(i, self.app_state), Menu(
                    MenuItem(AssignMenuItem(i, self.app_state), Menu(AppMenu(i, self.app_state))),
                    MenuItem("Add application...", Menu(AddAppMenu(i, self.app_state))),
                    MenuItem("Unassign", UnassignAction(i, self.app_state))
                )))
        mi.append(MenuItem("Buttons", Menu(*buttons_menu)))

        knobs_menu = []
        for i in range(40, 48):
            if i < self.app_state.num_channels:
                knobs_menu.append(MenuItem(FaderMenuItem(i, self.app_state), Menu(
                    MenuItem(AssignMenuItem(i, self.app_state), Menu(AppMenu(i, self.app_state))),
                    MenuItem("Add application...", Menu(AddAppMenu(i, self.app_state))),
                    MenuItem("Unassign", UnassignAction(i, self.app_state))
                )))
        mi.append(MenuItem("Knobs", Menu(*knobs_menu)))

        mi.append(MenuItem("---", lambda: None))
        
        visuals_menu = [
            MenuItem("Mode", Menu(AnimationMenu(self.app_state))),
            MenuItem("Speed", Menu(AnimationSpeedMenu(self.app_state)))
        ]
        mi.append(MenuItem("Visual Effects", Menu(*visuals_menu)))

        tools_menu = [
            MenuItem("Open Config Folder", lambda: os.startfile(os.path.join(os.path.abspath(os.path.expanduser("~")), ".smc_mixer_control"))),
            MenuItem("Refresh Apps", lambda: self.app_state.event_queue.put(("interface", {"action": "refresh_apps"})))
        ]
        mi.append(MenuItem("Tools", Menu(*tools_menu)))

        mi.append(MenuItem("---", lambda: None))
        mi.append(MenuItem("Quit", lambda : self.app_state.event_queue.put(("interface", {"action": "quit"}))))
        return mi

class AppState(object):
    def __init__(self, num_channels, event_queue):
        self.num_channels = num_channels
        self.event_queue = event_queue
        self.application_names = get_application_names()
        self.animation_mode = "Chase Forward"
        self.animation_speed_name = "Normal"
        self.gen_channels()
    
    def gen_channels(self):
        self.channels = {}
        for i in range(self.num_channels):
            self.channels[i] = {
                "assigned": False,
                "name": None,
            }
    def update(self, state):
        apps = state.get("apps", self.application_names)
        
        assignments_changed = False
        if state["num_channels"] != self.num_channels:
            assignments_changed = True
        else:
            for cid, info in state["channels"].items():
                old_info = self.channels.get(cid, {})
                if info.get("assigned") != old_info.get("assigned") or \
                   info.get("name") != old_info.get("name"):
                    assignments_changed = True
                    break
        
        updated = any([
            assignments_changed,
            apps != self.application_names,
            state.get("animation_mode") != self.animation_mode,
            state.get("animation_speed_name") != self.animation_speed_name
        ])
        
        if state.get("animation_mode"):
            self.animation_mode = state["animation_mode"]
        if state.get("animation_speed_name"):
            self.animation_speed_name = state["animation_speed_name"]
        
        self.num_channels = state["num_channels"]
        self.channels = state["channels"]
        self.application_names = apps
        return updated

def systray(event_queue, update_queue, num_channels):
    wh.com_init()
    app_state = AppState(num_channels, event_queue)
    menu_options = Menu(MenuItems(app_state))

    def run_loop(icon):
        icon.visible = True
        try:
            while True:
                try:
                    event_type, event = update_queue.get(timeout=1.0)
                except:
                    if not icon._running:
                        break
                    continue

                if event_type == "state":
                    if app_state.update(event):
                        print("Updating systray menu")
                        icon.update_menu()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            icon.stop()

    st = Icon("SMC Mixer Control", load_icon(), menu=menu_options,)
    st.run(setup=run_loop)
