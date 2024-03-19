# Makefile

.ONESHELL:
SHELL := /bin/bash

SOURCE_INIT = /tmp/venv.oscal-insights
SOURCE = $(SOURCE_INIT)

all: run

run: venv-plus
	echo "=> run"; \
	source $(SOURCE_INIT)/bin/activate; \
	python python/oscal_component_definition_insights.py --base-path . --file-path component-definitions/acme-component-definition/component-definition.json --output-path plots/component-definitions/acme-component-definition; \
	
help: venv-plus
	echo "=> help"; \
	source $(SOURCE_INIT)/bin/activate; \
	python python/oscal_component_definition_insights.py --help;
	
venv-plus: venv
	echo "=> install extras"; \
	source $(SOURCE_INIT)/bin/activate; \
	python -m pip install matplotlib;
	
venv:
	if [ ! -d $(SOURCE_INIT) ]; then \
		echo "=> create python virtual environment"; \
		python -m venv $(SOURCE_INIT); \
		source $(SOURCE_INIT)/bin/activate; \
		echo "=> install prereqs"; \
		python -m pip install -q --upgrade pip setuptools; \
		python -m pip install -q compliance-trestle; \
	fi

clean-up:
	echo "=> remove python virtual environment"; \
	rm -fr $(SOURCE_INIT)