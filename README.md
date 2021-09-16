# photoOrganiser
Python scripts to organise my photo album.

# Comprised of two scripts:
1. import.py - reads an input directory for a list of accepted files (heic, jpg, png, mp4, mov), analyses them (metadata tagging, file size, hash), determines the destination path, compares it against any files that already exist/that would be imported into the same destination, and then executes the move
1. find_duplicates.py - reads an input directory, hashes the contents, searches for duplicates, and generates a report of the duplicates for a human to action

## Usage
import.py --input c:/some/input --output d:/some/output [--debug true] [--dryrun true]
find_duplicates.py --input c:/some/input --output d:/some/output

# Learning intention:
1. Multithreading that turned into multiprocessing given I quickly learned about Python's GIC issue
1. Finally work out packages vs modules vs scripts, and the different ways of importing stuff
1. A little more OO mindset - realised that I was using dictionaries as a poor stand-in for objects

# To do (if I care enough, which I probably won't but who knows):
1. Increased visibility into the decision process - in the import csv report, include details about the destination
1. Convert the decisions themselves into objects, so they can be interrogated properly
1. Add in ETC for long-running jobs
1. Set up a folder watcher so that this script will be triggered whenever I copy files into it (this would be pretty cool actually)
