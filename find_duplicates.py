from photo_organiser import argumentparser
import logging, sys, os, hashlib

logger = logging.getLogger(__file__)

def get_hash(file):
    BLOCK_SIZE = 65536  # The size of each read from the file

    file_hash = (
        hashlib.sha256()
    )  # Create the hash object, can use something other than `.sha256()` if you wish
    with open(file, "rb") as f:  # Open the file to read it's bytes
        fb = f.read(
            BLOCK_SIZE
        )  # Read from the file. Take in the amount declared above
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

    batch = []
    counter = 0
    for f in files:
        batch.append(f)
        counter += 1
        if counter == 400:
            batch = []
            counter = 0

    for dir in list(subfolders):
        sf, f, ign = run_fast_scandir(dir, ext)
        subfolders.extend(sf)
        files.extend(f)
        ignored.extend(ign)

    return subfolders, files, ignored

def main():
    paths = argumentparser.ArgumentParser(sys.argv)

    if paths.valid_arguments == False:
        print(f"Invalid parameters.  Exiting")
        exit()
    else:
        logger.debug("Paths is good")

    ext = [".mov", ".jpg", ".heic", ".mp4", ".png", ".jpeg", ".3gp", ".avi", ".jpe"]
    
    sf, f, ignored = run_fast_scandir(paths.incoming_path, ext)

    file_hashes = {}

    for this_file in f:
        file_hashes[this_file] = get_hash(this_file)

    flipped = {}
    
    for key, value in file_hashes.items():
        if value not in flipped:
            flipped[value] = [key]
        else:
            flipped[value].append(key)

    for hash in flipped:
        if len(flipped[hash]) > 1:
            print(f"Found duplicate for hash {hash}:")
            for duplicate_file in flipped[hash]:
                print(f"   {duplicate_file}")

if __name__ == "__main__":
    main()
