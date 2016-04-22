#!/usr/bin/python

"""
Copyright (c) 2016, John Brooks
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
-------------------------------------------------------------------------------

Converts a ZNC 1.4 log folder to ZNC 1.6.0 format
Merged logs are stored in all-lowercase ZNC 1.6.0 directory hierarchy in OUTDIR.
File attributes (including timestamp) are preserved.
"""
import re
import os
from collections import Counter
from itertools import chain
import shutil
import errno
import textwrap

OUTDIR = "./output/"

# This is what you'll need to change if your stuff contains underscores. Just
# make sure the named groups match properly.
globalRe = re.compile(r"^(?P<user>.+?)_(?P<network>[\w-]+?)_(?P<window>.+)_(?P<date>[0-9]+)\.log$")
networkRe = re.compile(r"^(?P<window>.+)_(?P<date>[0-9]+)\.log")
userRe = re.compile(r"^(?P<network>[\w-]+?)_(?P<window>.+)_(?P<date>[0-9]+)\.log")

globalDirFormat = "{user}/{network}/{window}"
userDirFormat = "{network}/{window}"
networkDirFormat = "{window}"

"""Sorts log lines by timestamp and returns the sorted lines"""
def sortLines(lines):
    out = []

    lineRe = re.compile(r'^\[(.*?)].*$')
    for line in lines:
        m = lineRe.match(line)
        if not m:
            print("WARNING: Line "+line+" doesn't look like a log line and will be removed!")
            continue
        ts = m.group(1).replace(':','')
        out.append((ts,line))
    # out list contains tuples like: (timestamp, message)
    # We will now sort on the time stamp
    out = sorted(out,key=lambda x: x[0])
    return [x[1] for x in out]

"""Finds log files that have mixed-case dupes and returns a list of
   tuples containing the different names of each log file"""
def findMixedCaseDupes(names):
    dupes = []

    # convert all names to lowercase and count how many instances exist of each
    nameslc = [name.lower() for name in names]
    counts = Counter(nameslc)
    dupenames = []

    # Find duplicates (Any lowercase name that occurs twice) 
    # and append them to dupenames
    for k,v in counts.items():
        if v == 2:
            dupenames.append(k)
        if v > 2: # We're not currently equipped to handle >2 copies 
            print("Warning: "+k+" has more than two occurrences. Skipping.")

    # Make a tuple for each duped file, containing the names of the copies
    for dupename in dupenames:
        tmp = []
        for i,v in enumerate(names):
            if v.lower() == dupename:
                tmp.append(v)
        dupes.append(tuple(tmp))
    return dupes

def mergeAndCopyLogs(logfiles, dupes):
    print("Merging logs...")
    for dupe in dupes:
        lines = []

        # Open both files
        # TODO: The way this code is set up is why we can only handle 2 dupes
        f1 = open(dupe[0])
        f2 = open(dupe[1])

        # Concatenate the files into the lines list
        lines.extend(f1.readlines())
        lines.extend(f2.readlines())
        f1.close()
        f2.close()

        # Sort the lines by timestamp
        sortedLines = sortLines(lines)
     
        # Store the 
        outf = open(OUTDIR+dupe[0].lower(),'w')
        for line in sortedLines:
            outf.write(line)
        outf.close()

        # Copy the file attributes from the old file to the new one
        shutil.copystat(dupe[1],OUTDIR+dupe[0].lower())

    print(str(len(dupes))+" logs merged.")

    dupeslist = list(chain(*dupes))

    # Copy all other files over in lowercase format
    print("Copying remaining logs...")
    logsCopied = 0
    for name in logfiles:
        if name not in dupeslist:
            shutil.copy2(name,OUTDIR+name.lower())
            logsCopied += 1
    print(str(logsCopied)+" files copied.")

"""Moves the files into a directory hierarchy based on http://wiki.znc.in/Log"""
def convertToHierarchy(logType):
    print("Rearranging logs into 1.6 hierarchy...")
    logfiles = os.listdir(OUTDIR)
    myRe = globalRe
    myFormat = globalDirFormat
    if logType == 'N':
        myRe = networkRe
        myFormat = networkDirFormat
    elif logType == 'U':
        myRe = userRe
        myFormat = userDirFormat

    for logfile in logfiles:
        m = myRe.match(logfile)
        if not m:
            print("warning: "+logfile+" did not match! It will be skipped.")
            continue
        user = ''
        network = ''
        window = ''
        date = ''

        newLogfile = ''

        try:
            user = m.group("user")
        except IndexError:
            pass
        try:
            network = m.group("network")
        except IndexError:
            pass
        try:
            window = m.group("window")
        except IndexError:
            print("warning: "+logfile+" doesn't have a window. That makes no sense. It's being skipped.")
            continue
        try:
            date = m.group("date")
            ymd = (date[:4],date[4:6],date[6:8])
            date = '-'.join(ymd)
        except IndexError:
            print("warning: "+logfile+" doesn't have a date. That makes no sense. It's being skipped.")
            continue

        path = OUTDIR+myFormat.format(user=user, network=network, window=window)

        try:
            os.makedirs(path)
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise 

        shutil.move(OUTDIR+logfile, path+"/"+date+".log")
    print("Done!")

### end of function definitions

filenames = os.listdir('.')
logfiles = [x for x in filenames if x.endswith('log')]
dupes = findMixedCaseDupes(logfiles)

try:
    print("""This script should be run in the same directory as your ZNC 1.4 log files.
Logs in subdirectories will not be processed.
Found """+str(len(logfiles))+" logs, "+str(len(dupes))+""" of which have duplicates.
Logs will be stored in """+OUTDIR+""", in an all-lowercase directory\
hierarchy compliant with ZNC 1.6.0

Your log files should be backed up and ZNC should *not* be running.\n""")
    print("If your network or user names contain underscores, the directory structure WILL be wrong unless you edit the script.")
    raw_input("Press Enter to continue or Ctrl+C to abort")
    print('')
    logType = raw_input("What log module are these logs from? (Global/Network/User)? ")
except KeyboardInterrupt:
    print('')
    exit(1)

# Global by default
if logType:
    logType = logType[0].upper()
else:
    logType = 'G'

try:
    os.mkdir(OUTDIR)
except OSError:
    pass

mergeAndCopyLogs(logfiles, dupes)
convertToHierarchy(logType)
