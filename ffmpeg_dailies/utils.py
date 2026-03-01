import sys

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
        import fileseq
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
    except ImportError:
        print("fileseq module not found. Falling back to basic regex input parsing.", file=sys.stderr)
        is_seq = ("%" in input_path) or ("@" in input_path) or ("#" in input_path)
        
        import re
        # Convert @@@@ to %04d
        match_at = re.search(r'(@+)', input_path)
        if match_at:
            count = len(match_at.group(1))
            ffmpeg_path = input_path.replace(match_at.group(1), f"%0{count}d")
            return ffmpeg_path, 1, True
            
        # Convert # to %04d (standard Nuke format)
        if "#" in input_path:
            # Technically # means 4 padding in some apps, or flexible in others, but usually %04d
            ffmpeg_path = input_path.replace("#", "%04d")
            return ffmpeg_path, 1, True
            
        return input_path, None, is_seq
    except Exception as e:
        print(f"Error resolving sequence: {e}", file=sys.stderr)
        return input_path, None, "%" in input_path

def populate_implicit_metadata(metadata: dict, input_media: str) -> dict:
    import os
    import re
    import datetime
    
    if not input_media:
        return metadata
        
    if "File Name" not in metadata:
        metadata["File Name"] = os.path.basename(input_media)
        
    if "Version" not in metadata:
        # Match _v01, _v002, etc. in the filename
        base = os.path.basename(input_media)
        match = re.search(r'_v(\d+)', base, re.IGNORECASE)
        if match:
            metadata["Version"] = f"v{match.group(1)}"

    if "Date Delivered" not in metadata:
        metadata["Date Delivered"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            
    if "Frame Range" not in metadata:
        # If it's a sequence, try fileseq first
        if "@" in input_media or "#" in input_media or "%" in input_media:
            try:
                import fileseq
                import os
                dirname = os.path.dirname(input_media)
                seqs = fileseq.findSequencesOnDisk(dirname)
                if seqs:
                    metadata["Frame Range"] = seqs[0].frameRange()
            except Exception:
                pass
                
    return metadata
