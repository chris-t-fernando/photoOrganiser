# from photo_organiser.imagefile import ImageFile
from imagefile import ImageFile
import os
import exiftool


# generate to-be destinations.  all the generated ones have already been run through exiftool, so we have metadata
# loop through all of the to-be destinations and work out if they exist or not
# if they DO exist, then we need to exiftool it and create an object for it
# then run through all of the candidates for that destination file, make a decision
# execute the decision


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

        # loop through all of the existing images
        for f in self.existing_images:
            # batch them into groups of 100
            this_batch.append(f)

            if len(this_batch) == 100:
                # do the batch of 100
                self.process_exif_batch()

                # its done so reset to an empty List
                this_batch = []

        # if there is more than 0 but less than 100 in the queue (last batch)
        if len(this_batch) > 0:
            self.process_exif_batch(this_batch)

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

    # return True is new is better than existing
    # or False if they're the same or existing is better
    def is_better(self, new, existing):
        # check size
        if new.file_size > existing.file_size:
            return True, "file size"

        # check hash - if its the same file, then the existing isn't better
        if new.get_hash() == existing.get_hash():
            return False, "hash matches"

        # check mod date - if new is older, go with it (maybe it got edited or stat updated or something)
        if new.tag_date < existing.tag_date:
            return True, "date"

        # file size is the same, contents are different, but existing has older modified stamp
        return False, "default"

    def execute_actions(self):
        # loop through the competitors for best destination_image
        for destination_image in self.ImageObjects_by_destination:

            # need to work out which one is the best option
            # this just resets the holder per destination_image
            best_option = None

            # for each contender
            for source_image in self.ImageObjects_by_destination[destination_image]:
                # if there hasn't been another contender yet - something is better than nothing
                if best_option == None:
                    best_option = source_image
                    print(f"there is no best_option, so {best_option} is the winner")
                    best_option.set_winner(True)
                else:
                    # there's something to compare against.  Pulled the logic out inot a separate method for ease of understanding and testing
                    if self.is_better(
                        self.ImageObjects_by_source[source_image],
                        self.ImageObjects_by_source[best_option],
                    ):
                        # this source is better than the previous best option
                        # first tell the old winner that it isn't any more
                        best_option.set_winner(False)

                        # now set best_option to the new winner
                        best_option = source_image

                        # last tell the new winner that its the winner
                        best_option.set_winner(True)

                        print(
                            f"best_option {best_option} is not better than contender {source_image} - replacing"
                        )

                    else:
                        # this source is less good than the previous best option
                        # set the old best_option to no longer be the best option - ie. change it to delete isntead of winner
                        print(
                            f"best_option {best_option} is better than contender {source_image}"
                        )
                        source_image.set_winner(False)


image_files = [
    "Y:/photoOrganiser/sample_data/input/IMG_0118.jpg",
    "Y:/photoOrganiser/sample_data/input/duplicate/IMG_0118.jpg",
]

state_machine = PhotoMachine("Y:/photoOrganiser/sample_data/output")

with exiftool.ExifTool() as et:
    metadata = et.get_metadata_batch(image_files)

for d in metadata:
    state_machine.add_image(
        ImageFile(
            source_fullpath=d["SourceFile"],
            destination_root="Y:/photoOrganiser/sample_data/output",
            metadata=d,
        )
    )

state_machine.process_exif()
state_machine.execute_actions()


# file1_metadata = {}
# file1_metadata["EXIF:CreateDate"] = "2017:12:12 12:12:12"
# file1_metadata["File:MIMEType"] = "application/whatever"
# file1_metadata["File:FileCreateDate"] = "2017:12:12 12:12:12+12:00"
# file1_metadata["File:FileModifyDate"] = "2017:12:12 12:12:12+12:00"
# file1_metadata["File:FileSize"] = 1000

# file1 = ImageFile(
#    "Y:/photoOrganiser/sample_data/input/IMG_0118.jpg",
#    "Y:/photoOrganiser/sample_data/output",
#    file1_metadata,
# )

# file2_metadata = {}
# file2_metadata["EXIF:CreateDate"] = "2017:12:12 12:12:12"
# file2_metadata["File:MIMEType"] = "application/whatever"
# file2_metadata["File:FileCreateDate"] = "2017:12:12 12:12:12+12:00"
# file2_metadata["File:FileModifyDate"] = "2017:12:12 12:12:12+12:00"
# file2_metadata["File:FileSize"] = 1000

# file2 = ImageFile(
#    "Y:/photoOrganiser/sample_data/input/duplicate/IMG_0118.jpg",
#    "Y:/photoOrganiser/sample_data/output",
#    file2_metadata,
# )
