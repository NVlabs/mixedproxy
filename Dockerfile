FROM ubuntu:20.04 as builder

RUN apt-get update && \
    DEBIAN_FRONTEND="noninteractive" TZ="America/Los_Angeles" apt-get install -y \
        openjdk-16-jdk \
        python3 \
        git \
        make \
        wget \
        && \
    git clone --depth=1 https://github.com/NVlabs/mixedproxy.git && \
    cd mixedproxy && \
    make

FROM ubuntu:20.04

COPY --from=builder mixedproxy ./src

RUN apt-get update && \
    DEBIAN_FRONTEND="noninteractive" TZ="America/New_York" apt-get install -y \
        openjdk-16-jre \
        python3 \
        python3-pip \
        && \
    python3 -m pip install --upgrade pip lark-parser

WORKDIR src

ENTRYPOINT ["python3", "src/test_to_alloy.py"]
