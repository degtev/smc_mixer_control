import mido
import mido.backends.rtmidi
from dataclasses import dataclass

from smc_mixer_control.device import DeviceChannel
from smc_mixer_control.target import ApplicationVolume, DeviceVolume, SystemSoundsVolume, Target, MultiTarget
from smc_mixer_control.controls import Button, Fader
from smc_mixer_control.scribble import scribble
import smc_mixer_control.windows_helpers as wh

@dataclass
class Channel:
    """
    The Channel is the virtual object that binds a DeviceChannel to a Target. Channels and
    DeviceChannels are distinct because we want a stored channel config to be portable betwween
    devices.

    cid:         Channel ID
    name:        Display name
    level:       Current volume level, 0-127
    color:       RGB+CYM+White+Black
    dev_binding: Channel in the device config
    target:      Target application or device
    """
    cid: int
    name: str 
    level: int
    mute: bool
    color: str
    dev_binding: DeviceChannel
    target: Target
    touch_lock: bool = False
    peak: float = 0.0

    def update_display(self, dev, fader=False, idle_brightness=None):
        self.update_scribble(dev)
        self.update_level(dev)
        self.update_meter(dev)
        self.update_leds(dev, idle_brightness)
        if fader:
            self.update_fader(dev)

    def update_leds(self, dev, idle_brightness=None):
        """
        Generic method to update all LEDs on the channel, including those with no specific function.
        """
        for c in self.dev_binding.controls:
            if not c.feedback or not isinstance(c, Button):
                continue
            
            value = None
            if self.target:
                if c.func == "mute":
                    value = c.down_value if self.mute else c.up_value
                elif c.func == "status":
                    if type(self.target) == ApplicationVolume:
                        value = c.down_value if (len(self.target.sessions) > 0) else c.up_value
                    else:
                        value = c.down_value
                elif c.func == "meter":
                    sensitivity_peak = self.peak ** 0.7
                    value = int(sensitivity_peak * 127)
                elif c.func == "select":
                    value = c.down_value
                else:
                    value = c.up_value
            elif idle_brightness is not None:
                value = idle_brightness
            else:
                value = c.up_value

            if value is not None:
                if value > 127: value = 127
                kwargs = {
                    c.midi_id_field: c.midi_id,
                    c.midi_value_field: value
                }
                dev.out_port.send(mido.Message(c.midi_type,**kwargs))

    def update_mute(self, dev, idle_brightness=None):
        c = self.dev_binding.find_control("mute")
        if c and c.feedback:
            if self.target:
                value = c.down_value if self.mute else c.up_value
            elif idle_brightness is not None:
                value = idle_brightness
            else:
                value = c.up_value

            kwargs = {
                c.midi_id_field: c.midi_id,
                c.midi_value_field: value
            }
            dev.out_port.send(mido.Message(c.midi_type,**kwargs))

    def update_status_led(self, dev, idle_brightness=None):
        c = self.dev_binding.find_control("status")
        if c and c.feedback:
            if self.target and type(self.target) == ApplicationVolume:
                value = c.down_value if (len(self.target.sessions) > 0) else c.up_value
            elif self.target and type(self.target) == DeviceVolume:
                value = c.down_value
            elif idle_brightness is not None:
                value = idle_brightness
            else:
                value = c.up_value

            kwargs = {
                c.midi_id_field: c.midi_id,
                c.midi_value_field: value
            }
            dev.out_port.send(mido.Message(c.midi_type,**kwargs))

    def update_meter_led(self, dev, idle_brightness=None):
        c = self.dev_binding.find_control("meter")
        if c and c.feedback:
            if self.target:
                sensitivity_peak = self.peak ** 0.7
                value = int(sensitivity_peak * 127)
            elif idle_brightness is not None:
                value = idle_brightness
            else:
                value = 0

            if value > 127: value = 127
            
            kwargs = {
                c.midi_id_field: c.midi_id,
                c.midi_value_field: value
            }
            dev.out_port.send(mido.Message(c.midi_type,**kwargs))

    def update_select(self, dev, idle_brightness=None):
        c = self.dev_binding.find_control("select")
        if c and c.feedback:
            if self.target:
                if type(self.target) == ApplicationVolume:
                    value = c.down_value if (len(self.target.sessions) > 0) else c.up_value
                elif type(self.target) == DeviceVolume:
                    value = c.down_value
                else:
                    value = c.up_value
            elif idle_brightness is not None:
                value = idle_brightness
            else:
                value = c.up_value
            kwargs = {
                c.midi_id_field: c.midi_id,
                c.midi_value_field: value
            }
            dev.out_port.send(mido.Message(c.midi_type,**kwargs))

    def update_scribble(self, dev):
        """
        Returns a sysex message to update a scribble strip be sent via midi
        """
        if dev.scribble:
            dev.out_port.send(scribble(self.cid, color=self.color, top=self.name, bottom=self.level, inv_bot=True))

    def update_fader(self, dev):
        """
        Returns a midi message to update volume position
        """
        if self.touch_lock:
            return

        d = self.dev_binding
        c = d.find_control("volume")
        if c and c.feedback:
            kwargs = {
                c.midi_id_field: c.midi_id,
                c.midi_value_field: self.level
            }
            dev.out_port.send(mido.Message(c.midi_type,**kwargs))

    def set_level(self, new_level):
        new_level = int(new_level)
        if new_level > 123: new_level = 127
            
        if new_level == self.level:
            return False
        
        self.level = new_level
        return True

    def update_level(self, dev):
        """
        Returns a midi message to update volume level display
        """
        d = self.dev_binding
        c = d.find_control("level")
        if c and c.feedback:
            if self.target or c.unset is None:
                display_level = int((self.level/127.0)*(c.max-c.min)+c.min)
            else:
                display_level = c.unset
            kwargs = {
                c.midi_id_field: c.midi_id,
                c.midi_value_field: display_level
            }
            dev.out_port.send(mido.Message(c.midi_type,**kwargs))

    def update_meter(self, dev):
        """
        Returns a midi message to update volume meter
        """
        if not self.target:
            return

        d = self.dev_binding
        c = d.find_control("meter")
        if c and c.feedback:
            kwargs = {
                c.midi_id_field: c.midi_id,
                c.midi_value_field: self.level
            }
            dev.out_port.send(mido.Message(c.midi_type,**kwargs))

    def change_color(self, inc):
        """
        inc: 1 or -1 to represent direction
        Changes the color of the channel
        """
        colors = ["black","white","red","green","yellow","blue","cyan","magenta"]
        cur_index = colors.index(self.color)
        new_index = (cur_index+inc)%8
        self.color = colors[new_index]

    def set_level_from_float(self, value):
        prelim_level = int(127*value)
        if prelim_level > 123: prelim_level = 127
            
        if self.level == prelim_level:
            return False
        self.level = int(prelim_level) if prelim_level >= 0 else 0
        return True

    def get_level_from_target(self):
        self.set_level_from_float(self.target.get_volume())
        self.mute = bool(self.target.get_mute())

    def update_target_volume(self):
        self.target.set_volume(self.level/127)

    def toggle_mute(self):
        self.mute = not self.mute
        self.target.set_mute(self.mute)

    def increment_level(self, inc):
        new_level = self.level + inc
        if new_level < 0:
            new_level = 0
        elif new_level > 127:
            new_level = 127
        self.level = new_level

    def set_target_from_app_def(self, app_def):
        if app_def is None:
            self.unset_target()
            return

        if app_def.name == "Master":
            self.set_master()
            return

        self.name = app_def.name
        self.target = ApplicationVolume(app_def.name, app_def.sessions) 

        self.color = app_def.color
        self.get_level_from_target()
        print(f"Setting channel {self.cid} to {self.name} with {self.target.session_count()} sessions ")

    def add_target_from_app_def(self, app_def):
        if app_def is None or app_def.name == "Master":
            return

        new_target = ApplicationVolume(app_def.name, app_def.sessions)
        
        if self.target is None:
            self.set_target_from_app_def(app_def)
        elif isinstance(self.target, MultiTarget):
            if not any(t.name == app_def.name for t in self.target.targets):
                self.target.targets.append(new_target)
                self.name = f"{len(self.target.targets)} Apps"
        elif isinstance(self.target, ApplicationVolume):
            if self.target.name != app_def.name:
                old_target = self.target
                self.target = MultiTarget(name="Group", targets=[old_target, new_target])
                self.name = "2 Apps"
        
        self.get_level_from_target()
        print(f"Added {app_def.name} to channel {self.cid}. Total: {self.name}")

    def unset_target(self):
        self.target = None
        self.name = "Unused"
        self.color = "black"
        self.level = 0
        print(f"Unsetting channel {self.cid}")

    def change_target(self, inc):
        apps = wh.get_applications_and_sessions()
        app_names = sorted(list(set(apps.keys()).difference(["Master"]))) + ["Master"]
        try:
            index = app_names.index(self.target.name) if self.target is not None else None
        except ValueError:
            index = None

        if index is None:
            if inc > 0:
                self.set_target_from_app_def(apps[app_names[0]])
            else:
                self.set_target_from_app_def(apps[app_names[-1]])
            
        else:
            pos = index + inc
            if pos >= len(app_names) or pos < 0:
                self.unset_target()
            else:
                self.set_target_from_app_def(apps[app_names[pos]])

    def set_master(self):
        self.name = "Master"
        self.color = "white"
        self.target = DeviceVolume(self.name, wh.get_master_volume_session())
        self.get_level_from_target()
        print(f"Setting channel {self.cid} to Master")

    def lock(self, lock, dev):
        if self.touch_lock and not lock:
            self.touch_lock = False
            self.update_fader(dev)
        else:
            self.touch_lock = lock

    def update_status(self, volume, mute, peak, dev):
        self.mute = mute
        self.peak = peak
        if self.set_level_from_float(volume):
            self.update_display(dev, fader=True)
        else:
            self.update_display(dev)

    def refresh_sessions(self, dev):
        if type(self.target) == DeviceVolume:
            if self.target.name == "Master":
                self.target.session = wh.get_master_volume_session()
                self.get_level_from_target()
        elif type(self.target) == ApplicationVolume:
            self._refresh_app_target(self.target)
        elif type(self.target) == MultiTarget:
            for t in self.target.targets:
                if type(t) == ApplicationVolume:
                    self._refresh_app_target(t)
            self.get_level_from_target()
            
        self.update_display(dev, fader=True)

    def _refresh_app_target(self, target):
        apps = wh.get_applications_and_sessions()
        if target.name not in apps:
            target.sessions = []
            print(f"Removing dead sessions for {target.name}")
        else:
            target.sessions = apps[target.name].sessions
