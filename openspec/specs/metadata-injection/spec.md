# Metadata Injection

## Purpose

Defines how dynamic data payloads are injected into the dailies generation pipeline to populate visual text elements.

## Requirements

### Requirement: Metadata Injection Dictionary
The Python API MUST accept a `metadata` dictionary mapping string keys to string values.

#### Scenario: Bypassing CLI arguments
- **WHEN** a user renders using `ffmpeg_dailies.render(..., metadata={"Show Title": "My Specific Show", "Notes": "WIP version"})`
- **THEN** the pipeline applies these exact strings to any `{Show Title}` and `{Notes}` tokens defined in the `slate` or `burnin` YAML configuration blocks, identical to how `--meta-show` and `--meta-notes` work via CLI.

### Requirement: Implicit File Name Resolution
If the `metadata` payload does not contain a `File Name` key, the pipeline MUST attempt to resolve it automatically from the `input_media` basename.

#### Scenario: Missing filename mapping
- **WHEN** a user renders an image sequence `seq_v001.%04d.exr` without passing a `"File Name"` key
- **THEN** the metadata dictionary implicitly injects `{"File Name": "seq_v001.%04d.exr"}` during template resolution.

### Requirement: Shot and Vendor Metadata Support
The pipeline SHALL support `{Shot}` and `{Vendor Name}` metadata variables. These values MUST be supplied via the YAML configuration or CLI metadata overrides. No automatic inference is required.

#### Scenario: User-supplied metadata via CLI
- **WHEN** the user runs `./run_dailies --meta-shot RAP_090 --meta-vendor "My Studio" ...`
- **THEN** the metadata dictionary contains `{"Shot": "RAP_090", "Vendor Name": "My Studio"}` and the tokens `{Shot}` and `{Vendor Name}` are resolved correctly.

### Requirement: Dynamic Date and Time Resolution
The pipeline MUST inject the current local date and time into the `Date Delivered` metadata key if it is absent from the user-supplied `metadata` dictionary.

#### Scenario: Date and Time injected at render time
- **WHEN** the user renders and `Date Delivered` is not defined in the YAML metadata block
- **THEN** the metadata dictionary is implicitly populated with the current local timestamp formatted as `YYYY-MM-DD HH:MM` (e.g., `2026-02-27 13:55`).
