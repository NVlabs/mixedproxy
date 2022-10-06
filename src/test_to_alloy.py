#!/usr/bin/env python3

import sys
import argparse
import output
import subprocess
import os
import re
from litmus_parser import parse


basepath = os.path.dirname(__file__) + "/.."


def litmus_to_alloy(model, input_file):
    output.verbose("Original test:\n")
    test = parse(model, input_file)
    output.verbose(test)

    output.verbose("Alloy translation:\n")
    alloy = test.to_alloy()
    output.verbose(alloy)

    return alloy, test.commands


def run_alloy(model, text, out=None, allow_failure=False):
    text, commands = litmus_to_alloy(model, text)

    if out:
        with open(out, "w") as f:
            f.write(text)

    output.info("Launching Alloy...\n")
    output.godbolt("\n// Launching Alloy...\n")
    proc = subprocess.run(
        [
            "java",
            "-cp",
            basepath
            + "/alloy:"
            + basepath
            + "/alloy/org.alloytools.alloy.dist.jar",
            "RunAlloy",
        ],
        input=text.encode(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    out = proc.stdout.decode()
    output.info(out)

    line = None
    for ln in out.split("\n"):
        if not ln:
            line = None
        else:
            match = re.search("^([A-Za-z_][A-Za-z0-9_]*): ", ln)
            if match:
                name = match.group(1)
                try:
                    command = commands[name]
                    line = command.line
                except KeyError:
                    if len(name) > 7 and name[:7] == "sanity_":
                        try:
                            command = commands[name[7:]]
                            line = command.line
                        except KeyError:
                            line = None
                    else:
                        line = None
        if line:
            output.godbolt(ln, line)
        else:
            output.godbolt(ln)

    sys.stderr.write(proc.stderr.decode())

    if proc.returncode != 0:
        sys.stderr.write(f"Alloy exited with code {proc.returncode}\n")
        output.always("// Alloy exited with non-zero return code\n")
        if not allow_failure:
            sys.exit(1)


def main(argv=sys.argv[1:], input_string=None):
    arg_parser = argparse.ArgumentParser(
        description="Convert a readable PTX-like litmus test into an Alloy representation."
    )
    arg_parser.add_argument(
        dest="input",
        type=str,
        help="input filename (stdin if left empty)",
        nargs="?",
    )
    arg_parser.add_argument(
        "-o",
        dest="output",
        type=str,
        default="",
        help="output filename (stdout if left empty)",
    )
    arg_parser.add_argument(
        "-a",
        dest="alloy",
        type=str,
        default="",
        help="save alloy model to specified file",
    )
    arg_parser.add_argument(
        "-m",
        dest="model",
        default=basepath + "/alloy/ptx.als",
        help="Alloy model",
    )
    arg_parser.add_argument(
        "-g", dest="godbolt", action="store_true", help="Godbolt mode"
    )
    arg_parser.add_argument(
        "-q", dest="quiet", action="store_true", help="Quiet mode"
    )
    arg_parser.add_argument(
        "-s",
        dest="skip",
        default=0,
        type=int,
        help="For templates, skip the first N tests",
    )
    arg_parser.add_argument(
        "-v", dest="verbose", action="store_true", help="verbose"
    )
    arg_parser.add_argument(
        "--version", action="store_true", help="verbose"
    )

    args = arg_parser.parse_args(argv)

    if args.version:
        print("NVLitmus version 0.1")
        sys.exit(0)

    if args.verbose:
        output.set_verbose(True)

    if args.output:
        output.set_output(open(args.output, "w"))

    if args.godbolt:
        output.set_godbolt(True, args.input)

    if args.quiet:
        output.set_info(False)

    warning_string = """// NVLitmus is a research prototype, and comes with no guarantees of completeness, correctness, or authoritativeness.  Please see https://github.com/NVlabs/mixedproxy for more information.
"""
    output.info(warning_string)
    output.godbolt(warning_string)

    with open(args.model, "r") as f:
        model = f.read()

    if args.input:
        with open(args.input, "r") as f:
            input_file = f.read()
    elif input_string is not None:
        input_file = input_string
    else:
        input_file = sys.stdin.read()

    if "$$" in input_file:
        n = 0
        test, parameter_lists = input_file.split("$$\n")
        instances = [
            i for i in parameter_lists.split("\n") if i.strip() and i[0] != "#"
        ]
        output.info(f"{len(instances)} instances\n\n")
        for parameter_list in instances:
            if n < args.skip:
                n += 1
                continue
            # sys.stdout.write(f'Instance {n}: {parameter_list.strip()}\n')
            instance = test
            for i, parameter in enumerate(parameter_list.split("|")):
                instance = instance.replace(f"${i}", parameter.strip())
            output.info(f"Litmus test instance is:\n{instance}")
            output.info(f"\n\nInstance {n+1}/{len(instances)}:\n{instance}\n")
            run_alloy(model, instance, args.alloy, args.godbolt)
            output.info("\n")
            n += 1
        output.info("Done!\n")
    else:
        output.info(f"Test:\n{input_file}\n")
        run_alloy(model, input_file, args.alloy, args.godbolt)


if __name__ == "__main__":
    main()
