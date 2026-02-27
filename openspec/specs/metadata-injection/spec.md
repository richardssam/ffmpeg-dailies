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
