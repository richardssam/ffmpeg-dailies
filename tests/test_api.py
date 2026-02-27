import pytest
import os
from ffmpeg_dailies import render

def test_render_api_dry_run_resolves_metadata():
    """
    Validates that the `render` function correctly merges explicit metadata 
    and implicitly resolves the filename without opening a subprocess.
    """
    
    # Use the sample config in the root
    config_path = os.path.join(os.path.dirname(__file__), "..", "sample_config.yaml")
    
    cmd = render(
        config_path=config_path,
        input_media="my_sequence.%04d.exr",
        output_media="out.mov",
        metadata={
            "Show Title": "Unit Test Show",
            "Notes": "Checking API Injection"
        },
        dry_run=True
    )
    
    # Convert command list to a single string for easier assertions
    cmd_str = " ".join(cmd)
    
    # Assert the FFmpeg command was built
    assert cmd[0].endswith("ffmpeg")
    assert "-i" in cmd
    assert "out.mov" in cmd
    
    # Assert the metadata was injected into the drawtext filters
    assert "text='Unit Test Show'" in cmd_str
    assert "text='Checking API Injection'" in cmd_str
    
    # Assert implicit filename resolution worked
    assert "text='my_sequence.%04d.exr'" in cmd_str

def test_render_api_dry_run_overrides():
    """
    Validates that explicit API kwargs override the YAML global config.
    """
    config_path = os.path.join(os.path.dirname(__file__), "..", "sample_config.yaml")
    
    cmd = render(
        config_path=config_path,
        input_media="test.%04d.exr",
        output_media="out.mov",
        framerate="60",
        start_number=1001,
        dry_run=True
    )
    
    cmd_str = " ".join(cmd)
    
    # Assert framerate override was passed to FFmpeg input
    assert "-framerate 60" in cmd_str
    
    # Assert the start_number was passed correctly
    assert "-start_number 1001" in cmd_str

def test_render_visual_regression(tmp_path):
    """
    Renders a single frame to a temporary PNG and asserts 
    1:1 pixel fidelity against the checked-in golden reference image.
    """
    try:
        from PIL import Image, ImageChops
    except ImportError:
        pytest.skip("Pillow is not installed, skipping visual test")
        
    config_path = os.path.join(os.path.dirname(__file__), "test_config.yaml")
    golden_frame_path = os.path.join(os.path.dirname(__file__), "golden_frame.png")
    
    test_media = os.environ.get("FFMPEG_DAILIES_TEST_MEDIA")
    if not test_media:
        pytest.skip("Set FFMPEG_DAILIES_TEST_MEDIA env var to run visual regression test")
    
    if not os.path.exists(golden_frame_path):
        pytest.skip("golden_frame.png is missing. Please generate it first.")
        
    out_png = os.path.join(tmp_path, "test_render.png")
    
    # Run a real FFmpeg non-dry process 
    cmd = render(
        config_path=config_path,
        input_media=test_media,
        output_media=out_png,
        start_number=6700,
        target_width=1280,
        target_height=720,
        framerate="24",
        dry_run=True  # We get the command so we can patch it for 1 frame
    )
    
    # We only want to encode a single frame for the test to save time and 
    # guarantee it writes a single PNG instead of an image sequence
    out_idx = cmd.index(out_png)
    cmd.insert(out_idx, "-frames:v")
    cmd.insert(out_idx + 1, "1")
    cmd.insert(out_idx + 2, "-update")
    cmd.insert(out_idx + 3, "1")
    
    import subprocess
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Assert output exists
    assert os.path.exists(out_png)
    
    # Compare pixels using PIL
    img_golden = Image.open(golden_frame_path).convert('RGB')
    img_test = Image.open(out_png).convert('RGB')
    
    # ImageChops.difference returns an image of the absolute difference.
    # If the images are perfectly identical, getbbox() returns None.
    diff = ImageChops.difference(img_golden, img_test)
    assert diff.getbbox() is None, "Visual regression detected: test_render.png does not match golden_frame.png!"
