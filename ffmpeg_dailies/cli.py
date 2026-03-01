import argparse
import sys
import os

from . import render


def parse_args():
    parser = argparse.ArgumentParser(description="Create dailies using ffmpeg with OCIO, slate, and burn-ins.")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML configuration file")
    parser.add_argument("--input", "-i", required=True, help="Input media path (quicktime or image sequence %%04d.exr / .png)")
    parser.add_argument("--output", "-o", required=True, help="Output quicktime path")
    parser.add_argument("--framerate", "-r", default=None, help="Input framerate (default: from config or 24)")
    parser.add_argument("--input-width", type=int, default=None, help="Input width (default: from config or 1920)")
    parser.add_argument("--input-height", type=int, default=None, help="Input height (default: from config or 1080)")
    parser.add_argument("--target-width", type=int, default=None, help="Target delivery width (default: from config or 1920)")
    parser.add_argument("--target-height", type=int, default=None, help="Target delivery height (default: from config or 1080)")
    parser.add_argument("--start-number", type=int, help="Start frame for image sequence")
    
    # Allow overriding metadata via CLI
    parser.add_argument("--meta-notes", help="Notes meta")
    parser.add_argument("--meta-vendor", help="Vendor Name meta")
    parser.add_argument("--meta-filename", help="File Name meta")
    parser.add_argument("--meta-show", help="Show Title meta")
    parser.add_argument("--meta-date", help="Date Delivered meta")
    parser.add_argument("--meta-shot", help="Shot meta")
    parser.add_argument("--dry-run", action="store_true", help="Print the command without running it.")

    parser.add_argument("--fit", action="store_true", help="Preserve aspect ratio by padding", default=None)

    return parser.parse_args(), parser

def main():
    args, parser = parse_args()
    
    if not os.path.exists(args.config):
        print(f"Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    metadata = {}
    if args.meta_notes: metadata["Notes"] = args.meta_notes
    if (args.meta_vendor): metadata["Vendor Name"] = args.meta_vendor
    if args.meta_filename: metadata["File Name"] = args.meta_filename
    if args.meta_show: metadata["Show Title"] = args.meta_show
    if (args.meta_date): metadata["Date Delivered"] = args.meta_date
    if (args.meta_shot): metadata["Shot"] = args.meta_shot

    cmd = render(
        config_path=args.config,
        input_media=args.input,
        output_media=args.output,
        metadata=metadata,
        framerate=args.framerate,
        start_number=args.start_number,
        input_width=args.input_width,
        input_height=args.input_height,
        target_width=args.target_width,
        target_height=args.target_height,
        fit=args.fit,
        dry_run=args.dry_run
    )

    if args.dry_run:
        print("Dry run requested. Generated command:")
        print(" ".join(cmd))

if __name__ == "__main__":
    main()
