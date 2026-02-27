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
        print("fileseq module not found. Falling back to basic input.", file=sys.stderr)
        return input_path, None, "%" in input_path
    except Exception as e:
        print(f"Error resolving sequence: {e}", file=sys.stderr)
        return input_path, None, "%" in input_path
