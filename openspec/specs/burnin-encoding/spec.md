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

### Requirement: Dynamic Frame Counter Resolution
The `{frame}` token in burn-in layouts MUST be resolved to FFmpeg's internal dynamic frame counter variable (`%{n}`) and MUST NOT be escaped in a way that prevents FFmpeg from rendering the actual frame number.

#### Scenario: Rendering with frame counter
- **WHEN** a burn-in layout contains `{frame}`
- **THEN** the generated FFmpeg filter string contains `drawtext=text='%{n}':...` unescaped, ensuring the output video displays incrementing frame numbers.

### Requirement: Cascading Font Size
Burn-in text elements MUST respect the font size defined in the `globals` section of the configuration if no component-specific font size is provided.

#### Scenario: Global font size inheritance
- **WHEN** `globals.font_size` is set to `30` and `burnins` does not specify a separate `global_font_size` or per-position size
- **THEN** the generated burn-in `drawtext` filters use `fontsize=30`.
