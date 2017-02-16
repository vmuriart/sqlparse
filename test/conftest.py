# -*- coding: utf-8 -*-

"""Helpers for testing."""

import io
import os

import pytest


import ctypes
import sys
import sysconfig


def pytest_report_header(config):
    """Generate extra report headers"""
    is_64bits = sys.maxsize > 2**32
    arch = "x64" if is_64bits else "x86"
    arch = "Arch: {0}".format(arch)

    ucs = ctypes.sizeof(ctypes.c_wchar)
    libdir = sysconfig.get_config_var("LIBDIR")
    shared = bool(sysconfig.get_config_var("Py_ENABLE_SHARED"))

    output = ("Arch: {arch}, UCS: {ucs}, LIBDIR: {libdir}, "
              "Py_ENABLE_SHARED: {shared}".format(**locals()))

    return output


DIR_PATH = os.path.dirname(__file__)
FILES_DIR = os.path.join(DIR_PATH, 'files')


@pytest.fixture()
def filepath():
    """Returns full file path for test files."""

    def make_filepath(filename):
        # http://stackoverflow.com/questions/18011902/parameter-to-a-fixture
        # Alternate solution is to use paramtrization `inderect=True`
        # http://stackoverflow.com/a/33879151
        # Syntax is noisy and requires specific variable names
        return os.path.join(FILES_DIR, filename)

    return make_filepath


@pytest.fixture()
def load_file(filepath):
    """Opens filename with encoding and return its contents."""

    def make_load_file(filename, encoding='utf-8'):
        # http://stackoverflow.com/questions/18011902/parameter-to-a-fixture
        # Alternate solution is to use paramtrization `inderect=True`
        # http://stackoverflow.com/a/33879151
        # Syntax is noisy and requires specific variable names
        # And seems to be limited to only 1 argument.
        with io.open(filepath(filename), encoding=encoding) as f:
            return f.read().strip()

    return make_load_file


@pytest.fixture()
def get_stream(filepath):
    def make_stream(filename, encoding='utf-8'):
        return io.open(filepath(filename), encoding=encoding)

    return make_stream
