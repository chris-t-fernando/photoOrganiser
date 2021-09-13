import multiprocessing
import logging, sys
import os
import shutil
import datetime
from photo_organiser import argument_functions
from photo_organiser import imagefile
import exiftool
import csv
from pprint import pprint

# logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
# logger.info("Starting up photo organiser")

imageLogger = logging.getLogger("ImageFile")
logger = logging.getLogger("photo_organiser")

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
imageLogger.setLevel(logging.ERROR)
logger.setLevel(logging.INFO)

log_file = open("photo_organiser.log", "w", newline="")
log_writer = csv.writer(log_file, delimiter=",", quotechar='"')
log_writer.writerow(
    [
        "Log date",
        "Destination",
        "Source",
        "Winner?",
        "Reason",
        "Source size",
        "Source hash",
        "Source date",
        "Destination size",
        "Destination hash",
        "Destination date",
    ]
)


def write_log(
    destination_image,
    source_image,
    winner,
    reason,
    source_size,
    source_hash,
    source_date,
    #    destination_size,
    #    destination_hash,
    #    destination_date,
):
    log_writer.writerow(
        [
            datetime.datetime.now().strftime("%H:%M:%S"),
            destination_image,
            source_image,
            winner,
            reason,
            source_size,
            source_hash,
            source_date,
            #            destination_size,
            #            destination_hash,
            #            destination_date,
        ]
    )


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
                logger.debug(
                    f"{proc_name}: Finished exif analysis. Found {files_total} in total ({files_media} valid, {files_skipped} ignored). Process exiting successfully."
                )
                self.output_queue.put(None)
                self.input_queue.put(None)
                break
            error_encountered = False
            with exiftool.ExifTool() as et:
                try:
                    metadata = et.get_metadata_batch(next_task)
                except Exception as e:
                    error_encountered = True

            if error_encountered:
                for task in next_task:
                    try:
                        metadata = et.get_metadata_batch(task)
                    except Exception as e:
                        print(f"Error on {task}")
                        exit()
                print(f"Shouldn't have gotten here?!")
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
    def __init__(self, input_queue, output_queue):
        multiprocessing.Process.__init__(self)
        self.input_queue = input_queue
        self.output_queue = output_queue

    def run(self):
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
    def __init__(self, input_queue):
        multiprocessing.Process.__init__(self)
        self.input_queue = input_queue

    def run(self):
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


# Flow:
# 1. SearchConsumer (1 process) starts searching for files, makes batch of 100 at a time and pushes them to exifqueue
# 2. ExifConsumer (4 processes) picks them up and instantiates ImageFile and pushes them to execution queue
def main():
    paths = argument_functions.validate_arguments(sys.argv)

    if paths == False:
        logger.error("Invalid parameters.  Exiting")
    else:
        logger.debug("Paths is good")

    state_machine = imagefile.PhotoMachine(paths["output_path"])

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

    ### EXIF PROCESS ###
    exif_results = multiprocessing.JoinableQueue()

    # Start exif consumers
    if paths["debug"]:
        num_consumers = 1
    else:
        num_consumers = multiprocessing.cpu_count() * 2

    logging.debug(f"exif_results: Creating {num_consumers} consumers")
    exif_consumers = [
        ExifConsumer(search_results, exif_results, paths["output_path"])
        for i in range(num_consumers)
    ]

    for w in exif_consumers:
        w.start()

    # Start outputting results
    while True:
        thisExifResult = exif_results.get()

        # poison pill, we're done here
        if thisExifResult == None:
            logger.debug(f"All queues exhausted - finished multiprocessing")
            print(f"Processing exif for existing files", end="\r")
            state_machine.process_exif()

            print(f"\nProcessing decisions", end="\r")
            state_machine.decide()

            print(f"Writing decision log", end="\r")
            # first pass for logging
            counter_written = 0
            for destination_image in state_machine.ImageObjects_by_destination:
                for source_image in state_machine.ImageObjects_by_destination[
                    destination_image
                ]:
                    # for source in destination_image:
                    write_log(
                        destination_image=destination_image,
                        source_image=source_image,
                        winner=str(
                            state_machine.ImageObjects_by_source[source_image].winner
                        ),
                        reason=state_machine.ImageObjects_by_source[
                            source_image
                        ].reason,
                        source_size=state_machine.ImageObjects_by_source[
                            source_image
                        ].file_size,
                        source_hash=state_machine.ImageObjects_by_source[
                            source_image
                        ].file_hash,
                        source_date=state_machine.ImageObjects_by_source[
                            source_image
                        ].destination_year
                        + "-"
                        + state_machine.ImageObjects_by_source[
                            source_image
                        ].destination_month,
                    )
                    counter_written += 1
                    print(
                        f"\rWriting decisions for {len(state_machine.ImageObjects_by_source)} input files ({round(counter_written/len(state_machine.ImageObjects_by_source)*100,1)}% decisions out of {len(state_machine.ImageObjects_by_source)} input files)        ",
                        end="\r",
                    )

            print(f"\nExecuting decisions", end="\r")
            # second pass for losers (deletes)
            counter_deleted = 0
            for source_image in state_machine.ImageObjects_by_source:
                if state_machine.ImageObjects_by_source[source_image].winner == False:
                    logger.debug(f"{source_image}: Deleting loser")

                    if paths["dryrun"] == False:
                        try:
                            os.remove(
                                state_machine.ImageObjects_by_source[
                                    source_image
                                ].source_fullpath
                            )
                        except Exception as e:
                            print(
                                f"Failed to delete {state_machine.ImageObjects_by_source[source_image].source_fullpath} due to {str(e)}"
                            )

                    counter_deleted += 1
                    print(
                        f"\rExecuting actions for {len(state_machine.ImageObjects_by_source)} input files. Deleted: {counter_deleted}, Moved: 0, Remaining: {len(state_machine.ImageObjects_by_source)-counter_deleted} ({round(counter_deleted / len(state_machine.ImageObjects_by_source)*100,1)}%)        ",
                        end="\r",
                    )

            # get a list of the destination folders and make sure they all exist
            # todo: rework the ImageObjects_by_destination structure so that it has a pointer to the winner
            years = {}

            for source_image in state_machine.ImageObjects_by_source:
                if state_machine.ImageObjects_by_source[source_image].winner == True:
                    this_winner = state_machine.ImageObjects_by_source[source_image]
                    if this_winner.destination_year not in years.keys():
                        years[this_winner.destination_year] = set()

                    years[this_winner.destination_year].add(
                        this_winner.destination_month
                    )

            for year in years.keys():
                this_year_folder = (
                    state_machine.ImageObjects_by_source[source_image].destination_root
                    + "/"
                    + year
                )

                if not os.path.isdir(this_year_folder):
                    # it doesn't exist so make it
                    os.mkdir(this_year_folder)

                for month in years[year]:
                    this_month_folder = this_year_folder + "/" + month
                    if not os.path.isdir(this_month_folder):
                        # it doesn't exist so make it
                        os.mkdir(this_month_folder)

            counter_moved = 0
            # third pass for winners.  Do pass two and three separately so that we don't move something and then delete it later - ordering is important
            for source_image in state_machine.ImageObjects_by_source:
                if state_machine.ImageObjects_by_source[source_image].winner == True:
                    if (
                        state_machine.ImageObjects_by_source[
                            source_image
                        ].source_fullpath
                        == state_machine.ImageObjects_by_source[
                            source_image
                        ].destination_fullpath
                    ):
                        # don't need to do anything - the file in situ is the right one
                        logger.debug(
                            f"{source_image}: Winner already in place, skipping"
                        )
                    else:
                        logger.debug(
                            f"{source_image}: Moving winner to {state_machine.ImageObjects_by_source[source_image].destination_fullpath}"
                        )
                        if paths["dryrun"] == False:
                            try:
                                shutil.move(
                                    state_machine.ImageObjects_by_source[
                                        source_image
                                    ].source_fullpath,
                                    state_machine.ImageObjects_by_source[
                                        source_image
                                    ].destination_fullpath,
                                )
                            except Exception as e:
                                print(
                                    f"Failed to move {state_machine.ImageObjects_by_source[source_image].source_fullpath} to {state_machine.ImageObjects_by_source[source_image].destination_fullpath} due to {str(e)}"
                                )

                    counter_moved += 1

                print(
                    f"\rExecuting decisions for {len(state_machine.ImageObjects_by_source)} input files. Deleted: {counter_deleted}, Moved: {counter_moved}, Remaining: {len(state_machine.ImageObjects_by_source)-counter_deleted-counter_moved} ({round((counter_deleted+counter_moved) / len(state_machine.ImageObjects_by_source)*100,1)}% complete)             ",
                    end="\r",
                )

            logger.debug("\nFinished executing state machine actions, cleaning up")

            for w in exif_consumers:
                w.terminate()

            search_consumer.terminate()

            # close the queues so that we can exit cleanly
            log_file.close()
            search_tasks.close()
            search_results.close()
            exif_results.close()

            logger.debug("\nSuccessfully exiting!")

            exit()
        else:
            # processed a new image, add it to the state machine
            state_machine.add_image(thisExifResult)
