import os
import subprocess
import json
import logging
import re
import fileseq
import opentimelineio as otio
from .models import DailiesContext
from .filtergraph import build_slate_filtergraph, build_video_filtergraph

logger = logging.getLogger(__name__)
from .utils import get_video_frame_count

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
    # Resolution order: config YAML → $FFMPEG_BIN env var → "ffmpeg" on $PATH
    ffmpeg_bin = ctx.globals_config.ffmpeg_bin or os.environ.get("FFMPEG_BIN", "ffmpeg")
    
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
    if ctx.slate_config.template_image and ctx.slate_config.template_image != "":
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
        
    cmd.extend([
        "-map", "[final_v]",
    ])
    
    # Map Output Codec Profile
    codec_profile = None
    if ctx.globals_config.output_codec:
        codec_profile = ctx.output_codecs.get(ctx.globals_config.output_codec)

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

    # Timecode and Editorial Metadata
    if ctx.resolved_timecode:
        start_tc = ctx.resolved_timecode
        # If we have a slate, the file must start 1 frame earlier to ensure 
        # the main content starts at the resolved timecode.
        if ctx.slate_config.fields:
            try:
                rate = float(ctx.input_settings.framerate or 24)
                if ctx.globals_config.timecode and ctx.globals_config.timecode.rate:
                    rate = ctx.globals_config.timecode.rate
                
                rt = otio.opentime.from_timecode(start_tc, rate)
                offset_rt = rt - otio.opentime.RationalTime(1, rate)
                
                # Handle midnight rollover (24-hour wrap)
                if offset_rt.value < 0:
                    # add 24 hours (86400 seconds)
                    offset_rt = offset_rt + otio.opentime.RationalTime(24 * 3600 * rate, rate)
                    
                start_tc = offset_rt.to_timecode()
            except Exception as e:
                logger.warning(f"Could not calculate slate timecode offset: {e}")
        
        cmd.extend(["-timecode", start_tc])

    if ctx.resolved_reel:
        cmd.extend(["-metadata:s:v:0", f"reel_name={ctx.resolved_reel}"])

    cmd.append(ctx.output_settings.path)
    
    return cmd

def run_ffmpeg(cmd: list[str]) -> None:
    """
    Executes the constructed FFmpeg command as a synchronous subprocess.
    
    Args:
        cmd: A list of string arguments forming the execution array.
        
    Raises:
        subprocess.CalledProcessError: If FFmpeg exits with a non-zero status code indicating failure.
    """
    logger.info("Executing FFmpeg command:")
    logger.info(" ".join(cmd))
    print("Executed ffmpeg command:")
    print(" ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        logger.info("Success!")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed with exit code {e.returncode}")
        raise
