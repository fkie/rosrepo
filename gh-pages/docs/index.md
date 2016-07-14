# Introduction

**rosrepo** manages catkin workspaces with multiple Gitlab repositories.
It can crawl projects on Gitlab servers to discover ROS
packages, clone them into your workspace, and take care of all
dependencies.

Additionally, **rosrepo** integrates with the
[Catkin Command Line Tools](http://catkin-tools.readthedocs.io) to build
your workspace, [catkin_lint](http://fkie.github.io/catkin_lint) to check
your packages for configuration mistakes, and rosclipse to generate Eclipse
project files.

You can find the following information in this documentation:

- How to [install](install.md) **rosrepo** on your computer
- How to [initialize your workspace](cmd_init.md) to work with **rosrepo**


# Quick-Start

```sh
$ rosrepo init $HOME/ros
$ rosrepo config --set-gitlab-url MyGitlab https://gitlab.example.com
$ rosrepo build my_package
```

