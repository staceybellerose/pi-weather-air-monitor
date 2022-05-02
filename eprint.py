import sys

def eprint(*args, **kwargs):
    """
    Wrapper function for print() to use stderr instead of stdout.
    """
    print(*args, file=sys.stderr, **kwargs)
