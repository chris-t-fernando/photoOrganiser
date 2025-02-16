import multiprocessing
from multiprocessing import JoinableQueue
import logging
import os
import datetime
from photo_organiser import imagefile
import exiftool
import csv
from typing import Tuple

logger = logging.getLogger("photo_organiser")
logger.setLevel(logging.INFO)


def run_fast_scandir(
    dir, ext: list, output_queue: JoinableQueue
) -> Tuple[list, list, list]:  # dir: str, ext: list
    subfolders, files, ignored = [], [], []

    for f in os.scandir(dir):
        if f.is_dir():
            subfolders.append(f.path)
        if f.is_file():
            if os.path.splitext(f.name)[1].lower() in ext:
                files.append(f.path)
            else:
                logger.debug(f"{f} ignored due to filetype")
                ignored.append(f.path)

    batch = []
    counter = 0
    for f in files:
        batch.append(f)
        counter += 1
        if counter == 400:
            output_queue.put(batch)
            batch = []
            counter = 0

    # for any extras left in the batch beyond the last 100
    if len(batch) > 0:
        output_queue.put(batch)

    for dir in list(subfolders):
        sf, f, ign = run_fast_scandir(dir, ext, output_queue)
        subfolders.extend(sf)
        files.extend(f)
        ignored.extend(ign)

    return subfolders, files, ignored


#    # best tool ever https://regex101.com/
#    result = list(Path(paths["incoming_path"])).rglob(
#        "*.[jJmMpPhH][pPoOnNeE][gGvV4iI][cC]?"
#    )
#


class ExifConsumer(multiprocessing.Process):
    input_queue: JoinableQueue
    output_queue: JoinableQueue
    destination_root: str

    def __init__(self, input_queue, output_queue, destination_root):
        multiprocessing.Process.__init__(self)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.destination_root = destination_root

    def run(self) -> None:
        proc_name = self.name
        files_media = 0
        files_skipped = 0
        files_total = 0

        while True:
            next_task = self.input_queue.get()

            if next_task is None:
                # Poison pill means shutdown
                logger.debug(
                    f"{proc_name}: Finished exif analysis. Found {files_total} in total ({files_media} valid, {files_skipped} ignored). Process exiting successfully."
                )
                self.output_queue.put(None)
                self.input_queue.put(None)
                break
            error_encountered = False
            with exiftool.ExifToolHelper() as et:
                try:
                    metadata = et.get_metadata(next_task)
                except Exception as e:
                    error_encountered = True

            # find out which file in the batch caused the error - need to run get_metadata file by file to do it
            if error_encountered:
                for task in next_task:
                    try:
                        metadata = et.get_metadata(task)
                    except Exception as e:
                        print(
                            f"Error on {task} - usually this is caused by bad characters in the filesystem path"
                        )
                        exit()
                print(
                    f"Shouldn't have gotten here - only ran this block of code to find the failure in the batch, but wasn't able to re-create it when running file by file"
                )
                exit()

            for d in metadata:
                # now fan out - create images out of each directory search batch
                files_total += 1
                try:
                    self.output_queue.put(
                        imagefile.ImageFile(
                            source_fullpath=d["SourceFile"],
                            destination_root=self.destination_root,
                            metadata=d,
                        )
                    )
                    logging.debug(
                        f"{d['SourceFile']}: Pushed new media object to queue"
                    )
                    files_media += 1
                    if files_total % 100 == 0:
                        logging.debug(
                            f"{proc_name}: Found {files_total} so far. {files_media} are valid media, {files_skipped} were ignored."
                        )

                except imagefile.ImageNotValidError as e:
                    logging.debug(
                        f"{proc_name}: {d['SourceFile']}: Invalid media object.  Skipped"
                    )
                    files_skipped += 1


class SearchConsumer(multiprocessing.Process):
    input_queue: JoinableQueue
    output_queue: JoinableQueue

    def __init__(self, input_queue, output_queue):
        multiprocessing.Process.__init__(self)
        self.input_queue = input_queue
        self.output_queue = output_queue

    def run(self) -> None:
        ext = [".mov", ".jpg", ".heic", ".mp4", ".png", ".jpeg", ".3gp", ".avi", ".jpe"]
        proc_name = self.name
        while True:
            next_task = self.input_queue.get()
            if next_task is None:
                # Poison pill means shutdown
                self.output_queue.put(None)
                # pass on the poison pill
                self.input_queue.put(None)
                # self.input_queue.task_done()
                break

            sf, f, ignored = run_fast_scandir(next_task, ext, self.output_queue)

        ignored_file = open("ignored.log", "w", newline="", encoding="utf-8")
        ignored_writer = csv.writer(ignored_file, delimiter=",", quotechar='"')
        for igfile in ignored:
            ignored_writer.writerow([igfile])
        ignored_file.close()

        return


class StatusConsumer(multiprocessing.Process):
    input_queue: JoinableQueue

    def __init__(self, input_queue):
        multiprocessing.Process.__init__(self)
        self.input_queue = input_queue

    def run(self) -> None:
        proc_name = self.name
        last_state = {}
        while True:
            next_task = self.input_queue.get()
            if next_task is None:
                # Poison pill means shutdown
                self.input_queue.put(None)
                self.input_queue.task_done()
                break

            # assume next_task is a dict
            # next_task['proc_name'] = "ProcessorConsumer4"
            # next_task['queue_size'] = 500
            # next_task['processed'] = 10
            last_state[next_task["proc_name"]] = next_task

            # if seconds % 5 == 0 then show a status update
            #
            a = datetime.datetime.now()
            if a.second % 5 == 0:
                for t in last_state:
                    print(f'{t["proc_name"]}')
                pass

        return
