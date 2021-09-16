import multiprocessing
import logging, sys
import os
import shutil
import datetime
from photo_organiser import argumentparser
from photo_organiser import imagefile
from photo_organiser import statemachine
from photo_organiser import photoprocesses
import csv

imageLogger = logging.getLogger("imagefile")
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


# Flow:
# 1. SearchConsumer (1 process) starts searching for files, makes batch of 100 at a time and pushes them to exifqueue
# 2. ExifConsumer (4 processes) picks them up and instantiates ImageFile and pushes them to execution queue
def main():
    paths = argumentparser.ArgumentParser(sys.argv)

    if paths.valid_arguments == False:
        print(f"Invalid parameters.  Exiting")
        exit()
    else:
        logger.debug("Paths is good")

    state_machine = statemachine.PhotoMachine(paths.output_path)

    ### SEARCHER PROCESS ###
    # establish communication queues
    search_tasks = (
        multiprocessing.JoinableQueue()
    )  # overkill given I'm only allowing one input path - could just pass the string
    search_results = multiprocessing.JoinableQueue()

    # start searchers
    search_consumer = photoprocesses.SearchConsumer(search_tasks, search_results)
    search_consumer.start()

    # push the incoming search path into the search process
    search_tasks.put(paths.incoming_path)

    # poison pill to close search process
    search_tasks.put(None)

    ### EXIF PROCESS ###
    exif_results = multiprocessing.JoinableQueue()

    # Start exif consumers
    if paths.debug:
        num_consumers = 1
    else:
        num_consumers = multiprocessing.cpu_count() * 2

    logging.debug(f"exif_results: Creating {num_consumers} consumers")
    exif_consumers = [
        photoprocesses.ExifConsumer(search_results, exif_results, paths.output_path)
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

                    if paths.dryrun == False:
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
                        if paths.dryrun == False:
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


if __name__ == "__main__":
    main()
