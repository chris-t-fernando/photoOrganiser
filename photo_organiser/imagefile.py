import logging, sys
import datetime
import hashlib
import os
import exiftool

# logger.basicConfig(stream=sys.stderr, level=logger.ERROR)
logger = logging.getLogger("ImageFile")
logger.setLevel(logging.WARN)


class ImageNotValidError(Exception):
    # exception thrown when the file exists but is not a valid image
    def __init__(self, file_fullpath):
        super().__init__(self, f"{file_fullpath}: File does not contain a valid image")


class ImageFile:
    # path stuff
    source_fullpath: str = None
    source_file_name: str = None
    source_folder: str = None

    # where is the root of the destination - will be used with validated_year and validated_month to construct destination folder
    destination_root: str = None
    file_create: datetime = None
    file_modify: datetime = None
    file_size: int = None
    valid_media: bool = False

    # must be explicitly called, because its an expensive operation and ultimately it may not be needed
    file_hash: str = None

    # attributes set by decide()
    destination_fullpath: str = None
    destination_folder: str = None
    destination_date: datetime = None
    destination_month: str = None
    destination_year: str = None
    tag_date: datetime = None
    tagging_present = False

    # attributes set by set_winner()
    winner = None
    reason = None

    def __init__(self, source_fullpath, destination_root, metadata):

        self.source_fullpath = source_fullpath
        self.destination_root = destination_root

        # mess around with path string
        folder_separator = source_fullpath.rfind("/")
        self.source_file_name = source_fullpath[(folder_separator + 1) :]
        self.source_folder = source_fullpath[:folder_separator]

        # validate file - just trust exiftool
        if "File:MIMEType" in metadata.keys():
            if metadata["File:MIMEType"] != "application/unknown":
                self.valid_media = True
            else:
                raise ImageNotValidError(self.source_fullpath)
        else:
            raise ImageNotValidError(self.source_fullpath)

        # hold on to stat info from exiftool
        self.file_create = datetime.datetime.strptime(
            metadata["File:FileCreateDate"], "%Y:%m:%d %H:%M:%S%z"
        ).replace(tzinfo=None)
        self.file_modify = datetime.datetime.strptime(
            metadata["File:FileModifyDate"], "%Y:%m:%d %H:%M:%S%z"
        ).replace(tzinfo=None)
        self.file_size = metadata["File:FileSize"]

        # grab whichever date field we can find
        self.select_date_metadata(metadata)

        # determine the to-be
        self.generate_destination()

        if self.tag_date == None:
            logger.info(
                f"{self.source_fullpath}: Finished analysing file.  Destination {self.destination_fullpath} (file modified date)"
            )
        else:
            logger.info(
                f"{self.source_fullpath}: Finished analysing file.  Destination {self.destination_fullpath} (exif date)"
            )

    def set_winner(self, bool_winner, reason):
        self.winner = bool_winner
        self.reason = reason

    def select_date_metadata(self, metadata):
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
                # got some malformed tags coming back from exif
                if (
                    metadata[tag] != "0000:00:00 00:00:00"
                    and str(metadata[tag]).count(" ") == 1
                ):
                    self.tag_date = datetime.datetime.strptime(
                        metadata[tag], "%Y:%m:%d %H:%M:%S"
                    )
                    self.tagging_present = True
                    return True

        return False

    def generate_destination(self):
        # decide on the date to use
        # decide on the target folder location

        # which timestamp are we going to use? In order of priority:
        # tag
        # file date modified (can't use create date since files got moved around)
        if self.tag_date != None:
            self.destination_date = self.tag_date
            logger.debug(
                f"{self.source_fullpath}: Destination generated using EXIF data"
            )
        else:
            self.destination_date = self.file_modify
            logger.debug(
                f"{self.source_fullpath}: Destination generated using file stat data"
            )
            # poor form but fall back to stat date
            self.tag_date = self.file_modify

        self.destination_year = self.destination_date.strftime("%Y")
        self.destination_month = self.destination_date.strftime("%m")

        self.destination_folder = (
            self.destination_root
            + "/"
            + self.destination_year
            + "/"
            + self.destination_month
        )

        self.destination_fullpath = (
            self.destination_folder + "/" + self.source_file_name
        )

        return

    # shamelessly stolen from https://nitratine.net/blog/post/how-to-hash-files-in-python/
    def get_hash(self):
        # don't do it again if its already done...
        if self.file_hash != None:
            return self.file_hash

        BLOCK_SIZE = 65536  # The size of each read from the file

        file_hash = (
            hashlib.sha256()
        )  # Create the hash object, can use something other than `.sha256()` if you wish
        with open(self.source_fullpath, "rb") as f:  # Open the file to read it's bytes
            fb = f.read(
                BLOCK_SIZE
            )  # Read from the file. Take in the amount declared above
            while len(fb) > 0:  # While there is still data being read from the file
                file_hash.update(fb)  # Update the hash
                fb = f.read(BLOCK_SIZE)  # Read the next block from the file

        self.file_hash = file_hash.hexdigest()  # Get the hexadecimal digest of the hash

        return self.file_hash


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

    def add_image(self, the_image):
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

    def process_exif(self):
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

    def process_exif_batch(self, this_batch):
        with exiftool.ExifTool() as et:
            metadata = et.get_metadata_batch(this_batch)

        for d in metadata:
            self.add_image(
                ImageFile(
                    source_fullpath=d["SourceFile"],
                    destination_root=self.destination_root,
                    metadata=d,
                )
            )

    # return True if new is better than existing
    # or False if they're the same or existing is better
    def is_better(self, new, existing):
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

    def decide(self):
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
                    f"\rProcessing {len(self.ImageObjects_by_destination)} decisions ({round(files_complete / len(self.ImageObjects_by_destination) *100,1)}% complete)",
                    end="\r",
                )
        print(
            f"\rProcessed {len(self.ImageObjects_by_destination)} decisions (100% complete)         ",
        )
