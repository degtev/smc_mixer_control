import multiprocessing
import pathlib

import smc_mixer_control.midi_listener as midi_listener
import smc_mixer_control.system_listener as system_listener
import smc_mixer_control.event_handler as event_handler
from smc_mixer_control.device import Device
from smc_mixer_control.channel import Channel
from smc_mixer_control.control_mappings import ChannelMap, SharedMap
from smc_mixer_control.interface import get_config, systray

import sys
DIR = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).parent.parent.resolve()))
DEVICES = DIR.joinpath("static", "devices")
if not DEVICES.is_dir():
    DEVICES = DIR.joinpath("devices")

def init_channels(dev):
    """
    Initialize the Channels with basic mappings to the DeviceChannels. This will also configure
    any DeviceChannels where default==master.
    """
    shared_map = SharedMap(dev.shared_controls)
    shared_map.light(dev)
    channel_map = ChannelMap([
        Channel(
            cid=i,
            name="Unused",
            color="black",
            level=0,
            mute=False,
            dev_binding=dev.device_channels[i],
            target=None
        )
        for i in range(len(dev.device_channels))
    ], dev.unique_id)

    for channel in channel_map.channels.values():
        if channel.dev_binding.default == "master":
            channel.set_master()
        channel.update_display(dev, fader=True)

    return shared_map, channel_map

def start():
    """
    This is the primary entry point for the application. We're running multiprocessing here so we
    can have totally separate processes listening for midi events and system events, all funneling
    into a single event queue to be processed by the event_handler. Listeners are intended to be
    "dumb" and not do significant processing in their processes, saving most filtering and
    processing for the handler.
    """
    multiprocessing.freeze_support()

    try:
        dev_info = get_config()
    except:
        dev_info = None

    event_queue = multiprocessing.Queue()
    systray_update_queue = multiprocessing.Queue()
    gui_update_queue = multiprocessing.Queue()
    osd_queue = multiprocessing.Queue()
    
    if dev_info is None:
        print("SMC Mixer Control device not found. Please ensure your MIDI device is connected and configured in the devices directory.")
        return

    dev = Device(dev_info)
    shared_map, channel_map = init_channels(dev)

    import smc_mixer_control.osd as osd
    import smc_mixer_control.gui as gui
    midi_listener_process = multiprocessing.Process(target = midi_listener.start, args=(event_queue,dev.in_name))
    system_listener_process = multiprocessing.Process(target = system_listener.start, args=(event_queue,))
    systray_process = multiprocessing.Process(target = systray, args=(event_queue, systray_update_queue, len(channel_map.channels.keys())))
    osd_process = multiprocessing.Process(target = osd.start, args=(osd_queue,))
    gui_process = multiprocessing.Process(target = gui.start, args=(event_queue, gui_update_queue, len(channel_map.channels.keys())))
    
    midi_listener_process.start()
    system_listener_process.start()
    systray_process.start()
    osd_process.start()
    gui_process.start()

    event_queue.put(("interface", {"action": "request_state"}))

    try:
        event_handler.start(event_queue, dev, shared_map, channel_map, [systray_update_queue, gui_update_queue], osd_queue)
    except (KeyboardInterrupt, SystemExit):
        print("\nStopping SMC Mixer Control...")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise e
    finally:
        print("Cleaning up processes...")
        for p in [midi_listener_process, system_listener_process, systray_process, osd_process, gui_process]:
            if p.is_alive():
                p.terminate()
                p.join(timeout=1)
        print("Done. Safe to close terminal.")
