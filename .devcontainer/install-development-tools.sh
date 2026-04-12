#!/bin/bash
apt update && apt install docker.io -y
make init && make init-dev && make install
