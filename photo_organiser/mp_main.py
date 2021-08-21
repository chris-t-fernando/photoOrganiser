import multiprocessing
from multiprocessing import Manager
import logging, sys
import os
import pathlib
import hashlib
import datetime
from photo_organiser import argument_functions
from photo_organiser import imagefile
import exiftool
import csv

# logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
# logger.info("Starting up photo organiser")

imageLogger = logging.getLogger("ImageFile")
logger = logging.getLogger("photo_organiser")

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
imageLogger.setLevel(logging.ERROR)
logger.setLevel(logging.INFO)

log_file = open("photo_organiser.log", "w")
log_writer = csv.writer(log_file, delimiter=",", quotechar='"')


def write_log(
    process,
    action,
    input_file,
    destination_file,
    message,
    input_comparison,
    destination_comparison,
):
    log_writer.writerow(
        [
            datetime.datetime.now().strftime("%H:%M:%S"),
            process,
            action,
            input_file,
            destination_file,
            message,
            input_comparison,
            destination_comparison,
        ]
    )
    log_file.flush()


# consolidate this down later
def select_date_metadata(metadata):
    search_tags = [
        "EXIF:CreateDate",
        "EXIF:DateTimeOriginal",
        "Composite:DateTimeCreated",
        "QuickTime:CreateDate",
        "QuickTime:TrackCreateDate",
        "QuickTime:MediaCreateDate",
        "RIFF:DateTimeOriginal",
    ]
    metadata_keys = metadata.keys()
    for tag in search_tags:
        if tag in metadata.keys():
            return datetime.datetime.strptime(metadata[tag], "%Y:%m:%d %H:%M:%S")
    return False


def get_hash(file):
    BLOCK_SIZE = 65536  # The size of each read from the file

    file_hash = (
        hashlib.sha256()
    )  # Create the hash object, can use something other than `.sha256()` if you wish
    with open(file, "rb") as f:  # Open the file to read it's bytes
        fb = f.read(BLOCK_SIZE)  # Read from the file. Take in the amount declared above
        while len(fb) > 0:  # While there is still data being read from the file
            file_hash.update(fb)  # Update the hash
            fb = f.read(BLOCK_SIZE)  # Read the next block from the file

    return file_hash.hexdigest()  # Get the hexadecimal digest of the hash


def run_fast_scandir(dir, ext, output_queue):  # dir: str, ext: list
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
        if counter == 100:
            output_queue.put(batch)
            batch = []
            counter = 0

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


class ProcessorConsumer(multiprocessing.Process):
    def __init__(self, input_queue, output_queue):
        multiprocessing.Process.__init__(self)
        self.input_queue = input_queue
        self.output_queue = output_queue

    def run(self):
        proc_name = self.name
        processed = 0
        while True:
            action = None
            message = None
            input_comparison = None
            destination_comparison = None

            next_task = self.input_queue.get()

            if next_task is None:
                # Poison pill means shutdown
                logger.info(
                    f"{proc_name}: Finished processing execution instructions.  Process exiting successfully."
                )
                self.output_queue.put(None)
                self.input_queue.task_done()
                break
            processed += 1

            # do the thing
            # first check if the destination folder exists
            # start with year
            yearFolder = next_task.destination_root + "\\" + next_task.destination_year
            if not os.path.isdir(yearFolder):
                try:
                    os.mkdir(yearFolder)
                except Exception as e:
                    logger.error(
                        f"{proc_name}: Unable to create directory {yearFolder}.  Error: {str(e)}"
                    )
                    continue

            # then month
            if not os.path.isdir(next_task.destination_folder):
                try:
                    os.mkdir(next_task.destination_folder)
                except Exception as e:
                    logger.error(
                        f"{proc_name}: Unable to create directory {next_task.destination_folder}.  Error: {str(e)}"
                    )
                    continue

            if os.path.isfile(next_task.destination_fullpath):
                # file exists
                # (size, modify date, and hash if need be)
                fname = pathlib.Path(next_task.destination_fullpath)
                fstat = fname.stat()
                dest_file_size = fstat.st_size
                dest_file_modify_date = datetime.datetime.fromtimestamp(fstat.st_mtime)

                replace_dest = False
                replace_reason = None

                # if new file is bigger than existing, then assume new is good
                if dest_file_size < next_task.file_size:
                    replace_dest = True
                    replace_reason = f"file size (input={next_task.file_size} existing={dest_file_size})"
                    message = "file size"
                    input_comparison = next_task.file_size
                    destination_comparison = dest_file_size
                # if content is the same
                elif next_task.get_hash() == get_hash(next_task.destination_fullpath):
                    replace_dest = False
                    replace_reason = "hashes match"
                    message = "hashes match"
                    input_comparison = next_task.get_hash()
                    destination_comparison = next_task.get_hash()
                else:
                    with exiftool.ExifTool() as et:
                        d = et.get_metadata(next_task.destination_fullpath)
                        # metadata = et.get_metadata_batch(next_task.destination_fullpath)
                        # for d in metadata:
                        # get tags
                        destination_metadata_date = select_date_metadata(d)

                        # couldn't find any metadata, so fall back on file stat
                        if destination_metadata_date == False:
                            # if the new file has tags, use them
                            if next_task.tag_date != None:
                                replace_reason = f'file modify date (input={next_task.tag_date.strftime("%Y-%m-%d")}(exif) existing={dest_file_modify_date.strftime("%Y-%m-%d")}(file))'
                                message = "file modify date (exif vs file)"
                                input_comparison = next_task.tag_date.strftime(
                                    "%Y-%m-%d"
                                )
                                destination_comparison = dest_file_modify_date.strftime(
                                    "%Y-%m-%d"
                                )
                                if dest_file_modify_date < next_task.tag_date:
                                    # if the existing file was modified more recently than the new file
                                    # keep the existing file, since its older
                                    replace_dest = False

                                else:
                                    # if the existing file was modified less recently than the new file
                                    # replace the existing with the new file
                                    replace_dest = True

                            # new file does not have tags either
                            else:
                                replace_reason = f'file modify date (input={next_task.file_modify.strftime("%Y-%m-%d")} existing={dest_file_modify_date.strftime("%Y-%m-%d")})'
                                message = "file modify date (file vs file)"
                                input_comparison = next_task.file_modify.strftime(
                                    "%Y-%m-%d"
                                )
                                destination_comparison = dest_file_modify_date.strftime(
                                    "%Y-%m-%d"
                                )
                                if dest_file_modify_date < next_task.file_modify:
                                    # if the existing file was modified more recently than the new file
                                    # keep the existing file, since its older
                                    replace_dest = False
                                else:
                                    # if the existing file was modified less recently than the new file
                                    # replace the existing with the new file
                                    replace_dest = True

                        # found metadata, so use that
                        else:
                            replace_reason = f"tag modify date (input={next_task.destination_date} existing={destination_metadata_date})"
                            message = "file modify date (exif vs exif)"
                            input_comparison = next_task.destination_date.strftime(
                                "%Y-%m-%d"
                            )
                            destination_comparison = destination_metadata_date.strftime(
                                "%Y-%m-%d"
                            )
                            if destination_metadata_date > next_task.destination_date:
                                # if the existing file was modified more recently than the new file
                                # replace the existing with the new file
                                replace_dest = True
                            else:
                                replace_dest = False

                if replace_dest:
                    logger.debug(
                        f"{proc_name}: REPLACE (input={next_task.source_fullpath} existing={next_task.destination_fullpath}) - {replace_reason}"
                    )
                    action = "REPLACE"

                    # os.replace(
                    #    next_task.source_fullpath, next_task.destination_fullpath
                    # )
                else:
                    logger.debug(
                        f"{proc_name}: RETAIN (input={next_task.source_fullpath} existing={next_task.destination_fullpath}) - {replace_reason}"
                    )
                    action = "RETAIN"
                    # os.remove(next_task.source_fullpath)

            else:
                # file does not exist, so just go ahead and copy it now
                logger.debug(
                    f"{proc_name}: NEW (input={next_task.source_fullpath} existing={next_task.destination_fullpath})"
                )
                action = "NEW"
                # os.rename(next_task.source_fullpath, next_task.destination_fullpath)
            write_log(
                process=proc_name,
                action=action,
                input_file=next_task.source_fullpath,
                destination_file=next_task.destination_fullpath,
                message=message,
                input_comparison=input_comparison,
                destination_comparison=destination_comparison,
            )

            if processed % 1000 == 0:
                logger.info(f"{proc_name}: Processed {processed} files")


class ExifConsumer(multiprocessing.Process):
    def __init__(self, input_queue, output_queue, destination_root):
        multiprocessing.Process.__init__(self)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.destination_root = destination_root

    def run(self):
        proc_name = self.name
        files_media = 0
        files_skipped = 0
        files_total = 0
        while True:
            next_task = self.input_queue.get()

            if next_task is None:
                # Poison pill means shutdown
                logger.info(
                    f"{proc_name}: Finished exif analysis. Found {files_total} in total ({files_media} valid, {files_skipped} ignored). Process exiting successfully."
                )
                self.output_queue.put(None)
                self.input_queue.put(None)
                # self.input_queue.task_done()
                break

            with exiftool.ExifTool() as et:
                metadata = et.get_metadata_batch(next_task)
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
    def __init__(self, input_queue, output_queue, manager_dict):
        multiprocessing.Process.__init__(self)
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.manager_dict = manager_dict

    def run(self):
        ext = [".mov", ".jpg", ".heic", ".mp4", ".png", ".jpeg", ".3gp", ".avi"]
        proc_name = self.name
        self.manager_dict["Search"] = "Searching..."
        while True:
            next_task = self.input_queue.get()
            if next_task is None:
                # Poison pill means shutdown
                self.manager_dict[
                    "Search"
                ] = f"{proc_name}: Search process finished. Ignored a total of {len(ignored)} files"
                self.output_queue.put(None)
                # pass on the poison pill
                self.input_queue.put(None)
                # self.input_queue.task_done()
                break

            sf, f, ignored = run_fast_scandir(next_task, ext, self.output_queue)

        return


# Flow:
# 1. SearchConsumer (1 process) starts searching for files, makes batch of 100 at a time and pushes them to exifqueue
# 2. ExifConsumer (4 processes) picks them up and instantiates ImageFile and pushes them to execution queue
# 3. ProcessorConsumer queue (1 process) then compares with any existing file (size, modify date, and hash if need be)
#    and makes the change
def main():
    paths = argument_functions.validate_arguments(sys.argv)

    if paths == False:
        logger.error("Invalid parameters.  Exiting")
        # sys.exit(-1)
    else:
        logger.debug("Paths is good")

    manager = Manager()
    managerDict = manager.dict()

    ### SEARCHER PROCESS ###
    # establish communication queues
    search_tasks = (
        multiprocessing.JoinableQueue()
    )  # overkill given I'm only allowing one input path - could just pass the string
    search_results = multiprocessing.JoinableQueue()

    # start searchers
    search_consumer = SearchConsumer(search_tasks, search_results, managerDict)
    search_consumer.start()

    # push the incoming search path into the search process
    search_tasks.put(paths["incoming_path"])

    # poison pill to close search process
    search_tasks.put(None)

    # search_tasks.join()

    ### EXIF PROCESS ###
    exif_results = multiprocessing.JoinableQueue()

    # Start exif consumers
    num_consumers = multiprocessing.cpu_count() * 2
    # for debugging
    # num_consumers = 1
    logging.debug(f"exif_results: Creating {num_consumers} consumers")
    exif_consumers = [
        ExifConsumer(search_results, exif_results, paths["output_path"])
        for i in range(num_consumers)
    ]

    for w in exif_consumers:
        w.start()

    ### PROCESSOR er.. PROCESS ###
    processor_results = multiprocessing.Queue()

    # start processor processes
    processor_consumer = ProcessorConsumer(exif_results, processor_results)
    processor_consumer.start()

    # Start outputting results
    while True:
        if "Search" in managerDict.keys():
            print(f"BLABLAH: {managerDict['Search']}")
        thisProcessorResult = processor_results.get()
        # poison pill, we're done here
        if thisProcessorResult == None:
            print(f"Exhausted output queue")
            # poison pill to kill exif consumers
            # is this even needed?
            # search_results.put(None)
            # exif_results.put(None)
            log_file.close()
            exit()
        else:
            print(f"Result: {thisProcessorResult }")
