import argparse
import os
import re
import subprocess

def pathParse(path):
    # match /mnt/{mountpoint}/
    mntPoint = path.split('/mnt/')[1].split('/')[0]
    if not mntPoint:
        raise Exception('Unable to extract mountpoint')
    
    # match /mnt/{mountpoint/{relative path}
    relPath = path.split(f'/mnt/{mntPoint}/')[1]
    if not relPath:
        raise Exception('Unable to extract mountpoint\'s relative path')
    
    return {
        'abslPath': path, 'relPath': relPath, # relative to the mountpoint
        'mntPoint': mntPoint, 'filename': os.path.split(path)[1]
    }

def getObjBlkPointers(args):
    path = pathParse(
        args.input_file)
    
    if args.debug:
        print(f'\n[debug] parsed path is\n{path}\n')
    
    command = ['zdb']
    
    if args.truenas:
        command += ['-U', '/data/zfs/zpool.cache']
    
    command += [
        '-vv',
        '-O', path["mntPoint"],
        path["relPath"]]
    
    if args.debug:
        print(f'[debug] get block pointers command is \n{command}\n')
    
    # shouldn't need to escape spaces with subprocess.run
    proc = subprocess.Popen(command, stdout=subprocess.PIPE)
    
    # read-in lines
    objInfo = []
    for line in proc.stdout:
        objInfo.append(line)
    
    if proc.returncode != None:
        if args.debug:
            print('\n[debug] zdb -O command output')
            for line in objInfo:
                print(line.decode('utf-8'))
            print()
        raise Exception('Unexpected zdb -O command response')
    
    # parse lines into L0 pointers
    LX_POINTERS=[]
    tsize=None
    for line in objInfo:
        line = line.decode('utf-8')
        if line.strip() == '':
            continue
        lineList=[]
        for part in line.split(' '):
            if part!='': lineList.append(part)
        
        if len(lineList)>1:
            if not re.match(r'L\d$', lineList[1]):  
                continue # if not an LX pointer
            pointer = {
                    "level": lineList[1], # E.G. L0
                    "size": lineList[3], # physical/logical size
                    "vdev": lineList[2].split(':')[0],
                    "offset": lineList[2].split(':')[1], # offset of the block on the disk
                    "dumbsize": lineList[2].split(':')[2],
                    "fileoffset": lineList[0], # offset of this block from the start of the file
                    "???": False,
            }
            if len(lineList)>=7:
                pointer['checksums'] = lineList[6].strip().split('=')[1]
            else:
                pointer['checksums'] = None
                ### idk wtf this is, sometimes it will print like this:
                #   1ef160000   L0 0:0:0 20000L B=104154
                # idk what'd happen if you tried to read one of these with zdb,
                # not my problem rn
                pointer['???'] = True
            
            isC = re.match(r'([0-9a-fA-F]{1,20})L/([0-9a-fA-F]{1,20})P$', pointer['size'])
            if isC:
                if isC[1]==isC[2]: pointer['isCompressed'] = False
                else: pointer['isCompressed'] = True
            else: pointer['isCompressed'] = None
            
            LX_POINTERS.append(pointer)
        
        else:
            lineList = lineList[0].split('\t')
            if not len(lineList) > 1:
                continue
            if lineList[1] == 'size':
                tsize = int(lineList[2].strip())
    
    if tsize == None:
        raise Exception('Unable to get total filesize')
    
    if args.debug:
        print(f'[debug] total filesize is \n{tsize}')
    
    return LX_POINTERS, path['mntPoint'], tsize

def main(args):
    # zdb -U /data/zfs/zpool.cache -R Boys 0:156ecb3f5000:20000L/8000P:rd > /mnt/Boys/audrey/testing/browserhist_l0_0_raw1_2.txt
    # python /mnt/Boys/audrey/testing/zdb_recover.py -i "/mnt/Boys/audrey/2022.09.15 centbrowser history" -o "/mnt/Boys/audrey/testing/dump.bin"
    
    print('Starting...')
    pointers, mntPoint, tsize = getObjBlkPointers(args)
    
    outfileExists = os.path.isfile(args.output_file)
    if not args.overwrite and outfileExists:
        raise Exception(f'Specified output file {args.output_file} already exists!')
    if outfileExists and args.debug:
        print('\n[debug] overwriting output file\n')
    
    with open(args.output_file, 'wb') as OF:
        with open(args.input_file, 'rb') as IF:
            previousOffset=None
            i=1
            byteCounter=0
            badBlockCounter=0
            for pointer in pointers:
                if pointer['level'] != 'L0': continue # skip non-data pointers
                if previousOffset != None: # check previous offset
                    if not int(pointer['fileoffset'], 16) > previousOffset:
                        raise Exception('Error, object block pointers being read out of order, not possible to properly reconstruct file') # it is possible you liar!!!     just not implemented.. 👉👈
                
                try:
                    IF.seek(byteCounter)
                    blockLen = re.match(r'^(\d{1,10})L', pointer['size'])
                    if blockLen:
                        blockLen=int(blockLen[1], 16)
                    else:
                        raise Exception('Error getting logical length of block')
                    blockBin = IF.read(blockLen)
                except OSError as e:
                    if not 'Input/output error' in str(e):
                        raise e
                    badBlockCounter+=1
                    print(f'block {i} is damaged')
                    
                    if pointer['isCompressed'] == None:
                        raise Exception('undefined block physical/logical bytes ratio?')
                    
                    # form command to read block
                    command = ['zdb']
                    if args.truenas:
                        command += ['-U', '/data/zfs/zpool.cache']
                    
                    command += [
                        '-R', mntPoint,
                        f"{pointer['vdev']}:{pointer['offset']}:{pointer['size']}:r{'d' if pointer['isCompressed'] else ''}"
                    ]
                    
                    proc = subprocess.Popen(command, stdout=subprocess.PIPE)
                    
                    # read-in binary
                    blockBin = bytes()
                    for data in proc.stdout:
                        blockBin += data
                    
                    if proc.returncode != None:
                        if args.debug:
                            print(f'\n[debug] printing -R command output\n')
                            for line in blockBin.splitlines():
                                print(line.decode('utf-8'))
                        raise Exception('Unexpected zdb -R command response')
                
                OF.write(blockBin[:tsize - byteCounter])
                byteCounter+=len(blockBin[:tsize - byteCounter]) # count bytes excluding overshoot no the last block
                
                print(f"({i}/{len(pointers)}) read {byteCounter} bytes total")
                
                previousOffset = int(pointer['fileoffset'], 16)
                i+=1
    print(f'Successfully copied {os.path.split(args.input_file)[1]}! ({byteCounter} bytes, {badBlockCounter} damaged blocks)')

if __name__=='__main__':
    # parse args
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-file', default=None, help='input file to read')
    parser.add_argument('-o', '--output-file', default=None, help='output file to write')
    parser.add_argument('-X', '--overwrite', action='store_true', help='overwrite output file if exists')
    parser.add_argument('-t', '--truenas', action='store_true', help='use this flag if your ZFS install is on Truenas')
    parser.add_argument('--debug', action='store_true', help='use this flag to print debug informations')
    
    args = parser.parse_args()
    
    if None in [args.input_file, args.output_file]:
        parser.print_help()
        print('\nTHE INPUT AND OUTPUT FILE ARGUMENTS ARE NOT OPTIONAL.')
        exit()
    
    main(args)
