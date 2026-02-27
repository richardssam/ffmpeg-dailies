## ADDED Requirements

### Requirement: Output Codecs Block
The system SHALL support parsing an `output_codecs` block in the YAML configuration to define custom encoding profiles.

#### Scenario: Resolving an output codec
- **WHEN** the `globals` section specifies an `output_codec` (e.g., `h264_hq`)
- **THEN** the system looks up the corresponding profile in the `output_codecs` block and applies its parameters (like `codec`, `crf`, `preset`) to the FFmpeg builder
