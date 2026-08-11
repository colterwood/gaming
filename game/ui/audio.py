"""Procedural sound (spec §9 M17). Rendering-side only, and entirely
optional: if the mixer can't start — headless test run, no audio device,
an unexpected sample format — every call here is a silent no-op.

Like the art (M7), sounds are generated in code rather than shipped as
assets. So far the only one the game needs is the thunder crash that
lands with the Thor signal.
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


GENERATORS = {"thunder": _thunder}


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
