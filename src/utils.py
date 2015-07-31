from __future__ import print_function
import os
import sys
from contextlib import contextmanager

#-------------------------------------------------------------------------------
# stdout / stderr redirection code couretesy of J.F. Sebastien:
# http://stackoverflow.com/questions/4675728/redirect-stdout-to-a-file-in-python
#-------------------------------------------------------------------------------

def fileno(file_or_fd):
    fd = getattr(file_or_fd, 'fileno', lambda: file_or_fd)()
    if not isinstance(fd, int):
        raise ValueError("Expected a file (`.fileno()`) or a file descriptor")
    return fd

@contextmanager
def stdout_redirected(to=os.devnull, stdout=None):
    if stdout is None:
       stdout = sys.stdout

    stdout_fd = fileno(stdout)
    # copy stdout_fd before it is overwritten
    #NOTE: `copied` is inheritable on Windows when duplicating a standard stream
    with os.fdopen(os.dup(stdout_fd), 'wb') as copied:
        stdout.flush()  # flush library buffers that dup2 knows nothing about
        try:
            os.dup2(fileno(to), stdout_fd)  # $ exec >&to
        except ValueError:  # filename
            with open(to, 'wb') as to_file:
                os.dup2(to_file.fileno(), stdout_fd)  # $ exec > to
        try:
            yield stdout # allow code to be run with the redirected stdout
        finally:
            # restore stdout to its previous value
            #NOTE: dup2 makes stdout_fd inheritable unconditionally
            stdout.flush()
            os.dup2(copied.fileno(), stdout_fd)  # $ exec >&copied

def merged_stderr_stdout():  # $ exec 2>&1
    return stdout_redirected(to=sys.stdout, stdout=sys.stderr)

if __name__ == "__main__":
    stdout_fd = sys.stdout.fileno()

    with merged_stderr_stdout(sys.stdout):
         print('this is printed on stdout')
         print('this is also printed on stdout', file=sys.stderr)

    with open('output_merged_stderr.txt', 'w') as f:
        with merged_stderr_stdout():
            with stdout_redirected(f):
                print('redirected to a file')
                os.write(stdout_fd, b'it is redirected now\n')
                os.system('echo this is also redirected')
                print('this is also printed on stdout', file=sys.stderr)

    with open('output.txt', 'w') as f:
        with stdout_redirected(f):
            print('redirected to a file')
            os.write(stdout_fd, b'it is redirected now\n')
            os.system('echo this is also redirected')

    print('this is goes back to stdout')
