## ADDED Requirements

### Requirement: Globals Section
The system SHALL support parsing a `globals` block in the YAML configuration.

#### Scenario: Parsing global parameters
- **WHEN** the `globals` section contains `framerate`, `width`, `height`, `cropwidth`, `cropheight`, `cropx`, `cropy`, `fit`, `output_codec`, `reel_name`, and `timecode`
- **THEN** the system applies these as base defaults before processing CLI arguments

### Requirement: Global Font Options
The system SHALL allow defining global font settings (like `font_size`) that apply to all text overlays unless overridden individually.

#### Scenario: Applying a global font size
- **WHEN** `globals.font_size` is defined in the configuration
- **THEN** all burn-ins and slates use that size if they do not explicitly specify their own font size

### Requirement: Timecode Configuration
The system SHALL support a `timecode` object in the globals section with `source`, `start`, `rate`, and `drop_frame` fields.

#### Scenario: Manual Timecode Override
- **WHEN** `globals.timecode.start` is set to `"01:00:00:00"`
- **THEN** the system uses this as the starting timecode regardless of the input frame number
