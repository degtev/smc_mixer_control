import mido
import mido.backends.rtmidi

def debug_midi():
    inputs = mido.get_input_names()
    if not inputs:
        print("No MIDI inputs found!")
        return
    
    print("Available inputs:")
    for i, name in enumerate(inputs):
        print(f"{i}) {name}")
    
    try:
        selection = int(input("Select device to debug: "))
        dev_name = inputs[selection]
    except:
        print("Invalid selection")
        return

    print(f"--- Listening to {dev_name} ---")
    print("Move a fader or press a button on your device...")
    
    try:
        with mido.open_input(dev_name) as in_port:
            for msg in in_port:
                print(f"RECEIVED: {msg}")
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    debug_midi()
