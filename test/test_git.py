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

import os
import sys
sys.stderr = sys.stdout
import shutil

from tempfile import mkdtemp
try:
    from mock import patch
except ImportError:
    from unittest.mock import patch
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from .helper import call_process

import rosrepo.git as git

class GitTest(unittest.TestCase):

    def setUp(self):
        self.upstream_gitdir = mkdtemp()
        self.upstream_git = git.Git(self.upstream_gitdir)
        self.upstream_git.init()
        self.upstream_git.config("user.name", "Unit Tester")
        self.upstream_git.config("user.email", "unittest@example.com")
        with open(os.path.join(self.upstream_gitdir, "hello.txt"), "w") as f:
            f.write("Hello, World!\n")
        self.upstream_git.add("hello.txt")
        self.upstream_git.commit(m="First commit")
        self.upstream_git.tag("ancient")
        with open(os.path.join(self.upstream_gitdir, "hello.txt"), "a") as f:
            f.write("Nice to see you...\n")
        self.upstream_git.add("hello.txt")
        self.upstream_git.commit(m="More text")
        self.upstream_git.checkout("other", b=True)
        with open(os.path.join(self.upstream_gitdir, "other.txt"), "w") as f:
            f.write("One file to rule them all...\n")
        self.upstream_git.add("other.txt")
        self.upstream_git.commit(m="Moar files")
        self.upstream_git.checkout("master")
        with open(os.path.join(self.upstream_gitdir, "other.txt"), "w") as f:
            f.write("I for one welcome our new Git overlords\n")
        self.upstream_git.add("other.txt")
        self.upstream_git.commit(m="Pledge allegiance")

        self.gitdir = mkdtemp()
        self.git = git.Git(self.gitdir)
        self.git.clone(self.upstream_gitdir, ".")
        self.git.config("user.name", "Unit Tester")
        self.git.config("user.email", "unittest@example.com")
        self.git.branch("other", "origin/other", track=True)

    def tearDown(self):
        shutil.rmtree(self.gitdir, ignore_errors=True)
        shutil.rmtree(self.upstream_gitdir, ignore_errors=True)

    def test_read_access(self):
        """Test Python Git API (read only)"""
        repo = git.Repo(self.gitdir)
        upstream_repo = git.Repo(self.upstream_gitdir)
        invalid_repo = git.Repo("invalid")
        self.assertTrue(repo)
        self.assertFalse(invalid_repo)
        self.assertNotEqual(repo, upstream_repo)
        self.assertEqual(repo.workspace, self.gitdir)

        self.assertIsInstance(repo.refs, git.RootReference)
        self.assertIsInstance(repo.refs.heads, git.Branches)
        self.assertIsInstance(repo.refs.heads.master, git.BranchReference)
        self.assertIsInstance(repo.refs.tags, git.Tags)
        self.assertIsInstance(repo.refs.tags.ancient, git.TagReference)
        self.assertIsInstance(repo.refs.remotes, git.Remotes)
        self.assertIsInstance(repo.refs.remotes.origin, git.Remote)
        self.assertIsInstance(repo.refs.remotes.origin.master, git.RemoteReference)

        self.assertEqual(repo.from_string("invalid"), None)
        self.assertEqual(repo.from_string("HEAD"), repo.head)
        self.assertEqual(repo.from_string("ORIG_HEAD"), repo.orig_head)
        self.assertEqual(repo.from_string("FETCH_HEAD"), repo.fetch_head)
        self.assertEqual(repo.from_string("MERGE_HEAD"), repo.merge_head)
        self.assertEqual(repo.from_string("refs"), repo.refs)
        self.assertEqual(repo.from_string("refs/heads"), repo.refs.heads)
        self.assertEqual(repo.from_string("refs/remotes"), repo.remotes)
        self.assertEqual(repo.from_string("refs/tags"), repo.tags)
        self.assertEqual(repo.from_string("refs/invalid"), None)
        self.assertEqual(repo.from_string("refs/heads/master"), repo.heads.master)
        self.assertEqual(repo.from_string("refs/tags/foo"), repo.tags.foo)
        self.assertEqual(repo.from_string("refs/remotes/bar"), repo.remotes.bar)
        self.assertEqual(repo.from_string("refs/remotes/bar/master"), repo.remotes.bar.master)

        self.assertEqual(repo.head.commit, repo.heads.master.commit)
        self.assertRaises(AttributeError, lambda: repo.head.other)
        self.assertEqual(repo.refs.heads.master, repo.heads.master)
        self.assertEqual(repo.heads.master, repo.heads["master"])
        self.assertNotEqual(repo.heads.master, repo.heads.other)
        self.assertNotEqual(repo.heads.master, upstream_repo.heads.master)
        self.assertFalse(repo.heads.master.is_ancestor(repo.heads.other))
        self.assertTrue(repo.heads.master.merge_base(repo.heads.other).is_ancestor(repo.heads.master))
        self.assertTrue(repo.heads.master.merge_base(repo.heads.other).is_ancestor(repo.heads.other))
        self.assertTrue(repo.heads.master)
        self.assertFalse(repo.heads.missing)

        self.assertTrue(repo.heads.master in repo.heads)
        self.assertFalse(repo.head in repo.heads)
        self.assertTrue("master" in repo.heads)
        self.assertFalse("missing" in repo.heads)
        self.assertTrue("origin" in repo.remotes)
        self.assertFalse("other" in repo.remotes)
        self.assertTrue(repo.remotes.origin)
        self.assertFalse(repo.remotes.other)
        self.assertFalse(repo.fetch_head)

        self.assertEqual(repo.heads.master.branch_name, "master")
        self.assertEqual(repo.heads.other.branch_name, "other")
        self.assertEqual(repo.heads.other.ref_name, "refs/heads/other")
        self.assertEqual(repo.heads.master.name, "master")
        self.assertEqual(str(repo.heads.master), "master")
        self.assertEqual(str(repo.tags.ancient), "ancient")
        self.assertEqual(str(repo.head), "HEAD")
        self.assertEqual(repo.head.name, "HEAD")
        self.assertEqual(repo.head.reference, repo.heads.master)
        self.assertEqual(str(repo.orig_head), "ORIG_HEAD")
        self.assertFalse(repo.orig_head)
        self.assertEqual(str(repo.fetch_head), "FETCH_HEAD")
        self.assertFalse(repo.fetch_head)
        self.assertEqual(str(repo.merge_head), "MERGE_HEAD")
        self.assertFalse(repo.merge_head)
        self.assertEqual(repo.conflicts(), [])


        self.assertEqual(repo.refs.remotes.origin, repo.remotes.origin)
        self.assertEqual(repo.remotes.origin.master.name, "origin/master")
        self.assertEqual(repo.remotes.origin.master.remote_name, "origin")
        self.assertEqual(repo.remotes.origin.master.branch_name, "master")
        self.assertEqual(repo.remotes.origin.master, repo.remotes.origin["master"])
        self.assertEqual(repo.remotes.origin, repo.remotes["origin"])
        self.assertTrue("master" in repo.remotes.origin)
        self.assertTrue("origin/master" in repo.remotes.origin)
        self.assertFalse("missing" in repo.remotes.origin)
        self.assertTrue(repo.remotes.origin.master in repo.remotes.origin)
        self.assertFalse(repo.heads.master in repo.remotes.origin)

        for ref in repo.heads:
            self.assertIsInstance(ref, git.BranchReference)
        for remote in repo.remotes:
            self.assertIsInstance(remote, git.Remote)
            self.assertTrue(remote["master"].commit == repo.head.commit)
        for ref in repo.remote("origin"):
            self.assertIsInstance(ref, git.RemoteReference)
            self.assertEqual (ref.remote, repo.remote("origin"))
            self.assertTrue(ref.branch_name != "master" or ref == repo.remotes.origin.master)
            self.assertTrue(ref.branch_name == "master" or ref != repo.remotes.origin.master)

        self.assertEqual(str(repo.remote("origin")), "origin")
        self.assertEqual(repo.remote("origin").url, self.upstream_gitdir)
        self.assertEqual(repo.remote("origin").push_url, self.upstream_gitdir)
        self.assertTrue(repo.head.commit == repo.heads.master.commit)
        self.assertTrue(repo.head.commit == repo.remotes.origin.master.commit)
        self.assertEqual(repo.head.tree, repo.heads.master.tree)

        self.assertEqual(repo.heads.master.tracking_branch, repo.remotes.origin.master)
        self.assertIsNone(upstream_repo.heads.master.tracking_branch)
        self.assertNotEqual(repo.heads.master, upstream_repo.heads.master)
        self.assertNotEqual(repo.remotes.origin, upstream_repo.remotes.origin)

        s = set([repo.heads.master, repo.heads.other])
        self.assertIn(repo.head.reference, s)
        s = set([repo.remotes.origin])
        self.assertIn(repo.remote("origin"), s)
        s = set([repo])
        self.assertIn(repo, s)

        stdout = StringIO()
        with patch("sys.stdout", stdout):
            with patch("sys.stderr", stdout):
                with patch("rosrepo.git.call_process", call_process):
                    repo.git.status(console=True)
        stdout = stdout.getvalue()
        self.assertIn("On branch master", stdout)
        self.assertIn("nothing to commit", stdout)

        self.assertEqual(repr(repo), "Repo(%r)" % self.gitdir)
        self.assertEqual(repr(repo.remotes.origin), "Remote(Repo(%r), %r)" % (self.gitdir, "origin"))
        self.assertEqual(repr(repo.heads), "Branches(Repo(%r))" % self.gitdir)
        self.assertEqual(repr(repo.heads.master), "BranchReference(Repo(%r), %r)" % (self.gitdir, "refs/heads/master"))

        def simulate_git_fail(*args, **kwargs):
            return 128, "", "fail"
        with patch("rosrepo.git.call_process", simulate_git_fail):
            self.assertRaises(git.GitError, repo.heads.master.is_ancestor, repo.head)
            self.assertRaises(git.GitError, repo.git.reset, on_fail="myfail")

    def test_write_access(self):
        """Test Python Git API (write access)"""
        def del_helper(arg):
            del arg
        repo = git.Repo(self.gitdir)
        self.assertFalse(repo.is_dirty())
        with open(os.path.join(self.gitdir, "untracked.txt"), "w") as f:
            f.write("ha")
        self.assertTrue(repo.is_dirty())
        with repo.temporary_stash():
            self.assertFalse(repo.is_dirty())
            repo.git.checkout(repo.heads.other)
            self.assertEqual(repo.head.reference, repo.heads.other)
            with open(os.path.join(self.gitdir, "hello.txt"), "w") as f:
                f.write("Good bye")
            self.assertRaises(git.GitError, repo.git.merge, repo.heads.master)
            self.assertEqual(repo.conflicts(), ["other.txt"])
        self.assertTrue(repo.is_dirty())
        self.assertEqual(repo.head.reference, repo.heads.master)
        self.assertEqual(repo.uncommitted(), ["untracked.txt"])
        self.assertEqual(repo.uncommitted("hello.txt"), [])
        os.unlink(os.path.join(self.gitdir, "untracked.txt"))
        self.assertFalse(repo.is_dirty())
        self.assertEqual(repo.uncommitted(), [])
        with open(os.path.join(self.gitdir, "hello.txt"), "w") as f:
            f.write("Good bye")
        self.assertTrue(repo.is_dirty())
        self.assertEqual(repo.uncommitted(), ["hello.txt"])
        repo.git.reset(hard=True)
        self.assertFalse(repo.is_dirty())
        repo.git.checkout("master^")
        self.assertTrue(repo.detached_head())
        repo.git.checkout("master")
        self.assertFalse(repo.detached_head())
        self.assertFalse(repo.heads.test_branch)
        test_branch = repo.heads.new("test_branch")
        self.assertEqual(test_branch, repo.heads.test_branch)
        self.assertTrue(test_branch)
        self.assertFalse(test_branch.commit == repo.head.reference)
        test_branch.checkout()
        self.assertTrue(test_branch == repo.head.reference)
        repo.heads.master.checkout()
        test_branch.branch_name = "renamed_branch"
        self.assertTrue(test_branch)
        self.assertFalse(repo.heads.test_branch)
        self.assertTrue(repo.heads.renamed_branch)
        test_branch.delete()
        self.assertFalse(test_branch)
        test2 = repo.heads.new("test2")
        test2.checkout()
        with open(os.path.join(self.gitdir, "test2.txt"), "w") as f:
            f.write("Test2\n")
        repo.git.add("test2.txt")
        repo.git.commit(m="Test2 diverges")
        repo.heads.master.checkout()
        self.assertRaises(git.GitError, lambda: test2.delete())
        self.assertTrue(test2)
        test2.delete(force=True)
        self.assertFalse(test2)
        repo.heads.new("test3")
        self.assertTrue(repo.heads.test3)
        del repo.heads.test3
        self.assertFalse(repo.heads.test3)
        test_tag = repo.tags.new("test")
        self.assertTrue(test_tag)
        self.assertRaises(git.GitError, lambda: test_tag.tag)  # lightweight tag
        self.assertTrue(test_tag.commit == repo.head.commit)
        self.assertTrue(test_tag.tree == repo.head.tree)
        test_tag.reference = repo.heads.other
        self.assertTrue(test_tag.commit == repo.heads.other.commit)
        test_tag.delete()
        self.assertFalse(test_tag)
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            repo.git.branch("dream", set_upstream_to=repo.remotes.origin.master, simulate=True)
        self.assertEqual(stdout.getvalue(), "git -C %s branch --set-upstream-to=origin/master dream\n" % self.gitdir)
        self.assertFalse(repo.heads.dream)
        self.assertEqual(repo.heads.other.tracking_branch, repo.remotes.origin.other)
        repo.heads.other.tracking_branch = repo.remotes.origin.master
        self.assertEqual(repo.heads.other.tracking_branch, repo.remotes.origin.master)
        test_tag = repo.tags.new("test")
        self.assertTrue(test_tag)
        self.assertTrue(repo.tags.test)
        self.assertTrue(test_tag.commit == repo.head.commit)
        self.assertTrue(test_tag.commit == test_tag.reference)
        del repo.tags.test
        self.assertFalse(repo.tags.test)
        self.assertFalse(test_tag)
        test_tag = repo.refs.tags.new("test")
        self.assertTrue(test_tag)
        self.assertTrue(test_tag.commit == repo.head.commit)
        test_tag.reference = repo.heads.other
        self.assertFalse(test_tag.commit == repo.head.commit)
        self.assertTrue(test_tag.commit == repo.heads.other.commit)
        del repo.tags["test"]
        self.assertFalse(repo.tags.test)
        self.assertFalse(test_tag)
        example_remote = repo.remotes.new("example", self.upstream_gitdir)
        self.assertEqual(example_remote, repo.remotes.example)
        self.assertTrue(example_remote)
        example_remote.fetch()
        self.assertTrue(example_remote.master.commit == repo.remotes.origin.master.commit)
        example_remote.delete()
        self.assertFalse(example_remote)
        example_remote = repo.refs.remotes.new("example", "invalid")
        example_remote.url = self.upstream_gitdir
        example_remote.push_url = "still_invalid"
        example_remote.fetch()
        self.assertTrue(example_remote)
        self.assertTrue(example_remote.master.commit == repo.remotes.origin.master.commit)
        self.assertNotEqual(example_remote.url, example_remote.push_url)
        self.assertEqual(example_remote.name, "example")
        self.assertTrue(repo.remotes.example)
        example_remote.name = "shiny"
        self.assertEqual(example_remote.name, "shiny")
        self.assertFalse(repo.remotes.example)
        self.assertTrue(repo.remotes.shiny)
        del repo.remotes.shiny
        self.assertFalse(repo.remotes.shiny)
        self.assertFalse(example_remote)
