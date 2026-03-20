import pytest
import os
from ffmpeg_dailies import render
from ffmpeg_dailies.models import DailiesContext, SlateConfig, SlateField, InputSettings, OutputSettings, OCIOSettings, BurninConfig

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


# -----------------------------------------------------------------------
# Tests for implicit Date Delivered and Shot metadata
# -----------------------------------------------------------------------

def test_implicit_date_delivered_includes_time():
    """
    Validates that Date Delivered is auto-populated with both date and time
    when not present in the metadata dict.
    """
    import datetime
    from ffmpeg_dailies.utils import populate_implicit_metadata

    metadata = populate_implicit_metadata({}, "my_seq.%04d.exr")

    assert "Date Delivered" in metadata
    # Format should be YYYY-MM-DD HH:MM
    val = metadata["Date Delivered"]
    # Verify it matches the format
    datetime.datetime.strptime(val, "%Y-%m-%d %H:%M")
    
    # Time Delivered should NOT be present as a separate field
    assert "Time Delivered" not in metadata


def test_no_implicit_shot_extraction():
    """
    Validates that Shot is NOT automatically extracted from the path anymore.
    """
    from ffmpeg_dailies.utils import populate_implicit_metadata

    metadata = populate_implicit_metadata(
        {},
        "/show/jp4/RAP_090/pix/comp/RAP_090_comp_v74/RAP_090_comp_v74.%04d.exr"
    )
    assert "Shot" not in metadata


def test_explicit_shot_and_vendor_via_metadata():
    """
    Validates that Shot and Vendor Name can be supplied via metadata and resolves.
    """
    from ffmpeg_dailies.utils import populate_implicit_metadata

    metadata = populate_implicit_metadata(
        {"Shot": "RAP_090", "Vendor Name": "My Studio"},
        "my_seq.%04d.exr"
    )
    assert metadata["Shot"] == "RAP_090"
    assert metadata["Vendor Name"] == "My Studio"


def test_frame_counter_not_escaped():
    """
    Validates that the {frame} token resolves to %{n} and is NOT escaped in the CLI.
    """
    config_path = os.path.join(os.path.dirname(__file__), "..", "sample_config.yaml")
    cmd = render(
        config_path=config_path,
        input_media="test.%04d.exr",
        output_media="out.mov",
        dry_run=True
    )
    cmd_str = " ".join(cmd)
    
    # Check for the burn-in drawtext that should have %{n}
    # It used to be \\\\%
    assert "%{n}" in cmd_str
    assert "\\\\%{" not in cmd_str

def test_burnin_font_size_inheritance():
    """
    Validates that burn-ins inherit fontsize from globals.font_size if not specified.
    """
    import yaml
    from ffmpeg_dailies.models import DailiesContext, GlobalsConfig, BurninConfig, SlateConfig, InputSettings, OutputSettings, OCIOSettings
    from ffmpeg_dailies.filtergraph import build_video_filtergraph
    
    # Create a mock context
    ctx = DailiesContext(
        input_settings=InputSettings(path="test.mov", framerate="24", width=1920, height=1080, is_image_sequence=False),
        output_settings=OutputSettings(path="out.mov", target_width=1280, target_height=720),
        ocio_settings=OCIOSettings(),
        slate_config=SlateConfig(fields={}),
        burnin_config=BurninConfig(layout={"top_left": "Test"}),
        metadata={},
        globals_config=GlobalsConfig(font_size=55) # Custom global font size
    )
    
    fg = build_video_filtergraph(ctx)
    
    # The burn-in should have fontsize=55
    assert "fontsize=55" in fg

def test_slate_font_alignment_and_wrapping():
    """
    Validates that slates correctly wrap long text into multi-line drawtext filters
    and apply the requested alignment expressions (e.g. right-align).
    """
    from ffmpeg_dailies.models import DailiesContext, SlateConfig, SlateField, InputSettings, OutputSettings, OCIOSettings
    from ffmpeg_dailies.filtergraph import build_slate_filtergraph
    
    # A long description that should wrap at 300px with 50px font 
    # (heuristic: ~27px per char, 300/27 = ~11 chars per line)
    long_note = "This is a very long note that should definitely wrap."
    
    ctx = DailiesContext(
        input_settings=InputSettings(path="test.mov", framerate="24", width=1920, height=1080, is_image_sequence=False),
        output_settings=OutputSettings(path="out.mov", target_width=1280, target_height=720),
        ocio_settings=OCIOSettings(),
        slate_config=SlateConfig(fields={
            "Notes": SlateField(text=long_note, max_width=300, align="right", y="500")
        }),
        burnin_config=BurninConfig(),
        metadata={}
    )
    
    fg, _ = build_slate_filtergraph(ctx)
    
    # Count how many drawtext filters are in the chain
    # Each one starts with 'drawtext='
    drawtext_count = fg.count("drawtext=")
    
    # Heuristic: ~52 chars. 11 chars per line. Should be at least 4 lines.
    assert drawtext_count >= 4
    
    # Assert alignment expression for right align
    assert "x=w-tw-10" in fg
    
    # Assert centered fallback for other fields if we had them or by checking default logic
    # (Existing default was centered fallback)
    assert "y=500" in fg 
    # Check that Y increments (500 + 50 * 1.2 = 560)
    assert "y=560" in fg

