__all__ = [
    "PlaysoundNote",
    "get_notes",
    "get_pitch",
]


import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, List, Tuple

import pynbs
from src.sounds import TWO_OCTAVE_HIGH, TWO_OCTAVE_LOW, SoundResource

# Logical instrument names for distance rolloff (indexed like NBS default instruments)
NBS_ROLLOFF_INSTRUMENTS = [
    "harp",
    "bass",
    "basedrum",
    "snare",
    "hat",
    "guitar",
    "flute",
    "bell",
    "chime",
    "xylophone",
    "iron_xylophone",
    "cow_bell",
    "didgeridoo",
    "bit",
    "banjo",
    "pling",
    "trumpet",
    "trumpet_exposed",
    "trumpet_weathered",
    "trumpet_oxidized",
]

_FILE_STEM_ALIASES = {
    "bassattack": "bass",
    "icechime": "chime",
    "xylobone": "xylophone",
}

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

# NBS key ranges (inclusive); 2-octave band shared with src.sounds
TWO_OCTAVE_MIN, TWO_OCTAVE_MAX = TWO_OCTAVE_LOW, TWO_OCTAVE_HIGH
SIX_OCTAVE_MIN, SIX_OCTAVE_MAX = 9, 81
SIX_OCTAVE_CENTER = (SIX_OCTAVE_MIN + SIX_OCTAVE_MAX) / 2  # 45
SIX_OCTAVE_HALF_SPAN = SIX_OCTAVE_CENTER - SIX_OCTAVE_MIN  # 36


@dataclass
class PlaysoundNote:
    """Represents a note produced by a /playsound command."""

    instrument: str = "nbs:note_harp"
    volume: float = 1
    falloff: float = 16
    pitch: float = 1
    panning: float = 0

    def play(
        self, inner_range: float, outer_range: float, stereo_separation: float = None
    ) -> str:
        """Play a sound that can be heard in a range by all players in range

        Args:
            `inner_range`: The range (in blocks) at which all frequencies of the sound will be audible at full volume.
            `outer_range`: The range (in blocks) at which all frequencies of the sound will be inaudible.
            `stereo_separation`: The separation (in blocks) between the two stereo audio channels.

        Returns:
            The `/playsound` command to play the note for the given player.
        """

        play_function = (
            self.play_short_range if outer_range <= 16 else self.play_long_range
        )

        if stereo_separation is None:  # use the function's default stereo separation
            return play_function(full_range=inner_range, decay_range=outer_range)
        else:
            return play_function(
                full_range=inner_range,
                decay_range=outer_range,
                stereo_separation=stereo_separation,
            )

    def play_short_range(
        self,
        full_range: float = 9,
        decay_range: float = 12,
        stereo_separation: float = 4,
    ) -> str:
        """
        Play a sound that can be heard in a small radius by all players in range.

        The sound will be audible at full volume inside a spherical range of `full_range` blocks.
        As the player moves away from the source, higher notes will stop being audible. At `decay_range` blocks, all notes will be inaudible.
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
        # So, the only way to achieve a gradual rolloff less than 16 blocks is by entirely limiting
        # who will be able to hear the songs at all via target selection. As such, we can use the
        # `distance` condition to play notes only to players in a certain range.
        #
        # Audible radius is centered on the midpoint of [full_range, decay_range]. Notes at the
        # center of the scale (falloff=0, key 45) use that midpoint; lower notes add up to
        # +span/2 and higher notes subtract down to -span/2.

        span = decay_range - full_range
        half_span = span / 2
        midpoint = (full_range + decay_range) / 2

        radius = midpoint + pitch_rolloff_offset(self.falloff, half_span)
        radius = clamp(radius, full_range, decay_range)

        stereo_offset = self.panning * stereo_separation // 2
        position = f"^{stereo_offset} ^ ^"

        return self.get_playsound_command(
            radius=radius, position=position, volume=self.volume
        )

    def play_long_range(
        self,
        full_range: float = 32,
        decay_range: float = 48,
        stereo_separation: float = 8,
    ) -> str:
        """
        Play a sound that can be heard in a large radius by all players in range.

        In Java Edition, `/playsound` volume ≥ 1 sets the silence distance to
        `volume * 16` blocks, with gradual falloff from the source (not a full-volume
        plateau). Bass notes use `decay_range`; treble notes use `full_range`.
        """

        # volume ≥ 1: audible range = volume * 16 (silence at that distance, minVolume=0).
        # Map falloff onto [full_range, decay_range] the same way as short-range, then
        # convert distance → playsound volume. Selector radius stays at decay_range so
        # players in the outer band still receive the command.

        span = decay_range - full_range
        half_span = span / 2
        midpoint = (full_range + decay_range) / 2

        silence_distance = midpoint + pitch_rolloff_offset(self.falloff, half_span)
        silence_distance = clamp(silence_distance, full_range, decay_range)

        # Reduce contribution of note volume because it also shrinks the audible sphere.
        # Since it's very common to use lower layer volumes, some songs are 'capped' and
        # end up not reaching the speaker's full range. At the same time, we don't want to
        # completely ignore the note volume as that would kill the song's dynamics.
        note_volume_factor = 0.5 + self.volume * 0.5
        volume = (silence_distance / 16) * note_volume_factor
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
        selector_arguments.append("tag=!nbs.nomusic")
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


def get_empty_instrument_ids(song: pynbs.File) -> list[int]:
    """Get the IDs of all instruments that have no sound file assigned."""
    return [
        instrument.id + song.header.default_instruments
        for instrument in song.instruments
        if instrument.file == ""
    ]


def get_notes(song: pynbs.File) -> Iterator[Tuple[int, List["PlaysoundNote"]]]:
    """Yield all the notes from the given nbs file."""

    # Quantize notes to nearest tick (pigstep always exports at 20 t/s)
    # Remove notes outside the 6-octave range (vanilla or custom)

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

    # Songs with tempo greater than 20 t/s are slowed down so they can be played in Minecraft
    effective_tempo = song.header.tempo

    # Special case: 'expanded' songs that only use even ticks (effectively half the tempo)
    # In Summit '26, 'Permafrost' is the only song that uses this.
    expansion_factor = 1
    if effective_tempo >= 30:
        expansion_factor = 0.5
    effective_tempo *= expansion_factor

    if effective_tempo > 20:
        effective_tempo = 20

    empty_instrument_ids = get_empty_instrument_ids(song)

    for note in song.notes:
        new_tick = round(note.tick * expansion_factor * 20 / effective_tempo)
        note.tick = new_tick
        note_pitch = note.key + note.pitch / 100
        is_6_octave = SIX_OCTAVE_MIN <= note_pitch <= SIX_OCTAVE_MAX

        if not is_6_octave:
            # print(
            #     f"Warning: Instrument out of 6-octave range at {note.tick},{note.layer}: {note_pitch}"
            # )
            continue

        if note.instrument in empty_instrument_ids:
            # No sound file assigned to instrument; ignore this note
            continue

        new_notes.append(note)

    song.notes = new_notes

    # Ensure that there are as many layers as the last layer with a note
    max_layer = max(note.layer for note in song.notes)
    while len(song.layers) <= max_layer:
        song.layers.append(pynbs.Layer(id=len(song.layers)))

    def rolloff_instrument_name(note: pynbs.Note) -> str:
        if 0 <= note.instrument < len(NBS_ROLLOFF_INSTRUMENTS):
            return NBS_ROLLOFF_INSTRUMENTS[note.instrument]
        resource = SoundResource.from_note(song, note)
        stem = Path(resource.src_path).stem
        return _FILE_STEM_ALIASES.get(stem, stem)

    def get_playsound_note(note: pynbs.Note) -> PlaysoundNote:
        """Get an intermediary note for /playsound based on a pynbs note."""

        layer = song.layers[note.layer]

        if note.instrument < 0:
            return PlaysoundNote(instrument="BEAT")

        resource = SoundResource.from_note(song, note)
        if resource is None:
            # This should never happen because we already filtered out empty instruments
            raise ValueError(f"No sound file assigned to instrument: {note.instrument}")

        source = f"nbs:{resource.sound_event}"

        note_pitch = note.key + (note.pitch / 100)
        layer_volume = layer.volume / 100
        note_volume = note.velocity / 100
        volume = layer_volume * note_volume

        falloff = get_rolloff_factor(note_pitch, rolloff_instrument_name(note))
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

    if key < TWO_OCTAVE_MIN:
        key -= 9
    elif key > TWO_OCTAVE_MAX:
        key -= 57
    else:
        key -= 33

    return 2 ** (key / 12) / 2


def sigmoid(x: float, slope: float = 1, offset: float = 0, scale: float = 1) -> float:
    return (1 / (1 + math.exp(-x * slope)) + offset) * scale


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp a value between a minimum and maximum value."""
    return max(min_value, min(value, max_value))


def pitch_rolloff_offset(falloff: float, half_span: float) -> float:
    """
    Map falloff in [-1, 1] onto exactly [-half_span, half_span].

    Low pitches (negative falloff) return positive offsets (travel farther);
    high pitches return negative offsets. Zero at the center of the scale.
    see: https://www.desmos.com/calculator/roidl8wnxl
    """
    # slope = -6, offset = -0.5 → steep S-curve centered at y=0, low→+, high→-
    raw = sigmoid(falloff, -6, -0.5, 1)
    endpoint = abs(sigmoid(1.0, -6, -0.5, 1))
    return (raw / endpoint) * half_span


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
