import time
import smc_mixer_control.windows_helpers as wh

def start(event_queue):
    """
    This is the entry point for the system listener process. It listens to system events such as
    volume changes and sends events to the event_queue to update motorized faders and other
    feedback controls on the device.
    """
    wh.com_init()
    master = wh.get_master_volume_session()
    try:
        while True:
            time.sleep(0.03)
            apps = wh.get_applications_and_sessions()
            app_volumes = {}
            for app in apps.values():
                if app.name != "Master":
                    app_volumes[app.name] = [{
                        "identifier": session.InstanceIdentifier,
                        "level": session.SimpleAudioVolume.GetMasterVolume(),
                        "mute": session.SimpleAudioVolume.GetMute(),
                        "peak": wh.get_session_peak(session)
                    } for session in app.sessions]

            try:
                master_level = master.GetMasterVolumeLevelScalar()
                master_mute = master.GetMute()
                master_peak = wh.get_session_peak(master)
            except Exception:
                master = wh.get_master_volume_session()
                master_level = master.GetMasterVolumeLevelScalar()
                master_mute = master.GetMute()
                master_peak = wh.get_session_peak(master)

            event = {
                "apps": app_volumes,
                "master": {"level": master_level, "mute": master_mute, "peak": master_peak}
            }
            event_queue.put(("system", event))
    except KeyboardInterrupt:
        pass
