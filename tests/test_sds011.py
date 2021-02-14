""" test file for sds011 package """

import pytest
import os

from sds011 import SDS011

TESTPORT = "/dev/ttyUSB0"


@pytest.mark.skipif(not os.path.exists(TESTPORT), reason="this test requires a serial port")
def test_sds011(port=TESTPORT):
    sds = SDS011(port=port)
    assert sds
