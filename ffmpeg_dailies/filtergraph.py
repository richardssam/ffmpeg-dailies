import sys
import textwrap
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
        escaped_config = escape_path_for_filtergraph(ctx.ocio_settings.config_path)
        ocio_params.append(f"config='{escaped_config}'")
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

def escape_path_for_filtergraph(path: str) -> str:
    """
    Escapes paths for use within FFmpeg filtergraphs.
    Specifically, it escapes colons in Windows drive-letter paths (e.g., C:/ -> C\\:/).
    """
    if not path:
        return path
    
    # Check for Windows-style drive letter (e.g., C:/ or D:\)
    import re
    if re.match(r'^[a-zA-Z]:[/\\]', path):
        # Escape ONLY the first colon
        return path.replace(":", "\\:", 1)
    
    return path

def wrap_text_heuristic(text: str, max_width: int, font_size: float) -> str:
    """
    Approximates text wrapping by injecting newlines using a character-width heuristic.
    Average char width is assumed to be ~55% of font_size for typical sans-serif fonts.
    """
    if not max_width or max_width <= 0:
        return text
    
    avg_char_w = font_size * 0.55
    chars_per_line = max(1, int(max_width / avg_char_w))
    
    lines = []
    # Preserve existing newlines while wrapping long blocks
    for part in text.splitlines():
        if not part:
            lines.append("")
            continue
        wrapped = textwrap.fill(part, width=chars_per_line, break_long_words=True, replace_whitespace=False)
        lines.append(wrapped)
        
    return "\n".join(lines)

def build_drawtext_filter(text: str = None, x: str = "0", y: str = "0", fontfile: str = None, fontsize: int = 48, fontcolor: str = "white", box: bool = False, boxcolor: str = "black@0.5", boxborderw: int = 5, start_number: Optional[int] = None, timecode: Optional[str] = None, tc_rate: Optional[float] = None) -> str:
    """
    Constructs an extensive FFmpeg drawtext filter string with specified positioning and text features.
    """
    params = [
        f"x={x}",
        f"y={y}",
        f"fontcolor={fontcolor}",
        f"fontsize={fontsize}"
    ]
    
    if text:
        params.insert(0, f"text='{escape_drawtext(text)}'")
        
    if timecode and tc_rate:
        params.insert(0, f"rate={tc_rate}")
        params.insert(0, f"timecode='{escape_drawtext(timecode)}'")
        
    if fontfile:
        params.append(f"fontfile='{escape_path_for_filtergraph(fontfile)}'")
    if box:
        params.append("box=1")
        params.append(f"boxcolor={boxcolor}")
        params.append(f"boxborderw={boxborderw}")
    if start_number is not None:
        params.append(f"start_number={start_number}")
        
    return "drawtext=" + ":".join(params)

def resolve_burnin_text(template: str, ctx: DailiesContext) -> str:
    """
    Evaluates a string template (like '{frame}') dynamically using the given context.
    """
    class SafeDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'
            
    # Always include 'frame' as FFmpeg's active render variable %{frame_num}
    # For actual FFmpeg drawtext we must pass literal %{frame_num} so drawtext updates per frame.
    eval_dict = SafeDict(ctx.metadata)
    eval_dict["frame"] = "%{frame_num}"
    
    if hasattr(ctx, 'resolved_timecode') and ctx.resolved_timecode:
        eval_dict["timecode"] = ctx.resolved_timecode
    if hasattr(ctx, 'resolved_reel') and ctx.resolved_reel:
        eval_dict["reel"] = ctx.resolved_reel
        
    return template.format_map(eval_dict) if "{" in template else template

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
        
        # Scale thumbnail to user-defined width, or a reasonable fallback (e.g. 40% of slate width)
        thumb_w = ctx.slate_config.thumbnail_width or int(w * 0.4)
        if thumb_w <= 0: thumb_w = int(w * 0.4)
        # Assuming 16:9 for default thumb height calculations
        thumb_h = int(thumb_w * (9/16)) 
        
        crop_filter = ""
        cw = ctx.input_settings.cropwidth
        ch = ctx.input_settings.cropheight
        cx = ctx.input_settings.cropx
        cy = ctx.input_settings.cropy
        if cw is not None and ch is not None:
            crop_filter = f"crop={cw}:{ch}"
            if cx is not None and cy is not None:
                crop_filter += f":{cx}:{cy}"
            crop_filter += ","
            
        pip_chain = f"[thumb_stream]select='eq(n\\,{mid_frame})',{crop_filter}scale={thumb_w}:{thumb_h}:force_original_aspect_ratio=decrease"
        
        # Apply OCIO if enabled
        ocio_filter = build_ocio_filter(ctx)
        if ocio_filter:
            pip_chain += "," + ocio_filter
            
        # Apply global vf filters to PIP
        if ctx.globals_config.vf:
            pip_chain += "," + ",".join(ctx.globals_config.vf)
                
        pip_chain += f",trim=end_frame=1,setpts=PTS-STARTPTS[pip]"
        
        # Select the middle frame, scale it, and force 1 frame output 
        filters.append(pip_chain)
        
        # Overlay the PIP onto the slate background 
        pip_x = ctx.slate_config.thumbnail_x if ctx.slate_config.thumbnail_x is not None else w - thumb_w - 50
        pip_y = ctx.slate_config.thumbnail_y if ctx.slate_config.thumbnail_y is not None else 50
        filters.append(f"{current_out}[pip]overlay=x={pip_x}:y={pip_y}[slate_with_pip]")
        current_out = "[slate_with_pip]"

    # Apply global vf filters to the slate background/template as well
    if ctx.globals_config.vf:
        filters.append(f"{current_out}{','.join(ctx.globals_config.vf)}[slate_vf]")
        current_out = "[slate_vf]"

    # Apply Text Setup
    drawtexts = []
    
    # If using string fallbacks, we space them manually. 
    # If using absolute positions, we respect them.
    y_offset = h // 4
    spacing = 60
    
    class SafeDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'
            
    safe_metadata = SafeDict(ctx.metadata)
    
    if getattr(ctx, 'resolved_timecode', None):
        safe_metadata["timecode"] = ctx.resolved_timecode
    if getattr(ctx, 'resolved_reel', None):
        safe_metadata["reel"] = ctx.resolved_reel
    
    for key, field in ctx.slate_config.fields.items():
        text_template = field.text
        val = text_template.format_map(safe_metadata) if "{" in text_template else text_template
        display_text = f"{key}: {val}" if not has_template else val
        
        font_size = field.font_size or ctx.slate_config.global_font_size or 50
        
        # Apply wrapping heuristic
        display_text = wrap_text_heuristic(display_text, field.max_width, font_size)
        
        # Determine base X/Y coordinates
        if field.y is not None:
            base_y = field.y
        else:
            base_y = str(y_offset)
            y_offset += spacing
            display_text = f"{key}: {val}" # Force key rendering on fallback layout
            
        # Split into lines for individual alignment
        lines = display_text.splitlines()
        for i, line in enumerate(lines):
            if not line: continue
            
            # Calculate Y for this line
            # If base_y is a number (string or int), we can increment it. 
            # If it's an expression like 'h/2', we append an offset.
            try:
                current_y = str(int(base_y) + int(i * font_size * 1.2))
            except (ValueError, TypeError):
                current_y = f"({base_y})+{int(i * font_size * 1.2)}"

            # Determine X based on alignment
            # If max_width is specified, alignment is relative to the box [x, x + max_width]
            # Otherwise it's screen-relative (w) or x-relative (left)
            mw = int(field.max_width or 0)
            base_x = int(field.x or 0)
            
            if field.align == "center":
                if mw > 0:
                    x_pos = f"({base_x}+({mw}-tw)/2)"
                else:
                    x_pos = "(w-tw)/2"
            elif field.align == "right":
                if mw > 0:
                    x_pos = f"({base_x}+{mw}-tw)"
                else:
                    x_pos = "w-tw-10"
            elif field.x is not None:
                x_pos = field.x
            else:
                x_pos = "(w-tw)/2" # Default to centered if no X and no align specified
                
            dt_filter = build_drawtext_filter(
                text=line,
                x=x_pos,
                y=current_y,
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
    
    # Calculate tc_rate from framerate (e.g. 24000/1001 or 24)
    tc_rate_str = str(ctx.input_settings.framerate or "24")
    if "/" in tc_rate_str:
        num, den = tc_rate_str.split("/")
        tc_rate = float(num) / float(den) if float(den) != 0 else 24.0
    else:
        tc_rate = float(tc_rate_str)
        
    for pos, template in ctx.burnin_config.layout.items():
        # apply font config if available based on pos, or use default
        font_file = ctx.burnin_config.fonts.get(pos, get_default_font(ctx))
        # Cascading font size: burnin global -> globals -> fallback 40
        font_size = ctx.burnin_config.global_font_size or ctx.globals_config.font_size or 40
        # Cascading colors: burnin -> global -> defaults
        font_color = ctx.burnin_config.font_color or ctx.globals_config.font_color or "white"
        bg_color = ctx.burnin_config.background_color or ctx.globals_config.background_color or "black@0.5"
        
        base_x, base_y = get_burnin_position(pos)

        # Detect rolling timecode token
        if "{timecode}" in template and getattr(ctx, 'resolved_timecode', None):
            parts = template.split("{timecode}")
            prefix_template = parts[0]
            suffix_template = parts[1] if len(parts) > 1 else ""
            
            # Use %{frame_num} for better expansion reliability
            resolved_prefix = resolve_burnin_text(prefix_template, ctx)
            resolved_suffix = resolve_burnin_text(suffix_template, ctx)
            
            # Heuristics for widths
            char_w = font_size * 0.55
            # Assume frame counter is 4 digits if using %{n} or %{frame_num}
            w_prefix = len(resolved_prefix.replace("%{n}", "0000").replace("%{frame_num}", "0000")) * char_w
            w_tc = 11 * char_w
            w_suffix = len(resolved_suffix.replace("%{n}", "0000").replace("%{frame_num}", "0000")) * char_w
            total_w = w_prefix + w_tc + w_suffix
            
            target_w = ctx.output_settings.target_width
            
            # Determine starting X based on logical position
            if "right" in pos:
                base_x_num = target_w - total_w - 10
            elif "center" in pos:
                base_x_num = (target_w - total_w) / 2
            else:
                base_x_num = 10
                
            # 1. Render Unified Background Box
            # To ensure the box is visible and covers the full height of the font, 
            # we use a string of capital 'M' characters with transparent font color.
            # 'M' is typically the tallest and widest character.
            bg_char_count = int(total_w / (font_size * 0.5)) + 1
            drawtexts.append(build_drawtext_filter(
                text="M" * bg_char_count,
                x=int(base_x_num),
                y=base_y,
                fontfile=font_file,
                fontsize=int(font_size),
                fontcolor="white@0.0", # Transparent text
                box=True,
                boxcolor=bg_color
            ))

            # 2. Render Prefix
            if resolved_prefix:
                drawtexts.append(build_drawtext_filter(
                    text=resolved_prefix,
                    x=int(base_x_num),
                    y=base_y,
                    fontfile=font_file,
                    fontsize=int(font_size),
                    fontcolor=font_color,
                    box=False,
                    start_number=ctx.input_settings.start_number
                ))

            # 3. Render Rolling Timecode
            drawtexts.append(build_drawtext_filter(
                text=None,
                x=int(base_x_num + w_prefix),
                y=base_y,
                fontfile=font_file,
                fontsize=int(font_size),
                fontcolor=font_color,
                box=False,
                timecode=ctx.resolved_timecode,
                tc_rate=tc_rate,
                start_number=ctx.input_settings.start_number
            ))

            # 4. Render Suffix
            if resolved_suffix:
                drawtexts.append(build_drawtext_filter(
                    text=resolved_suffix,
                    x=int(base_x_num + w_prefix + w_tc),
                    y=base_y,
                    fontfile=font_file,
                    fontsize=int(font_size),
                    fontcolor=font_color,
                    box=False,
                    start_number=ctx.input_settings.start_number
                ))
        else:
            text = resolve_burnin_text(template, ctx)
            drawtexts.append(build_drawtext_filter(
                text=text,
                x=base_x,
                y=base_y,
                fontfile=font_file,
                fontsize=int(font_size),
                fontcolor=font_color,
                box=True,
                boxcolor=bg_color,
                start_number=ctx.input_settings.start_number
            ))
        
    if drawtexts:
        filters.append(",".join(drawtexts))
        
    # Apply global vf filters if specified
    if ctx.globals_config.vf:
        filters.extend(ctx.globals_config.vf)
        
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
