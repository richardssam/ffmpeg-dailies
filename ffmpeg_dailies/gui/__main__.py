import argparse
import sys
import uvicorn
import os

def main():
    parser = argparse.ArgumentParser(description="FFmpeg Dailies Slate GUI Editor")
    parser.add_argument("--config", required=True, help="Path to the YAML configuration file")
    parser.add_argument("--input", required=False, help="Path to the input media (for accurate PIP preview)")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the local server on")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.config):
        print(f"Error: Config file not found at {args.config}")
        sys.exit(1)
        
    # We pass the config path to the app environment so FastAPI can read it
    os.environ["FFMPEG_DAILIES_GUI_CONFIG"] = os.path.abspath(args.config)
    if args.input:
        os.environ["FFMPEG_DAILIES_GUI_INPUT"] = os.path.abspath(args.input)
    
    print(f"Starting generic FFmpeg Dailies GUI editing {args.config}")
    # Run the uvicorn server
    url = f"http://127.0.0.1:{args.port}"
    print(f"Open {url} in your browser.")
    
    import threading
    import webbrowser
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    
    uvicorn.run("ffmpeg_dailies.gui.app:app", host="127.0.0.1", port=args.port, reload=False)

if __name__ == "__main__":
    main()
