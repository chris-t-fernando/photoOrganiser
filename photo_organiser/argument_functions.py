import logging

# import os.path
from os import path

# from pathlib import Path


def get_argument(arguments, search_argument):
    found = False
    for s in search_argument:
        if s in arguments:
            try:
                logging.debug(
                    f"Found argument {search_argument}.  Value is {arguments[arguments.index(s)+1]}"
                )
                return arguments[arguments.index(s) + 1]
            except Exception as e:
                return False

    return False


def validate_arguments(arguments):
    valid_arguments = True

    incoming_path = get_argument(arguments, ["--input", "-i"])
    output_path = get_argument(arguments, ["--output", "-o"])

    if incoming_path == False or output_path == False:
        valid_arguments = False

    if not path.exists(incoming_path):
        logging.error(f"Invalid incoming path: {incoming_path}")
        valid_arguments = False

    if not path.exists(output_path):
        logging.error(f"Invalid output path: {output_path}")
        valid_arguments = False

    if not valid_arguments:
        logging.error(f"Correct usage:")
        logging.error(f'{__file__} --input "c:\\some directory" --output c:\\myphotos')
        return False

    return_paths = {}
    return_paths["incoming_path"] = incoming_path
    return_paths["output_path"] = output_path

    return return_paths


def get_mov_timestamps(filename):
    ''' Get the creation and modification date-time from .mov metadata.

        Returns None if a value is not available.
    '''
    from datetime import datetime as DateTime
    import struct

    ATOM_HEADER_SIZE = 8
    # difference between Unix epoch and QuickTime epoch, in seconds
    EPOCH_ADJUSTER = 2082844800

    creation_time = modification_time = None

    # search for moov item
    with open(filename, "rb") as f:
        while True:
            atom_header = f.read(ATOM_HEADER_SIZE)
            #~ print('atom header:', atom_header)  # debug purposes
            if atom_header[4:8] == b'moov':
                break  # found
            else:
                atom_size = struct.unpack('>I', atom_header[0:4])[0]
                f.seek(atom_size - 8, 1)

        # found 'moov', look for 'mvhd' and timestamps
        atom_header = f.read(ATOM_HEADER_SIZE)
        if atom_header[4:8] == b'cmov':
            raise RuntimeError('moov atom is compressed')
        elif atom_header[4:8] != b'mvhd':
            raise RuntimeError('expected to find "mvhd" header.')
        else:
            f.seek(4, 1)
            creation_time = struct.unpack('>I', f.read(4))[0] - EPOCH_ADJUSTER
            creation_time = DateTime.fromtimestamp(creation_time)
            if creation_time.year < 1990:  # invalid or censored data
                creation_time = None

            modification_time = struct.unpack('>I', f.read(4))[0] - EPOCH_ADJUSTER
            modification_time = DateTime.fromtimestamp(modification_time)
            if modification_time.year < 1990:  # invalid or censored data
                modification_time = None

    return creation_time, modification_time