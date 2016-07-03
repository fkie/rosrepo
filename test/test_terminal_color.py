# coding=utf-8
#
# ROSREPO
# Manage ROS workspaces with multiple Gitlab repositories
#
# Author: Timo Röhling
#
# Copyright (c) 2016 Fraunhofer FKIE
#
#
import unittest

import sys
sys.stderr = sys.stdout

import rosrepo.terminal_color as tc
import rosrepo.ui as ui

class TerminalColorTest(unittest.TestCase):

    def test_enable_disable(self):
        tc.set_color(False)
        self.assertEqual(tc.fmt("@!Bold@|"), "Bold")
        tc.set_color(True)
        self.assertTrue(tc.fmt("@!Bold@|").startswith("\x1b"))

    def test_ansi_string(self):
        tc.set_color(True)
        self.assertEqual(ui.remove_ansi(tc.fmt("@!Bold@{yf}yellow@|")), "Boldyellow")
        self.assertEqual(len(ui.printed_len(tc.fmt("@!Bold@{yf}yellow@|"))), len("Boldyellow"))
        self.assertEqual(
            len(ui.printed_len(ui.pad_ansi_text(tc.fmt("@!This@|@|@|is@{yf}an@{rf}example"), 8))), 8
        )
        self.assertEqual(
            len(ui.printed_len(ui.pad_ansi_text(tc.fmt("@!This@|@|@|is@{yf}an@{rf}example"), 64))), 64
        )

    def test_text_wrap(self):
        tc.set_color(True)
        paragraph = """This is a @|@|@|@|@|@|@|paragraph with @!bold@| text, @{cf}cyan@| text, and @{yf}yellow@| text."""
        wrapped_text = ui.wrap_ansi_text(tc.fmt(paragraph), width=None)
        self.assertEqual(wrapped_text,
             (tc.fmt(paragraph))
        )
        wrapped_text = ui.wrap_ansi_text(tc.fmt(paragraph), width=16).split("\n")
        self.assertTrue(
            max([len(ui.printed_len(t)) for t in wrapped_text]) <= 16
        )
        wrapped_text = ui.wrap_ansi_text(tc.fmt(paragraph), width=16, indent_first=4).split("\n")
        self.assertTrue(
            max([len(ui.printed_len(t)) for t in wrapped_text]) <= 16
        )
        self.assertEqual(wrapped_text[0][:5], "    T")
        wrapped_text = ui.wrap_ansi_text(tc.fmt(paragraph), width=16, indent_first=4, indent_next=4).split("\n")
        self.assertTrue(
            max([len(ui.printed_len(t)) for t in wrapped_text]) <= 16
        )
        for t in wrapped_text:
            self.assertEqual(t[:4], "    ")
            self.assertNotEqual(t[4], " ")

