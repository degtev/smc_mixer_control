import mido
import time

def test_note_off():
    outputs = mido.get_output_names()
    selection = int(input("Select SMC-Mixer output: "))
    out_port = mido.open_output(outputs[selection])

    print("Step 1: Sending Note 16 ON...")
    out_port.send(mido.Message('note_on', note=16, velocity=127))
    time.sleep(2)

    print("Step 2: Trying to turn OFF using note_on with velocity=0...")
    out_port.send(mido.Message('note_on', note=16, velocity=0))
    
    print("Did it go out? (Waiting 3 seconds)")
    time.sleep(3)
    
    out_port.close()

if __name__ == "__main__":
    test_note_off()
