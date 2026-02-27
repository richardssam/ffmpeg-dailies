# Unit Testing

## Purpose

Defines the requirements for testing the `ffmpeg_dailies` pipeline, ensuring both correct argument rendering and visual fidelity over time.

## Requirements

### Requirement: Unit Testing Suite
The project MUST include a `pytest` suite in a `tests/` directory to validate the core logic of the Python API and CLI. 

#### Scenario: Running the test suite
- **WHEN** a developer runs `pytest` in the project root
- **THEN** all tests execute successfully, validating configuration parsing, argument resolution, and FFmpeg command generation.

### Requirement: Visual Reference Testing
The test suite MUST include an end-to-end test that renders a single lossless frame (e.g. PNG) using the generated FFmpeg command and compares it against a known "golden" reference image to ensure visual fidelity of slates, burn-ins, and OCIO transformations.

#### Scenario: Catching a visual regression
- **WHEN** a change inadvertently offsets a text burn-in coordinate, and the visual test suite is run
- **THEN** the test automatically fails because the generated output frame's pixels do not perfectly match the golden reference image.
