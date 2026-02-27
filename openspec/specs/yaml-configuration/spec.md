## ADDED Requirements

### Requirement: YAML Layout Configuration
The system SHALL accept a YAML configuration file defining the layout and styling of slates and burn-ins.

#### Scenario: Loading Config Parameters
- **WHEN** a valid YAML file is provided as input
- **THEN** the system parses parameters including metadata mappings, font choices, positions (x/y), colors, and opacity

### Requirement: Multiple Layout Presets
The system SHALL allow selecting different layouts or presets defined within the YAML configuration.

#### Scenario: Selecting a Preset
- **WHEN** a specific preset name is provided at execution
- **THEN** the system uses the corresponding layout rules defined under that preset in the yaml file
## MODIFIED Requirements

### Requirement: YAML Layout Configuration
The system SHALL accept a YAML configuration file defining global tool settings, and the layout and styling of slates and burn-ins.

#### Scenario: Loading Config Parameters
- **WHEN** a valid YAML file is provided as input
- **THEN** the system parses parameters including globals (framerate, dimensions), metadata mappings, font choices, positions (x/y), colors, and opacity
