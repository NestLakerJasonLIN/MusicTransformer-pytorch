import pretty_midi

NUM_TRACKS = 5
RANGE_NOTE_ON = 128 * NUM_TRACKS
RANGE_NOTE_OFF = 128 * NUM_TRACKS
RANGE_VEL = 32
RANGE_TIME_SHIFT = 100

START_IDX = {
    'note_on': 0,
    'note_off': RANGE_NOTE_ON,
    'time_shift': RANGE_NOTE_ON + RANGE_NOTE_OFF,
    'velocity': RANGE_NOTE_ON + RANGE_NOTE_OFF + RANGE_TIME_SHIFT
}

INSTRUMENT_OFFSET = {
    'Drums': 128 * 0,
    'Piano': 128 * 1,
    'Guitar': 128 * 2,
    'Bass': 128 * 3,
    'Strings': 128 * 4
}

IDX_TO_INSTRUMENT = {
    0: 'Drums',
    1: 'Piano',
    2: 'Guitar',
    3: 'Bass',
    4: 'Strings'
}

INSTRUMENT_TO_FIELDS = {
    'Drums': {'program': 0, 'is_drum': True},
    'Piano': {'program': 0, 'is_drum': False},
    'Guitar': {'program': 24, 'is_drum': False},
    'Bass': {'program': 32, 'is_drum': False},
    'Strings': {'program': 48, 'is_drum': False},
}

class SustainAdapter:
    def __init__(self, time, type):
        self.start =  time
        self.type = type


class SustainDownManager:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.managed_notes = []
        self._note_dict = {} # key: pitch, value: note.start

    def add_managed_note(self, note: pretty_midi.Note):
        self.managed_notes.append(note)

    def transposition_notes(self):
        for note in reversed(self.managed_notes):
            try:
                note.end = self._note_dict[note.pitch]
            except KeyError:
                note.end = max(self.end, note.end)
            self._note_dict[note.pitch] = note.start


# Divided note by note_on, note_off
class SplitNote:
    def __init__(self, type, time, value, velocity, instrument):
        ## type: note_on, note_off
        self.type = type
        self.time = time
        self.velocity = velocity
        self.value = value
        self.instrument = instrument

    def __repr__(self):
        return '<[SNote] time: {} type: {}, value: {}, velocity: {}, instrument: {}>'\
            .format(self.time, self.type, self.value, self.velocity, self.instrument)


class Event:
    # Differentiate different instrument notes
    def __init__(self, event_type, value, instrument=None):
        self.type = event_type
        self.value = value
        assert instrument is not None if event_type in ['note_on', 'note_off'] else instrument is None
        self.instrument = instrument

    def __repr__(self):
        return '<Event type: {}, value: {}>'.format(self.type, self.value)

    def to_int(self):
        if self.instrument is not None:
            return START_IDX[self.type] + INSTRUMENT_OFFSET[self.instrument] + self.value
        else:
            return START_IDX[self.type] + self.value

    @staticmethod
    def from_int(int_value):
        info = Event._type_check(int_value)
        if info['type'] in ['note_on', 'note_off']:
            assert 'instrument' in info
            return Event(info['type'], info['value'], info['instrument'])
        else:
            return Event(info['type'], info['value'])

    @staticmethod
    def _type_check(int_value):
        range_note_on = range(0, RANGE_NOTE_ON)
        range_note_off = range(RANGE_NOTE_ON, RANGE_NOTE_ON+RANGE_NOTE_OFF)
        range_time_shift = range(RANGE_NOTE_ON+RANGE_NOTE_OFF,RANGE_NOTE_ON+RANGE_NOTE_OFF+RANGE_TIME_SHIFT)

        valid_value = int_value

        if int_value in range_note_on:
            return {'type': 'note_on', 'value': int_value % 128, 'instrument': IDX_TO_INSTRUMENT[int_value // 128]}
        elif int_value in range_note_off:
            valid_value -= RANGE_NOTE_ON
            return {'type': 'note_off', 'value': valid_value % 128, 'instrument': IDX_TO_INSTRUMENT[valid_value // 128]}
        elif int_value in range_time_shift:
            valid_value -= (RANGE_NOTE_ON + RANGE_NOTE_OFF)
            return {'type': 'time_shift', 'value': valid_value}
        else:
            valid_value -= (RANGE_NOTE_ON + RANGE_NOTE_OFF + RANGE_TIME_SHIFT)
            return {'type': 'velocity', 'value': valid_value}


def _divide_note(notes, instrument):
    result_array = []
    notes.sort(key=lambda x: x.start)

    for note in notes:
        on = SplitNote('note_on', note.start, note.pitch, note.velocity, instrument)
        off = SplitNote('note_off', note.end, note.pitch, None, instrument)
        result_array += [on, off]
    return result_array


def _merge_note(snote_sequence):
    note_on_dicts = {}
    result_arrays = {}

    for instrument in INSTRUMENT_OFFSET:
        note_on_dicts[instrument] = {}
        result_arrays[instrument] = []

    for snote in snote_sequence:
        # print(note_on_dict)
        if snote.type == 'note_on':
            note_on_dicts[snote.instrument][snote.value] = snote
        elif snote.type == 'note_off':
            try:
                on = note_on_dicts[snote.instrument][snote.value]
                off = snote
                if off.time - on.time == 0:
                    continue
                result = pretty_midi.Note(on.velocity, snote.value, on.time, off.time)
                result_arrays[snote.instrument].append(result)
            except:
                print('info removed pitch: {}'.format(snote.value))
    return result_arrays


def _snote2events(snote: SplitNote, prev_vel: int):
    result = []
    if snote.velocity is not None:
        modified_velocity = snote.velocity // 4
        if prev_vel != modified_velocity:
            result.append(Event(event_type='velocity', value=modified_velocity))
    result.append(Event(event_type=snote.type, value=snote.value, instrument=snote.instrument))
    return result


def _event_seq2snote_seq(event_sequence):
    timeline = 0
    velocity = 0
    snote_seq = []

    for event in event_sequence:
        if event.type == 'time_shift':
            timeline += ((event.value+1) / 100)
        if event.type == 'velocity':
            velocity = event.value * 4
        else:
            snote = SplitNote(event.type, timeline, event.value, velocity, event.instrument)
            snote_seq.append(snote)
    return snote_seq


def _make_time_sift_events(prev_time, post_time):
    time_interval = int(round((post_time - prev_time) * 100))
    results = []
    while time_interval >= RANGE_TIME_SHIFT:
        results.append(Event(event_type='time_shift', value=RANGE_TIME_SHIFT-1))
        time_interval -= RANGE_TIME_SHIFT
    if time_interval == 0:
        return results
    else:
        return results + [Event(event_type='time_shift', value=time_interval-1)]


def _control_preprocess(ctrl_changes):
    sustains = []

    manager = None
    for ctrl in ctrl_changes:
        if ctrl.value >= 64 and manager is None:
            # sustain down
            manager = SustainDownManager(start=ctrl.time, end=None)
        elif ctrl.value < 64 and manager is not None:
            # sustain up
            manager.end = ctrl.time
            sustains.append(manager)
            manager = None
        elif ctrl.value < 64 and len(sustains) > 0:
            sustains[-1].end = ctrl.time
    return sustains


def _note_preprocess(susteins, notes):
    note_stream = []

    for sustain in susteins:
        for note_idx, note in enumerate(notes):
            if note.start < sustain.start:
                note_stream.append(note)
            elif note.start > sustain.end:
                notes = notes[note_idx:]
                sustain.transposition_notes()
                break
            else:
                sustain.add_managed_note(note)

    for sustain in susteins:
        note_stream += sustain.managed_notes

    note_stream.sort(key= lambda x: x.start)
    return note_stream


def encode_midi(file_path):
    events = []
    dnotes = []
    mid = pretty_midi.PrettyMIDI(midi_file=file_path)

    # scan all instruments and store into dict <instrument, split_note_list>
    for inst in mid.instruments:
        inst_notes = inst.notes
        dnotes += _divide_note(inst_notes, inst.name)

    # print(dnotes)
    dnotes.sort(key=lambda x: x.time)
    # print('sorted:')
    # print(dnotes)
    cur_time = 0
    cur_vel = 0
    for snote in dnotes:
        events += _make_time_sift_events(prev_time=cur_time, post_time=snote.time)
        events += _snote2events(snote=snote, prev_vel=cur_vel)
        # events += _make_time_sift_events(prev_time=cur_time, post_time=snote.time)

        cur_time = snote.time
        cur_vel = snote.velocity

    return [e.to_int() for e in events]

def encode_midi_mtracks(file_path):
    instrument_events = {}
    events = []
    dnotes = []
    mid = pretty_midi.PrettyMIDI(midi_file=file_path)

    # scan all instruments and store into dict <instrument, split_note_list>
    for inst in mid.instruments:
        inst_notes = inst.notes
        dnotes += _divide_note(inst_notes, inst.name)

        # print(dnotes)
        dnotes.sort(key=lambda x: x.time)
        # print('sorted:')
        # print(dnotes)
        cur_time = 0
        cur_vel = 0
        for snote in dnotes:
            events += _make_time_sift_events(prev_time=cur_time, post_time=snote.time)
            events += _snote2events(snote=snote, prev_vel=cur_vel)
            # events += _make_time_sift_events(prev_time=cur_time, post_time=snote.time)

            cur_time = snote.time
            cur_vel = snote.velocity

        instrument_events[inst.name] = [e.to_int() for e in events]

    return instrument_events

def decode_midi(idx_array, file_path=None):
    event_sequence = [Event.from_int(idx) for idx in idx_array]
    # print(event_sequence)
    snote_seq = _event_seq2snote_seq(event_sequence)
    note_seqs = _merge_note(snote_seq)

    mid = pretty_midi.PrettyMIDI()

    for instrument, note_seq in note_seqs.items():
        note_seq.sort(key=lambda x:x.start)
        # if want to change instrument, see https://www.midi.org/specifications/item/gm-level-1-sound-set
        program, is_drum = INSTRUMENT_TO_FIELDS[instrument]['program'], INSTRUMENT_TO_FIELDS[instrument]['is_drum']
        instrument = pretty_midi.Instrument(program, is_drum, instrument)
        instrument.notes = note_seq

        mid.instruments.append(instrument)
    if file_path is not None:
        mid.write(file_path)
    return mid


if __name__ == '__main__':
    encoded = encode_midi('bin/ADIG04.mid')
    print(encoded)
    decided = decode_midi(encoded,file_path='bin/test.mid')

    ins = pretty_midi.PrettyMIDI('bin/ADIG04.mid')
    print(ins)
    print(ins.instruments[0])
    for i in ins.instruments:
        print(i.control_changes)
        print(i.notes)

