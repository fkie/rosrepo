
ROS Repository Management Tool
==============================

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

## Commands

### init
Creates or updates a catkin workspace to the new layout. 
Existing folders in `src` are moved to `repos`.

    rosrepo init [--autolink] [--delete] [path]

* `path`: path to the new catkin workspace. If omitted, `.` is assumed.
* `-a`,`--autolink`: search for and symlink to ROS-FKIE checkout.
* `--delete`: delete the workspace path if it already exists.

### use
Selects packages and their dependencies for the current working set.

    rosrepo use [-w WORKSPACE] [--clean] --all
    rosrepo use [-w WORKSPACE] [--clean] package [package ...]

* `package`: packages name(s) which are to be included in the working set.
* `--all`: select all available packages as working set.
* `--clean`: force clean build by removing `build` and `devel` folders.

### include
Adds additional packages and their dependencies to the working set.

    rosrepo include [-w WORKSPACE] [--clean] [--mark-auto] --all
    rosrepo include [-w WORKSPACE] [--clean] [--mark-auto] \
                    package [package ...]

* `package`: package name(s) which are to be included in the working set.
* `--all`: select all available packages as working set.
* `--clean`: force clean build by removing `build` and `devel` folders.
* `--mark-auto`: mark included packages as automatically added dependencies.

### exclude
Removes packages from the working set. Automatically added dependencies
are removed if no remaining package in the working set depends on them.

    rosrepo exclude [-w WORKSPACE] [--clean] --all
    rosrepo exclude [-w WORKSPACE] [--clean] package [package ...]

* `package`: package name(s) which are to be excluded from the working set.
* `--all`: remove all packages from the working set, leaving it empty.
* `--clean`: force clean build by removing `build` and `devel` folders.

### build
Runs `catkin_make`. If packages are specified on the command line,
these packages and their dependencies replace the current working set as
if the `use` command had been invoked first.

    rosrepo build [-w WORKSPACE] [--clean] [-cc CC] [--cxx CXX] \
                  [package [package ...]]
    rosrepo build [-w WORKSPACE] [--clean] [-cc CC] [--cxx CXX] --all

* `package`: package name(s) which are to replace the working set.
* `--all`: select all available packages as working set.
* `--clean`: force clean build by removing `build` and `devel` folders first.
* `--cc`: force C compiler for build
* `--cxx`: force C++ compiler for build

### list
Lists the current working set or all available packages.

    rosrepo list [-w WORKSPACE] [--name-only] [--all | --manual]

* `--name-only`: show package names only
* `--all`: show all available packages instead of the current working set
* `--manual`: only show explicitly included packages and not automatically
  added dependencies.

### find
Prints the path of the specified package in the `repos` folder.

    rosrepo find [-w WORKSPACE] [--relative] package

* `package`: package name
* `--relative`: print path that is relative to the workspace

### checkout
Performs an SVN checkout or a Git clone. The repository is added
as subfolder in `repos`. This is command is provided for convenience,
you can add package folders to `repos` just like you would to `src`.

    rosrepo checkout [-w WORKSPACE] (--git | --svn | --link) \
                     url [name]

* `url`: repository URL
* `name`: repository name (this will become the folder name in `repos`)
* `--git`: `url` points to a Git repository
* `--svn`: `url` points to a Subversion repository
* `--link`: `url` is another folder which will be symlinked

## License

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

 * Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 * Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
