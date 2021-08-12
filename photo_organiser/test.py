import logging, sys
import pathlib
import datetime
import hashlib
import subprocess
from PIL import Image, ExifTags
import exiftool

# hachoir sucks for metadata
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

# File types:
# JPG (done)
# MOV
# HEIC
# MP4
# PNG (done)
# 3GP
# AVI


def hachoir_tags(filename):
    parser = createParser(filename)
    metadata = extractMetadata(parser)
    if metadata.has("date_time_original"):
        logging.error(f"{filename}: Used date_time_original")
        return metadata.get("date_time_original")
    elif metadata.has("last_modification"):
        logging.error(f"{filename}: Used last_modification")
        return metadata.get("last_modification")
    elif metadata.has("creation_date"):
        logging.error(f"{filename}: Used creation_date")
        return metadata.get("creation_date")
    else:
        logging.debug(
            f"{filename}: Hachoir failed to find last_modification and creation_date in metadata"
        )
        return False


def exiftool_tags(filename):
    # and here I'm going to have to spawn exiftool, which is the whole thing I set out to avoid...
    # assumes exiftool is in same folder as this script

    folder_separator = __file__.rfind("\\")
    script_dir = __file__[:folder_separator]

    output = (
        subprocess.Popen(
            [script_dir + "\\exiftool.exe", filename],
            stdout=subprocess.PIPE,
        )
        .communicate()[0]
        .decode()
        .split("\r\n")
    )

    # 					if ( $extension == "PNG" )
    # 						$dateString = "Date Created";
    # 					elseif ( $extension == "AVI" )
    # 						$dateString = "Date/Time Original";
    # 					elseif (
    # 						( $extension == "MOV" ) ||
    # 						( $extension == "EIC") ||
    # 						( $extension == "JPG") ||
    # 						( $extension == "PEG") ||
    # 						( $extension == "MP4" ) ||
    # 						( $extension == "3GP" )
    # 						$dateString = "Create Date";

    # looks like I'm stuck with exiftool, so re-create this logic.  Sad face
    for line in output:
        if "Modify Date" in line:
            date_string = line[(line.find(": ") + 2) :]
            if date_string.strip() != "":
                return datetime.datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")

    return False


class ImageNotValidError(Exception):
    # exception thrown when the file exists but is not a valid image
    def __init__(self, file_fullpath):
        super().__init__(self, f"{file_fullpath}: File does not contain a valid image")


class ImageFile:
    # attributes populated by parent class constructor (ImageFile)
    source_fullpath: str = None  #
    source_file_name: str = None  #
    source_folder: str = None  #
    # where is the root of the destination - will be used with validated_year and validated_month to construct destination folder
    destination_root: str = None  #
    file_create: datetime = None  #
    file_modify: datetime = None  #
    file_size: int = None  #

    # must be explicitly called, because its an expensive operation and it may not be needed
    file_hash: str = None  #

    # parent class attributes called by decide()
    destination_fullpath: str = None
    destination_folder: str = None
    validated_date: datetime = None
    validated_month_string: str = None
    validated_year_string: str = None

    # attributes populated by implementing class (JPG or whatever)
    tag_create: datetime = None  #
    valid_image: bool = False  #

    def __init__(self, source_fullpath, destination_root):
        self.source_fullpath = source_fullpath
        self.destination_root = destination_root

        # mess around with path string
        folder_separator = source_fullpath.rfind("\\")
        self.source_file_name = source_fullpath[(folder_separator + 1) :]
        self.source_folder = source_fullpath[:folder_separator]

        # stat file and hold on to interesting parts
        fname = pathlib.Path(source_fullpath)
        try:
            fstat = fname.stat()
        except Exception as e:
            logging.error(f"{source_fullpath}: File does not exist")
            # no need to set self.valid_image to False since it already defaults to it
            # do I need a valid_file?? I don't think so...
            raise

        self.file_create = datetime.datetime.fromtimestamp(fstat.st_ctime)
        self.file_modify = datetime.datetime.fromtimestamp(fstat.st_mtime)
        self.file_size = fstat.st_size

        try:
            if self.validate_image() == False:
                raise ImageNotValidError(self.source_fullpath)

            if self.get_tags() == False:
                # do something sensible here, since the image has no tags
                # there's probably nothing to do, just fall back on stat output?
                pass

        except Exception as e:
            raise

        if self.generate_destination():
            logging.info(
                f"{self.source_fullpath}: Finished analysing file.  Destination fullpath proposed to be {self.destination_fullpath}"
            )
        else:
            raise ImageNotValidError(self.source_fullpath)

    def validate_image(self):
        ...

    def get_tags(self):
        ...

    def generate_destination(self):
        # decide on the date to use
        # decide on the target folder location

        # is it a valid file?
        if self.valid_image == False:
            return False

        # which timestamp are we going to use? In order of priority:
        # tag
        # file date modified
        if self.tag_create != None:
            self.validated_date = self.tag_create
            logging.info(
                f"{self.source_fullpath}: Destination generated using EXIF data"
            )
        else:
            self.validated_date = self.file_modify
            logging.info(
                f"{self.source_fullpath}: Destination generated using file stat data"
            )

        self.validated_year_string = self.validated_date.strftime("%Y")
        self.validated_month_string = self.validated_date.strftime("%m")

        self.destination_folder = (
            self.destination_root
            + "\\"
            + self.validated_year_string
            + "\\"
            + self.validated_month_string
        )

        self.destination_fullpath = (
            self.destination_folder + "\\" + self.source_file_name
        )

        return True

    # shamelessly stolen from https://nitratine.net/blog/post/how-to-hash-files-in-python/
    def generate_hash(self):
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


# used for any file types that can be handled by PIL - PNG and JPG
# if those classes don't do anything at all, maybe its best to just have my code instantiate
# a PILFile rather than JPG/PNGFile which is 100% implemented by PILFile
class PILFile(ImageFile):
    def __init__(self, source_fullpath, destination_root):
        super().__init__(source_fullpath, destination_root)

    def validate_image(self):
        try:
            img = Image.open(self.source_fullpath)  # open the image file
            self.valid_image = img.verify()  # verify that it is, in fact an image
            logging.debug(f"{self.source_fullpath}: Validated image")
            return True
        except (IOError, SyntaxError) as e:
            logging.error(f"{self.source_fullpath}: Not a valid image")
            return False

    def get_tags(self):
        img = Image.open(self.source_fullpath)
        exif_tags = {
            ExifTags.TAGS[k]: v for k, v in img._getexif().items() if k in ExifTags.TAGS
        }
        if "DateTimeOriginal" in exif_tags.keys():
            self.tag_create = datetime.datetime.strptime(
                exif_tags["DateTimeOriginal"], "%Y:%m:%d %H:%M:%S"
            )
            logging.debug(f"{self.source_fullpath}: Found EXIF data")
            return True
        elif "DateTime" in exif_tags.keys():
            self.tag_create = datetime.datetime.strptime(
                exif_tags["DateTime"], "%Y:%m:%d %H:%M:%S"
            )
            logging.debug(f"{self.source_fullpath}: Found EXIF data")
            return True
        else:
            # no exif tags for create timestamp
            logging.debug(f"{self.source_fullpath}: Failed to find EXIF data")
            return False


# hacoir is bloody useless - munges stat with metadata and can't properly read metadata anyway
class HachoirFile(ImageFile):
    def __init__(self, source_fullpath, destination_root):
        super().__init__(source_fullpath, destination_root)

    def validate_image(self):
        # ugh I'm going to have to spawn ffmpeg to do this
        # todo: that
        self.valid_image = True
        logging.debug(
            f"{self.source_fullpath}: Validated file (not really, this is a stub)"
        )
        return True

    def get_tags(self):
        tag = hachoir_tags(self.source_fullpath)
        if tag != False:
            self.tag_create = tag
            logging.debug(f"{self.source_fullpath}: Found EXIF data")
            return True
        else:
            # no need to push out to logging - already did that in hachoir_tags
            return False


class ExiftoolFile(ImageFile):
    def __init__(self, source_fullpath, destination_root):
        super().__init__(source_fullpath, destination_root)

    def validate_image(self):
        # ugh I'm going to have to spawn ffmpeg to do this
        # todo: that
        self.valid_image = True
        logging.debug(
            f"{self.source_fullpath}: Validated file (not really, this is a stub)"
        )
        return True

    def get_tags(self):
        tag = exiftool_tags(self.source_fullpath)
        if tag != False:
            self.tag_create = tag
            logging.debug(f"{self.source_fullpath}: Found EXIF data")
            return True
        else:
            # no need to push out to logging - already did that in hachoir_tags
            return False


# can maybe consolidate MOV and AVI, depending on whether I choose to validate the files
class AVIFile(HachoirFile):
    ...


class MOVFile(HachoirFile):
    ...


class MP4File(HachoirFile):
    ...


class JPGFile(PILFile):
    ...


class PNGFile(PILFile):
    ...


files = [
    "Y:\\photoOrganiser\\sample_data\input\\IMG_5616.PNG",
    "Y:\\photoOrganiser\\sample_data\input\\IMG_0118.jpg",
    "Y:\\photoOrganiser\\sample_data\\input\\invalid\\._IMG_0095.jpg",
]
with exiftool.ExifTool() as et:
    metadata = et.get_metadata_batch(files)
for d in metadata:
    print("{:20.20} {:20.20}".format(d["SourceFile"], d["EXIF:DateTimeOriginal"]))
exit()
#    def __init__(self, source_fullpath, destination_root):
#        super().__init__(source_fullpath, destination_root)

inFile = "Y:\\photoOrganiser\\sample_data\input\\IMG_5616.PNG"
outPath = "c:\\output"
imgFile = PNGFile(inFile, outPath)
imgFile.generate_hash()
print(imgFile.file_hash)
print(imgFile.tag_create)


inFile = "Y:\\photoOrganiser\\sample_data\input\\IMG_0118.jpg"

try:
    imgFile = JPGFile(inFile, outPath)
    imgFile.generate_hash()
    print(imgFile.file_hash)
    print(imgFile.tag_create)
except Exception as e:
    logging.error(f"{inFile}: Failed to instantiate file.  Error: {str(e)}")


inFile = "Y:\\photoOrganiser\\sample_data\input\\IMG_1516.MOV"
try:
    imgFile = MOVFile(inFile, outPath)
    imgFile.generate_hash()
    print(imgFile.file_hash)
    print(imgFile.tag_create)
except Exception as e:
    logging.error(f"{inFile}: Failed to instantiate file.  Error: {str(e)}")

inFile = "Y:\\photoOrganiser\\sample_data\input\\MVI_1186.avi"
try:
    imgFile = AVIFile(inFile, outPath)
    imgFile.generate_hash()
    print(imgFile.file_hash)
    print(imgFile.tag_create)
except Exception as e:
    logging.error(f"{inFile}: Failed to instantiate file.  Error: {str(e)}")


inFile = "Y:\\photoOrganiser\\sample_data\input\\IMG_4156.MP4"
try:
    imgFile = MP4File(inFile, outPath)
    imgFile.generate_hash()
    print(imgFile.file_hash)
    print(imgFile.tag_create)
except Exception as e:
    logging.error(f"{inFile}: Failed to instantiate file.  Error: {str(e)}")


inFile = "Y:\\photoOrganiser\\sample_data\input\\Video005.3gp"
try:
    imgFile = MP4File(inFile, outPath)
    imgFile.generate_hash()
    print(imgFile.file_hash)
    print(imgFile.tag_create)
except Exception as e:
    logging.error(f"{inFile}: Failed to instantiate file.  Error: {str(e)}")
