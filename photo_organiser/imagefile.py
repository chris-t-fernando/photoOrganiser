import logging, sys
import datetime
import hashlib


# logger.basicConfig(stream=sys.stderr, level=logger.ERROR)
logger = logging.getLogger("ImageFile")
logger.setLevel(logging.WARN)

# File types:
# JPG (done)
# MOV
# HEIC
# MP4
# PNG (done)
# 3GP
# AVI


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
                self.tag_date = datetime.datetime.strptime(
                    metadata[tag], "%Y:%m:%d %H:%M:%S"
                )
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

        self.destination_year = self.destination_date.strftime("%Y")
        self.destination_month = self.destination_date.strftime("%m")

        self.destination_folder = (
            self.destination_root
            + "\\"
            + self.destination_year
            + "\\"
            + self.destination_month
        )

        self.destination_fullpath = (
            self.destination_folder + "\\" + self.source_file_name
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
