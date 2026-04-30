from pycaw.pycaw import AudioUtilities
import pythoncom

pythoncom.CoInitialize()
try:
    sessions = AudioUtilities.GetAllSessions()
    print(f"Sessions: {sessions}")
    if sessions:
        s = sessions[0]
        print(f"Session object: {s}")
        print(f"Session attributes: {dir(s)}")
except Exception as e:
    print(f"Error: {e}")
