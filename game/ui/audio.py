"""Procedural sound (spec §9 M17). Rendering-side only, and entirely
optional: if the mixer can't start — headless test run, no audio device,
an unexpected sample format — every call here is a silent no-op.

Like the art (M7), sounds are generated in code rather than shipped as
assets. The thunder crash that lands with the Thor signal is the loud one
and fires once a campaign; the M37 chimes fire constantly, so they are
soft, eased in rather than struck, and mixed well underneath it:

    thunder 92% of full scale | level up 42% | training/assignment 34%
"""

import array
import math
import random

import pygame

_cache = {}
_unavailable = False


def _mixer():
    """(frequency, size, channels) if we can make noise, else None."""
    global _unavailable
    if _unavailable:
        return None
    init = pygame.mixer.get_init()
    if init is None:
        try:
            pygame.mixer.init()
        except pygame.error:
            _unavailable = True
            return None
        init = pygame.mixer.get_init()
    if init is None or init[1] != -16:       # signed 16-bit is all we author
        _unavailable = True
        return None
    return init


def _thunder(frequency, channels):
    """One close strike: a bright crack that decays in a few hundredths of
    a second, over a two-pole-filtered noise rumble that rolls and swells
    for a couple of seconds."""
    rng = random.Random(1991)               # fixed: the same crash every time
    samples = array.array("h")
    total = int(frequency * 2.2)
    low = lower = 0.0
    for i in range(total):
        t = i / frequency
        white = rng.uniform(-1.0, 1.0)
        low += 0.045 * (white - low)        # ~160 Hz corner, two poles deep
        lower += 0.045 * (low - lower)
        rumble = lower * 7.0 * math.exp(-t * 1.25) * (
            1.0 + 0.5 * math.sin(t * 5.5) * math.exp(-t * 0.8))
        crack = white * math.exp(-t * 26.0)
        value = max(-1.0, min(1.0, rumble + crack * 0.75))
        sample = int(value * 30000)
        for _ in range(channels):
            samples.append(sample)
    return samples.tobytes()


def _bell(frequency, channels, notes, length, attack=0.012, volume=0.85):
    """A soft struck-bell arpeggio: sine fundamental plus a quiet octave and
    twelfth, each note eased in over `attack` seconds so nothing clicks, and
    decaying away. Deliberately blunt — these fire often, and a sharp
    transient that is pleasant once is a hazard by the fiftieth time."""
    samples = array.array("h")
    per_note = length / len(notes)
    total = int(frequency * length)
    for i in range(total):
        t = i / frequency
        index = min(int(t / per_note), len(notes) - 1)
        local = t - index * per_note
        pitch = notes[index]
        # ease in, then a long exponential tail
        envelope = min(1.0, local / attack) * math.exp(-local * 4.2)
        value = (math.sin(2 * math.pi * pitch * local)
                 + 0.30 * math.sin(4 * math.pi * pitch * local)
                 + 0.12 * math.sin(6 * math.pi * pitch * local))
        sample = int(max(-1.0, min(1.0, value * envelope * 0.5)) * 30000 * volume)
        for _ in range(channels):
            samples.append(sample)
    return samples.tobytes()


def _level_up(frequency, channels):
    """Rising major triad — the one that means "you got stronger"."""
    return _bell(frequency, channels, (523.25, 659.25, 783.99), 0.62)


def _training_done(frequency, channels):
    """Two notes, up: somebody is off the mats and back."""
    return _bell(frequency, channels, (587.33, 880.00), 0.44, volume=0.70)


def _assignment_done(frequency, channels):
    """Two notes, down and settling: somebody is home from a job."""
    return _bell(frequency, channels, (783.99, 523.25), 0.46, volume=0.70)


GENERATORS = {"thunder": _thunder,
              "level_up": _level_up,
              "training_done": _training_done,
              "assignment_done": _assignment_done}


def play(name):
    """Play a generated sound by name. Unknown names and a dead mixer are
    both no-ops — sound never gates gameplay."""
    if not name:
        return
    init = _mixer()
    if init is None:
        return
    key = (name, init)
    if key not in _cache:
        generator = GENERATORS.get(name)
        if generator is None:
            return
        try:
            sound = pygame.mixer.Sound(buffer=generator(init[0], init[2]))
            sound.set_volume(0.7)
        except (pygame.error, ValueError):
            sound = None
        _cache[key] = sound
    sound = _cache[key]
    if sound is not None:
        sound.play()
