#!/usr/bin/env python3
import subprocess
import argparse
import sys
import os

def generate_slate_template(width: int, height: int, steps: int, output_path: str):
    """
    Generates a slate template image featuring SMPTE color bars, a white strip, and a grayscale wedge.
    """
    # The layout is typically:
    # Top ~85% is black (where the text and thumbnail will go)
    # Bottom ~15% is the stripes (bars, white, wedge)
    
    stripes_height_base = max(height // 7, 100)
    stripe_h = (stripes_height_base // 3) // 2
    
    bottom_padding = 100
    top_black_height = height - (stripe_h * 3) - bottom_padding
    
    # We can generate a full properly proportioned SMPTE HD bars image
    # and then crop out the top section (standard bars) and the bottom section (grey wedge/pluge).
    # SMPTE HD bars bottom section is the last 25% (1/4th) of the image.
    # So if we make the SMPTE bars 4x the height of a single stripe, 
    # the top stripe is exactly the top 1/4th, and the wedge is the bottom 1/4th.
    
    smpte_h = stripe_h * 4
    smpte_filter = f"smptehdbars=size={width}x{smpte_h}:rate=1[smpte]"
    
    # 1. Top part of the colorbars
    bars_crop = f"[smpte]crop={width}:{stripe_h}:0:0[bars]"
    
    # 2. White strip
    white_filter = f"color=white:size={width}x{stripe_h}:rate=1[white]"
    
    # 3. Grey wedge (Procedural N-steps)
    # Using geq to calculate step values from 0 to 255. min(trunc((X/W)*steps), steps-1) / (steps-1)
    eq = f"255*min(trunc((X/W)*{steps})\\,{steps}-1)/({steps}-1)"
    wedge_filter = f"color=black:size={width}x{stripe_h}:rate=1,format=rgb24,geq=r='{eq}':g='{eq}':b='{eq}'[wedge]"
    
    # 4. Generate the main top black background
    bg_top_filter = f"color=black:size={width}x{top_black_height}:rate=1[bg_top]"
    
    # 5. Generate the bottom black padding
    bg_bottom_filter = f"color=black:size={width}x{bottom_padding}:rate=1[bg_bottom]"
    
    # Stack them vertically: bg_top, then bars, white, wedge, bg_bottom
    vstack_filter = "[bg_top][bars][white][wedge][bg_bottom]vstack=inputs=5[out]"
    
    full_filter = f"{smpte_filter};{bars_crop};{wedge_filter};{white_filter};{bg_top_filter};{bg_bottom_filter};{vstack_filter}"
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "nullsrc=s=2x2", # dummy input to trigger lavfi
        "-filter_complex", full_filter,
        "-map", "[out]",
        "-frames:v", "1",
        output_path
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully generated slate template at {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating template: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a procedural slate template image with color bars.")
    parser.add_argument("--width", type=int, default=1920, help="Output width")
    parser.add_argument("--height", type=int, default=1080, help="Output height")
    parser.add_argument("--steps", type=int, default=13, help="Number of steps in the grayscale wedge")
    parser.add_argument("--output", "-o", required=True, help="Output file path (e.g. template.exr or template.png)")
    
    args = parser.parse_args()
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    
    generate_slate_template(args.width, args.height, args.steps, args.output)
