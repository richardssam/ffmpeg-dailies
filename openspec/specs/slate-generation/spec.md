## ADDED Requirements

### Requirement: Slate Template Image
The system SHALL support utilizing an external image file as the base plate for the slate, enabling custom branding, color bars, or wedges.

#### Scenario: Using a template image
- **WHEN** `slate.template_image` is specified in the configuration
- **THEN** the system uses this image instead of generating a black background for the slate frame

### Requirement: Picture-In-Picture Thumbnail
The system SHALL support extracting a frame from the input media to composite onto the slate as a thumbnail.

#### Scenario: Default thumbnail extraction
- **WHEN** `slate.thumbnail_enabled` is true
- **THEN** the system extracts the middle frame of the input video and overlays it onto the slate base

### Requirement: Absolute Coordinate Text Placement
The system SHALL permit specifying exact X and Y coordinates, as well as font sizes, for individual text fields on the slate.

#### Scenario: Placing a customized field
- **WHEN** a slate field defines `x`, `y`, and `font_size` overrides
- **THEN** the system renders the field text at those exact coordinates with the specified size, bypassing default auto-centering logic

### Requirement: Slate Template Generator
The system SHALL include a standalone tool capable of procedurally generating a default slate template image featuring standard color bars and a grayscale wedge.

#### Scenario: Bootstrapping a new project
- **WHEN** the generator script is executed
- **THEN** it outputs an EXR or PNG image file containing the procedurally generated color bars that can be used directly as the `template_image`
