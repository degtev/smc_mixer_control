from pycaw.pycaw import AudioUtilities
import pythoncom

pythoncom.CoInitialize()
try:
    sessions = AudioUtilities.GetAllSessions()
    if sessions:
        s = sessions[0]
        print(f"Session: {s}")
        print(f"SimpleAudioVolume attributes: {dir(s.SimpleAudioVolume)}")
        vol = s.SimpleAudioVolume.GetMasterVolume()
        print(f"Current Volume: {vol}")
except Exception as e:
    print(f"Error: {e}")
