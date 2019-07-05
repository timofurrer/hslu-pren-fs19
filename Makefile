all:
	python3 setup.py sdist bdist_wheel

install:
	python3 setup.py install


install-test-dependencies:
	python3 -m pip install -r requirements-dev.txt

test:
	python3 -m pytest tests/ -s --failed-first {posargs}
