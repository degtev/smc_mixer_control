from dataclasses import dataclass, field

@dataclass
class Target:
    """
    Targets are the applications or system volume channels to be controlled by the midi device.
    name: freeform string
    ttype: 'application' or 'master'
    session: an audio session with methods to get and set volume
    """
    name: str

    def session_count(self):
        return 1

    def get_volume(self):
        return 0

    def get_mute(self):
        return False

    def set_volume(self, level):
        pass

    def set_mute(self, mute):
        pass

@dataclass
class ApplicationVolume(Target):
    sessions: list[any] = field(default_factory=list)

    def get_volume(self):
        if self.sessions:
            return min(session.SimpleAudioVolume.GetMasterVolume() for session in self.sessions)
        else:
            return 0
    
    def get_mute(self):
        if self.sessions:
            return bool(min(session.SimpleAudioVolume.GetMute() for session in self.sessions))
        else:
            return False

    def set_volume(self, level):
        for session in self.sessions:
            session.SimpleAudioVolume.SetMasterVolume(level, None)

    def set_mute(self, mute):
        for session in self.sessions:
            session.SimpleAudioVolume.SetMute(mute, None)

    def session_count(self):
        return len(self.sessions)

@dataclass
class MultiTarget(Target):
    targets: list[Target] = field(default_factory=list)

    def get_volume(self):
        if not self.targets: return 0
        return sum(t.get_volume() for t in self.targets) / len(self.targets)
        
    def get_mute(self):
        if not self.targets: return False
        return any(t.get_mute() for t in self.targets)

    def set_volume(self, level):
        for t in self.targets:
            t.set_volume(level)

    def set_mute(self, mute):
        for t in self.targets:
            t.set_mute(mute)

    def session_count(self):
        return sum(t.session_count() for t in self.targets)

@dataclass
class SystemSoundsVolume(Target):
    session: any

    def get_volume(self): 
        return self.session.SimpleAudioVolume.GetMasterVolume() if self.session else 0
    
    def get_mute(self):
        return self.session.SimpleAudioVolume.GetMute() if self.session else False

    def set_volume(self, level):
        self.session.SimpleAudioVolume.SetMasterVolume(level, None)

    def set_mute(self, mute):
        self.session.SetMute(mute, None)

@dataclass
class DeviceVolume(Target):
    session: any

    def get_volume(self):
        return self.session.GetMasterVolumeLevelScalar() if self.session else 0

    def get_mute(self):
        return self.session.GetMute() if self.session else 0

    def set_volume(self, level):
        try:
            self.session.SetMasterVolumeLevelScalar(level, None)
        except ValueError as e:
            print(f"Failed to set device volume: {e}")
    
    def set_mute(self, mute):
        self.session.SetMute(mute, None)
