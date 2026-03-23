import sys
import os
import re
import datetime
import fileseq

def resolve_input(input_path: str):
    """
    Resolves an input path, potentially using fileseq to expand sequence wildcards (e.g. %04d) 
    and identify the start frame.
    
    Returns:
        tuple[str, int, bool]: (resolved_input_path, start_frame, is_image_sequence)
    """
    # If not a sequence pattern and file exists, return as is
    if not ("@" in input_path or "#" in input_path or "%" in input_path):
        return input_path, None, False
        
    try:
        # findSequencesOnDisk returns a list of FileSequences found on disk for the given pattern
        seq_list = fileseq.findSequencesOnDisk(input_path)
        if not seq_list:
            # fallback if no sequence found on disk but pattern provided
            seq = fileseq.FileSequence(input_path)
        else:
            seq = seq_list[0]
            
        start_frame = seq.start()
        # Formulate ffmpeg sequence string like %05d
        zfill = seq.zfill()
        if zfill > 0:
            fmtspec = f"%0{zfill}d"
        else:
            fmtspec = "%d"
            
        ffmpeg_path = seq.dirname() + seq.basename() + fmtspec + seq.extension()
        return ffmpeg_path, start_frame, True
    except Exception as e:
        print(f"Error resolving sequence: {e}", file=sys.stderr)
        return input_path, None, "%" in input_path

def get_video_frame_count(input_path: str) -> int:
    """
    Uses ffprobe to determine the number of frames in a video container.
    """
    import subprocess
    import json
    try:
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
            return int(nb_frames)
            
        # Try nb_read_packets
        nb_packets = stream.get("nb_read_packets")
        if nb_packets:
            return int(nb_packets)
            
        # Try duration * fps
        duration = float(stream.get("duration", 0))
        fps_str = stream.get("r_frame_rate", "24/1")
        num, den = map(int, fps_str.split('/'))
        fps = num / den if den != 0 else 24
        
        return int(duration * fps)
    except Exception:
        return 0

def populate_implicit_metadata(metadata: dict, input_media: str, dynamic_config: 'DynamicMetadataConfig' = None) -> dict:
    if not input_media:
        return metadata

    # 1. Base Defaults (Legacy / Core)
    if "File Name" not in metadata:
        # Get a clean basename
        if "@" in input_media or "#" in input_media or "%" in input_media:
            try:
                seqs = fileseq.findSequencesOnDisk(os.path.dirname(input_media))
                if seqs:
                    metadata["File Name"] = seqs[0].basename().rstrip('.')
                else:
                    metadata["File Name"] = os.path.basename(input_media)
            except Exception:
                metadata["File Name"] = os.path.basename(input_media)
        else:
            metadata["File Name"] = os.path.basename(input_media)
            
    if "Date Delivered" not in metadata:
        metadata["Date Delivered"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 2. Rule-based Dynamic Metadata
    if dynamic_config and dynamic_config.enabled:
        for rule in dynamic_config.rules:
            # Skip if target already explicitly set
            if rule.target in metadata and metadata[rule.target]:
                continue
                
            # Get source value
            source_val = ""
            if rule.source == "input_path":
                source_val = input_media
            elif rule.source in metadata:
                source_val = metadata[rule.source]
            
            if not source_val:
                continue
                
            # Apply Regex extraction
            if rule.regex:
                try:
                    match = re.search(rule.regex, source_val, re.IGNORECASE)
                    if match:
                        if rule.replace:
                            # Use regex replacement if provided (supports \1, \2 etc)
                            metadata[rule.target] = re.sub(rule.regex, rule.replace, source_val, flags=re.IGNORECASE)
                        else:
                            # Otherwise just use the first group if it exists, or the whole match
                            metadata[rule.target] = match.group(1) if match.groups() else match.group(0)
                except Exception as e:
                    print(f"Error applying metadata rule for {rule.target}: {e}")

    # 3. Fallback / Legacy auto-population if rules didn't cover them
    if "Version" not in metadata:
        # Match _v01, _v002, etc. in the filename
        base = os.path.basename(input_media)
        match = re.search(r'_v(\d+)', base, re.IGNORECASE)
        if match:
            metadata["Version"] = f"v{match.group(1)}"
            
    if "Frame Range" not in metadata:
        # If it's a sequence, try fileseq
        if "@" in input_media or "#" in input_media or "%" in input_media:
            try:
                dirname = os.path.dirname(input_media)
                seqs = fileseq.findSequencesOnDisk(dirname)
                if seqs:
                    metadata["Frame Range"] = seqs[0].frameRange()
            except Exception:
                pass
        else:
            # It's a movie file, use ffprobe
            count = get_video_frame_count(input_media)
            if count > 0:
                metadata["Frame Range"] = f"0-{count-1}"
                
    return metadata
