# coding=utf-8
#
# ROSREPO
# Manage ROS workspaces with multiple Gitlab repositories
#
# Author: Timo Röhling
#
# Copyright 2016 Fraunhofer FKIE
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
import unittest

import sys
import os
sys.stderr = sys.stdout

try:
    from mock import patch
except ImportError:
    from unittest.mock import patch

import rosrepo.terminal_color as tc
import rosrepo.ui as ui
import test.helper as helper


class TerminalColorTest(unittest.TestCase):

    def test_color_enable(self):
        """Test global flag for terminal coloring"""
        tc.set_color(False)
        self.assertEqual(tc.fmt("@!Bold@|"), "Bold")
        tc.set_color(True)
        self.assertTrue(tc.fmt("@!Bold@|").startswith("\x1b"))

    def test_ansi_string(self):
        """Test proper handling of ANSI annotated strings"""
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
        """Test line wrapping for fixed terminal width"""
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
        ansi_paragraph = tc.fmt(paragraph)
        ansi_words = ansi_paragraph.split()
        for width in range(len(paragraph)):
            self.assertEqual(
                ui.wrap_ansi_text(ansi_paragraph, width).split(),
                ansi_words
            )
        paragraph = "This    is Sparta"
        self.assertEqual(
            ui.wrap_ansi_text(paragraph, 4),
            "This\nis\nSparta"
        )

    def test_msg_without_terminal(self):
        """Test fallback if rosrepo is run without proper terminal"""
        with patch("os.ctermid", lambda: os.devnull):
            stdin = helper.StringIO("Timo\n")
            stderr = helper.StringIO()
            with patch("sys.stdin", stdin):
                with patch("sys.stderr", stderr):
                    name = ui.readline("What is your name: ")
                    ui.error("To Err Is Human\n")
                    ui.warning("Hello there!\n")
                    ui.msg("Hi %s!" % name)
                    table = ui.TableView()
                    table.add_row("One", "1")
                    table.add_row("More Data here", "Yay")
                    table.add_row(u"Oh-oh", u"Ünicöde nightmare")
                    table.sort(0)
                    table.write(fd=stderr)
                    with patch("rosrepo.ui.get_terminal_size", lambda: (5, 5)):
                        table.write(fd=stderr)
                    with patch("rosrepo.ui.get_terminal_size", lambda: (15, 5)):
                        table.write(fd=stderr)
            stderr = stderr.getvalue()
            self.assertIn("Human", stderr)
            self.assertIn("Hello there!", stderr)
            self.assertIn("Hi Timo!", stderr)

    def test_reformat_paragraphs(self):
        """Test reformatting paragraphs with embedded newlines"""
        self.assertEqual(
            ui.reformat_paragraphs("\n\n\nThis is a\nhard-wrapped paragraph.\n\nThis is a second paragraph in one line.\n\n    This is a hard-wrapped\n    paragraph with indentation.\n\r\n"),
            "This is a hard-wrapped paragraph.\n\nThis is a second paragraph in one line.\n\nThis is a hard-wrapped paragraph with indentation."
        )
