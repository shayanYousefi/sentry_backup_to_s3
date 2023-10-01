#!/usr/bin/env python3

from subprocess import run, PIPE
from sys import argv
from os import linesep
from json import loads
from datetime import datetime
import requests
import requests_unixsocket
import argparse

requests_unixsocket.monkeypatch()

def define_arguments():
    parser = argparse.ArgumentParser(description='Sentry backup script')
    parser.add_argument('--s3_endpoint',
    description='Endpoint to store backup file',
    )
    parser.add_argument('--access-key',
    description='Access key for s3')
    parser.add_argument('--secret-key',
    description='Secret key for s3')

endpoint = "unix:///var/run/docker.sock"

