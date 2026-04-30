from collections import namedtuple
import yaml
import os
import smc_mixer_control.windows_helpers as wh
import mido
import mido.backends.rtmidi
from smc_mixer_control.target import MultiTarget

MapEntry = namedtuple("MapEntry",["control", "channel"])

class ChannelMap(object):
    """
    The ChannelMap is the primary means by which we quickly look up incoming midi events
    to see if we "care" about them. This lookup needs to be very fast, otherwise we risk
    slowing down handling of important events downstream.
    """
    def __init__(self, channels, device_id):
        self.channels = {channel.cid:channel for channel in channels}
        self.cmap = {}
        self.device_id = device_id
        self.animation_mode = "Chase Forward"
        self.animation_speed = 1.0
        self.animation_speed_name = "Normal"
        self.build_map()

    def build_map(self):
        for channel in self.channels.values():
            for control in channel.dev_binding.controls:
                if control.type not in ["meter", "level"]:
                    self.cmap[f"{control.midi_type}:{control.midi_id}"] = MapEntry(control=control, channel=channel)

    def lookup(self, msg):
        if msg.type == "control_change":
            key = f"{msg.type}:{msg.control}"
            value = msg.value
        elif msg.type == "note_on":
            key = f"{msg.type}:{msg.note}"
            value = msg.velocity
        elif msg.type == "note_off":
            key = f"note_on:{msg.note}"
            value = 0
        elif msg.type == "pitchwheel":
            key = f"{msg.type}:{msg.channel}"
            value = msg.pitch
        else:
            key = None
            value = None
        
        return self.cmap.get(key), value
    
    def last(self):
        return self.channels[max(self.channels.keys())]

    def file_path(self, filename):
        abs_home = os.path.abspath(os.path.expanduser("~"))
        app_dir = os.path.join(abs_home, ".smc_mixer_control")
        old_dir = os.path.join(abs_home, ".havomi")

        if not os.path.exists(app_dir) and os.path.exists(old_dir):
            print(f"Migrating config from {old_dir} to {app_dir}")
            try:
                os.rename(old_dir, app_dir)
            except Exception as e:
                print(f"Migration failed: {e}")
                app_dir = old_dir

        if not os.path.exists(app_dir):
            print(f"Directory {app_dir} doesn't exist; creating.")
            os.mkdir(app_dir)
        device_dir = os.path.join(app_dir, self.device_id)
        if not os.path.exists(device_dir):
            print(f"Directory {device_dir} doesn't exist; creating.")
            os.mkdir(device_dir)
        return os.path.join(device_dir, filename)

    def save(self):
        channels_data = {}
        for cid, channel in self.channels.items():
            if channel is not None and channel.target is not None:
                if isinstance(channel.target, MultiTarget):
                    names = [t.name for t in channel.target.targets]
                else:
                    names = [channel.target.name]
                channels_data[cid] = [names, channel.color]
        
        data = {
            "channels": channels_data,
            "animation_mode": self.animation_mode,
            "animation_speed": self.animation_speed,
            "animation_speed_name": self.animation_speed_name
        }

        with open(self.file_path("config.yaml"), "w") as config_file:
            yaml.dump(data, config_file)
    
    def load(self):
        filename = self.file_path("config.yaml")
        if os.path.exists(filename):
            print(f"Found config file: {filename}")
            with open(filename) as config_file:
                raw_config = config_file.read()
                config = yaml.safe_load(raw_config)
            
            self.animation_mode = config.get("animation_mode", "Chase Forward")
            self.animation_speed = config.get("animation_speed", 1.0)
            self.animation_speed_name = config.get("animation_speed_name", "Normal")

            for cid, chan_conf in config["channels"].items():
                if cid in self.channels:
                    if isinstance(chan_conf[0], list):
                        names, color = chan_conf
                    else:
                        names, color = [chan_conf[0]], chan_conf[1]
                        
                    for i, name in enumerate(names):
                        app_def = wh.get_app_def_from_name(name) or wh.AppDef(name, color, [])
                        if i == 0:
                            self.channels[cid].set_target_from_app_def(app_def)
                        else:
                            self.channels[cid].add_target_from_app_def(app_def)
            return True
        else:
            print(f"No config file found at {filename}; skipping load.")
            return False
    
    def get_state(self):
        state = {
            "num_channels": len(self.channels.keys()),
            "channels": {},
            "animation_mode": self.animation_mode,
            "animation_speed_name": self.animation_speed_name
        }
        for c in self.channels.values():
            funcs = list(set(ctrl.func for ctrl in c.dev_binding.controls))
            state["channels"][c.cid] = {
                "assigned": bool(c.target),
                "name": c.name,
                "mute": c.mute,
                "peak": c.peak,
                "funcs": funcs
            }
        return state

class SharedMap(object):
    def __init__(self, shared):
        self.smap = {}
        self.build_map(shared)

    def build_map(self, shared):
        for control in shared:
            if control.type not in ["meter", "level"]:
                self.smap[f"{control.midi_type}:{control.midi_id}"] = control

    def lookup(self, msg):
        if msg.type == "control_change":
            key = f"{msg.type}:{msg.control}"
            value = msg.value
        elif msg.type == "note_on":
            key = f"{msg.type}:{msg.note}"
            value = msg.velocity
        elif msg.type == "pitchwheel":
            key = f"{msg.type}:{msg.channel}"
            value = msg.pitch
        else:
            key = None
            value = None
        
        return self.smap.get(key), value

    def light(self, dev):
        for c in self.smap.values():
            if c and c.feedback:
                value = c.up_value 

                kwargs = {
                    c.midi_id_field: c.midi_id,
                    c.midi_value_field: value
                }
                dev.out_port.send(mido.Message(c.midi_type,**kwargs))
