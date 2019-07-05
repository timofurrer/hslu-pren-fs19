# 2/4 HNS Control Software

This repository contains the application developed for the
PREN challenge @ HSLU in the FS19.

See the [hslu-pren-digit-cnn](https://github.com/timofurrer/hslu-pren-digit-cnn) repository
for more details about the CNN used to detect the signals.


## HNS application

```bash
# use default stable config
python3 -m hns
# use specific config
python3 -m hns configs/stable.ini
```

## Development

Run tests:

```bash
# make sure to have the test dependencies installed
make install-test-dependencies

# run the tests
make test
```

Build and Install to system

```bash
make && sudo make install
```
