__version__ = "0.1.0"
__all__ = ["render", "__version__"]

import os

from .config import load_config, parse_globals_config, parse_output_codecs, parse_ocio_settings, parse_slate_config, parse_burnin_config, parse_dynamic_metadata_config
from .models import DailiesContext, InputSettings, OutputSettings
from .execute import build_ffmpeg_command, run_ffmpeg
from .utils import resolve_input, populate_implicit_metadata, extract_source_metadata, get_start_timecode, resolve_reel_name

def render(
    config_path: str,
    input_media: str,
    output_media: str,
    metadata: dict = None,
    framerate: str = None,
    start_number: int = None,
    input_width: int = None,
    input_height: int = None,
    target_width: int = None,
    target_height: int = None,
    fit: bool = None,
    timecode: str = None,
    dry_run: bool = False,
    verbose: bool = False,
    output_codec: str = None
) -> list[str]:
    """
    Programmatic entry point for generating dailies via FFmpeg.
    
    Args:
        config_path: Path to the YAML configuration file defining slates, burn-ins, and OCIO rules.
        input_media: Path to the input media (QuickTime or image sequence pattern).
        output_media: Path to write the output QuickTime.
        metadata: Dictionary of dynamic variables to resolve against `{Var}` tokens in the config.
        framerate: Overrides the framerate derived from the config.
        start_number: Overrides the starting frame number derived from the sequence on disk.
        input_width: Overrides the input width defined in the config.
        input_height: Overrides the input height defined in the config.
        target_width: Overrides the target delivery width defined in the config.
        target_height: Overrides the target delivery height defined in the config.
        fit: If True, preserves aspect ratio by padding instead of stretching. Overrides config.
        dry_run: If True, returns the FFmpeg command list without executing it.
        
    Returns:
        A list of strings representing the final FFmpeg command.
    """
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw_config = load_config(config_path)
    globals_config = parse_globals_config(raw_config)
    output_codecs = parse_output_codecs(raw_config)
    
    # Resolve input sequence with fileseq
    resolved_input_path, resolved_start, is_image_sequence = resolve_input(input_media)
    
    # Custom arg resolver equivalent
    final_framerate = str(framerate if framerate is not None else globals_config.framerate or "24")
    final_input_width = input_width if input_width is not None else 1920
    final_input_height = input_height if input_height is not None else 1080
    final_target_width = target_width if target_width is not None else globals_config.width or 1920
    final_target_height = target_height if target_height is not None else globals_config.height or 1080
    
    # Fit is special: defaults to True if missing globally, overridden if explicitly passed
    if fit is not None:
        final_fit = fit
    elif globals_config.fit is not None:
        final_fit = globals_config.fit
    else:
        final_fit = True
    
    # Override start number if provided
    final_start = start_number if start_number is not None else resolved_start
    
    input_settings = InputSettings(
        path=resolved_input_path,
        framerate=final_framerate,
        width=final_input_width,
        height=final_input_height,
        is_image_sequence=is_image_sequence,
        start_number=final_start,
        cropwidth=globals_config.cropwidth,
        cropheight=globals_config.cropheight,
        cropx=globals_config.cropx,
        cropy=globals_config.cropy
    )
    
    output_settings = OutputSettings(
        path=output_media,
        target_width=final_target_width,
        target_height=final_target_height,
        fit=final_fit
    )
    
    ocio_settings = parse_ocio_settings(raw_config)
    dynamic_metadata_config = parse_dynamic_metadata_config(raw_config)
    slate_config = parse_slate_config(raw_config, globals_config.font_size)
    burnin_config = parse_burnin_config(raw_config, final_target_width, final_target_height, globals_config.font_size)
    
    # Process metadata payload
    final_metadata = raw_config.get("metadata", {}).copy()
    if metadata:
        final_metadata.update(metadata)
        
    final_metadata = populate_implicit_metadata(final_metadata, input_media, dynamic_metadata_config)
    
    from .utils import extract_source_metadata, get_start_timecode, resolve_reel_name
    source_meta = extract_source_metadata(input_media)
    
    if output_codec:
        globals_config.output_codec = output_codec
        
    ctx = DailiesContext(
        input_settings=input_settings,
        output_settings=output_settings,
        ocio_settings=ocio_settings,
        slate_config=slate_config,
        burnin_config=burnin_config,
        metadata=final_metadata,
        dynamic_metadata=dynamic_metadata_config,
        globals_config=globals_config,
        output_codecs=output_codecs
    )
    
    if timecode:
        if not globals_config.timecode:
            from .models import TimecodeConfig
            globals_config.timecode = TimecodeConfig()
        globals_config.timecode.start = timecode

    # Resolve timecode and reel name using the context
    ctx.resolved_timecode = get_start_timecode(ctx, source_meta)
    ctx.resolved_reel = resolve_reel_name(ctx, source_meta)
    
    from .execute import get_filter_complex
    filter_complex = get_filter_complex(ctx)
    
    if not dry_run:
        import tempfile
        # Use a temporary file to avoid command line length limits
        with tempfile.NamedTemporaryFile(suffix=".fg", mode="w", delete=False) as f:
            # Make the filter graph slightly more human readable by adding newlines
            readable_filter = filter_complex.replace(";", ";\n\n")
            f.write(readable_filter)
            script_path = f.name
            
        try:
            cmd = build_ffmpeg_command(ctx, filter_script_path=script_path)
            run_ffmpeg(cmd, verbose=verbose)
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)
    else:
        cmd = build_ffmpeg_command(ctx, filter_complex_str=filter_complex)
        
    return cmd
