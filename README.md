# ASVSP 2026

## Rendering the presentation

Run `presentation/render.sh` for rendering the PDF that represents the project presentation.

Requires:
- `quarto`
- `npx` (`node`)
- `quarto install tinytex`
- `quarto install chrome-headless-shell`

## Downloading datasets

In the `dataset/` directory, there are two Python files:
- `dw_batch_dataset.py` - for downloading the batch dataset containing historical weather data
- `dw_master_dataset.py` - for downloading the master dataset containing US specific geographical codenames (state, county and forecast zone identificators)

Before running, install the required libraries by running: `pip install -r requirements.txt`.