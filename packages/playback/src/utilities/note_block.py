__all__ = [
    "PlaysoundNote",
    "get_notes",
    "get_pitch",
]


import math
from dataclasses import dataclass
from typing import Any, Iterator, List, Tuple

import pynbs

NBS_DEFAULT_INSTRUMENTS = [
    "block.note_block.harp",
    "block.note_block.bass",
    "block.note_block.basedrum",
    "block.note_block.snare",
    "block.note_block.hat",
    "block.note_block.guitar",
    "block.note_block.flute",
    "block.note_block.bell",
    "block.note_block.chime",
    "block.note_block.xylophone",
    "block.note_block.iron_xylophone",
    "block.note_block.cow_bell",
    "block.note_block.didgeridoo",
    "block.note_block.bit",
    "block.note_block.banjo",
    "block.note_block.pling",
    "block.note_block.trumpet",
    "block.note_block.trumpet_exposed",
    "block.note_block.trumpet_weathered",
    "block.note_block.trumpet_oxidized",
]

octaves = {
    "harp": 0,
    "bass": -2,
    "basedrum": -1,
    "snare": 1,
    "hat": 0,
    "guitar": -1,
    "flute": 1,
    "bell": 2,
    "chime": 2,
    "xylophone": 2,
    "iron_xylophone": 0,
    "cow_bell": 0,
    "didgeridoo": -2,
    "bit": 0,
    "banjo": 0,
    "pling": 0,
    "trumpet": 0,
    "trumpet_exposed": 0,
    "trumpet_weathered": -1,
    "trumpet_oxidized": -1,
}

# NBS key ranges (inclusive)
TWO_OCTAVE_MIN, TWO_OCTAVE_MAX = 33, 57
SIX_OCTAVE_MIN, SIX_OCTAVE_MAX = 9, 81
SIX_OCTAVE_CENTER = (SIX_OCTAVE_MIN + SIX_OCTAVE_MAX) / 2  # 45
SIX_OCTAVE_HALF_SPAN = SIX_OCTAVE_CENTER - SIX_OCTAVE_MIN  # 36


@dataclass
class PlaysoundNote:
    """Represents a note produced by a /playsound command."""

    instrument: str = "block.note_block.harp"
    volume: float = 1
    falloff: float = 16
    pitch: float = 1
    panning: float = 0

    def play_short_range(
        self, full_range: 9, decay_range: 12, stereo_separation: float = 4
    ) -> str:
        """
        Play a sound that can be heard in a small radius by all players in range.
        """

        # This is achieved by bypassing the `volume` argument completely and instead using the
        # target selector's `distance` argument to determine what players will be able to hear
        # the song at all. Decay is achieved by using the `distance` argument to limit the range
        # of the sound, with a base range and a rolloff factor that increases the audible range
        # of notes according to its pitch (lower notes will be audible from further away).
        #
        # The regular value for volume in a /playsound command is 1.0 = 16 blocks. It's possible
        # to increase it to increase the audible range (e.g. 2.0 = 32 blocks and so on), but
        # decreasing it does *not* actually decrease the audible range, as you'd expect (e.g.
        # 0.5 = 8 blocks). Instead, the sound is still audible within a 16-block range, but is
        # softer overall.
        #
        # So, the only to achieve a gradual rolloff less than 16 blocks, is by entirely limiting
        # who will be able to hear the songs at all via target selection. As such, we can use the
        # `distance` condition to play notes only to players in a certain range. The code
        # works with a base range of 9, adding ±3 blocks for lower and higher notes, giving an
        # effective range between 6-12 blocks. This rolloff can be easily customized by tweaking
        # the parameters of the sigmoid function used in the calculation. This creates a harsher
        # decay/rolloff than using volume, but is necessary to achieve rolloff with a ranger smaller
        # than 16 blocks.

        def rolloff_curve(x: float) -> float:
            # slope  = -6   -> make curve steeper towards the center and mirror it in the x axis
            # offset = -0.5 -> move the curve down so its center is at y=0
            # scale  = 6    -> scale the curve so it goes from -3 to 3 as x approaches +/-inf

            # see: https://www.desmos.com/calculator/roidl8wnxl

            return sigmoid(x, -6, -0.5, 6)

        radius = 9 + rolloff_curve(self.falloff)

        stereo_offset = self.panning * stereo_separation // 2
        position = f"^{stereo_offset} ^ ^"

        return self.get_playsound_command(
            radius=radius, position=position, volume=self.volume
        )

    def play_long_range(self, stereo_separation: float = 8) -> str:
        """
        Play a sound that can be heard in a large radius by all players in range.
        """

        # This is achieved by using a large `volume` (sound will be audible at full volume
        # inside a spherical range of `volume * 16` blocks) and setting `min_volume` to 0.
        # The volume is multiplied by the `rolloff_factor` to make bass notes propagate further,
        # giving the impression of the song 'fading' away as the player moves away from the source.

        full_range = 32  # all notes will be audible at this range
        decay_range = 48  # only bass notes will be audible at this range

        min_volume = full_range // 16
        max_volume = decay_range // 16

        rolloff_factor = self.falloff

        target_volume = (
            min_volume + (max_volume - min_volume) * linear(rolloff_factor, -0.5, 0.5)
        ) * self.volume

        volume = target_volume
        radius = decay_range

        stereo_offset = self.panning * stereo_separation // 2
        position = f"^{stereo_offset} ^ ^"

        return self.get_playsound_command(
            radius=radius,
            volume=volume,
            position=position,
        )

    def get_playsound_command(
        self,
        radius: float | None = None,
        tag: str | None = None,
        source: str = "record",
        position: str = "^ ^ ^",
        volume: float = 1,
        min_volume: float = 0,
        selector: str = "@a",
    ):
        """Return the /playsound command to play the note for the given player."""

        instrument = self.instrument.replace("/", "_")

        selector_arguments = []
        if radius is not None:
            selector_arguments.append(f"distance=..{radius:.2f}")
        if tag is not None:
            selector_arguments.append(f"tag={tag}")
        target_selector = f"{selector}[{','.join(selector_arguments)}]"

        if self.pitch > 2:
            # print("Warning pitch", self.pitch, "is larger than 2", source)
            pitch = 2
        else:
            pitch = self.pitch

        if min_volume > 1:
            # print("Warning min_volume", min_volume, "is larger than 1", target_selector)
            min_volume = 1

        args = f"{instrument} {source} {target_selector} {position} {volume:.3f} {pitch:.5f} {min_volume:.3f}"
        return args


def get_notes(song: pynbs.File) -> Iterator[Tuple[int, List["PlaysoundNote"]]]:
    """Yield all the notes from the given nbs file."""

    # Quantize notes to nearest tick (pigstep always exports at 20 t/s)
    # Remove vanilla instrument notes outside the 6-octave range
    # Remove custom instrument notes outside the 2-octave range

    new_notes = []

    # Add special notes to mark the beats
    # (we'll quantize the song afterwards so doing it later on would be out of sync)
    beat_interval_ticks = 4
    if song.header.tempo > 15:
        beat_interval_ticks = 8

    for tick in range(0, song.header.song_length, beat_interval_ticks):
        song.notes.append(
            pynbs.Note(
                tick=tick,
                layer=150,
                key=45,
                instrument=-1,
            )
        )

    for note in song.notes:
        new_tick = round(note.tick * 20 / song.header.tempo)
        note.tick = new_tick
        note_pitch = note.key + note.pitch / 100
        is_custom_instrument = note.instrument >= song.header.default_instruments
        is_2_octave = TWO_OCTAVE_MIN <= note_pitch <= TWO_OCTAVE_MAX
        is_6_octave = SIX_OCTAVE_MIN <= note_pitch <= SIX_OCTAVE_MAX

        if is_custom_instrument and not is_2_octave:
            # print(
            #    f"Warning: Custom instrument out of 2-octave range at {note.tick},{note.layer}: {note_pitch}"
            # )
            continue

        if not is_custom_instrument and not is_6_octave:
            # print(
            #    f"Warning: Vanilla instrument out of 6-octave range at {note.tick},{note.layer}: {note_pitch}"
            # )
            continue

        new_notes.append(note)

    song.notes = new_notes

    # Ensure that there are as many layers as the last layer with a note
    max_layer = max(note.layer for note in song.notes)
    while len(song.layers) <= max_layer:
        song.layers.append(pynbs.Layer(id=len(song.layers)))

    # Make sure instrument paths are valid
    for instrument in song.instruments:
        instrument.file = instrument.file.lower().replace(" ", "_")
        if not instrument.file.startswith("minecraft/"):
            print(f"Warning: Invalid instrument path: {instrument.file}")

    sounds = NBS_DEFAULT_INSTRUMENTS + [
        instrument.file.replace("minecraft/", "").replace(".ogg", "")
        for instrument in song.instruments
    ]

    def get_playsound_note(note: pynbs.Note) -> PlaysoundNote:
        """Get an intermediary note for /playsound based on a pynbs note."""

        layer = song.layers[note.layer]

        sound = sounds[note.instrument % 15] if note.instrument >= 0 else "BEAT"
        pitch = note.key + (note.pitch / 100)
        octave_suffix = "_-1" if pitch < 33 else "_1" if pitch > 57 else ""
        source = f"{sound}{octave_suffix}"

        layer_volume = layer.volume / 100
        note_volume = note.velocity / 100
        instrument = sound.split(".")[-1]
        volume = layer_volume * note_volume

        falloff = get_rolloff_factor(pitch, instrument)
        panning = get_panning(note, layer)
        pitch = get_pitch(note)

        return PlaysoundNote(
            instrument=source,
            volume=volume,
            falloff=falloff,
            panning=panning,
            pitch=pitch,
        )

    output = {}

    for tick in range(0, song.header.song_length, 8):
        output[tick] = []

    for tick, chord in song:
        if tick not in output:
            output[tick] = []
        output[tick].extend(get_playsound_note(note) for note in chord)

    for tick, notes in output.items():
        yield tick, notes


def get_panning(note: Any, layer: Any) -> float:
    """Get panning for a given nbs note."""
    if layer.panning == 0:
        pan = note.panning
    else:
        pan = (layer.panning + note.panning) / 2
    pan /= 100
    return pan


def get_pitch(note: Any) -> float:
    """Get pitch for a given nbs note."""
    key = note.key + note.pitch / 100

    if key < 33:
        key -= 9
    elif key > 57:
        key -= 57
    else:
        key -= 33

    return 2 ** (key / 12) / 2


def sigmoid(x: float, slope: float = 1, offset: float = 0, scale: float = 1) -> float:
    return (1 / (1 + math.exp(-x * slope)) + offset) * scale


def linear(x: float, slope: float = 1, offset: float = 0) -> float:
    return x * slope + offset


def get_rolloff_factor(pitch: float, instrument: str) -> float:
    """
    Return the rolloff factor of a note, given its pitch and instrument.

    Maps absolute pitch onto [-1, 1]: 0 at the center of the 6-octave range
    (key 45), negative for lower pitches (travel farther), positive for higher
    pitches (travel less). Clamped so instrument octave offsets cannot push
    the factor outside that range.
    """

    # Calculate true pitch taking into account each instrument's octave offset
    real_pitch = pitch + 12 * octaves.get(instrument, 0)
    factor = (real_pitch - SIX_OCTAVE_CENTER) / SIX_OCTAVE_HALF_SPAN
    return max(-1.0, min(1.0, factor))
