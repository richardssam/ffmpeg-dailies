import subprocess
import os
import json
import logging
from .models import DailiesContext
from .filtergraph import build_slate_filtergraph, build_video_filtergraph

logger = logging.getLogger(__name__)

def get_middle_frame_index(input_path: str, is_sequence: bool = False, start_number: int = None) -> int:
    """
    Calculates the middle frame index of the input media, used for the slate thumbnail selection.
    Relies on ffprobe for video container files or directory listing checks for image sequences.
    
    Args:
        input_path: Path to the media file or the sequence pattern.
        is_sequence: Whether the input implies an image sequence.
        start_number: The starting frame number (if known) for a sequence context.
        
    Returns:
        The calculated middle frame index (1-based offset relative to the stream). Falls back to 1 on failure.
    """
    try:
        if is_sequence and start_number is not None:
            # We can't easily ffprobe wildcards to get frame counts generically, 
            # so we check the directory for matching files.
            base_dir = os.path.dirname(input_path)
            # A simple heuristic: just count files in the directory for now, 
            # or default to 1 if we can't determine it easily.
            # For a robust production tool, fileseq sequence parsing would be used here.
            files = [f for f in os.listdir(base_dir) if os.path.isfile(os.path.join(base_dir, f))]
            return max(1, len(files) // 2)
            
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-count_packets", "-show_entries", "stream=nb_read_packets,nb_frames,duration,r_frame_rate",
            "-of", "json", input_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        
        # Try nb_frames first
        nb_frames = stream.get("nb_frames")
        if nb_frames:
            return int(nb_frames) // 2
            
        # Try nb_read_packets
        nb_packets = stream.get("nb_read_packets")
        if nb_packets:
            return int(nb_packets) // 2
            
        # Try duration * fps
        duration = float(stream.get("duration", 0))
        fps_str = stream.get("r_frame_rate", "24/1")
        num, den = map(int, fps_str.split('/'))
        fps = num / den if den != 0 else 24
        
        frames = int(duration * fps)
        return max(1, frames // 2)

    except Exception as e:
        logger.warning(f"Could not determine middle frame, defaulting to 1. Error: {e}")
        return 1

def build_ffmpeg_command(ctx: DailiesContext) -> list[str]:
    """
    Assembles the complete FFmpeg CLI command list from the resolved DailiesContext.
    Connects the complex filtergraphs (slate + video) with input scaling, OCIO processing, and output encoding.
    
    Args:
        ctx: The fully populated context specifying inputs, outputs, pipelines, and encoders.
        
    Returns:
        A list of strings that can be passed directly to subprocess.run().
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
    complex_filter = f"{split_node}{slate_fg};{video_fg};[slate_out][video_out]concat=n=2:v=1:a=0[final_v]"
    
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
    
    if has_template and ctx.slate_config.template_image:
        cmd.extend([
            "-i", ctx.slate_config.template_image
        ])
        
    cmd.extend([
        "-filter_complex", complex_filter,
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
            cmd.extend([f"-{k}", str(v)])
    else:
        # Generic encoder settings (could be pulled from config in the future)
        cmd.extend([
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p"
        ])
        
    cmd.extend([
        "-r", ctx.input_settings.framerate,
        ctx.output_settings.path
    ])
    
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
    try:
        subprocess.run(cmd, check=True)
        logger.info("Success!")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed with exit code {e.returncode}")
        raise
