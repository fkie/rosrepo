rosrepo
#######

**rosrepo** is a workspace manager for ROS. Under the hood, it runs the
excellent `catkin tools <https://catkin-tools.readthedocs.io/>`_ to build
packages. Additionally, it supports Git operations, can scan Gitlab
servers for available packages, and use these packages to satisfy
dependencies in the workspace.

Build status of latest version:

.. image:: https://travis-ci.org/fkie/rosrepo.png?branch=master
   :target: https://travis-ci.org/fkie/rosrepo
.. image:: https://codecov.io/github/fkie/rosrepo/coverage.svg?branch=master
    :target: https://codecov.io/github/fkie/rosrepo?branch=master

