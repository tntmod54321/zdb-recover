## zdb_recover
 Copy files off a ZFS pool that have corrupted blocks, using ZDB to grab corrupted blocks.  

### ABSOLUTELY NO WARRANTY, NO SUPPORT.
### *DO NOT RUN THIS PROGRAM WITHOUT READING THROUGH THE SOURCE CODE UNLESS YOU'RE OK WITH LOSING EVERY BYTE OF YOUR DATA*  
Verify that the output of this script is sane before using, try copying multiple types of known good files and verifying that the output is correct  .
Only tested with TrueNAS-13.0-U2, with OpenZFS-2.1.5

### unexpected problems I encountered:
* filesystem compression is not global (detect using ratio of physical/logical bytes)
* the last block had extra data (count written bytes and slice output by bytecount of original file)
* reading the binary from os.popen() (subprocess.popen didn't behave how I expected either..) (op.popen().buffer returns underlying binary buffer that's feeding the textiowrapper)
