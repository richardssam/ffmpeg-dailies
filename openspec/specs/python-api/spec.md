# Python API

## Purpose

Defines the core Python interface to the FFmpeg dailies generation pipeline, allowing DCCs and rendering tools to encode dailies bypasssing the CLI.

## Requirements

### Requirement: Python API Entry Point
The package MUST expose a native Python API function `render` in the `ffmpeg_dailies` namespace, allowing execution without invoking a subprocess on the CLI entry point.

#### Scenario: Running a default job
- **WHEN** a user calls `ffmpeg_dailies.render(config_path="layout.yaml", input_media="seq.%04d.exr", output_media="out.mov")`
- **THEN** the API fully constructs the DailiesContext and executes the FFmpeg render sequence synchronously.

### Requirement: API Dry Run Execution
The `render` function MUST support a `dry_run` flag that prevents process execution and instead returns the raw FFmpeg arguments.

#### Scenario: Requesting dry-run execution
- **WHEN** a user calls `ffmpeg_dailies.render(..., dry_run=True)`
- **THEN** the API returns the constructed FFmpeg command list, e.g., `["ffmpeg", "-y", "-i", ...]`, without executing it.

### Requirement: ShotGrid Config Fallbacks
The `render` function MUST support passing standard override arguments like `framerate`, `start_number`, `input_width`, and `input_height` directly as keyword arguments to bypass global config files.

#### Scenario: Overriding the framerate programmatically
- **WHEN** the `config_path` defines 24fps but the user passes `render(..., framerate="23.976")`
- **THEN** the API constructs the FFmpeg command using the explicit `23.976` framerate.
