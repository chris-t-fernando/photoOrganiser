# shamelessly stolen from https://www.tutorialspoint.com/python/python_multithreading.htm

import queue
import threading
import time
import logging, sys
import os.path
from os import path
import pytest
from pathlib import Path

logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

logging.info("Starting")


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


class search_thread(threading.Thread):
    def __init__(self, threadID, name, q, paths):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.q = q

    def run(self):
        logging.info(f"Starting {self.name}")
        ext = ["mov", "jpg", "heic", "mp4", "png"]
        subfolders, files = run_fast_scandir(paths["incoming_path"], ext)
        logging.info(f"Exiting {self.name}")


def run_fast_scandir(dir, ext):  # dir: str, ext: list
    subfolders, files = [], []

    for f in os.scandir(dir):
        if f.is_dir():
            subfolders.append(f.path)
        if f.is_file():
            if os.path.splitext(f.name)[1].lower() in ext:
                files.append(f.path)

    for dir in list(subfolders):
        sf, f = run_fast_scandir(dir, ext)
        subfolders.extend(sf)
        files.extend(f)
    return subfolders, files


#    # best tool ever https://regex101.com/
#    result = list(Path(paths["incoming_path"])).rglob(
#        "*.[jJmMpPhH][pPoOnNeE][gGvV4iI][cC]?"
#    )
#

paths = validate_arguments(sys.argv)

if paths == False:
    logging.error("Invalid parameters.  Exiting")
    # sys.exit(-1)
else:
    logging.warning("Paths is good")


q = queue.Queue()
threadList = ["Finder-1"]
threads = []
threadID = 1

# files to analyse
pThreadList = ["Worker-1","Worker-2","Worker-3","Worker-4"]
pThreads = []
pThreadID = 1

# Create new threads
for tName in threadList:
    thread = search_thread(threadID, tName, q, paths)
    thread.start()
    threads.append(thread)
    threadID += 1

# Create new threads
for ptName in threadList:
    pThread = search_thread(threadID, tName, q, paths)
    thread.start()
    threads.append(thread)
    threadID += 1
