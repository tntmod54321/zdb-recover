import os
import sys
import re

isTruenas = True

examplePath = '/mnt/CROWN/user1/testing/boys_datasets3.txt'

### update printhelp
def printHelp():
    print("Usage:", "py wpd_save_post.py -u [POST URL] -o [OUTPUT DIR] -c cookies.txt\n\n"+
    "Arguments:\n", "  -h, --help\t\tdisplay this usage info\n",
    "  -u, --url\t\tpost url\n",
    "  -id, --id\t\tpost id\n",
    "  -o, --output-dir\toutput directory\n",
    "  -s, --session\tsession cookie\n",
    "  -c, --cookies\tcookies file")
    exit()

def pathParse(path):
    mntPoint = re.match(r'/mnt/([^/\\]+)/', path)
    if mntPoint: mntPoint=mntPoint[1]
    else: raise Exception('Unable to extract mountpoint')
    
    relPath = re.match(r'/mnt/[^/]+/(.+)', path)
    if relPath: relPath=relPath[1]
    else: raise Exception('Unable to extract mountpoint\'s relative path')
    
    return {
        'abslPath': path, 'relPath': relPath, # relative to the mountpoint
        'mntPoint': mntPoint, 'filename': os.path.basename(path)
    }

def getObjBlkPointers(path):
    path = path.replace(' ','\ ') # sanitize spaces
    path = pathParse(path)
    
    # form command
    command = 'zdb '
    if isTruenas: command+='-U /data/zfs/zpool.cache ' # non boot-pool pools are cached here
    command+=f"-vv -O {path['mntPoint']} " # specify pool, two levels of verbosity to print block pointers, L0 blocks are raw block data
    command+=f"{path['relPath']}"
    
    cmdInfo = os.popen(command)
    objInfo = cmdInfo.readlines() # get pointers along with other info
    
    objStatus = cmdInfo.close()
    if objStatus != None: raise Exception('Unexpected zdb -O command response')
    
    # parse lines into L0 pointers
    LX_POINTERS=[]
    tsize=None
    for line in objInfo:
        if line.strip() == '': continue
        lineList=[]
        for part in line.split(' '):
            if part!='': lineList.append(part)
        
        if len(lineList)>1:
            if not re.match(r'L\d$', lineList[1]): continue # if not an LX pointer
            pointer = {
                "level": lineList[1], # E.G. L0
                "size": lineList[3], # physical/logical size
                "vdev": lineList[2].split(':')[0],
                "offset": lineList[2].split(':')[1], # offset of the block on the disk
                "dumbsize": lineList[2].split(':')[2],
                "fileoffset": lineList[0], # offset of this block from the start of the file
                "checksums": lineList[6].strip().split('=')[1]
            }
            
            isC = re.match(r'([0-9a-fA-F]{1,20})L/([0-9a-fA-F]{1,20})P$', pointer['size'])
            if isC:
                if isC[1]==isC[2]: pointer['isCompressed'] = False
                else: pointer['isCompressed'] = True
            else: pointer['isCompressed'] = None
            
            LX_POINTERS.append(pointer)
        
        else:
            lineList = lineList[0].split('\t')
            if not len(lineList)>1: continue
            if lineList[1]=='size': tsize = int(lineList[2].strip())
    
    if tsize==None: raise Exception('Unable to get total filesize')
    return LX_POINTERS, path['mntPoint'], tsize

def main():
    # zdb -U /data/zfs/zpool.cache -R Boys 0:156ecb3f5000:20000L/8000P:rd > /mnt/Boys/audrey/testing/browserhist_l0_0_raw1_2.txt
    # python /mnt/Boys/audrey/testing/zdb_recover.py -i "/mnt/Boys/audrey/2022.09.15 centbrowser history" -o "/mnt/Boys/audrey/testing/dump.bin"
    
    path = ''
    outfile = ''
    overwrite = False
    
    if len(sys.argv[1:]) == 0: printHelp()
    i=1 # for arguments like [--command value] get the value after the command
    for arg in sys.argv[1:]: # first arg in sys.argv is the python file
        if (arg in ["help", "/?", "-h", "--help"]): printHelp()
        if (arg in ["-i", "--in-file"]): path = sys.argv[1:][i]
        if (arg in ["-o", "--out-file"]): outfile = sys.argv[1:][i]
        if (arg in ["-X"]): overwrite = True
        i+=1
    if '' in [path, outfile]: printHelp()
    
    pointers, mntPoint, tsize = getObjBlkPointers(path)
    
    pathExists = os.path.exists(outfile)
    if not overwrite and pathExists: raise Exception(f'Specified output file {outfile} already exists!')
    if not pathExists and not os.path.exists(os.path.split(outfile)[0]): os.makedirs(os.path.split(outfile)[0])
    
    with open(outfile, 'wb') as OF:
        with open(path, 'rb') as IF:
            previousOffset=None
            i=1
            byteCounter=0
            badBlockCounter=0
            for pointer in pointers:
                if pointer['level'] != 'L0': continue # skip non-data pointers
                if previousOffset!=None: # check previous offset
                    if not int(pointer['fileoffset'], 16)>previousOffset:
                        raise Exception('Error, object block pointers being read out of order, not possible to properly reconstruct file') # it is possible you liar!!!     just not implemented.. 👉👈
                
                try:
                    if i==2: raise OSError
                    IF.seek(byteCounter)
                    blockLen = re.match(r'^(\d{1,10})L', pointer['size'])
                    if blockLen: blockLen=int(blockLen[1], 16)
                    else: raise Exception('Error getting logical length of block')
                    blockBin = IF.read(blockLen)
                except OSError as e:
                    if not 'Input/output error' in str(e): raise e
                    badBlockCounter+=1
                    print(f'block {i} is damaged')
                    
                    # form command to read block
                    command = 'zdb '
                    if isTruenas: command+='-U /data/zfs/zpool.cache ' # non boot-pool pools are cached here
                    command+=f'-R {mntPoint} '
                    command+=f"{pointer['vdev']}:{pointer['offset']}:{pointer['size']}:r"
                    
                    if pointer['isCompressed']==True: command+='d' # add decompress flag if compression is detected in this block
                    elif pointer['isCompressed']==False: pass
                    elif pointer['isCompressed']==None: raise Exception('undefined block physical/logical bytes ratio?')
                    
                    blockRead = os.popen(command) # read block from disk
                    blockBin = blockRead.buffer.read() # read the underlying buffer that the textiowrapper is using so we don't have issues encoding to bytes 😏
                    blockReadStatus = blockRead.close()
                    if blockReadStatus!=None: raise Exception(f"Error reading block {pointer['offset']} content")
                
                OF.write(blockBin[:tsize-byteCounter])
                byteCounter+=len(blockBin[:tsize-byteCounter]) # count bytes excluding overshoot no the last block
                
                print(f"({i}/{len(pointers)-1}) read {byteCounter} bytes total")
                
                previousOffset = int(pointer['fileoffset'], 16)
                i+=1
    print(f'Successfilly transfered {os.path.split(path)[1]}! ({byteCounter} bytes, {badBlockCounter} damaged blocks)')

if __name__=='__main__':
    main()

# unexpected problems I encountered:
# filesystem compression is not global (detect using ratio of physical/logical bytes)
# the last block had extra data (count written bytes and slice output by bytecount of original file)
# reading the binary from os.popen() (subprocess.popen didn't behave how I expected either..) (op.popen().buffer returns underlying binary buffer that's feeding the textiowrapper)
