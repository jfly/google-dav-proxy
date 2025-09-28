import contextlib
import os
import tempfile


# Copied from <https://github.com/pimutils/vdirsyncer/blob/v0.20.0/vdirsyncer/utils.py#L229>.
@contextlib.contextmanager
def atomic_write(dest, mode="wb", overwrite=False):
    if "w" not in mode:
        raise RuntimeError("`atomic_write` requires write access")

    fd, src = tempfile.mkstemp(prefix=os.path.basename(dest), dir=os.path.dirname(dest))
    file = os.fdopen(fd, mode=mode)

    try:
        yield file
    except Exception:
        os.unlink(src)
        raise
    else:
        file.flush()
        file.close()

        if overwrite:
            os.rename(src, dest)
        else:
            os.link(src, dest)
            os.unlink(src)
