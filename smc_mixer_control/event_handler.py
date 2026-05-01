from collections import defaultdict
import time
import math
import mido
from smc_mixer_control.target import ApplicationVolume, DeviceVolume, MultiTarget
import smc_mixer_control.windows_helpers as wh

def start(event_queue, dev, shared_map, channel_map, update_queue, osd_queue):
    """
    This is the main event handler loop. It listens to the multiprocessing event queue and reacts
    to events based on basic rules. The intent is for this code to be static for all devices, and
    for device config and application config (target bindings) to be the means by which we change
    behaviors of various controls.
    """
    wh.com_init()
    active_modes = set()
    active_channel_modes = defaultdict(set)
    last_apps_list = []

    if channel_map.load():
        for channel in channel_map.channels.values():
            channel.update_display(dev, fader=True)

    def _send_osd(channel):
        display_name = channel.name
        if isinstance(channel.target, MultiTarget):
            names = [t.name for t in channel.target.targets]
            clean_names = [n.replace(".exe", "") for n in names]
            display_name = ", ".join(clean_names)
        elif channel.name.endswith(".exe"):
            display_name = channel.name.replace(".exe", "")

        osd_queue.put(("update", {
            "name": display_name,
            "volume": channel.level,
            "mute": channel.mute
        }))

    def _update_target_from_system(channel, target, event, dev, update_display=True, osd_queue=None):
        if target.name in event["apps"]:
            channel_sessions = set(s.InstanceIdentifier for s in target.sessions)
            app_sessions = set(a["identifier"] for a in event["apps"][target.name])
            if channel_sessions != app_sessions:
                channel.refresh_sessions(dev)
            else:
                volume = min(a["level"] for a in event["apps"][target.name])
                mute = all(bool(a["mute"]) for a in event["apps"][target.name])
                peak = max(a["peak"] for a in event["apps"][target.name])
                
                if mute and volume == 0 and channel.level > 0:
                    volume = channel.level / 127.0
                
                old_level = channel.level
                old_mute = channel.mute
                
                channel.update_status(volume, mute, peak, dev)
                
                if update_display:
                    channel.update_display(dev)
                
                if osd_queue and (old_level != channel.level or old_mute != channel.mute):
                    _send_osd(channel)
        elif target.sessions:
            channel.refresh_sessions(dev)

    last_anim_time = 0
    last_chase_idx = -1
    last_mode = ""
    
    horiz_order = []
    for y in range(4):
        row = [(x, y) for x in range(8)]
        if y % 2 == 1: row.reverse()
        horiz_order.extend(row)
    
    vert_order = []
    for x in range(8):
        col = [(x, y) for y in range(4)]
        if x % 2 == 0: col.reverse() 
        vert_order.extend(col)

    try:
        while True:
            real_t = time.time()
            speed_mult = getattr(channel_map, "animation_speed", 1.0)
            t = real_t * speed_mult
            mode = getattr(channel_map, "animation_mode", "Chase Forward")
            
            unassigned_strips = [i for i in range(8) if not channel_map.channels[i].target]
            num_strips = len(unassigned_strips)
            
            unassigned_cids = [c.cid for c in channel_map.channels.values() if not c.target and 8 <= c.cid <= 39]
            
            current_order = []
            if "Horizontal" in mode:
                current_order = [p for p in horiz_order if ((p[1]*8+8) + p[0]) in unassigned_cids]
            elif "Vertical" in mode:
                current_order = [p for p in vert_order if ((p[1]*8+8) + p[0]) in unassigned_cids]
            
            num_steps = len(current_order)
            
            global_peak = max([c.peak for c in channel_map.channels.values()] + [0.0])

            if num_steps > 0 and (mode in ["Fill Horizontal", "Fill Vertical", "Crawl Horizontal", "Crawl Vertical"]):
                if "Fill" in mode:
                    total_cycle = num_steps * 2
                    chase_idx = int(t / 0.08) % total_cycle
                else:
                    total_cycle = num_steps
                    chase_idx = int(t / 0.1) % total_cycle
            elif num_strips > 0 and (mode in ["Chase Forward", "Chase Backward", "Knight Rider"]):
                if mode == "Chase Forward":
                    chase_idx = unassigned_strips[int(t / 0.15) % num_strips]
                elif mode == "Chase Backward":
                    chase_idx = unassigned_strips[num_strips - 1 - (int(t / 0.15) % num_strips)]
                elif mode == "Knight Rider":
                    cycle = num_strips * 2 - 2 if num_strips > 1 else 1
                    idx = int(t / 0.1) % cycle
                    logic_idx = idx if idx < num_strips else cycle - idx
                    chase_idx = unassigned_strips[logic_idx]
            elif mode == "Blink":
                chase_idx = -1 if (int(t / 0.5) % 2 == 0) else -2
            elif mode == "Random Pulse":
                chase_idx = int(t * 10) 
            elif mode == "Equalizer":
                chase_idx = int(t * 20) 
            else:
                chase_idx = -2

            if chase_idx != last_chase_idx or mode != last_mode:
                led_states = [0] * 32
                for channel in channel_map.channels.values():
                    is_on = False
                    if not channel.target:
                        if (mode in ["Fill Horizontal", "Fill Vertical", "Crawl Horizontal", "Crawl Vertical"]) and num_steps > 0:
                            cid = channel.cid
                            if 8 <= cid <= 39:
                                x = (cid - 8) % 8
                                y = (cid - 8) // 8
                                try:
                                    target_idx = current_order.index((x, y))
                                    if "Fill" in mode:
                                        if chase_idx < num_steps:
                                            is_on = (target_idx <= chase_idx)
                                        else:
                                            drain_progress = chase_idx - num_steps
                                            is_on = (target_idx > drain_progress)
                                    else:
                                        length = num_steps // 2
                                        is_on = (target_idx - chase_idx) % num_steps < length
                                except ValueError: pass
                        elif mode == "Equalizer":
                            cid = channel.cid
                            if 8 <= cid <= 39:
                                x = (cid - 8) % 8
                                y = (cid - 8) // 8
                                
                                jitter = (math.sin(t * 8 + x * 2) * 0.15)
                                strip_peak = global_peak + jitter
                                if strip_peak < 0: strip_peak = 0
                                if strip_peak > 1: strip_peak = 1
                                
                                buttons_to_light = int(strip_peak * 4.5)
                                is_on = (3 - y) < buttons_to_light
                        elif mode in ["Chase Forward", "Chase Backward", "Knight Rider"]:
                            is_on = (channel.cid % 8 == chase_idx)
                        elif mode == "Blink":
                            is_on = (chase_idx == -1)
                        elif mode == "Random Pulse":
                            is_on = (hash(str(channel.cid) + str(chase_idx)) % 10 < 2)
                        
                        brightness = 127 if is_on else 0
                        channel.update_leds(dev, idle_brightness=brightness)
                    
                    cid = channel.cid
                    if 8 <= cid <= 39:
                        idx = cid - 8

                        if is_on:
                            led_states[idx] = 127
                        elif channel.target:
                            pass

                for q in update_queue:
                    q.put(("led_states", led_states))
                
                last_chase_idx = chase_idx
                last_mode = mode
                last_anim_time = t

            try:
                event_type, event = event_queue.get(timeout=0.01)
            except:
                event_type, event = None, None

            if event_type == "midi":
                shared_control, val = shared_map.lookup(event)
                if shared_control and shared_control.feedback:
                    fb_val = shared_control.down_value if val > 0 else shared_control.up_value
                    kwargs = {
                        shared_control.midi_id_field: shared_control.midi_id,
                        shared_control.midi_value_field: fb_val
                    }
                    dev.out_port.send(mido.Message(shared_control.midi_type, **kwargs))

                match, value = channel_map.lookup(event)
                if match is not None:
                    if match.control.func == "volume":
                        if hasattr(match.control, "normalize_level"):
                            new_level = match.control.normalize_level(value)
                            if match.channel.set_level(new_level):
                                if match.channel.target:
                                    match.channel.update_target_volume()
                                    _send_osd(match.channel)
                                match.channel.update_display(dev)
                        
                        if hasattr(match.control, "get_increment"):
                            inc = match.control.get_increment(value)
                            if "assign_mod" in active_modes:
                                match.channel.change_target(inc)
                                match.channel.update_display(dev, fader=True)
                                channel_map.save()
                            elif match.channel.increment_level(inc):
                                if match.channel.target:
                                    match.channel.update_target_volume()
                                    _send_osd(match.channel)
                                match.channel.update_display(dev)

                    elif match.control.func == "assign":
                        inc = match.control.get_increment(value)
                        if "color_mod" in active_channel_modes[match.channel.cid]:
                            match.channel.change_color(inc)
                        else:
                            match.channel.change_target(inc)

                        channel_map.save()
                        match.channel.update_display(dev, fader=True)
                    
                    elif match.control.func == "select" and match.control.down_value == value:
                        app_def = wh.get_active_window_app_def()
                        if app_def:
                            match.channel.set_target_from_app_def(app_def)
                        channel_map.save()
                        match.channel.update_display(dev, fader=True)

                    elif match.control.func in ["status", "meter"]:
                        if match.control.func == "status" and match.control.down_value == value:
                            if match.channel.target:
                                print(f"Focusing application: {match.channel.target.name}")
                                wh.focus_application(match.channel.target.name)
                                match.channel.update_display(dev)
                        
                        state = channel_map.get_state()
                        for q in update_queue:
                            q.put(("state", state))
                    
                    elif match.control.func == "mute":
                        if match.control.down_value == value:
                            if match.channel.target:
                                match.channel.toggle_mute()
                                _send_osd(match.channel)
                        
                        if value == 0:
                            time.sleep(0.05)
                        
                        match.channel.update_display(dev)

                    elif match.control.func == "touch":
                        match.channel.lock(value == match.control.down_value, dev)

                    if match.control.func.endswith("_mod"):
                        if value == match.control.down_value:
                            print(f"{match.channel.cid}:{match.control.func} enabled")
                            active_channel_modes[match.channel.cid].add(match.control.func)
                        else:
                            print(f"{match.channel.cid}:{match.control.func} disabled")
                            active_channel_modes[match.channel.cid].remove(match.control.func)
                else:
                    match, value = shared_map.lookup(event)
                    if match is not None:
                        if match.func == "quit":
                            print("Got quit button; quitting.")
                            break

                        elif match.func in ["media_play", "media_pause", "media_play_pause"] and value == match.down_value:
                            wh.send_key("VK_MEDIA_PLAY_PAUSE")

                        elif match.func == "media_stop" and value == match.down_value:
                            wh.send_key("VK_MEDIA_STOP")

                        elif match.func == "media_prev" and value == match.down_value:
                            wh.send_key("VK_MEDIA_PREV_TRACK")

                        elif match.func == "media_next" and value == match.down_value:
                            wh.send_key("VK_MEDIA_NEXT_TRACK")

                        elif match.func.endswith("_mod"):
                            if value == match.down_value:
                                print(f"{match.func} enabled")
                                active_modes.add(match.func)
                            else:
                                print(f"{match.func} disabled")
                                active_modes.remove(match.func)

            if event_type == "system":
                for channel in channel_map.channels.values():
                    if type(channel.target) == ApplicationVolume:
                        _update_target_from_system(channel, channel.target, event, dev, osd_queue=osd_queue)
                    elif type(channel.target) == MultiTarget:
                        for t in channel.target.targets:
                            if type(t) == ApplicationVolume:
                                _update_target_from_system(channel, t, event, dev, update_display=False, osd_queue=osd_queue)
                        channel.update_display(dev)
                    elif type(channel.target) == DeviceVolume:
                        if channel.target.name == "Master":
                            old_level = channel.level
                            old_mute = channel.mute
                            channel.update_status(event["master"]["level"], event["master"]["mute"], event["master"]["peak"], dev)
                            if old_level != channel.level or old_mute != channel.mute:
                                _send_osd(channel)
                            channel.update_display(dev)

            if event_type == "interface":
                if event["action"] == "quit":
                    print("Got quit from menu; quitting.")
                    break
                elif event["action"] == "assign":
                    print(f"Got assign event: {event}")
                    if event["channel"] in channel_map.channels:
                        channel = channel_map.channels[event["channel"]]
                        
                        if event["app"] == "Master":
                            channel.set_master()
                        elif event["app"] == "Unused":
                            channel.unset_target()
                        else:
                            channel.set_target_from_app_def(wh.get_app_def_from_name(event["app"]))
                        
                        channel_map.save()
                        channel.update_display(dev, fader=True)
                elif event["action"] == "add_app":
                    print(f"Got add_app event: {event}")
                    if event["channel"] in channel_map.channels:
                        channel = channel_map.channels[event["channel"]]
                        app_def = wh.get_app_def_from_name(event["app"])
                        if app_def:
                            channel.add_target_from_app_def(app_def)
                        channel_map.save()
                        channel.update_display(dev, fader=True)
                elif event["action"] == "assign_func":
                    print(f"Got assign_func event: {event}")
                    if event["channel"] in channel_map.channels:
                        channel = channel_map.channels[event["channel"]]
                        target_type = event["type"]
                        target_func = event["func"]
                        
                        for control in channel.dev_binding.controls:
                            if control.type == target_type:
                                print(f"Updating control type {target_type} on CID {channel.cid} to func {target_func}")
                                control.func = target_func
                        
                        channel_map.save()
                        channel.update_display(dev, fader=True)
                elif event["action"] == "unassign":
                    print(f"Got unassign event: {event}")
                    if event["channel"] in channel_map.channels:
                        channel = channel_map.channels[event["channel"]]
                        channel.unset_target()
                        channel_map.save()
                        channel.update_display(dev, fader=True)
                elif event["action"] == "set_animation":
                    print(f"Got set_animation event: {event}")
                    channel_map.animation_mode = event["mode"]
                    channel_map.save()
                elif event["action"] == "set_animation_speed":
                    print(f"Got set_animation_speed event: {event}")
                    channel_map.animation_speed = event["speed"]
                    channel_map.animation_speed_name = event["name"]
                    channel_map.save()
                elif event["action"] == "show_gui":
                    for q in update_queue:
                        q.put(("show", {}))
                elif event["action"] == "request_state":
                    state = channel_map.get_state()
                    apps = wh.get_applications_and_sessions()
                    apps_list = sorted(list(apps.keys()))
                    for q in update_queue:
                        q.put(("state", state))
                        q.put(("apps", apps_list))
                    last_apps_list = apps_list

            if event_type in ["interface", "system"]:
                state = channel_map.get_state()
                for q in update_queue:
                    q.put(("state", state))
                
                if event_type == "system":
                    apps_list = sorted(list(event["apps"].keys()))
                    if apps_list != sorted(last_apps_list):
                        for q in update_queue:
                            q.put(("apps", apps_list))
                        last_apps_list = apps_list

    except KeyboardInterrupt:
        pass
