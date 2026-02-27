## ADDED Requirements

### Requirement: Burn-in Text Overlays
The system SHALL apply text overlays to the main video frames during encoding.

#### Scenario: Metadata Burn-ins
- **WHEN** the configuration defines burn-in layouts (like source timecode, record timecode, clip name)
- **THEN** these text values are accurately drawn onto every frame of the video at the defined positions, fonts, colors, and sizes

### Requirement: Configuration-Driven Variables
The system SHALL support dynamic variable replacement within burn-in definitions.

#### Scenario: Dynamic Timecode Source
- **WHEN** a burn-in is configured to display `{timecode}`
- **THEN** the system determines the correct timecode value for each frame (e.g., from source metadata or a calculated start value) and displays it
