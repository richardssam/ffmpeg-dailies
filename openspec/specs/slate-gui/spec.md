# slate-gui

## Capabilities

- **Browser-based Visual Editor**: A local web application to visualize the current `slate` configuration atop an background image.
- **Draggable Bounding Boxes**: Text elements and PIP overlays mapped from the YAML should be interactively draggable to absolute (x, y) coordinates within the bounding dimensions of the output format.
- **Save Functionality**: Interacting with a primary action button should invoke an API to flush the new coordinate state to the active YAML configuration file on disk.

## Requirements

### Interactive Layout Editor
The system SHALL provide a browser-based visual editor to configure the `slate` layout atop a background image. It MUST support draggable bounding boxes for text elements and PIP overlays, mapping absolute (x, y) coordinates from the YAML.

#### Scenario: Visualizing configuration
- **WHEN** the user navigates to the editor URL
- **THEN** the system displays the slate background image, draggable bounding boxes for each text field, and UI controls for adjusting text size and font choices along with PIP thumbnails.

### Save Layout Configuration
The system SHALL provide a mechanism to save updated coordinates back to the active YAML configuration file.

#### Scenario: Saving new coordinates and text styles
- **WHEN** the user drags a text element to a new position, alters its font size or typeface, and clicks 'Save'
- **THEN** the system updates the corresponding `x`, `y`, `font_size`, and font path values in the active configuration file on disk.

### FFmpeg Render Preview
The system SHALL provide an option to generate a pixel-accurate preview using FFmpeg.

#### Scenario: Requesting pixel-accurate preview
- **WHEN** the user requests an FFmpeg preview
- **THEN** the system executes `build_slate_filtergraph()`, generates exactly 1 rendered frame containing accurate font-kerning and OCIO color application, and displays it in the browser.
