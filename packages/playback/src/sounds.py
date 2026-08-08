import logging
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path

import pynbs
import samplerate
import soundfile as sf
from beet import Context, ResourcePack, Sound, SoundConfig
from beet.contrib.vanilla import AssetIndex, Vanilla

from nbs_shared.manifest import SongManifest
from src.config import SONGS_PATH
from src.utilities.parallel import map_as_completed
from src.utilities.songs_cache import (
    cache_sounds_draft,
    songs_cache,
    songs_cache_key,
)

logger = logging.getLogger(__name__)

DEFAULT_SOUNDS = [
    "minecraft/note/harp.ogg",
    "minecraft/note/bass.ogg",
    "minecraft/note/bd.ogg",
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
    def from_note(cls, song: pynbs.File, note: pynbs.Note) -> SoundResource | None:
        return map_note_to_sound_resource(song, note)

    @property
    def key_offset(self) -> int:
        return self.octave_offset.value.value

    @property
    def _relative_stem(self) -> str:
        """Path under sounds/ without .ogg, e.g. `note/harp`."""
        return self.src_path.removeprefix("minecraft/").removesuffix(".ogg")

    @property
    def resource_location(self) -> str:
        """Vanilla asset-index / mount path."""
        return f"assets/minecraft/sounds/{self._relative_stem}.ogg"

    @property
    def vanilla_sound_key(self) -> str:
        """Key in `vanilla.assets['minecraft'].sounds`."""
        return self._relative_stem

    @property
    def pack_sound_path(self) -> str:
        """Path under `assets/nbs/sounds/` (no .ogg)."""
        return f"{self._relative_stem}{self.octave_offset.value.suffix}"

    @property
    def mono_pack_sound_path(self) -> str:
        """Path under `assets/nbs/sounds/` for a forced-mono copy (no .ogg)."""
        return f"{self.pack_sound_path}_mono"

    @property
    def sound_name(self) -> str:
        """`sounds.json` file reference with the correct namespace."""
        namespace = (
            "minecraft" if self.octave_offset is OctaveOffsetEnum.NONE else "nbs"
        )
        return f"{namespace}:{self.pack_sound_path}"

    @property
    def mono_sound_name(self) -> str:
        """`sounds.json` file reference for a forced-mono copy under `nbs`."""
        return f"nbs:{self.mono_pack_sound_path}"

    @property
    def sound_event(self) -> str:
        """Key in `nbs/sounds.json` → plays as `nbs:{sound_event}`."""
        return self.pack_sound_path.replace("/", ".")


@dataclass(frozen=True)
class PitchShiftTask:
    resource: SoundResource
    ogg_bytes: bytes


@dataclass(frozen=True)
class MonoConvertTask:
    resource: SoundResource
    ogg_bytes: bytes


def map_note_to_sound_resource(
    song: pynbs.File, note: pynbs.Note
) -> SoundResource | None:
    """Map a note to a sound file and octave variant. Single source of truth for RP + playsound."""

    pitch = note.key + note.pitch / 100

    is_higher = pitch > TWO_OCTAVE_HIGH
    is_lower = pitch < TWO_OCTAVE_LOW
    is_custom_instrument = note.instrument >= song.header.default_instruments

    if is_custom_instrument:
        custom_index = note.instrument - song.header.default_instruments
        instrument = song.instruments[custom_index]
        sound_path = instrument.file.lower().replace(" ", "_")
    else:
        sound_path = DEFAULT_SOUNDS[note.instrument]

    if sound_path == "":
        # No sound file assigned to instrument; ignore this note
        return None

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
        if sound_resource := map_note_to_sound_resource(song, note):
            sound_files.add(sound_resource)
    return sound_files


def collect_song_sounds(song_id: str) -> frozenset[SoundResource]:
    """Worker entrypoint: read one NBS file and collect its sound resources."""

    song = pynbs.read(SONGS_PATH / f"{song_id}.nbs")
    return frozenset(get_song_custom_sounds(song))


def get_all_custom_sounds(song_manifest: SongManifest) -> set[SoundResource]:
    sound_files: set[SoundResource] = set()
    song_ids: list[str] = []

    logger.info("Processing custom sounds for %d songs", len(song_manifest))

    for song_data in song_manifest:
        song_id = song_data["id"]
        song_file = SONGS_PATH / f"{song_id}.nbs"
        if not song_file.exists():
            logger.warning("Song file not found: %s", song_file)
            continue
        song_ids.append(song_id)

    for song_id, extra_sounds in map_as_completed(
        collect_song_sounds,
        song_ids,
        item_id=str,
        thread_name_prefix="sound-scanner",
        failure_message="Failed to scan sounds for song: %s",
    ):
        sound_files.update(extra_sounds)
        logger.debug("Added %d custom sounds for song: %s", len(extra_sounds), song_id)

    logger.info("Found %d unique custom sounds", len(sound_files))
    return sound_files


# libvorbis stack-overflows on Windows when encoding large buffers in one write
# (bastibe/python-soundfile#396). Chunk to keep vorbis_analysis_wrote small.
OGG_WRITE_FRAMES = 4096


def to_mono(data):
    """Average multi-channel audio to a single channel. Expects shape (frames, channels)."""
    if data.shape[1] == 1:
        return data
    return data.mean(axis=1, keepdims=True)


def is_mono_ogg(ogg_bytes: bytes) -> bool:
    """Return True if the OGG already has a single channel."""
    return sf.info(BytesIO(ogg_bytes)).channels == 1


def write_mono_ogg(data, sr: int) -> bytes:
    """Encode mono float32 frames as OGG/Vorbis."""
    out = BytesIO()
    with sf.SoundFile(
        out,
        mode="w",
        samplerate=sr,
        channels=1,
        format="OGG",
        subtype="VORBIS",
    ) as sound_file:
        for start in range(0, len(data), OGG_WRITE_FRAMES):
            sound_file.write(data[start : start + OGG_WRITE_FRAMES])
    return out.getvalue()


def to_mono_ogg(ogg_bytes: bytes) -> bytes:
    """Decode an OGG and re-encode it as mono without changing pitch or duration."""
    data, sr = sf.read(BytesIO(ogg_bytes), dtype="float32", always_2d=True)
    return write_mono_ogg(to_mono(data), sr)


def pitch_shift_ogg(ogg_bytes: bytes, semitones: int) -> bytes:
    """Varispeed pitch shift: raise/lower pitch and shorten/lengthen duration together."""
    data, sr = sf.read(BytesIO(ogg_bytes), dtype="float32", always_2d=True)
    data = to_mono(data)
    factor = 2 ** (semitones / 12)
    shifted = samplerate.resample(data, 1 / factor, "sinc_best")
    return write_mono_ogg(shifted, sr)


def load_vanilla_ogg(asset_index: AssetIndex, resource: SoundResource) -> bytes | None:
    """Fetch a vanilla OGG, retrying once if its cached object is corrupt."""

    try:
        path = Path(asset_index[resource.resource_location])
    except KeyError:
        logger.warning(
            "Sound not found in vanilla assets: %s", resource.vanilla_sound_key
        )
        return None

    ogg_bytes = path.read_bytes()
    if ogg_bytes.startswith(b"OggS"):
        return ogg_bytes

    logger.warning(
        "Invalid cached vanilla sound, downloading it again: %s",
        resource.vanilla_sound_key,
    )
    path.unlink(missing_ok=True)
    path = Path(asset_index.missing(resource.resource_location))
    ogg_bytes = path.read_bytes()

    if not ogg_bytes.startswith(b"OggS"):
        raise ValueError(
            f"Vanilla sound is not a valid OGG: {resource.vanilla_sound_key}"
        )

    return ogg_bytes


def pitch_shift_task(task: PitchShiftTask) -> bytes:
    """Worker entrypoint: pitch-shift one preloaded vanilla OGG."""

    try:
        return pitch_shift_ogg(task.ogg_bytes, task.resource.key_offset)
    except sf.LibsndfileError as err:
        raise ValueError(
            f"Failed to decode vanilla sound: {task.resource.vanilla_sound_key}"
        ) from err


def convert_to_mono_task(task: MonoConvertTask) -> bytes:
    """Worker entrypoint: re-encode one preloaded vanilla OGG as mono."""

    try:
        return to_mono_ogg(task.ogg_bytes)
    except sf.LibsndfileError as err:
        raise ValueError(
            f"Failed to decode vanilla sound: {task.resource.vanilla_sound_key}"
        ) from err


def generate_sounds(
    ctx: Context, assets: ResourcePack, sound_list: set[SoundResource]
) -> None:
    vanilla = ctx.inject(Vanilla)
    release = vanilla.releases[ctx.minecraft_version]
    asset_index = release.object_mapping.files
    if not isinstance(asset_index, AssetIndex):
        raise TypeError(
            "Expected AssetIndex from vanilla object mapping, "
            f"got {type(asset_index).__name__}"
        )

    sound_config: dict = {}
    pitch_tasks: list[PitchShiftTask] = []
    mono_tasks: list[MonoConvertTask] = []

    # Resolve vanilla samples on the main thread so AssetIndex cache repairs stay
    # single-threaded. Only the CPU-bound encode steps run in the worker pool.
    for resource in sound_list:
        logger.debug("Generating sound for %s", resource.pack_sound_path)
        event = resource.sound_event

        if resource.octave_offset is OctaveOffsetEnum.NONE:
            # Keep playsound as nbs:<sound_event>. Point at vanilla when already
            # mono; otherwise ship an nbs:*_mono copy and alias the same event.
            if (ogg_bytes := load_vanilla_ogg(asset_index, resource)) is None:
                sound_config[event] = {
                    "sounds": [resource.sound_name],
                    "subtitle": SUBTITLE,
                }
                continue

            if is_mono_ogg(ogg_bytes):
                sound_config[event] = {
                    "sounds": [resource.sound_name],
                    "subtitle": SUBTITLE,
                }
            else:
                logger.info(
                    "Vanilla sound is stereo; converting to mono: %s",
                    resource.vanilla_sound_key,
                )
                mono_tasks.append(MonoConvertTask(resource, ogg_bytes))
            continue

        if (ogg_bytes := load_vanilla_ogg(asset_index, resource)) is None:
            continue

        pitch_tasks.append(PitchShiftTask(resource, ogg_bytes))

    # Beet pack containers aren't thread-safe. Merge completed samples here.
    for task, mono_bytes in map_as_completed(
        convert_to_mono_task,
        mono_tasks,
        item_id=lambda task: task.resource.vanilla_sound_key,
        thread_name_prefix="sound-mono",
        failure_message="Failed to mono-convert sound: %s",
    ):
        resource = task.resource
        assets["nbs"].sounds[resource.mono_pack_sound_path] = Sound(mono_bytes)
        sound_config[resource.sound_event] = {
            "sounds": [resource.mono_sound_name],
            "subtitle": SUBTITLE,
        }

    for task, shifted in map_as_completed(
        pitch_shift_task,
        pitch_tasks,
        item_id=lambda task: task.resource.vanilla_sound_key,
        thread_name_prefix="sound-pitcher",
        failure_message="Failed to pitch-shift sound: %s",
    ):
        resource = task.resource
        assets["nbs"].sounds[resource.pack_sound_path] = Sound(shifted)
        sound_config[resource.sound_event] = {
            "sounds": [resource.sound_name],
            "subtitle": SUBTITLE,
        }

    assets["nbs"].sound_config = SoundConfig(sound_config)
    logger.info("Registered %d sound events under nbs", len(sound_config))


def beet_default(ctx: Context):
    song_manifest = ctx.meta["song_manifest"]
    cache_key = songs_cache_key(ctx)

    with ctx.generate.draft() as draft:
        cache_sounds_draft(draft, songs_cache(ctx), cache_key)
        sound_resources = get_all_custom_sounds(song_manifest)
        logger.info("Adding custom sounds to sound config")
        generate_sounds(ctx, draft.assets, sound_resources)
