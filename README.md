# photoOrganiser

Python scripts to organise my photo album.  I have about 150GB of photos of my kids, family and 20s fun times.  Across multiple external hard drives, laptops and HTPCs, I've ended up with duplicates of duplicates in different folders, drives etc.  It was an absolute mess, which belies how important to me these digital records really are, so I wanted to get this all perfect so I could throw it up into AWS Glacier.

## Comprised of two scripts:

1. import.py - reads an input directory for a list of accepted files (heic, jpg, png, mp4, mov), analyses them (metadata tagging, file size, hash), determines the destination path, compares it against any files that already exist/that would be imported into the same destination, and then executes the move
1. find_duplicates.py - reads an input directory, hashes the contents, searches for duplicates, and generates a report of the duplicates for a human to action

## Usage

    import.py --input c:/some/input --output d:/some/output [--debug true] [--dryrun true]
    find_duplicates.py --input c:/some/input --output d:/some/output

## Learning intention:

This one was less about learning (except the multithreading bit) and much more about doing something valuable.
1. Multithreading that turned into multiprocessing given I quickly learned about Python's GIC issue
1. Finally work out packages vs modules vs scripts, and the different ways of importing stuff
1. A little more OO mindset - realised that I was using dictionaries as a poor stand-in for objects

## To do (if I care enough, which I probably won't but who knows):

1. Increased visibility into the decision process - in the import csv report, include details about the destination
1. Convert the decisions themselves into objects, so they can be interrogated properly
1. Add in ETC for long-running jobs
1. Set up a folder watcher so that this script will be triggered whenever I copy files into it (this would be pretty cool actually)
1. Facial recognition - OpenCV looks super well suited to this, though I've only had a 5 minute look at this (this also would be super cool)
1. find_duplicates.py doesn't actually need or do anything with the --output flag.  I'd need to make the argument parser object more intelligent in order to deal with that, but for now it's more expedient to just enter dummy stuff 
