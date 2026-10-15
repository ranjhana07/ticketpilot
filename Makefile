PYTHON ?= python

.PHONY: install test data models helpdesk serve eval clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

data:
	ticketpilot data download

models:
	ticketpilot triage train --task synthetic_intent --kind baseline
	ticketpilot triage train --task synthetic_priority --kind baseline
	ticketpilot triage train --task synthetic_intent --kind transformer
	ticketpilot triage train --task synthetic_priority --kind transformer

helpdesk:
	ticketpilot helpdesk --reset

serve:
	ticketpilot serve

eval:
	ticketpilot eval all

clean:
	rm -rf .pytest_cache build dist *.egg-info
