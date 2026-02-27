## ADDED Requirements

### Requirement: OCIO Color Conversion
The system SHALL support applying OpenColorIO color conversions to the video essence utilizing the FFmpeg `ocio` filter.

#### Scenario: Applying a Display Transform
- **WHEN** the configuration specifies an OCIO config file, input color space, output color space, or view
- **THEN** an FFmpeg filtergraph is constructed including the `ocio` filter configured with these parameters to correctly transform the video's color
