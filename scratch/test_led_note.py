import mido
import time

def test_note_led():
    outputs = mido.get_output_names()
    print("Available outputs:")
    for i, name in enumerate(outputs):
        print(f"{i}) {name}")
    
    selection = int(input("Select SMC-Mixer output: "))
    out_port = mido.open_output(outputs[selection])

    print("Sending Note 16 ON (Velocity 127)...")
    out_port.send(mido.Message('note_on', note=16, velocity=127))
    
    print("Did the LED light up? (Waiting 5 seconds)")
    time.sleep(5)

    print("Sending Note 16 OFF...")
    out_port.send(mido.Message('note_off', note=16, velocity=0))
    out_port.close()

if __name__ == "__main__":
    test_note_led()
