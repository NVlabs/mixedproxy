# Mixed-Proxy Extensions for the NVIDIA PTX Memory Consistency Model

This repository contains the artifact assocatied with the following paper:

Daniel Lustig, Simon Cooksey, and Olivier Giroux, "Mixed-Proxy Extensions for the NVIDIA PTX Memory Consistency Model", _49th International Symposium on Computer Architecture (ISCA), Industry Track_, New York, NY, USA, 2022.

This is a research prototype meant to help us evaluate the content of the paper.  It is not production-quality tooling, and it comes with no guarantees of correctness or completeness.  The [PTX Memory Consistency Model documentation](https://docs.nvidia.com/cuda/parallel-thread-execution/index.html#memory-consistency-model) serves as the authoritative reference for PTX.

If you are interested in using or extending the tooling or concepts in the paper or in this artifact, I (Dan) would be happy to work with you.  Please feel free to reach out to dlustig@nvidia.com with any questions.

## Features

* The mixed-proxy PTX memory model, encoded in Alloy
* A human-readable litmus test format (see [grammar](src/grammar.lark)), and a collection of [litmus tests](tests)
* A tool called "nvlitmus" to run the tests by automatically converting them into Alloy syntax and then running them

The proxy model is designed to accomodate more proxies in the future, but as of now, this research tool currently supports two types of proxies:
* Virtual aliases (officially supported PTX)
* Abstracted forms of surface, texture, and constant operations (not officially supported in PTX, but explored as a hypothetical in the paper)

See the sample litmus test for examples of how to use the tool.
 
## Usage

`./src/test_to_alloy.py <foo.test> [-o <foo.als>]`

For more verbosity, add `-v`.

For Compiler Explorer mode, add `-g`.

Run `./src/test_to_alloy.py.py -h` for other options.

All tests automatically run a `sanity` check to make sure the test is at least well-formed, independent of memory model constraints.

## Installation

### Docker

The [Dockerfile](Dockerfile) can be used to containerize nvlitmus.

It can be built using:

```
docker build -t nvlitmus:latest .
```

It can then be run as follows (for example):

```
docker run --rm nvlitmus:latest tests/SB_cta.test  # run test from within container
docker run --rm -i nvlitmus:latest < foo.test  # run a test provided via stdin
docker run --rm -i nvlitmus:latest -g < foo.test  # run in godbolt mode
```

### Direct install

0. Run `python3 -m pip install lark-parser` (NOTE: `lark-parser` not `lark`) to install the [lark](https://github.com/lark-parser/lark) parser in python.  Do this in a venv if you'd like, or pick your favorite form of python packaging.
1. Call `make` to build the Alloy command line front end `RunAlloy.class`
2. Look over the existing tests in the [tests](tests) folder, or write a new test
3. Call `./src/test_to_alloy.py <file>`, or run `make check` to run all tests in the suite
