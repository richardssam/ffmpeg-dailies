# Capability: Font Alignment and Layout

## Purpose
This capability provides advanced text layout controls for slate metadata fields, including horizontal alignment, geometric text wrapping (`max_width`), and vertical capacity limits (`max_height`) with cropping support.

## Requirements

### Requirement: Horizontal Alignment
The dailies rendering pipeline must support setting horizontal alignment (left, center, right) for multi-line text fields on the slate.

#### Scenario: Right-aligned multi-line text
- **WHEN** a slate field has `align="right"` and contains newlines
- **THEN** the generated FFmpeg command must construct separate `drawtext` filters for each line such that all lines are anchored precisely to their right edge relative to the bounding box.

### Requirement: Bounding Box Text Wrapping
The dailies rendering pipeline must support defining a maximum pixel width for slate fields to enforce text wrapping without resizing the font.

#### Scenario: Text exceeds max_width
- **WHEN** a slate field has `max_width=800` and its content would render wider than 800 pixels
- **THEN** the pipeline must automatically insert newlines to wrap the text into multiple lines before filter generation.

### Requirement: Vertical Bounding Box and Cropping
The dailies rendering pipeline must support defining a maximum pixel height for slate fields to control vertical capacity and enforce cropping if the content exceeds the allocated space.

#### Scenario: Text exceeds max_height
- **WHEN** a slate field has `max_height=100` and its content would render taller than 100 pixels
- **THEN** the pipeline must crop the text vertically at the 100-pixel mark, ensuring the top of the text remains visible and aligned with the box's top edge.

### Requirement: Top-Aligned Fixed Containers
When a fixed bounding box (`max_width` and/or `max_height`) is defined, text must always remain anchored to the top-left of the container by default, matching standard compositing behavior.
