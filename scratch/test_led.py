import mido
import time

def test_all_leds():
    outputs = mido.get_output_names()
    print("Available outputs:")
    for i, name in enumerate(outputs):
        print(f"{i}) {name}")
    
    selection = int(input("Select SMC-Mixer output: "))
    out_port = mido.open_output(outputs[selection])

    # Список всех ID, которые мы видели в логах
    test_ids = [20, 28, 52, 9, 30, 40, 58, 61]
    
    print("Testing CC (Control Change) IDs...")
    for mid in test_ids:
        print(f"Sending CC {mid} ON")
        out_port.send(mido.Message('control_change', control=mid, value=127))
    
    print("Testing Note IDs...")
    for mid in test_ids:
        print(f"Sending Note {mid} ON")
        out_port.send(mido.Message('note_on', note=mid, velocity=127))

    print("\nCheck your mixer! Did ANY button start glowing?")
    time.sleep(5)

    print("Turning everything OFF...")
    for mid in test_ids:
        out_port.send(mido.Message('control_change', control=mid, value=0))
        out_port.send(mido.Message('note_off', note=mid, velocity=0))
    
    out_port.close()

if __name__ == "__main__":
    test_all_leds()
