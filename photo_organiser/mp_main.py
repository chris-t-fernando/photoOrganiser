import multiprocessing
import time
import logging, sys
import os
from photo_organiser import argument_functions as helper
from PIL import Image, ExifTags

# logger.basicConfig(stream=sys.stderr, level=logger.DEBUG)
# logger.info("Starting up photo organiser")

logger = logging.getLogger("photo_organiser")


def run_fast_scandir(dir, ext, result_queue):  # dir: str, ext: list
    subfolders, files = [], []

    for f in os.scandir(dir):
        if f.is_dir():
            subfolders.append(f.path)
        if f.is_file():
            if os.path.splitext(f.name)[1].lower() in ext:
                # files.append(f.path)
                result_queue.put(f.path)
            else:
                logger.debug(f"{f} ignored due to filetype")

    for dir in list(subfolders):
        sf, f = run_fast_scandir(dir, ext, result_queue)
        subfolders.extend(sf)
        files.extend(f)
    return subfolders, files


#    # best tool ever https://regex101.com/
#    result = list(Path(paths["incoming_path"])).rglob(
#        "*.[jJmMpPhH][pPoOnNeE][gGvV4iI][cC]?"
#    )
#


class ImageFile:
    filename = None
    validImage = False
    exif = None

    def __init__(self, filename):
        self.filename = filename
        # get file size

        # get folder

        # get file attributes (last modified etc)

        # this stuff requires some knowledge of what file type it is
        # next steps: turn ImageFile into an interface, and then implement those in different types eg HEICImageFile
        # this means that the constructor can just do stuff like call gettagging and leave it to HEICImageFile to implement that in a way that makes sense for HEICs
        # validate that it's actually an image
        try:
            img = Image.open(filename)  # open the image file
            self.validImage = img.verify()  # verify that it is, in fact an image
            print(f"valid image: {filename}")
        except (IOError, SyntaxError) as e:
            print("Bad file:", filename)  # print out the names of corrupt files
            raise

        # get exif
        self.exif = {
            ExifTags.TAGS[k]: v for k, v in img._getexif().items() if k in ExifTags.TAGS
        }


class ProcessorConsumer(multiprocessing.Process):
    def __init__(self, task_queue, result_queue):
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        proc_name = self.name
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                # Poison pill means shutdown
                logger.info(f"{proc_name}: Queue exhausted, shutting down")
                self.result_queue.put(-1)
                self.task_queue.task_done()
                break
            try:
                thisImage = ImageFile(next_task)
                logger.info(f"{next_task}: Valid image, proceeding to processing")
            except Exception as e:
                logger.error(f"{next_task}: Invalid image, skipping")
            self.result_queue.put(f"Finished processing {next_task}")


class SearchConsumer(multiprocessing.Process):
    def __init__(self, task_queue, result_queue):
        multiprocessing.Process.__init__(self)
        self.task_queue = task_queue
        self.result_queue = result_queue

    def run(self):
        ext = [".mov", ".jpg", ".heic", ".mp4", ".png", ".jpeg", ".3gp", ".avi"]
        proc_name = self.name
        while True:
            next_task = self.task_queue.get()
            if next_task is None:
                # Poison pill means shutdown
                logger.info(f"{proc_name}: Queue exhausted, shutting down")
                self.result_queue.put(None)
                self.task_queue.task_done()
                break

            logger.info(
                f"Search process named {proc_name} received message from queue: {next_task}"
            )
            run_fast_scandir(next_task, ext, self.result_queue)
        return


def main():
    paths = helper.validate_arguments(sys.argv)

    if paths == False:
        logger.error("Invalid parameters.  Exiting")
        # sys.exit(-1)
    else:
        logger.debug("Paths is good")

    ### SEARCHER PROCESS ###
    # establish communication queues
    search_tasks = (
        multiprocessing.JoinableQueue()
    )  # overkill given I'm only allowing one input path - could just pass the string
    search_results = multiprocessing.JoinableQueue()

    # start searchers
    search_consumer = SearchConsumer(search_tasks, search_results)
    search_consumer.start()

    # push the incoming search path into the search process
    search_tasks.put(paths["incoming_path"])

    # poison pill to close search process
    search_tasks.put(None)

    # search_tasks.join()

    ### PROCESSOR PROCESS ###
    processor_results = multiprocessing.Queue()

    # Start processors
    num_consumers = multiprocessing.cpu_count() * 2
    print(f"Creating {num_consumers} consumers")
    processor_consumers = [
        ProcessorConsumer(search_results, processor_results)
        for i in range(num_consumers)
    ]

    for w in processor_consumers:
        w.start()

    processors_finished = False
    # Start outputting results
    while not processors_finished:
        thisProcessorResult = processor_results.get()
        # poison pill, we're done here
        if thisProcessorResult == -1:
            processors_finished = True
            print(f"Exhausted output queue")
            # poison pill to kill processors
            search_results.put(None)
            break
        else:
            print(f"Result: {thisProcessorResult}")
