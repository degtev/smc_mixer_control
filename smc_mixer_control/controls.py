from dataclasses import dataclass

@dataclass
class Control:
    """
    Controls are the various controls on midi devices that are used for input and output.
    """
    type: str
    func: str
    midi_type: str
    midi_id_field: str
    midi_id: int
    midi_value_field: str
    feedback: bool

@dataclass
class Fader(Control):
    midi_value_min: int
    midi_value_max: int

    def normalize_level(self, value):
        if self.midi_value_max == self.midi_value_min:
            return 0
        return int((value-self.midi_value_min)/(self.midi_value_max-self.midi_value_min)*127)

@dataclass  
class RotaryEncoder(Control):
    increment_value: int
    decrement_value: int
    accel: bool = False

    def get_increment(self, value):
        if value <= 64:
            return value
        else:
            return value - 128

@dataclass
class Button(Control):
    down_value: int = 127
    up_value: int = 0

@dataclass
class Meter(Control):
    min: int = 0
    max: int = 127
    unset: int = 0
    pass
