"""Three shared execution lanes for the two authorized independent campaigns."""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import json
import os
import time


@contextmanager
def lane(identity):
    root=Path(os.environ['SKILLHONE_SHARED_ROOT'])
    locks=root/'lanes';locks.mkdir(exist_ok=True)
    receipts=root/'lane-receipts';receipts.mkdir(exist_ok=True)
    receipt=receipts/(identity+'.json')
    def save(status,number=None):
        receipt.write_text(json.dumps({'identity':identity,'pid':os.getpid(),'status':status,'lane':number,'time':time.time()})+'\n')
    save('waiting')
    chosen=None
    while chosen is None:
        for number in range(3):
            handle=(locks/f'{number}.lock').open('a')
            try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:handle.close();continue
            chosen=(number,handle);break
        if chosen is None:time.sleep(0.5)
    number,handle=chosen;save('running',number)
    try:
        yield handle.fileno()
    except BaseException:
        save('failed',number);raise
    else:save('complete',number)
    finally:
        fcntl.flock(handle.fileno(),fcntl.LOCK_UN);handle.close()
