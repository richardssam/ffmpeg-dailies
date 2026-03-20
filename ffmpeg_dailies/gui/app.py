from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import yaml
from typing import Dict, Any, Optional

import tempfile
import subprocess
from typing import Dict, Any, Optional

from ffmpeg_dailies.config import load_config, parse_slate_config, parse_globals_config, parse_output_codecs, parse_ocio_settings, parse_dynamic_metadata_config
from ffmpeg_dailies.models import DailiesContext, InputSettings, OutputSettings
from ffmpeg_dailies.execute import get_middle_frame_index
from ffmpeg_dailies.filtergraph import build_slate_filtergraph
from ffmpeg_dailies.utils import resolve_input, populate_implicit_metadata

app = FastAPI(title="FFmpeg Dailies Slate Editor")

# Base directory for the GUI module
GUI_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(GUI_DIR, "templates")

class SavePayload(BaseModel):
    fields: Dict[str, Dict[str, Any]]
    thumbnail: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    
def get_config_path() -> str:
    path = os.environ.get("FFMPEG_DAILIES_GUI_CONFIG")
    if not path:
        raise HTTPException(status_code=500, detail="FFMPEG_DAILIES_GUI_CONFIG not set in environment.")
    return path

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serves the main frontend canvas editor."""
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html not found in templates directory.")
        
    with open(index_path, "r") as f:
        return f.read()

@app.get("/api/state")
async def get_state():
    """Returns the parsed slate fields and their current formatting properties."""
    config_path = get_config_path()
    try:
        raw_config = load_config(config_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse config: {e}")
        
    # We don't parse Burnins since they aren't fully supported in the UI yet.
    # But we parse Globals for global_font_size fallbacks.
    glbs = parse_globals_config(raw_config)
    slate_cfg = parse_slate_config(raw_config, glbs.font_size)
    dynamic_cfg = parse_dynamic_metadata_config(raw_config)
    
    # We want to return a serializable JSON payload of the fields
    payload_fields = {}
    for key, field in slate_cfg.fields.items():
        try:
            x_val = int(field.x) if field.x is not None else None
        except ValueError:
            x_val = None
            
        try:
            y_val = int(field.y) if field.y is not None else None
        except ValueError:
            y_val = None
            
        payload_fields[key] = {
            "text": field.text if field.text else f"{{{key}}}",
            "x": x_val,
            "y": y_val,
            "font_size": field.font_size or slate_cfg.global_font_size or 50,
            # Placeholder for future font_choice from UI dropdown
            "font_file": "default",
            "align": field.align if hasattr(field, "align") else "left",
            "max_width": field.max_width if hasattr(field, "max_width") else 0,
            "max_height": field.max_height if hasattr(field, "max_height") else 0,
        }

        
    metadata = raw_config.get("metadata", {}).copy()
    metadata = populate_implicit_metadata(metadata, os.environ.get("FFMPEG_DAILIES_GUI_INPUT", ""), dynamic_cfg)
    
    for meta_key in metadata:
        if meta_key not in payload_fields and meta_key not in ["Notes", "Show Title", "Date Delivered", "Vendor Name"]:
            payload_fields[meta_key] = {
                "text": f"{{{meta_key}}}",
                "x": None,
                "y": None,
                "font_size": slate_cfg.global_font_size or 50,
                "font_file": "default" 
            }
            
    # Hardcode some dummy output bounds (would ideally be dynamic off the active codec config)
    w = 1920
    h = 1080
    
    return {
        "dimensions": {"width": w, "height": h},
        "thumbnail_enabled": slate_cfg.thumbnail_enabled,
        "thumbnail_x": slate_cfg.thumbnail_x,
        "thumbnail_y": slate_cfg.thumbnail_y,
        "thumbnail_width": slate_cfg.thumbnail_width,
        "fields": payload_fields,
        "metadata": metadata
    }

@app.post("/api/save")
async def save_state(payload: SavePayload = Body(...)):
    """Saves updated text layout coordinates and font choices to the active YAML config."""
    config_path = get_config_path()
    try:
        raw_config = load_config(config_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse config: {e}")
        
    slate_block = raw_config.get("slate", {})
    if "fields" not in slate_block:
        slate_block["fields"] = {}
        
    for key, updates in payload.fields.items():
        if key not in slate_block["fields"]:
            # If a field was inexplicably missing, init it from the key so we don't save a blank string
            slate_block["fields"][key] = {"text": updates.get("text", f"{{{key}}}")}
            
        field_cfg = slate_block["fields"][key]
        
        # If the original config had a simple string ("{Show Title}"), we must convert it to a dict first to hold x/y
        if isinstance(field_cfg, str):
            field_cfg = {"text": field_cfg}
            slate_block["fields"][key] = field_cfg
            
        # Apply GUI updates
        if "x" in updates: field_cfg["x"] = updates["x"]
        if "y" in updates: field_cfg["y"] = updates["y"]
        if "font_size" in updates: field_cfg["font_size"] = updates["font_size"]
        if "text" in updates: field_cfg["text"] = updates["text"]
        if "align" in updates: field_cfg["align"] = updates["align"]
        if "max_width" in updates: field_cfg["max_width"] = updates["max_width"]
        if "max_height" in updates: field_cfg["max_height"] = updates["max_height"]
        
    if payload.thumbnail:
        if "x" in payload.thumbnail:
            slate_block["thumbnail_x"] = payload.thumbnail["x"]
        if "y" in payload.thumbnail:
            slate_block["thumbnail_y"] = payload.thumbnail["y"]
        if "width" in payload.thumbnail:
            slate_block["thumbnail_width"] = payload.thumbnail["width"]
        
        # We don't overwrite text to avoid destroying template `{Tokens}` accidentally via the GUI.
        
    raw_config["slate"] = slate_block
    
    if payload.metadata:
        if "metadata" not in raw_config:
            raw_config["metadata"] = {}
            
        # To avoid "baking in" dynamic defaults, we only save metadata if it differs 
        # from what the dynamic default would be for the CURRENT input.
        input_media = os.environ.get("FFMPEG_DAILIES_GUI_INPUT", "")
        dynamic_cfg = parse_dynamic_metadata_config(raw_config)
        
        # We need a clean copy of the ORIGINAL metadata (before implicit population) 
        # to know what was already there vs what we are adding now.
        original_metadata = raw_config.get("metadata", {}).copy()
        
        # Calculate what the defaults WOULD be
        current_defaults = populate_implicit_metadata({}, input_media, dynamic_cfg)
        
        for k, v in payload.metadata.items():
            val_str = str(v)
            # Save if:
            # 1. It was already explicitly in the YAML
            # 2. OR it differs from the current dynamic default
            if k in original_metadata or val_str != current_defaults.get(k):
                raw_config["metadata"][k] = val_str
            else:
                # If it matches the default and wasn't there before, 
                # make sure we don't save it (or remove it if it was accidentally added)
                if k in raw_config["metadata"] and k not in original_metadata:
                    del raw_config["metadata"][k]
    
    try:
        # Note: standard pyyaml will strip comments here.
        with open(config_path, "w") as f:
            yaml.dump(raw_config, f, default_flow_style=False, sort_keys=False)
        return {"status": "success", "message": f"Saved config to {config_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {e}")

@app.post("/api/preview/fast")
async def get_fast_preview():
    """Generates a quick proxy JPG of the slate background plate to use as the browser canvas background."""
    config_path = get_config_path()
    try:
        raw_config = load_config(config_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse config: {e}")
        
    glbs = parse_globals_config(raw_config)
    slate_cfg = parse_slate_config(raw_config, glbs.font_size)
    ffmpeg_bin = glbs.ffmpeg_bin or os.environ.get("FFMPEG_BIN", "ffmpeg")
    
    # Generate a temporary file path for the JPEG
    temp_jpg = os.path.join(tempfile.gettempdir(), "ffmpeg_dailies_fast_preview.jpg")
    
    cmd = [
        ffmpeg_bin, "-y", "-v", "error"
    ]
    
    if slate_cfg.template_image and os.path.exists(slate_cfg.template_image):
        cmd.extend(["-i", slate_cfg.template_image])
        # Just scale the template to output dimensions
        w = glbs.width or 1920
        h = glbs.height or 1080
        cmd.extend(["-vf", f"scale={w}:{h}"])
    else:
        # If no template, generate a solid black background
        w = glbs.width or 1920
        h = glbs.height or 1080
        fps = glbs.framerate or "24"
        cmd.extend(["-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}"])
        
    cmd.extend(["-vframes", "1", "-q:v", "2", temp_jpg])
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return FileResponse(temp_jpg, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"FFmpeg fast preview failed: {e.stderr.decode()}")
        
@app.get("/api/preview/thumb")
async def get_thumb_preview():
    """Extracts a single proxy JPEG frame of the input media to use as an interactive thumbnail on the UI."""
    input_media = os.environ.get("FFMPEG_DAILIES_GUI_INPUT", "")
    if not input_media:
        raise HTTPException(status_code=404, detail="No input media found.")
        
    resolved_input_path, resolved_start, is_image_sequence = resolve_input(input_media)
    mid_frame = get_middle_frame_index(resolved_input_path, is_image_sequence, resolved_start)
    
    config_path = get_config_path()
    try:
        raw_config = load_config(config_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse config: {e}")
        
    glbs = parse_globals_config(raw_config)
    ffmpeg_bin = glbs.ffmpeg_bin or os.environ.get("FFMPEG_BIN", "ffmpeg")
    temp_jpg = os.path.join(tempfile.gettempdir(), "ffmpeg_dailies_thumb.jpg")
    
    cmd = [ffmpeg_bin, "-y", "-v", "error"]
    if is_image_sequence:
        cmd.extend(["-start_number", str(resolved_start)])
    cmd.extend(["-i", resolved_input_path])
    
    cmd.extend(["-vf", f"select='eq(n\\,{mid_frame})',scale=800:-1,setsar=1"])
    cmd.extend(["-vframes", "1", "-q:v", "5", temp_jpg])
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return FileResponse(temp_jpg, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"FFmpeg thumb extraction failed: {e.stderr.decode()}")
        
@app.post("/api/preview/ffmpeg")
async def get_ffmpeg_preview():
    """Generates an accurate 1-frame preview of the slate exactly as it will appear in the final video."""
    config_path = get_config_path()
    try:
        raw_config = load_config(config_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse config: {e}")
        
    # We need to construct a partial DailiesContext just for the slate rendering
    glbs = parse_globals_config(raw_config)
    slate_cfg = parse_slate_config(raw_config, glbs.font_size)
    
    # To run the accurate preview, we need to know the input media path to get the PIP frame.
    # We will look for an environment variable that the runner should pass to the GUI,
    # or just use a dummy if PIP is disabled text-only.
    input_media = os.environ.get("FFMPEG_DAILIES_GUI_INPUT", "")
    
    if slate_cfg.thumbnail_enabled and not input_media:
        # If PIP is enabled but we don't have the input media, the FFmpeg command will fail.
        # So we disable it for the preview if no input is provided.
        slate_cfg.thumbnail_enabled = False
        
    is_image_sequence = False
    resolved_start = 1
    if input_media:
        input_media, resolved_start, is_image_sequence = resolve_input(input_media)
        
    metadata = raw_config.get("metadata", {}).copy()
    dynamic_cfg = parse_dynamic_metadata_config(raw_config)
    metadata = populate_implicit_metadata(metadata, input_media, dynamic_cfg)
        
    # Mock a context for the filtergraph builder
    ctx = DailiesContext(
        input_settings=InputSettings(path=input_media, framerate=glbs.framerate or "24", width=1920, height=1080, is_image_sequence=is_image_sequence, start_number=resolved_start, cropwidth=None, cropheight=None, cropx=None, cropy=None),
        output_settings=OutputSettings(path="dummy.mov", target_width=glbs.width or 1920, target_height=glbs.height or 1080, fit=bool(glbs.fit)),
        ocio_settings=parse_ocio_settings(raw_config),
        burnin_config=None,
        slate_config=slate_cfg,
        globals_config=glbs,
        output_codecs={},
        metadata=metadata
    )
    
    mid_frame = 1
    if input_media and slate_cfg.thumbnail_enabled:
        mid_frame = get_middle_frame_index(input_media, ctx.input_settings.is_image_sequence, 1)

    slate_fg, has_template = build_slate_filtergraph(ctx, mid_frame)
    
    ffmpeg_bin = glbs.ffmpeg_bin or os.environ.get("FFMPEG_BIN", "ffmpeg")
    temp_jpg = os.path.join(tempfile.gettempdir(), "ffmpeg_dailies_accurate_preview.jpg")
    
    cmd = [ffmpeg_bin, "-y", "-v", "error"]
    
    if slate_cfg.thumbnail_enabled and input_media:
        # Input 0: Main media for PIP
        cmd.extend(["-i", input_media])
    else:
        # Dummy input 0 so filtergraph mappings don't break if they expect [0:v] implicitly
        # (Though build_slate_filtergraph expects PIP from [thumb_stream], so we must map it carefully)
        pass

    if has_template and slate_cfg.template_image:
        cmd.extend(["-i", slate_cfg.template_image])
        
    # Our build_slate_filtergraph assumes:
    # If PIP is enabled, it expects a [thumb_stream] to exist.
    # If a template is used, it expects it to be [1:v].
    
    complex_filter = ""
    if slate_cfg.thumbnail_enabled and input_media:
        complex_filter += "[0:v]split=1[thumb_stream];"
    
    complex_filter += slate_fg
    
    cmd.extend(["-filter_complex", complex_filter])
    cmd.extend(["-map", "[slate_out]"])
    cmd.extend(["-vframes", "1", "-vcodec", "mjpeg", "-q:v", "2", temp_jpg])
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return FileResponse(temp_jpg, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"FFmpeg accurate preview failed: {e.stderr.decode()}")

