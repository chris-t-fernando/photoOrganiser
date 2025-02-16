import logging
import os
import exiftool
from photo_organiser import imagefile

logger = logging.getLogger("statemachine")
logger.setLevel(logging.WARN)


class PhotoMachine:
    # this holds a dict of the ImageObjects
    ImageObjects_by_source = {}

    # this holds a dict of references to the image - allows me to search for source images that want to create this destination image
    # the reference here is the destination_fullpath, and this contains an array. looks like this:
    # ImageObjects_by_destination["c:/dest/foo.jpg"][0] = "c:/source/folder1/foo.jpg"
    # ImageObjects_by_destination["c:/dest/foo.jpg"][1] = "c:/source/folder2/foo.jpg"
    ImageObjects_by_destination = {}

    # holds a list of destination paths that already exist and therefore need to be exif'd
    existing_images = []

    def __init__(self, destination_root):
        self.destination_root = destination_root

    def add_image(self, the_image: imagefile.ImageFile) -> None:
        # store the image
        self.ImageObjects_by_source[the_image.source_fullpath] = the_image

        # check if this is the first source image that has wanted to write to this destination
        if (
            the_image.destination_fullpath
            not in self.ImageObjects_by_destination.keys()
        ):
            # a List to hold a reference back to the source file - can be used for lookups against ImageObjects_by_source
            self.ImageObjects_by_destination[the_image.destination_fullpath] = []

            # there's some special logic here - there might be a file that already exists at that destination
            if os.path.isfile(the_image.destination_fullpath):
                # there's a file there
                self.existing_images.append(the_image.destination_fullpath)

            # no else needed - don't care if there's not a file there

        self.ImageObjects_by_destination[the_image.destination_fullpath].append(
            the_image.source_fullpath
        )

    def process_exif(self) -> None:
        this_batch = []
        batches = 0

        # loop through all of the existing images
        for f in self.existing_images:
            # batch them into groups of 400
            this_batch.append(f)

            if len(this_batch) == 400:
                # do the batch of 400
                self.process_exif_batch(this_batch)
                batches += 1
                files_complete = batches * 400
                # \x1b[1K
                print(
                    f"Processing exif for {len(self.existing_images)} existing files ({round(files_complete / len(self.existing_images) * 100,1)}% complete)",
                    end="\r",
                )

                # its done, so reset to an empty List
                this_batch = []

        # if there is more than 0 but less than 100 in the queue (last batch)
        if len(this_batch) > 0:
            self.process_exif_batch(this_batch)
            print(
                f"Processed exif for {len(self.existing_images)} existing files (100% complete)          ",
                end="\r",
            )

    def process_exif_batch(self, this_batch: list) -> None:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(this_batch)

        for d in metadata:
            self.add_image(
                imagefile.ImageFile(
                    source_fullpath=d["SourceFile"],
                    destination_root=self.destination_root,
                    metadata=d,
                )
            )

    # return True if new is better than existing
    # or False if they're the same or existing is better
    def is_better(
        self, new: imagefile.ImageFile, existing: imagefile.ImageFile
    ) -> bool:
        # check size
        if new.file_size > existing.file_size:
            return True, "file size is larger"

        # check mod date - if new is older, go with it (maybe it got edited or stat updated or something)
        if new.tag_date < existing.tag_date:
            return True, "tag date is older"

        # check hash - if its the same file, then the existing isn't better
        if new.get_hash() == existing.get_hash():
            if new.destination_root in new.source_fullpath:
                return True, "hash matches, keep in situ destination file"
            else:
                return False, "hash matches"

        # file size is the same, contents are different, but existing has older modified stamp
        # if one of the comparison files is in the output path already, then take it - to reduce IO (assuming they're on different volumes)
        if new.destination_root in new.source_fullpath:
            return True, "default, keep in situ destination file"
        else:
            return False, "default"

    def decide(self) -> None:
        files_complete = 0
        # loop through the competitors for best destination_image
        for destination_image in self.ImageObjects_by_destination:
            files_complete += 1

            # need to work out which one is the best option
            # this just resets the holder per destination_image
            best_option = None

            # for each contender
            for source_image in self.ImageObjects_by_destination[destination_image]:
                # if there hasn't been another contender yet - something is better than nothing
                if best_option == None:
                    best_option = source_image
                    logging.debug(
                        f"there is no best_option, so {best_option} is the winner"
                    )
                    self.ImageObjects_by_source[best_option].set_winner(
                        True, "uncontested"
                    )

                else:
                    # there's something to compare against.  Pulled the logic out inot a separate method for ease of understanding and testing
                    is_better, reason = self.is_better(
                        self.ImageObjects_by_source[source_image],
                        self.ImageObjects_by_source[best_option],
                    )
                    if is_better:
                        # this source is better than the previous best option
                        # first tell the old winner that it isn't any more
                        self.ImageObjects_by_source[best_option].set_winner(
                            False, reason
                        )

                        logger.debug(
                            f"best_option {best_option} is not better than contender {source_image} - replacing"
                        )

                        # now set best_option to the new winner
                        best_option = source_image

                        # last tell the new winner that its the winner
                        self.ImageObjects_by_source[best_option].set_winner(
                            True, reason
                        )

                    else:
                        # this source is less good than the previous best option
                        # set the old best_option to no longer be the best option - ie. change it to delete isntead of winner
                        logger.debug(
                            f"best_option {best_option} is better than contender {source_image}"
                        )

                        self.ImageObjects_by_source[source_image].set_winner(
                            False, reason
                        )
            if files_complete % 200 == 0:
                print(
                    f"\rProcessing {len(self.ImageObjects_by_source)} decisions ({round(files_complete / len(self.ImageObjects_by_source) *100,1)}% complete)",
                    end="\r",
                )

        print(
            f"\rProcessed {len(self.ImageObjects_by_source)} decisions (100% complete)         ",
        )
