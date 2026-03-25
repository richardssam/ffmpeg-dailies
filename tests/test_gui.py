import os
import yaml
import pytest
from fastapi.testclient import TestClient

from ffmpeg_dailies.gui.app import app
from ffmpeg_dailies.config import load_config

client = TestClient(app)

@pytest.fixture
def mock_config(tmp_path):
    # Create a dummy config with both established coords and None coords, plus some global blocks to ensure they aren't deleted
    config_content = {
        "globals": {
            "width": 1920,
            "height": 1080
        },
        "output_codecs": {
            "prores": {"vcodec": "prores_ks"}
        },
        "slate": {
            "fields": {
                "Title": "{Show_Name}",
                "Date": {
                    "text": "{Date}",
                    "x": 100,
                    "y": 200,
                    "font_size": 45
                }
            }
        }
    }
    
    config_file = tmp_path / "test_gui_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_content, f)
        
    os.environ["FFMPEG_DAILIES_GUI_CONFIG"] = str(config_file)
    return str(config_file)

def test_api_state(mock_config):
    response = client.get("/api/state")
    assert response.status_code == 200
    data = response.json()
    
    # Check that both fields were parsed successfully
    assert "Title" in data["fields"]
    assert data["fields"]["Title"]["text"] == "{Show_Name}"
    # x/y shouldn't be populated natively by standard parsing if None, but standard models might default to None
    assert data["fields"]["Title"]["x"] is None
    
    assert "Date" in data["fields"]
    assert data["fields"]["Date"]["x"] == 100
    assert data["fields"]["Date"]["font_size"] == 45

def test_api_save(mock_config):
    # Simulate the frontend sending a save payload
    payload = {
        "fields": {
            "Title": {
                "x": 960,
                "y": 540,
                "font_size": 120
            },
            "Date": {
                "x": 150,
                "y": 250
            }
        }
    }
    
    response = client.post("/api/save", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Reload config from disk to verify
    saved_config = load_config(mock_config)
    
    # Check that original global blocks survived
    assert "globals" in saved_config
    assert "output_codecs" in saved_config
    
    # Check updated slate fields
    fields = saved_config["slate"]["fields"]
    
    # Title should have been converted from a string to a dict
    assert isinstance(fields["Title"], dict)
    assert fields["Title"]["x"] == 960
    assert fields["Title"]["y"] == 540
    assert fields["Title"]["font_size"] == 120
    assert fields["Title"]["text"] == "{Show_Name}"  # Text should not have been overwritten
    
    # Date should have updated x/y but kept its original font_size and text
    assert fields["Date"]["x"] == 150
    assert fields["Date"]["y"] == 250
    assert fields["Date"]["font_size"] == 45
