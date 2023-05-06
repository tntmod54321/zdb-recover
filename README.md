## zdb_recover
 Copy files off a ZFS pool that have corrupted blocks, using ZDB to grab corrupted blocks.  

### ABSOLUTELY NO WARRANTY, NO SUPPORT.
### *DO NOT RUN THIS PROGRAM WITHOUT READING THROUGH THE SOURCE CODE UNLESS YOU'RE OK WITH LOSING EVERY BYTE OF YOUR DATA*  
Verify that the output of this script is sane before using, try copying multiple types of known good files and verifying that the output is correct.
Only tested with TrueNAS-13.0-U2, with OpenZFS-2.1.5, and with Python 3.7+

## Usage
```
usage: zdb_recover.py [-h] [-i INPUT_FILE] [-o OUTPUT_FILE] [-X] [-t]

options:
  -h, --help            show this help message and exit
  -i INPUT_FILE, --input-file INPUT_FILE
                        input file to read
  -o OUTPUT_FILE, --output-file OUTPUT_FILE
                        output file to write
  -X, --overwrite       overwrite output file if exists
  -t, --truenas         use this flag if your ZFS install is on Truenas
```

## Example command
```
python3 "/mnt/CROWN/user1/zdb_recover.py" -i "/mnt/CROWN/user1/20201129_153851.mp4" -o "/mnt/CROWN/user1/recovered.mp4 -t"
```

unexpected problems I encountered:
* filesystem compression is not global across all blocks (detect using ratio of physical/logical bytes)
* the last block had extra data (count written bytes and slice output by bytecount of original file)
