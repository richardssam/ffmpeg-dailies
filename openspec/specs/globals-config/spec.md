## ADDED Requirements

### Requirement: Globals Section
The system SHALL support parsing a `globals` block in the YAML configuration.

#### Scenario: Parsing global parameters
- **WHEN** the `globals` section contains `framerate`, `width`, `height`, `cropwidth`, `cropheight`, `cropx`, `cropy`, `fit`, and `output_codec`
- **THEN** the system applies these as base defaults before processing CLI arguments

### Requirement: Global Font Options
The system SHALL allow defining global font settings (like `font_size`) that apply to all text overlays unless overridden individually.

#### Scenario: Applying a global font size
- **WHEN** `globals.font_size` is defined in the configuration
- **THEN** all burn-ins and slates use that size if they do not explicitly specify their own font size
