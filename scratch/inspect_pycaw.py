from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import pythoncom

pythoncom.CoInitialize()
try:
    devices = AudioUtilities.GetSpeakers()
    print(f"Device object: {devices}")
    print(f"Attributes: {dir(devices)}")
except Exception as e:
    print(f"Error: {e}")
