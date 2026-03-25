import dataclasses
from typing import Optional, Dict, List

@dataclasses.dataclass
class GlobalsConfig:
    """Global configuration settings for the dailies pipeline (framerate, dimensions, font paths, etc.)."""
    framerate: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    cropwidth: Optional[int] = None
    cropheight: Optional[int] = None
    cropx: Optional[int] = None
    cropy: Optional[int] = None
    fit: Optional[bool] = None
    output_codec: Optional[str] = None
    font_size: Optional[float] = None
    font_color: Optional[str] = "white"
    background_color: Optional[str] = "black@0.5"
    ffmpeg_bin: Optional[str] = None
    font: Optional[Dict[str, str]] = None
    reel_name: Optional[str] = None
    timecode: Optional['TimecodeConfig'] = None

@dataclasses.dataclass
class TimecodeConfig:
    """Settings for timecode generation (source, start TC, rate, etc.)."""
    source: str = "media"  # "media" or "frame"
    start: str = "auto"    # "auto" or SMPTE TC "HH:MM:SS:FF"
    rate: Optional[float] = None
    drop_frame: bool = False

@dataclasses.dataclass
class OutputCodecProfile:
    """Defines an FFmpeg output codec configuration preset (e.g., h264_hq, prores)."""
    codec: Optional[str] = None
    crf: Optional[int] = None
    preset: Optional[str] = None
    profile_args: Dict[str, str] = dataclasses.field(default_factory=dict)

@dataclasses.dataclass
class InputSettings:
    """Resolved properties of the input media payload (path, sequence state, padding dimensions)."""
    path: str
    framerate: str
    width: int
    height: int
    is_image_sequence: bool
    start_number: Optional[int] = None
    cropwidth: Optional[int] = None
    cropheight: Optional[int] = None
    cropx: Optional[int] = None
    cropy: Optional[int] = None

@dataclasses.dataclass
class OutputSettings:
    """Properties for the target output media format (path, delivery dimensions, scaling logic)."""
    path: str
    target_width: int
    target_height: int
    fit: bool = True

@dataclasses.dataclass
class OCIOSettings:
    """OpenColorIO configuration mapping to FFmpeg's ocio video filter arguments."""
    enabled: bool = False
    config_path: Optional[str] = None
    input_space: Optional[str] = None
    output_space: Optional[str] = None
    view: Optional[str] = None

@dataclasses.dataclass
class BurninConfig:
    """Configuration for persistent text overlays drawn over the main video content."""
    # positions mapping like "lower_left" -> "Notes", "top_center" -> "Show Title"
    layout: Dict[str, str] = dataclasses.field(default_factory=dict)
    target_width: int = 1920
    target_height: int = 1080
    # font configuration map
    fonts: Dict[str, str] = dataclasses.field(default_factory=dict)
    global_font_size: Optional[float] = None
    font_color: Optional[str] = None
    background_color: Optional[str] = None

@dataclasses.dataclass
class SlateField:
    """A single textual metadata field to be drawn onto the slate title card."""
    text: str
    x: Optional[str] = None
    y: Optional[str] = None
    font_size: Optional[float] = None
    align: str = "left"
    max_width: int = 0
    max_height: int = 0
    font_color: Optional[str] = None
    background_color: Optional[str] = None

@dataclasses.dataclass
class MetadataRule:
    """A rule to dynamically derive one metadata field from another (or the input path) using regex."""
    target: str
    source: str  # "input_path" or a metadata key
    regex: Optional[str] = None
    replace: Optional[str] = None # Support for backreferences like \1

@dataclasses.dataclass
class DynamicMetadataConfig:
    """Governs how metadata is automatically populated and extracted."""
    enabled: bool = True
    rules: List[MetadataRule] = dataclasses.field(default_factory=list)

@dataclasses.dataclass
class SlateConfig:
    """Configuration for the preroll slate title card and thumbnail preview layout."""
    fields: Dict[str, SlateField]
    template_image: Optional[str] = None
    thumbnail_enabled: bool = True
    thumbnail_x: Optional[int] = None
    thumbnail_y: Optional[int] = None
    thumbnail_width: Optional[int] = None
    global_font_size: Optional[float] = None

@dataclasses.dataclass
class DailiesContext:
    """The master context object holding all resolved configurations for the current rendering job."""
    input_settings: InputSettings
    output_settings: OutputSettings
    ocio_settings: OCIOSettings
    slate_config: SlateConfig
    burnin_config: BurninConfig
    metadata: Dict[str, str]
    dynamic_metadata: DynamicMetadataConfig = dataclasses.field(default_factory=DynamicMetadataConfig)
    globals_config: GlobalsConfig = dataclasses.field(default_factory=GlobalsConfig)
    output_codecs: Dict[str, OutputCodecProfile] = dataclasses.field(default_factory=dict)
    resolved_timecode: Optional[str] = None
    resolved_reel: Optional[str] = None
