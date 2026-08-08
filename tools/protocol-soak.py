#!/usr/bin/env python3
"""
Hammer a driver's read/write path and report how much of it survives.

Devices answer their own protocol at their own pace. A driver that looks
fine interactively can still fail under the burst the GUI's Apply
produces -- brightness, LED effect, DPI stages and one command per stage
colour, all with no gap. That burst is what this reproduces.

It found a real bug: x2a.py raised on the first unexpected response byte
instead of polling for the device's ack, and 15 of 32 write groups failed
(see _poll_ack() in drivers/x2a.py). Run this after touching any
driver's transport, and when adding a new one.

Every write puts the CURRENT value back, so a complete run leaves the
device exactly as it found it. A run that fails partway may not -- so
the device's settings are captured up front and restored at the end,
and printed so they can be re-applied by hand if even that fails.

Usage:
    PYTHONPATH=src python3 tools/protocol-soak.py [--device NAME]
                                                  [--rounds N] [--profile N]

Exit status is 1 if any operation failed, so CI or a shell loop can gate
on it -- though it needs real hardware, so it is not part of the CI run.
"""

import argparse
import sys
import time

from openperiph import find_device
from openperiph.drivers import discover_all


def _fmt_color(c):
    return '#%02X%02X%02X' % tuple(c)


def snapshot(device, profile):
    """Read every settable field the device admits to having.

    Anything that raises is left out of the returned dict rather than
    aborting -- a driver that implements half the optional getters should
    still get its implemented half soaked.
    """
    caps = device.capabilities
    state = {}

    def grab(key, fn):
        try:
            state[key] = fn()
        except Exception:
            pass

    grab('polling_rate', device.get_polling_rate)
    if caps.has_debounce:
        grab('debounce', device.get_debounce)
    if caps.has_angle_snap:
        grab('angle_snap', device.get_angle_snap)
    if caps.has_ripple_control:
        grab('ripple', device.get_ripple_control)
    if caps.has_motion_sync:
        grab('motion_sync', device.get_motion_sync)
    if caps.lod_values:
        grab('lod', lambda: device.get_lod(profile))
    if caps.has_led:
        grab('brightness', lambda: device.get_brightness(profile))
        grab('led_effect', lambda: device.get_led_effect(profile))
        if caps.has_breath_speed:
            grab('breath_speed', lambda: device.get_breath_speed(profile))

    try:
        info = device.get_dpi_stages(profile)
        state['dpi'] = {
            'active': info['active'],
            'stages': [dx for dx, _dy in info['stages'][:info['count']]],
        }
        if caps.has_stage_colors:
            state['colors'] = [tuple(device.get_stage_color(i, profile))
                               for i in range(1, info['count'] + 1)]
    except Exception:
        pass

    return state


def write_ops(device, state, profile):
    """(label, callable) for every field in *state*, writing it back as-is."""
    ops = []
    if 'polling_rate' in state:
        ops.append(('polling_rate',
                    lambda: device.set_polling_rate(state['polling_rate'])))
    if 'debounce' in state:
        ops.append(('debounce', lambda: device.set_debounce(state['debounce'])))
    if 'angle_snap' in state:
        ops.append(('angle_snap',
                    lambda: device.set_angle_snap(state['angle_snap'])))
    if 'ripple' in state:
        ops.append(('ripple',
                    lambda: device.set_ripple_control(state['ripple'])))
    if 'motion_sync' in state:
        ops.append(('motion_sync',
                    lambda: device.set_motion_sync(state['motion_sync'])))
    if 'lod' in state:
        ops.append(('lod', lambda: device.set_lod(state['lod'], profile)))
    if 'brightness' in state:
        ops.append(('brightness',
                    lambda: device.set_brightness(state['brightness'], profile)))
    if 'led_effect' in state:
        ops.append(('led_effect',
                    lambda: device.set_led_effect(state['led_effect'], profile)))
    if 'breath_speed' in state:
        ops.append(('breath_speed',
                    lambda: device.set_breath_speed(state['breath_speed'], profile)))
    if 'dpi' in state:
        ops.append(('dpi_stages',
                    lambda: device.set_dpi_stages(state['dpi']['stages'],
                                                  state['dpi']['active'], profile)))
    # One command per stage - the burst that broke x2a.py.
    for i, rgb in enumerate(state.get('colors', []), start=1):
        ops.append((f'stage_color[{i}]',
                    lambda i=i, rgb=rgb: device.set_stage_color(i, *rgb, profile)))
    return ops


def restore(device, state, profile, attempts=8):
    """Put *state* back, retrying with settle time. Returns list of failures."""
    failed = []
    for label, op in write_ops(device, state, profile):
        for attempt in range(attempts):
            try:
                op()
                break
            except Exception as e:
                last = e
                time.sleep(0.3)
        else:
            failed.append((label, str(last)))
    return failed


def main():
    p = argparse.ArgumentParser(
        description='Soak a driver read/write path against real hardware.')
    p.add_argument('--device', metavar='NAME',
                   help=f'Driver to use ({", ".join(sorted(discover_all()))})')
    p.add_argument('--rounds', type=int, default=8, metavar='N',
                   help='Write/read rounds (default: 8)')
    p.add_argument('--profile', type=int, default=1, metavar='N',
                   help='Profile to soak (default: 1)')
    args = p.parse_args()

    try:
        device = find_device(args.device)
    except RuntimeError as e:
        sys.exit(f'Error: {e}')

    device.open()
    try:
        state = snapshot(device, args.profile)
        if not state:
            sys.exit('Error: could not read any settings from the device')

        print(f'{device.capabilities.name} - profile {args.profile}')
        print('Captured state (restore by hand if this run dies badly):')
        for k, v in state.items():
            if k == 'colors':
                v = [_fmt_color(c) for c in v]
            print(f'  {k:14} {v}')

        ops = write_ops(device, state, args.profile)
        reads = [('snapshot', lambda: snapshot(device, args.profile))]
        print(f'\n{len(ops)} writes + {len(reads)} reads per round, '
              f'{args.rounds} rounds\n')

        w_ok = w_fail = r_ok = r_fail = 0
        failures = []
        t0 = time.time()
        for rnd in range(args.rounds):
            for label, op in ops:
                try:
                    op()
                    w_ok += 1
                except Exception as e:
                    w_fail += 1
                    failures.append((rnd, 'write', label, str(e)))
            for label, op in reads:
                try:
                    op()
                    r_ok += 1
                except Exception as e:
                    r_fail += 1
                    failures.append((rnd, 'read', label, str(e)))
        elapsed = time.time() - t0

        print(f'writes: {w_ok}/{w_ok + w_fail} ok')
        print(f'reads:  {r_ok}/{r_ok + r_fail} ok')
        print(f'time:   {elapsed:.1f}s')
        if failures:
            print(f'\nfirst {min(10, len(failures))} failures:')
            for rnd, kind, label, err in failures[:10]:
                print(f'  round {rnd} {kind:5} {label:16} {err}')

        # A clean run already left everything as it was; this only matters
        # when writes failed partway and left a field half-set.
        print('\nrestoring captured state...')
        left = restore(device, state, args.profile)
        after = snapshot(device, args.profile)
        if left:
            print('  COULD NOT RESTORE:')
            for label, err in left:
                print(f'    {label:16} {err}')
        elif after == state:
            print('  device state matches the capture')
        else:
            print('  device state DIFFERS from the capture:')
            for k in sorted(set(state) | set(after)):
                if state.get(k) != after.get(k):
                    print(f'    {k:14} was {state.get(k)}  now {after.get(k)}')

        sys.exit(1 if (failures or left or after != state) else 0)
    finally:
        device.close()


if __name__ == '__main__':
    main()
