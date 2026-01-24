# Localized FRBs

A database of Fast Radio Bursts (FRBs) with sub-arcsecond localizations and host galaxy associations.

## Browse the Data

**Live database:** [Coming soon - deploy to fly.io]

Run locally:
```bash
pip install datasette
datasette frbs.db --metadata metadata.json --template-dir templates
```
Then open http://127.0.0.1:8001

## Data

The database contains **162 localized FRBs** from:
- **CHIME** (85)
- **DSA-110** (39)
- **ASKAP** (33)
- **MeerKAT** (4)
- **VLA** (1)

### Columns

| Column | Description |
|--------|-------------|
| `Name` | FRB name (TNS designation) |
| `ra`, `dec` | J2000 coordinates (degrees) |
| `DM` | Dispersion Measure (pc/cm³) |
| `z` | Redshift |
| `ee_a`, `ee_b` | Localization error ellipse (arcsec) |
| `RM` | Rotation Measure (rad/m²) |
| `repeater` | TRUE if repeating |
| `telescope` | Discovery instrument |
| `refs` | Literature references |

## Automated Updates

This repo includes a GitHub Action that runs weekly to check for new FRB localizations from:
- **ATels** (Astronomer's Telegrams)
- **arXiv** preprints

New FRBs are added via pull request for review.

### Setup

1. Add `ANTHROPIC_API_KEY` to repository secrets
2. The workflow runs every Monday at 9am UTC
3. Manual trigger available in Actions tab

## Data Source

Based on the [Community FRB Localization Spreadsheet](https://docs.google.com/spreadsheets/d/1nNwhYZWOnTcLq6Uv0KJebxMet4NzAnUKW7SFZ6n3GoY).

## License

Data: CC-BY-4.0
