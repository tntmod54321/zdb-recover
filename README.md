## zdb_recover
 Copy files off a ZFS pool that have corrupted blocks, using ZDB to grab corrupted blocks.  

### ABSOLUTELY NO WARRANTY, NO SUPPORT.
### *DO NOT RUN THIS PROGRAM WITHOUT READING THROUGH THE SOURCE CODE UNLESS YOU'RE OK WITH LOSING EVERY BYTE OF YOUR DATA*  
Verify that the output of this script is sane before using, try copying multiple types of known good files and verifying that the output is correct  .
Only tested with TrueNAS-13.0-U2, with OpenZFS-2.1.5, and with Python 3.7+

## Usage
```
Usage: python zdb_recover.py -i [INPUT FILE] -o [OUTPUT FILE]

Arguments:
   -h, --help           display this usage info
   -i, --input-file     input file to copy
   -o, --output-file    file to copy to
   -X                   overwrite output file if exists
```

## Example command
```
python3 /mnt/Boys/audrey/zdb_recover.py -i /mnt/Boys/audrey/20201129_153851.mp4 -o /mnt/Boys/audrey/recovered.mp4
```

unexpected problems I encountered:
* filesystem compression is not global across all blocks (detect using ratio of physical/logical bytes)
* the last block had extra data (count written bytes and slice output by bytecount of original file)
* reading the binary from os.popen() (subprocess.popen didn't behave how I expected either..) (op.popen().buffer returns underlying binary buffer that's feeding the textiowrapper)
