import sys
from typing import List, Dict, Tuple, Optional
from .models import DailiesContext, BurninConfig, SlateConfig

# Platform-aware font defaults
_PLATFORM_FONTS = {
    "darwin": "/System/Library/Fonts/Helvetica.ttc",
    "linux": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "win32": "C:/Windows/Fonts/arial.ttf",
}

def get_default_font(ctx: DailiesContext) -> str:
    """
    Returns the font path based on the config's per-OS font map, or a fallback platform-aware default.
    """
    if ctx.globals_config.font and isinstance(ctx.globals_config.font, dict):
        font = ctx.globals_config.font.get(sys.platform)
        if font:
            return font
    return _PLATFORM_FONTS.get(sys.platform, _PLATFORM_FONTS["linux"])

def build_ocio_filter(ctx: DailiesContext) -> Optional[str]:
    """
    Constructs the OCIO filter string based on the parsed OCIOSettings block.
    
    Args:
        ctx: The active rendering context yielding OCIO properties.
        
    Returns:
        A comma-separated FFmpeg format string (e.g., 'ocio=config=...'), or None if disabled.
    """
    if not ctx.ocio_settings.enabled:
        return None
    ocio_params = []
    if ctx.ocio_settings.config_path:
        ocio_params.append(f"config='{ctx.ocio_settings.config_path}'")
    if ctx.ocio_settings.input_space:
        ocio_params.append(f"input='{ctx.ocio_settings.input_space}'")
    if ctx.ocio_settings.output_space:
        ocio_params.append(f"display='{ctx.ocio_settings.output_space}'")
    if ctx.ocio_settings.view:
        ocio_params.append(f"view='{ctx.ocio_settings.view}'")
    if ocio_params:
        return "ocio=" + ":".join(ocio_params)
    return None

def escape_drawtext(text: str) -> str:
    """Escapes special characters specifically for FFmpeg's drawtext filter text parameter."""
    text = str(text).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
    return text

def build_drawtext_filter(text: str, x: str, y: str, fontfile: str = None, fontsize: int = 48, fontcolor: str = "white", box: bool = False, boxcolor: str = "black@0.5", boxborderw: int = 5, start_number: Optional[int] = None) -> str:
    """
    Constructs an extensive FFmpeg drawtext filter string with specified positioning and text features.
    """
    params = [
        f"text='{escape_drawtext(text)}'",
        f"x={x}",
        f"y={y}",
        f"fontcolor={fontcolor}",
        f"fontsize={fontsize}"
    ]
    if fontfile:
        params.append(f"fontfile='{fontfile}'")
    if box:
        params.append("box=1")
        params.append(f"boxcolor={boxcolor}")
        params.append(f"boxborderw={boxborderw}")
    if start_number is not None:
        params.append(f"start_number={start_number}")
        
    return "drawtext=" + ":".join(params)

def resolve_burnin_text(template: str, ctx: DailiesContext) -> str:
    """
    Resolves metadata placeholders (like {Show}) against the available token map, handling FFmpeg frame var logic.
    """
    if not isinstance(template, str):
        return str(template)
    
    fmt_dict = dict(ctx.metadata)
    fmt_dict["frame"] = "%{frame_num}"
    
    try:
        return template.format(**fmt_dict)
    except KeyError as e:
        print(f"Warning: Missing metadata key {e} in burnin template '{template}'")
        return template

def get_burnin_position(position: str) -> Tuple[str, str]:
    """
    Maps logical named quadrants (e.g. 'lower_left') to FFmpeg coordinate expressions.
    """
    position = position.lower().replace(" ", "_")
    if position == "lower_left":
        return "10", "h-th-10"
    elif position == "lower_center":
        return "(w-tw)/2", "h-th-10"
    elif position == "lower_right":
        return "w-tw-10", "h-th-10"
    elif position == "top_left":
        return "10", "10"
    elif position == "top_center":
        return "(w-tw)/2", "10"
    elif position == "top_right":
        return "w-tw-10", "10"
    return "10", "10" # Default

def build_slate_filtergraph(ctx: DailiesContext, mid_frame: int = 1) -> Tuple[str, bool]:
    """
    Constructs the pre-video slate filtergraph handling title cards, nested PIP overlays, and text generation.
    
    Args:
        ctx: Render context controlling target sizes and text layouts.
        mid_frame: Index to extract for the PIP preview (extracted from the main sequence).
        
    Returns:
        A tuple of (FFmpeg complex filter subgraph string, boolean indicating if a template plate was provided).
    """
    w = ctx.output_settings.target_width
    h = ctx.output_settings.target_height
    fps = ctx.input_settings.framerate
    
    filters = []
    has_template = bool(ctx.slate_config.template_image)
    
    if has_template:
        # Template is the second input [1:v]
        # We need to scale it to exactly match target dimensions and trim it to 1 frame to be safe
        filters.append(f"[1:v]scale={w}:{h},setsar=1,trim=end_frame=1[slate_bg]")
    else:
        # Generate 1 frame of black with fixed SAR 1:1
        filters.append(f"color=c=black:s={w}x{h}:r={fps},trim=end_frame=1,setsar=1[slate_bg]")
    
    current_out = "[slate_bg]"
    
    # Extract thumbnail if enabled
    if ctx.slate_config.thumbnail_enabled:
        # We need a branch from the main video [0:v] before any other video filters touch it.
        # But wait, building video filtergraph also uses [0:v]. 
        # A cleaner FFmpeg approach is to apply split at the very beginning of the entire complex_filter:
        # Actually, let's just take [0:v], we'll instruct build_video_filtergraph to read from [main_v] instead,
        # and we'll handle the [0:v] split in build_ffmpeg_command. 
        # But for modularity, let's expect [thumb_stream] as the input here if PIP is enabled.
        
        # Scale thumbnail to a reasonable size (e.g. 40% of slate width)
        thumb_w = int(w * 0.4)
        # Assuming 16:9 for default thumb height calculations
        thumb_h = int(thumb_w * (9/16)) 
        
        pip_chain = f"[thumb_stream]select='eq(n\\,{mid_frame})',scale={thumb_w}:{thumb_h}:force_original_aspect_ratio=decrease"
        
        # Apply OCIO if enabled
        ocio_filter = build_ocio_filter(ctx)
        if ocio_filter:
            pip_chain += "," + ocio_filter
                
        pip_chain += f",trim=end_frame=1,setpts=PTS-STARTPTS[pip]"
        
        # Select the middle frame, scale it, and force 1 frame output 
        filters.append(pip_chain)
        
        # Overlay the PIP onto the slate background (top right corner with padding)
        pip_x = w - thumb_w - 50
        pip_y = 50
        filters.append(f"{current_out}[pip]overlay=x={pip_x}:y={pip_y}[slate_with_pip]")
        current_out = "[slate_with_pip]"

    # Apply Text Setup
    drawtexts = []
    
    # If using string fallbacks, we space them manually. 
    # If using absolute positions, we respect them.
    y_offset = h // 4
    spacing = 60
    
    for key, field in ctx.slate_config.fields.items():
        text_template = field.text
        val = text_template.format(**ctx.metadata) if "{" in text_template else text_template
        display_text = f"{key}: {val}" if not has_template else val # If using a graphical plate, keys are usually baked in, so just print the value. Unless it lacks x/y.
        
        # Determine X/Y coordinates
        if field.x is not None:
            x_pos = field.x
        else:
            x_pos = "(w-text_w)/2" # Centered fallback
            
        if field.y is not None:
            y_pos = field.y
        else:
            y_pos = str(y_offset)
            y_offset += spacing
            display_text = f"{key}: {val}" # Force key rendering on fallback layout
            
        font_size = field.font_size or ctx.slate_config.global_font_size or 50
        
        dt_filter = build_drawtext_filter(
            text=display_text,
            x=x_pos,
            y=y_pos,
            fontfile=get_default_font(ctx),
            fontsize=int(font_size)
        )
        drawtexts.append(dt_filter)

    if not drawtexts:
        filter_chain = ";".join(filters) + f";{current_out}copy[slate_out]"
        return filter_chain, has_template
        
    filter_chain = ";".join(filters) + ";" + current_out + ",".join(drawtexts) + "[slate_out]"
    return filter_chain, has_template

def build_video_filtergraph(ctx: DailiesContext, input_stream: str = "[0:v]") -> str:
    """
    Builds the main processing filtergraph handling dimensions padding, aspect-ratio bounds, OCIO, and timeburn overlays.
    
    Args:
        ctx: Output context settings controlling formatting targets.
        input_stream: Specific video node input name reference.
        
    Returns:
        The video complex filtergraph string representing sequential operations.
    """
    w = ctx.output_settings.target_width
    h = ctx.output_settings.target_height
    fit = ctx.output_settings.fit
    
    filters = []
    
    # 0. Apply crop if specified
    cw = ctx.input_settings.cropwidth
    ch = ctx.input_settings.cropheight
    cx = ctx.input_settings.cropx
    cy = ctx.input_settings.cropy
    
    if cw is not None and ch is not None:
        crop_filter = f"crop={cw}:{ch}"
        if cx is not None and cy is not None:
            crop_filter += f":{cx}:{cy}"
        filters.append(crop_filter)
    
    # 1. Scale and pad to target dimensions, and force SAR 1:1
    if fit:
        # force output aspect ratio by scaling proportionally and then padding
        scale_pad = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1"
    else:
        # no padding: height is ignored, aspect ratio of the input is preserved relative to target width
        scale_pad = f"scale={w}:-2,setsar=1"
        
    filters.append(scale_pad)
    
    # 2. OCIO validation and filter
    ocio_filter = build_ocio_filter(ctx)
    if ocio_filter:
        filters.append(ocio_filter)
            
    # 3. Burn-ins
    drawtexts = []
    for pos, template in ctx.burnin_config.layout.items():
        text = resolve_burnin_text(template, ctx)
        x, y = get_burnin_position(pos)
        
        # apply font config if available based on pos, or use default
        font_file = ctx.burnin_config.fonts.get(pos, get_default_font(ctx))
        
        drawtexts.append(build_drawtext_filter(
            text=text,
            x=x,
            y=y,
            fontfile=font_file,
            fontsize=40, # or configurable
            box=True, # added background box for readability against video
            start_number=ctx.input_settings.start_number
        ))
        
    if drawtexts:
        filters.append(",".join(drawtexts))
        
    # Combine linearly
    # e.g. [input_stream]scale_pad[v1];[v1]ocio[v2];[v2]drawtext1,drawtext2...[video_out]
    
    steps = []
    current_in = input_stream
    
    for i, f in enumerate(filters):
        out_name = f"[v_step_{i}]"
        steps.append(f"{current_in}{f}{out_name}")
        current_in = out_name
        
    # The last out_name will be mapped to video_out
    final_graph = ";".join(steps)
    # rename last step's output to [video_out]
    if steps:
        final_graph = final_graph.replace(current_in, "[video_out]")
    else:
        final_graph = "[0:v]copy[video_out]"
        
    return final_graph
