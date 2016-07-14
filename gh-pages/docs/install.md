# Installation from Source

You can install **rosrepo** from source with
```sh
$ git clone https://github.com/fkie/rosrepo
$ cd rosrepo
$ sudo setup.py install
```

# Debian/Ubuntu packages

You can build your own Debian package with
```sh
$ sudo apt-get install dpkg-dev
$ git clone https://github.com/fkie/rosrepo
$ cd rosrepo
$ git checkout debian-3.x
$ dpkg-buildpackage -tc -us -uc
```

