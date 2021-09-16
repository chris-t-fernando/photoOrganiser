from photo_organiser import argumentparser
import logging, sys, os, hashlib, csv

logger = logging.getLogger(__file__)


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


def run_fast_scandir(dir, ext):  # dir: str, ext: list
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

    for dir in list(subfolders):
        sf, f, ign = run_fast_scandir(dir, ext)
        subfolders.extend(sf)
        files.extend(f)
        ignored.extend(ign)

    print(f"Filesystem walk: Walk in progress (finished {dir})", end="\r")

    return subfolders, files, ignored


def main():
    paths = argumentparser.ArgumentParser(sys.argv)

    if paths.valid_arguments == False:
        print(f"Invalid parameters.  Exiting")
        exit()
    else:
        logger.debug("Paths is good")
    print(
        f"Filesystem walk: Initiated walk of {paths.incoming_path}",
        end="\r",
    )

    ext = [".mov", ".jpg", ".heic", ".mp4", ".png", ".jpeg", ".3gp", ".avi", ".jpe"]

    sf, f, ignored = run_fast_scandir(paths.incoming_path, ext)

    print(
        f"Filesystem walk: Complete (found {len(f)} files)                             ",
    )

    print(
        f"File hashing: Initiated hashing of {len(f)} files",
        end="\r",
    )
    file_hashes = {}
    total_files = len(f)
    counter = 0

    for this_file in f:
        file_hashes[this_file] = get_hash(this_file)
        counter += 1
        print(
            f"File hashing: In progress ({round(counter/total_files*100,1)}% completed)        ",
            end="\r",
        )

    print(f"File hashing: Complete                                  ")

    flipped = {}

    for key, value in file_hashes.items():
        if value not in flipped:
            flipped[value] = [key]
        else:
            flipped[value].append(key)

    duplicate_file = open("duplicates.log", "w", newline="", encoding="utf-8")
    duplicate_writer = csv.writer(duplicate_file, delimiter=",", quotechar='"')

    counter = 0
    print(
        f"File comparison: In progress ({round(counter/total_files*100,1)}% completed)        ",
        end="\r",
    )
    for hash in flipped:
        if len(flipped[hash]) > 1:
            for duplicate in flipped[hash]:
                duplicate_writer.writerow([hash, duplicate])
        counter += 1
        print(
            f"File comparison: In progress ({round(counter/total_files*100,1)}% completed)        ",
            end="\r",
        )
    duplicate_file.close()

    print(
        f"File comparison: Complete                          \nFinished writing to duplicates.log\nProcess complete",
    )


if __name__ == "__main__":
    main()
