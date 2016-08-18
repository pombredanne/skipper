all: pep8 pylint tests build

build:
	python setup.py sdist

pep8:
	pep8 skipper tests

pylint:
	pylint skipper

tests:
	py.test --cov=skipper --cov-report=term-missing tests

install: build
	python setup.py install

clean:
	rm -rf dist *egg-info .tox tests/__pycache__
	find -name *.pyc -delete

.PHONY: build pep8 pylint tests install clean
