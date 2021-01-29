from unittest import TestCase

from lib.TWCManager.Control.KNXControl import is_knx_address, is_valid_port


class Test(TestCase):
    def test_is_knx_address(self):
        self.assertTrue(is_knx_address("1/1/123"))
        self.assertTrue(is_knx_address("111/222/123"))
        self.assertFalse(is_knx_address("1/1111/123"))
        self.assertFalse(is_knx_address("1.1.123"))

    def test_is_valid_port(self):
        self.assertTrue(is_valid_port(1))
        self.assertTrue(is_valid_port(65000))
        self.assertFalse(is_valid_port(65536))

        self.assertTrue(is_valid_port("1"))
        self.assertTrue(is_valid_port("65000"))
        self.assertFalse(is_valid_port("65536"))
