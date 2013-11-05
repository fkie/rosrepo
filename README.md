
Repository Management Tool for ROS-FKIE
=======================================

**rosrepo** introduces working sets to manage catkin workspaces
with a large number of packages. It is most useful if a workspace
contains multiple subprojects which are mostly developed independently, but
are still deployed together.

The catkin build process becomes slow with many packages, 
especially if CMake has to reconfigure the workspace. **rosrepo**
makes it very easy to build just a subset of packages for
rapid development and testing, yet provides a simple way to build 
the complete workspace if needed. The setup is simpler than multiple
workspace overlays, but almost as flexible.

The catkin workspace layout is slightly modified as follows:

* `/catkin_ws`
    * `build`
    * `devel`
    * `src`
    * `repos`

Packages are put in the `repos` folder. **rosrepo** creates
symlinks from `repos` to `src` for the packages of the current working set.
Dependencies are resolved and symlinked as needed. The standard ROS tools
can be used with the caveat that only packages in the current working set
are accessible unless the `ROS_PACKAGE_PATH` is augmented with the `repos`
folder.

Commands
========

## init
This command either creates or updates a catkin workspace to the
new layout. Existing folders in `src` are moved to `repos`.

## include
Adds packages and their dependencies to the working set

## exclude
Removes packages from the working set. Automatically added dependencies
are removed if no remaining package in the working set depends on them.

## build
Runs `catkin_make`. If packages are specified on the command line,
these packages and their dependencies replace the current working set.

## list
Lists the current working set or all available packages.

## find
Prints the path of the specified package in the `repos` folder.

## checkout
Performs an SVN checkout or a Git clone. The repository is added
as subfolder in `repos`. This is command is provided for convenience,
you can treat `repos` as you would treat `src` 

