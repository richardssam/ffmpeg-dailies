import os
import subprocess
import json
import logging
import re
import fileseq
import opentimelineio as otio
from .models import DailiesContext
from .filtergraph import build_slate_filtergraph, build_video_filtergraph
from .utils import get_video_frame_count

logger = logging.getLogger(__name__)

def check_ffmpeg_filters(ffmpeg_bin: str, required_filters: list[str]):
    """
    Checks if the given filters are available in the FFmpeg installation at ffmpeg_bin.
    Raises RuntimeError if any filter is missing.
    """
    try:
        res = subprocess.run([ffmpeg_bin, "-filters"], capture_output=True, text=True, check=True)
        missing = [f for f in required_filters if f not in res.stdout]
        if missing:
            raise RuntimeError(
                f"Missing required FFmpeg filter(s): {', '.join(missing)} in {ffmpeg_bin}. "
                "Ensure your FFmpeg build includes --enable-libfreetype and font support."
            )
    except subprocess.CalledProcessError:
        logger.warning(f"Could not verify FFmpeg filters via '{ffmpeg_bin} -filters'. Proceeding anyway.")
    except FileNotFoundError:
        raise RuntimeError(f"FFmpeg executable not found at: {ffmpeg_bin}")

def get_middle_frame_index(input_path: str, is_sequence: bool = False, start_number: int = None) -> int:
    """
    Calculates the middle frame index of the input media, used for the slate thumbnail selection.
    Relies on ffprobe for video container files or directory listing checks for image sequences.
    """
    try:
        if is_sequence and start_number is not None:
            seq_list = fileseq.findSequencesOnDisk(input_path)
            if seq_list:
                frames = list(seq_list[0].frameSet())
                if frames:
                    # Return the 0-indexed offset for use with FFmpeg's 'n' variable
                    return len(frames) // 2
                
            return 0
            
        count = get_video_frame_count(input_path)
        return max(1, count // 2)

    except Exception as e:
        logger.warning(f"Could not determine middle frame, defaulting to 1. Error: {e}")
        return 1

def get_filter_complex(ctx: DailiesContext) -> str:
    """
    Generates the core FFmpeg filtergraph string from the context.
    """
    if not ctx.slate_config.enabled:
        return build_video_filtergraph(ctx, "[0:v]")

    # Determine the middle frame for the PIP thumbnail
    mid_frame = get_middle_frame_index(
        ctx.input_settings.path, 
        ctx.input_settings.is_image_sequence,
        ctx.input_settings.start_number
    )
    
    slate_fg, has_template = build_slate_filtergraph(ctx, mid_frame)
    
    if ctx.slate_config.thumbnail_enabled:
        video_fg = build_video_filtergraph(ctx, "[main_v]")
        # split video to main and thumb streams
        split_node = "[0:v]split=2[main_v][thumb_stream];"
    else:
        video_fg = build_video_filtergraph(ctx, "[0:v]")
        split_node = ""
    
    # concat slate video map and main video map
    return f"{split_node}{slate_fg};{video_fg};[slate_out][video_out]concat=n=2:v=1:a=0[final_v]"

def build_ffmpeg_command(ctx: DailiesContext, filter_script_path: str = None, filter_complex_str: str = None) -> list[str]:
    """
    Assembles the complete FFmpeg CLI command list.
    Supports either an inline filter_complex_str or a path to a filter_complex_script.
    """
    ffmpeg_bin = ctx.globals_config.ffmpeg_bin or os.environ.get("FFMPEG_BIN", "ffmpeg")

    # 0. Validate requirements
    # If using slates or burn-ins, we MUST have drawtext support
    if ctx.slate_config.enabled or ctx.burnin_config.layout:
        check_ffmpeg_filters(ffmpeg_bin, ["drawtext"])
    
    cmd = [
        ffmpeg_bin, "-y"
    ]
    
    # If image sequence, force framerate on input
    if ctx.input_settings.is_image_sequence:
        cmd.extend(["-framerate", ctx.input_settings.framerate])
    
    if ctx.input_settings.start_number is not None:
        cmd.extend(["-start_number", str(ctx.input_settings.start_number)])
        
    cmd.extend([
        "-i", ctx.input_settings.path,
    ])
    
    # Check if we have a template image (this is a bit of a leak from build_filter_complex)
    # but we need it for the -i flags.
    if ctx.slate_config.enabled and ctx.slate_config.template_image and ctx.slate_config.template_image != "":
        cmd.extend([
            "-i", ctx.slate_config.template_image
        ])
        
    if filter_script_path:
        cmd.extend(["-/filter_complex", filter_script_path])
    elif filter_complex_str:
        cmd.extend(["-filter_complex", filter_complex_str])
    else:
        # Generate on the fly if not provided
        cmd.extend(["-filter_complex", get_filter_complex(ctx)])
        
    out_map = "[final_v]" if ctx.slate_config.enabled else "[video_out]"
    cmd.extend([
        "-map", out_map,
    ])
    
    # Map Output Codec Profile
    codec_profile = None
    if ctx.globals_config.output_codec:
        codec_profile = ctx.output_codecs.get(ctx.globals_config.output_codec)
        if not codec_profile:
            raise ValueError(f"Unknown output_codec profile: '{ctx.globals_config.output_codec}'. Check your config.")

    if codec_profile:
        if codec_profile.codec:
            cmd.extend(["-c:v", str(codec_profile.codec)])
        else:
            cmd.extend(["-c:v", "libx264"])
            
        if codec_profile.crf is not None:
            cmd.extend(["-crf", str(codec_profile.crf)])
            
        if codec_profile.preset:
            cmd.extend(["-preset", str(codec_profile.preset)])
            
        for k, v in codec_profile.profile_args.items():
            if k == "profile":
                cmd.extend(["-profile:v", str(v)])
            else:
                cmd.extend([f"-{k}", str(v)])
    else:
        # Generic encoder settings (could be pulled from config in the future)
        cmd.extend([
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p"
        ])
    cmd.extend([
        "-r", ctx.input_settings.framerate,
    ])

    # 1. Enrich metadata with production-trackable info
    # Copy metadata to avoid side-effects on the context object
    meta = ctx.metadata.copy()

    if "source_frame_rate" not in meta:
        meta["source_frame_rate"] = str(ctx.input_settings.framerate)
    
    if "slate_length" not in meta:
        meta["slate_length"] = "1" if (ctx.slate_config.enabled and ctx.slate_config.fields) else "0"
        
    if "display_type" not in meta and ctx.ocio_settings.enabled:
        meta["display_type"] = f"{ctx.ocio_settings.output_space or ctx.ocio_settings.display} ({ctx.ocio_settings.view})"
        
    if "watermarking" not in meta:
        meta["watermarking"] = "True" if ctx.burnin_config.layout else "False"

    # 2. Add metadata flags based on mappings
    default_mappings = {
        "Show Title": "title",
        "Notes": "comment",
        "Vendor Name": "artist",
        "Date Delivered": "date",
        "File Name": "original_filename",
        "reel": "s:v:0:reel_name"
    }
    
    # Ensure resolved_reel and resolved_timecode are available for mapping if not already there
    if ctx.resolved_reel:
        meta["reel"] = ctx.resolved_reel
        
    mappings = default_mappings.copy()
    if ctx.globals_config.metadata_mapping:
        mappings.update(ctx.globals_config.metadata_mapping)
        
    for key, value in meta.items():
        # Skip special internal tokens that are handled differently
        if key in ("timecode", "frame"):
            continue
            
        target_key = mappings.get(key, key)
        if target_key.startswith("s:v:0:"):
            real_key = target_key[6:]
            cmd.extend(["-metadata:s:v:0", f"{real_key}={value}"])
        else:
            cmd.extend(["-metadata", f"{target_key}={value}"])

    # Timecode is still handled via the -timecode flag for better container support
    if ctx.resolved_timecode:
        cmd.extend(["-timecode", ctx.resolved_timecode])

    # 3. Format-specific compatibility flags
    ext = os.path.splitext(ctx.output_settings.path)[1].lower()
    if ext in (".mov", ".mp4"):
        cmd.extend(["-movflags", "use_metadata_tags"])

    # 4. Append extra arbitrary args from globals
    if ctx.globals_config.extra_args:
        cmd.extend(ctx.globals_config.extra_args)

    cmd.append(ctx.output_settings.path)
    
    return cmd

def run_ffmpeg(cmd: list[str], verbose: bool = False) -> None:
    """
    Executes the constructed FFmpeg command as a synchronous subprocess.
    """
    # Look for the filter script path in the command to print it if verbose
    script_path = None
    if "-/filter_complex" in cmd:
        idx = cmd.index("-/filter_complex")
        if idx + 1 < len(cmd):
            script_path = cmd[idx+1]

    if verbose:
        print("\n" + "="*80)
        print("FFMPEG COMMAND:")
        print(" ".join(cmd))
        
        if script_path and os.path.exists(script_path):
            print("\nFFMPEG FILTER GRAPH:")
            with open(script_path, "r") as f:
                print(f.read())
        print("="*80 + "\n")

    try:
        # We still log to the logger regardless
        logger.info(f"Executing: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        if verbose:
            print("Execution successful!")
    except subprocess.CalledProcessError as e:
        # Always print the command on failure to help debugging
        if not verbose:
            print(f"FFmpeg failed with exit code {e.returncode}. Command:")
            print(" ".join(cmd))
        raise
