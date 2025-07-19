#!/usr/bin/env python

from unittest import TestCase, main
from unittest.mock import Mock

from tk_gui.geometry.base import Size, Padding


class SizeTest(TestCase):
    def test_size_str(self):
        self.assertEqual('3 x 4', str(Size(3, 4)))

    def test_size_add_padding(self):
        self.assertEqual(Size(9, 8), Size(3, 4) + Padding(1, 2, 3, 4))

    def test_size_add_size(self):
        self.assertEqual((1, 2, 3, 4), Size(1, 2) + Size(3, 4))

    def test_size_add_tuple(self):
        self.assertEqual((1, 2, 3, 4, 5), Size(1, 2) + (3, 4, 5))

    def test_size_add_other(self):
        size = Size(3, 4)
        for case in (1, [1, 2]):
            with self.subTest(case=case), self.assertRaises(TypeError):
                size + case


class PaddingTest(TestCase):
    def test_init_4(self):
        pad = Padding(1, 2, 3, 4)
        self.assertEqual((1, 2, 3, 4), (pad.top, pad.right, pad.bottom, pad.left))

    def test_init_3(self):
        pad = Padding(1, 2, 3)
        self.assertEqual((1, 2, 3, 2), (pad.top, pad.right, pad.bottom, pad.left))

    def test_init_2(self):
        pad = Padding(1, 2)
        self.assertEqual((1, 2, 1, 2), (pad.top, pad.right, pad.bottom, pad.left))

    def test_init_1(self):
        pad = Padding(1)
        self.assertEqual((1, 1, 1, 1), (pad.top, pad.right, pad.bottom, pad.left))

    def test_0_false(self):
        self.assertFalse(Padding(0))

    def test_other_true(self):
        for case in (Padding(1, 0, 0, 0), Padding(0, 1, 0, 0), Padding(0, 0, 1, 0), Padding(0, 0, 0, 1), Padding(1)):
            with self.subTest(case=case):
                self.assertTrue(case)

    def test_add_size(self):
        self.assertEqual((5, 6), Padding(2) + Size(1, 2))

    def test_add_tuple(self):
        self.assertEqual((5, 6), Padding(2) + (1, 2))

    def test_add_obj_with_size_attr(self):
        self.assertEqual((5, 6), Padding(2) + Mock(size=(1, 2)))

    def test_add_other(self):
        pad = Padding(1)
        for case in (1, (1, 2, 3), ('a', 'b'), Mock(size=(1, 2, 3)), Mock(size=None)):
            with self.subTest(case=case), self.assertRaises(TypeError):
                pad + case


if __name__ == '__main__':
    main(verbosity=2)
