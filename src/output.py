#!/usr/bin/env python3

import sys


output = sys.stdout

def set_output(f):
    global output
    output = f


def always(s):
    output.write(str(s))


_info = True


def set_info(info):
    global _info
    _info = info


def info(s):
    if _info:
        output.write(str(s))


_verbose = False


def set_verbose(verbose):
    global _verbose
    _verbose = verbose


def verbose(s):
    if _info and _verbose:
        output.write(str(s))


_godbolt_mode = False


def set_godbolt(mode, filename):
    global _godbolt_mode
    global _info
    _godbolt_mode = mode
    _info = not mode
    always(f".file 1 \"{filename}\"\n")


def godbolt(s, line=None):
    if _godbolt_mode:
        if line is not None:
            output.write(f".loc 1 {line} 1\n")
        output.write(f"{s}\n")
