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
                z=f.read().rpartition(")")[2].split()
            st=int(z[19])
            pp=z[1]
            # one SSH connection = one authenticated sshd process whose parent is the root sshd monitor.
            # forked helper children (same uid and name) and orphans reparented to init are not connections.
            with open("/proc/%s/comm"%pp) as f:
                if not f.read().startswith("sshd"):
                    continue
            with open("/proc/%s/status"%pp) as f:
                puid=None
                for l in f:
                    if l.startswith("Uid:"):
                        puid=int(l.split()[1])
                        break
            if puid!=0:
                continue
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
