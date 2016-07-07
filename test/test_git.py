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

import rosrepo.git as git

class GitTest(unittest.TestCase):

    def setUp(self):
        self.upstream_gitdir = mkdtemp()
        self.upstream_git = git.Git(self.upstream_gitdir)
        self.upstream_git.init()
        with open(os.path.join(self.upstream_gitdir, "hello.txt"), "w") as f:
            f.write("Hello, World!\n")
        self.upstream_git.add("hello.txt")
        self.upstream_git.commit(m="First commit")
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
        self.git.branch("other", "origin/other", set_upstream=True)

    def tearDown(self):
        shutil.rmtree(self.gitdir, ignore_errors=True)
        shutil.rmtree(self.upstream_gitdir, ignore_errors=True)

    def runTest(self):
        repo = git.Repo(self.gitdir)
        upstream_repo = git.Repo(self.upstream_gitdir)

        self.assertEqual(repo.head, repo.heads.master)
        self.assertEqual(repo.refs.heads.master, repo.heads.master)
        self.assertEqual(repo.heads.master, repo.heads["master"])
        self.assertNotEqual(repo.heads.master, repo.heads.other)
        self.assertNotEqual(repo.heads.master, upstream_repo.heads.master)
        self.assertFalse(repo.heads.master.is_ancestor(repo.heads.other))
        self.assertTrue(repo.heads.master.merge_base(repo.heads.other).is_ancestor(repo.heads.master))
        self.assertTrue(repo.heads.master.merge_base(repo.heads.other).is_ancestor(repo.heads.other))
        self.assertRaises(git.GitError, lambda: repo.heads.missing.full_name)
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
        self.assertEqual(repo.heads.other.full_name, "refs/heads/other")
        self.assertEqual(repo.heads.master.name, "master")
        self.assertEqual(str(repo.heads.master), "master")
        self.assertEqual(str(repo.head), "HEAD")
        self.assertEqual(repo.head.reference, repo.heads.master)

        self.assertEqual(repo.remotes.origin.master.name, "origin/master")
        self.assertEqual(repo.remotes.origin.master.remote_name, "origin")
        self.assertEqual(repo.remotes.origin.master.branch_name, "master")
        self.assertEqual(repo.remotes.origin.master, repo.remotes.origin["master"])
        self.assertEqual(repo.remotes.origin, repo.remotes["origin"])
        self.assertTrue("master" in repo.remotes.origin)
        self.assertTrue("origin/master" in repo.remotes.origin)
        self.assertFalse("missing" in repo.remotes.origin)

        for ref in repo.heads:
            self.assertIsInstance(ref, git.BranchReference)
        for remote in repo.remotes:
            self.assertIsInstance(remote, git.Remote)
            self.assertTrue(remote["master"].points_at(repo.head))
        for ref in repo.remote("origin"):
            self.assertIsInstance(ref, git.RemoteReference)
            self.assertEqual (ref.remote, repo.remote("origin"))
            self.assertTrue(ref.branch_name != "master" or ref == repo.remotes.origin.master)
            self.assertTrue(ref.branch_name == "master" or ref != repo.remotes.origin.master)

        self.assertEqual(str(repo.remote("origin")), "origin")
        self.assertEqual(repo.remote("origin").url, self.upstream_gitdir)
        self.assertEqual(repo.remote("origin").fetch_url, self.upstream_gitdir)
        self.assertEqual(repo.remote("origin").push_url, self.upstream_gitdir)
        self.assertTrue(repo.head.points_at(repo.heads.master))
        self.assertTrue(repo.head.points_at(repo.remotes.origin.master))
        self.assertEqual(repo.head.commit_ish, repo.heads.master.commit_ish)
        self.assertEqual(repo.head.tree_ish, repo.heads.master.tree_ish)

        self.assertEqual(repo.heads.master.tracking_branch, repo.remotes.origin.master)
        self.assertIsNone(upstream_repo.heads.master.tracking_branch)

        s = set([repo.heads.master, repo.heads.other])
        self.assertIn(repo.head, s)

