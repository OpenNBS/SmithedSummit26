import pynbs

DEFAULT_INSTRUMENT = pynbs.Instrument(id=0, name="", file="")

# F#4: default key of every vanilla sample and of `ins.key` in OpenNBS.
DEFAULT_KEY = DEFAULT_INSTRUMENT.pitch


def get_instrument(song: pynbs.File, note: pynbs.Note) -> pynbs.Instrument:
    if note.instrument >= song.header.default_instruments:
        instrument = song.instruments[note.instrument - song.header.default_instruments]
    else:
        instrument = DEFAULT_INSTRUMENT

    return instrument


def get_compensated_key(note: pynbs.Note, instrument: pynbs.Instrument) -> float:
    """Return the pitch-compensated key for a given NBS note."""

    instrument_key_offset = instrument.pitch - DEFAULT_KEY
    return note.key + instrument_key_offset + note.pitch / 100
