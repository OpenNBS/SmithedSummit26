import logging
from dataclasses import dataclass
from enum import Enum
from io import BytesIO

import pynbs
import samplerate
import soundfile as sf
from beet import Context, Sound, SoundConfig
from beet.contrib.vanilla import ClientJar, Vanilla
from src.config import SONGS_PATH

DEFAULT_SOUNDS = [
    "minecraft/note/harp.ogg",
    "minecraft/note/bassattack.ogg",
    "minecraft/note/basedrum.ogg",
    "minecraft/note/snare.ogg",
    "minecraft/note/hat.ogg",
    "minecraft/note/guitar.ogg",
    "minecraft/note/flute.ogg",
    "minecraft/note/bell.ogg",
    "minecraft/note/icechime.ogg",
    "minecraft/note/xylobone.ogg",
    "minecraft/note/iron_xylophone.ogg",
    "minecraft/note/cow_bell.ogg",
    "minecraft/note/didgeridoo.ogg",
    "minecraft/note/bit.ogg",
    "minecraft/note/banjo.ogg",
    "minecraft/note/pling.ogg",
    "minecraft/note/trumpet.ogg",
    "minecraft/note/trumpet_exposed.ogg",
    "minecraft/note/trumpet_weathered.ogg",
    "minecraft/note/trumpet_oxidized.ogg",
]

# NBS key range for the unshifted 2-octave sample (inclusive)
TWO_OCTAVE_LOW = 33
TWO_OCTAVE_HIGH = 57

SUBTITLE = "subtitles.block.note_block.note"


@dataclass
class OctaveOffset:
    value: int
    suffix: str


class OctaveOffsetEnum(Enum):
    HIGH = OctaveOffset(24, "_high")
    LOW = OctaveOffset(-24, "_low")
    NONE = OctaveOffset(0, "")


@dataclass(frozen=True)
class SoundResource:
    src_path: str
    octave_offset: OctaveOffsetEnum

    @classmethod
    def from_note(cls, song: pynbs.File, note: pynbs.Note) -> "SoundResource":
        return map_note_to_sound_resource(song, note)

    @property
    def key_offset(self) -> int:
        return self.octave_offset.value.value

    @property
    def _relative_stem(self) -> str:
        """Path under sounds/ without .ogg, e.g. note/basedrum."""
        return self.src_path.removeprefix("minecraft/").removesuffix(".ogg")

    @property
    def resource_location(self) -> str:
        """Vanilla asset-index / mount path."""
        return f"assets/minecraft/sounds/{self._relative_stem}.ogg"

    @property
    def vanilla_sound_key(self) -> str:
        """Key in vanilla.assets['minecraft'].sounds."""
        return self._relative_stem

    @property
    def vanilla_sound_name(self) -> str:
        """sounds.json file reference for the unpitched vanilla sample."""
        return f"minecraft:{self.vanilla_sound_key}"

    @property
    def pack_sound_path(self) -> str:
        """Path under assets/nbs/sounds/ (no .ogg)."""
        return f"{self._relative_stem}{self.octave_offset.value.suffix}"

    @property
    def sound_event(self) -> str:
        """Key in nbs sounds.json → plays as nbs:{sound_event}."""
        return self.pack_sound_path.replace("/", "_")


def map_note_to_sound_resource(song: pynbs.File, note: pynbs.Note) -> SoundResource:
    """Map a note to a sound file and octave variant. Single source of truth for RP + playsound."""

    is_higher = note.key > TWO_OCTAVE_HIGH
    is_lower = note.key < TWO_OCTAVE_LOW
    is_custom_instrument = note.instrument >= song.header.default_instruments

    if is_custom_instrument:
        custom_index = note.instrument - song.header.default_instruments
        instrument = song.instruments[custom_index]
        sound_path = instrument.file.lower().replace(" ", "_")
    else:
        sound_path = DEFAULT_SOUNDS[note.instrument]

    if is_higher:
        octave_offset = OctaveOffsetEnum.HIGH
    elif is_lower:
        octave_offset = OctaveOffsetEnum.LOW
    else:
        octave_offset = OctaveOffsetEnum.NONE

    return SoundResource(sound_path, octave_offset)


def get_song_custom_sounds(song: pynbs.File) -> set[SoundResource]:
    sound_files: set[SoundResource] = set()
    for note in song.notes:
        if note.instrument < 0:
            continue
        sound_files.add(map_note_to_sound_resource(song, note))
    return sound_files


def get_all_custom_sounds(song_manifest: dict) -> set[SoundResource]:
    sound_files: set[SoundResource] = set()

    logging.info(f"Processing custom sounds for {len(song_manifest)} songs")

    for song_data in song_manifest:
        song_id = song_data["id"]
        song_file = SONGS_PATH / f"{song_id}.nbs"

        if not song_file.exists():
            logging.warning(f"Song file not found: {song_file}")
            continue

        song = pynbs.read(song_file)
        extra_sounds = get_song_custom_sounds(song)
        sound_files.update(extra_sounds)
        logging.info(f"Added {len(extra_sounds)} custom sounds for song: {song_id}")

    logging.info(f"Found {len(sound_files)} unique custom sounds")
    return sound_files


# libvorbis stack-overflows on Windows when encoding large buffers in one write
# (bastibe/python-soundfile#396). Chunk to keep vorbis_analysis_wrote small.
OGG_WRITE_FRAMES = 4096


def pitch_shift_ogg(ogg_bytes: bytes, semitones: int) -> bytes:
    """Varispeed pitch shift: raise/lower pitch and shorten/lengthen duration together."""
    data, sr = sf.read(BytesIO(ogg_bytes), dtype="float32", always_2d=True)
    factor = 2 ** (semitones / 12)
    shifted = samplerate.resample(data, 1 / factor, "sinc_best")
    out = BytesIO()
    with sf.SoundFile(
        out,
        mode="w",
        samplerate=sr,
        channels=shifted.shape[1],
        format="OGG",
        subtype="VORBIS",
    ) as sound_file:
        for start in range(0, len(shifted), OGG_WRITE_FRAMES):
            sound_file.write(shifted[start : start + OGG_WRITE_FRAMES])
    return out.getvalue()


def load_vanilla_ogg(jar: ClientJar, resource: SoundResource) -> bytes | None:
    """Fetch raw ogg bytes for a vanilla sound via the asset index."""

    try:
        sound = jar.assets["minecraft"].sounds[resource.vanilla_sound_key]
    except KeyError:
        logging.warning(f"Sound not found in vanilla assets: {resource.vanilla_sound_key}")

        return

    return sound.get_content()


def generate_sounds(ctx: Context, sound_list: set[SoundResource]) -> None:
    vanilla = ctx.inject(Vanilla)
    jar = vanilla.releases[ctx.minecraft_version].mount(fetch_objects=True)

    sound_config: dict = {}

    for resource in sound_list:
        event = resource.sound_event

        if resource.octave_offset is OctaveOffsetEnum.NONE:
            sound_config[event] = {
                "sounds": [resource.vanilla_sound_name],
                "subtitle": SUBTITLE,
            }
            continue

        
        if (ogg_bytes := load_vanilla_ogg(jar, resource)) is None:
            continue

        shifted = pitch_shift_ogg(ogg_bytes, resource.key_offset)
        ctx.assets["nbs"].sounds[resource.pack_sound_path] = Sound(shifted)
        sound_config[event] = {
            "sounds": [resource.pack_sound_path],
            "subtitle": SUBTITLE,
        }

    ctx.assets["nbs"].sound_config = SoundConfig(sound_config)
    logging.info(f"Registered {len(sound_config)} sound events under nbs")


def beet_default(ctx: Context):
    song_manifest = ctx.meta["song_manifest"]
    sound_resources = get_all_custom_sounds(song_manifest)
    logging.info("Adding custom sounds to sound config")
    generate_sounds(ctx, sound_resources)
