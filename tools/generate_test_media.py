#!/usr/bin/env python3
import subprocess
import argparse
import os
import sys

def generate_test_media(output_dir: str, frames: int = 24, fps: int = 24):
    """
    Generates specific test media variants:
    1. EXR sequence starting at frame 1001
    2. Quicktime file WITHOUT timecode/reel
    3. Quicktime file WITH timecode/reel
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. EXR Sequence (starting at 1001)
    exr_dir = os.path.join(output_dir, "exr_1001")
    os.makedirs(exr_dir, exist_ok=True)
    exr_pattern = os.path.join(exr_dir, "test_seq.%04d.exr")
    cmd_exr = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate={fps}:duration={frames/fps}",
        "-start_number", "1001",
        exr_pattern
    ]
    
    # 2. MOV WITHOUT metadata
    mov_clean_path = os.path.join(output_dir, "test_clean.mov")
    cmd_mov_clean = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate={fps}:duration={frames/fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-map_metadata", "-1", # Strip all metadata
        mov_clean_path
    ]
    
    # 3. MOV WITH metadata
    mov_meta_path = os.path.join(output_dir, "test_metadata.mov")
    cmd_mov_meta = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate={fps}:duration={frames/fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-timecode", "09:00:00:00",
        "-metadata:s:v:0", "reel_name=PRO_REEL_001",
        mov_meta_path
    ]
    
    # 4. Complex Path Sequence (Shot/Version)
    complex_dir = os.path.join(output_dir, "shots", "SH010", "v001")
    os.makedirs(complex_dir, exist_ok=True)
    complex_pattern = os.path.join(complex_dir, "SH010_v001.%04d.exr")
    cmd_complex = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate={fps}:duration={frames/fps}",
        "-start_number", "1001",
        complex_pattern
    ]
    
    print(f"Generating EXR sequence (1001) to {exr_dir}...")
    subprocess.run(cmd_exr, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"Generating Clean MOV to {mov_clean_path}...")
    subprocess.run(cmd_mov_clean, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print(f"Generating Metadata MOV to {mov_meta_path}...")
    subprocess.run(cmd_mov_meta, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"Generating Complex Shot/Version Sequence to {complex_dir}...")
    subprocess.run(cmd_complex, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("\nRequested test media variants generated successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic test media for ffmpeg-dailies.")
    parser.add_argument("--output", "-o", default="tests/test_data", help="Output directory")
    args = parser.parse_args()
    
    generate_test_media(args.output)
