# Zenodo Publishing

This repository includes Zenodo and citation metadata:

- `.zenodo.json` for Zenodo GitHub release archiving.
- `CITATION.cff` for GitHub citation display and citation tools.

## Current publication constraint

The repository is currently private. GitHub's Zenodo guidance says Zenodo can access only public repositories for the GitHub archiving flow. For that path, make the repository public, enable the repository in Zenodo, then create a GitHub release from a tag that includes the metadata files.

The existing `v0.1.0` tag was created before the citation metadata was added. Use one of these publication paths:

1. Manual Zenodo upload from the current commit using a Zenodo personal access token.
2. Create a new GitHub release after enabling Zenodo on a public repository.

## Manual upload checklist

1. Confirm the source tree is clean.
2. Build an archive from the current commit.
3. Create a Zenodo software record using `.zenodo.json`.
4. Upload the source archive.
5. Review metadata, access right, license, and contact details.
6. Publish the record.
7. Add the issued DOI to `CITATION.cff`, `.zenodo.json`, and the README.

## GitHub release checklist

1. Make the repository public if using Zenodo's GitHub integration.
2. Log in to Zenodo with GitHub.
3. Enable `DiogoRibeiro7/perishable-inventory-decision-lab` on the Zenodo GitHub page.
4. Create a GitHub release from a tag that includes `.zenodo.json`.
5. Wait for Zenodo processing.
6. Add the issued DOI to `CITATION.cff`, `.zenodo.json`, and the README.
