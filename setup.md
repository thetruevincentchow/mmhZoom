## Prerequsites

* Python >= 3.8
* A package manager

## Instructions

1. If necessary, install appropriate Linux headers, e.g. with Linux 5.9 kernel. Needed to install `v4l2loopback`.

```sh
$ yay -Syu linux59-headers # Arch Linux with yay
```

2. Install `v4l2loopback`. The package name depends on your distro.

```sh
$ yay -Syu v4l2loopback-dkms # Arch Linux with yay
$ apt-get install v4l2loopback-utils # Ubuntu with apt-get
```

3. Make sure the `v4l2loopback` kernel module is loaded:

```sh
$ sudo modprobe v4l2loopback devices=1
```

4. (optional, recommended) Create a virtual environment and activate it. Python packages will be installed in the virtual environment instead of in your system-wide installation.

```
$ python3 -m venv deps
$ source deps/bin/activate
```

5. Install required Python packages:

```
$ python3 -m pip install -r requirements.txt
```
