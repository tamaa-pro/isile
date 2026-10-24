import os,signal
def scan(uids):
    want=set(uids)
    out={}
    if not want:
        return out
    try:
        names=os.listdir("/proc")
    except OSError:
        return out
    for n in names:
        if not n.isdigit():
            continue
        try:
            with open("/proc/%s/comm"%n) as f:
                if not f.read().startswith("sshd"):
                    continue
            uid=None
            with open("/proc/%s/status"%n) as f:
                for l in f:
                    if l.startswith("Uid:"):
                        uid=int(l.split()[1])
                        break
            if uid not in want:
                continue
            with open("/proc/%s/stat"%n) as f:
                st=int(f.read().rpartition(")")[2].split()[19])
        except (OSError,ValueError,IndexError):
            continue
        out.setdefault(uid,[]).append((st,int(n)))
    for v in out.values():
        v.sort()
    return out
def kill(pid):
    try:
        os.kill(pid,signal.SIGKILL)
        return True
    except OSError:
        return False
