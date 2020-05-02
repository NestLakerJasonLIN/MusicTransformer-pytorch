import pickle
import os
import sys
from progress.bar import Bar
import utils
from midi_processor_mtracks.processor_mtracks import encode_midi, encode_midi_mtracks


def preprocess_midi(path):
    return encode_midi(path)


def preprocess_midi_files_under(midi_root, save_dir):
    midi_paths = list(utils.find_files_by_extensions(midi_root, ['.mid', '.midi']))
    os.makedirs(save_dir, exist_ok=True)
    out_fmt = '{}-{}.data'

    for path in Bar('Processing').iter(midi_paths):
        print(' ', end='[{}]'.format(path), flush=True)

        try:
            data = preprocess_midi(path)
        except KeyboardInterrupt:
            print(' Abort')
            return
        except EOFError:
            print('EOF Error')
            return

        with open('{}/{}.pickle'.format(save_dir, path.split('/')[-1]), 'wb') as f:
            pickle.dump(data, f)

def preprocess_midi_mtracks(path):
    return encode_midi_mtracks(path)

def preprocess_midi_files_under_mtracks(midi_root, save_dir):
    midi_paths = list(utils.find_files_by_extensions(midi_root, ['.mid', '.midi']))
    os.makedirs(save_dir, exist_ok=True)
    out_fmt = '{}-{}.data'

    if save_dir[-1] != '/':
        save_dir += '/'

    for path in Bar('Processing').iter(midi_paths):
        print(' ', end='[{}]'.format(path), flush=True)

        try:
            data_mtracks = preprocess_midi_mtracks(path)
        except KeyboardInterrupt:
            print(' Abort')
            return
        except EOFError:
            print('EOF Error')
            return

        for inst, data in data_mtracks.items():
            save_path = save_dir + inst
            with open('{}/{}.pickle'.format(save_path, path.split('/')[-1]), 'wb') as f:
                pickle.dump(data, f)


if __name__ == '__main__':
    if sys.argv[3] == 'separate':
        print("processing multi-tracks separately...")
        preprocess_midi_files_under_mtracks(
            midi_root=sys.argv[1],
            save_dir=sys.argv[2])
    else:
        print("processing multi-tracks as a whole...")
        preprocess_midi_files_under(
                midi_root=sys.argv[1],
                save_dir=sys.argv[2])
