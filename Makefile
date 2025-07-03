local:                          ## run script with uv & preview
	uv run ./generate_graphs.py --show

install:                        ## create venv & install deps
	uv venv .venv && uv pip install -r requirements.txt