import yaml
import copy
from typing import Dict, Any, Optional

from .models import BurninConfig, SlateConfig, SlateField, OCIOSettings, GlobalsConfig, OutputCodecProfile, DynamicMetadataConfig, MetadataRule, TimecodeConfig

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Loads and parses the raw YAML configuration file.
    
    Args:
        config_path: Path to the .yaml configuration file.
        
    Returns:
        The parsed YAML document as a generic dictionary.
    """
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def parse_ocio_settings(config: Dict[str, Any]) -> OCIOSettings:
    """
    Extracts the OpenColorIO configuration block from the raw YAML representation.
    
    Args:
        config: The raw YAML dictionary.
        
    Returns:
        An OCIOSettings dataclass initialized with the parsed values.
    """
    ocio = config.get("ocio", {})
    return OCIOSettings(
        enabled=ocio.get("enabled", False),
        config_path=ocio.get("config_path"),
        input_space=ocio.get("input_space"),
        output_space=ocio.get("output_space"),
        view=ocio.get("view")
    )

def parse_burnin_config(config: Dict[str, Any], output_width: int, output_height: int, global_font_size: Optional[float] = None) -> BurninConfig:
    """
    Parses burn-in layout templates and font definitions.
    
    Args:
        config: The raw YAML dictionary.
        output_width: Target resolution width for dynamic sizing calculations (unused directly currently).
        output_height: Target resolution height for dynamic sizing calculations (unused directly currently).
        global_font_size: Fallback font size for text elements if not explicitly defined.
        
    Returns:
        A finalized BurninConfig mapping positions to text templates and font files.
    """
    burnin_cfg = config.get("burnins", {})
    return BurninConfig(
        layout=burnin_cfg.get("layout", {}),
        target_width=output_width,
        target_height=output_height,
        fonts=burnin_cfg.get("fonts", {}),
        global_font_size=global_font_size,
        font_color=burnin_cfg.get("font_color"),
        background_color=burnin_cfg.get("background_color")
    )

def parse_slate_config(config: Dict[str, Any], global_font_size: Optional[float] = None) -> SlateConfig:
    """
    Parses the slate setup including the background template path and text field geometries.
    
    Args:
        config: The raw YAML dictionary.
        global_font_size: Fallback text size applied to slate fields lacking explicit scaling.
        
    Returns:
        A SlateConfig mapping the text labels to SlateField layout definitions.
    """
    slate_cfg = config.get("slate", {})
    raw_fields = slate_cfg.get("fields", {})
    
    parsed_fields = {}
    for key, val in raw_fields.items():
        if isinstance(val, dict):
            # Advanced nested config
            parsed_fields[key] = SlateField(
                text=val.get("text", ""),
                x=str(val.get("x")) if "x" in val else None,
                y=str(val.get("y")) if "y" in val else None,
                font_size=val.get("font_size"),
                align=val.get("align", "left"),
                max_width=int(val.get("max_width", 0)),
                max_height=int(val.get("max_height", 0)),
                font_color=val.get("font_color"),
                background_color=val.get("background_color")
            )
        else:
            # Fallback simple string config
            parsed_fields[key] = SlateField(text=str(val))
            
    return SlateConfig(
        fields=parsed_fields,
        template_image=slate_cfg.get("template_image"),
        thumbnail_enabled=slate_cfg.get("thumbnail_enabled", True),
        thumbnail_x=slate_cfg.get("thumbnail_x"),
        thumbnail_y=slate_cfg.get("thumbnail_y"),
        thumbnail_width=slate_cfg.get("thumbnail_width"),
        global_font_size=global_font_size,
        enabled=slate_cfg.get("enabled", True)
    )

def parse_globals_config(config: Dict[str, Any]) -> GlobalsConfig:
    """
    Extracts top-level pipeline configurations (framerate, pipeline dimensions, font paths).
    
    Args:
        config: The raw YAML dictionary.
        
    Returns:
        A GlobalsConfig object.
    """
    glbs = config.get("globals", {})
    return GlobalsConfig(
        framerate=glbs.get("framerate"),
        width=glbs.get("width"),
        height=glbs.get("height"),
        cropwidth=glbs.get("cropwidth"),
        cropheight=glbs.get("cropheight"),
        cropx=glbs.get("cropx"),
        cropy=glbs.get("cropy"),
        fit=glbs.get("fit"),
        output_codec=glbs.get("output_codec"),
        font_size=glbs.get("font_size"),
        ffmpeg_bin=glbs.get("ffmpeg_bin"),
        reel_name=glbs.get("reel_name"),
        font_color=glbs.get("font_color", "white"),
        background_color=glbs.get("background_color", "black@0.5"),
        timecode=parse_timecode_config(glbs.get("timecode", {})) if "timecode" in glbs else None,
        font=glbs.get("font"),
        metadata_mapping=glbs.get("metadata_mapping"),
        vf=_to_list(glbs.get("vf")),
        extra_args=_to_list(glbs.get("extra_args") or glbs.get("args"))
    )

def _to_list(val):
    if val is None:
        return None
    if isinstance(val, str):
        return [val]
    return list(val)

def parse_timecode_config(cfg: Dict[str, Any]) -> TimecodeConfig:
    """Parses the timecode configuration block."""
    return TimecodeConfig(
        source=cfg.get("source", "media"),
        start=cfg.get("start", "auto"),
        rate=cfg.get("rate"),
        drop_frame=cfg.get("drop_frame", False)
    )

def parse_dynamic_metadata_config(config: Dict[str, Any]) -> DynamicMetadataConfig:
    """
    Parses the dynamic metadata rules from the YAML configuration.
    """
    dyn_meta = config.get("dynamic_metadata", {})
    rules = []
    raw_rules = dyn_meta.get("rules", [])
    for r in raw_rules:
        if isinstance(r, dict) and "target" in r and "source" in r:
            rules.append(MetadataRule(
                target=r["target"],
                source=r["source"],
                regex=r.get("regex"),
                replace=r.get("replace")
            ))
    
    return DynamicMetadataConfig(
        enabled=dyn_meta.get("enabled", True),
        rules=rules
    )

def parse_output_codecs(config: Dict[str, Any]) -> Dict[str, OutputCodecProfile]:
    """
    Parses the available FFmpeg output codec profiles into named presets.
    
    Args:
        config: The raw YAML dictionary.
        
    Returns:
        A dictionary mapping profile names (e.g. 'h264_hq') to OutputCodecProfile settings.
    """
    codecs = config.get("output_codecs", {})
    result = {}
    for name, profile in codecs.items():
        # Support legacy nested `profile_args` dict if it exists
        legacy_args = profile.get("profile_args", {})
        
        # Collect everything else that isn't a known core key into profile_args
        flat_args = {k: v for k, v in profile.items() if k not in ("codec", "crf", "preset", "profile_args")}
        
        # Merge them (flattened keys take precedence)
        merged_args = {**legacy_args, **flat_args}
        
        result[name] = OutputCodecProfile(
            codec=profile.get("codec"),
            crf=profile.get("crf"),
            preset=profile.get("preset"),
            profile_args=merged_args
        )
    return result
