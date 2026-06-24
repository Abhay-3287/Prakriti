import requests
import os
from pathlib import Path

# Create images directory if it doesn't exist
images_dir = Path("static/images")
images_dir.mkdir(parents=True, exist_ok=True)

# Dictionary of temple images with direct URLs (using different sources)
temple_images = {
    "ram-mandir.jpg": "https://en.wikipedia.org/wiki/Special:FilePath/Ram_Mandir,_Ayodhya.png",
    "kashi-vishwanath.jpg": "https://live.staticflickr.com/65535/52988482978_0f8b98f05f_b.jpg",
    "hampi.jpg": "https://live.staticflickr.com/65535/52915234275_3e1e56b05c_b.jpg",
    "golden-temple.jpg": "https://live.staticflickr.com/65535/52912234563_8c2f8c9e3a_b.jpg",
    "konark-temple.jpg": "https://live.staticflickr.com/65535/52965412834_f5c7d0b9c1_b.jpg",
    "taj-mahal.jpg": "https://live.staticflickr.com/65535/52992187046_7c1f3e8b9d_b.jpg",
    "meenakshi.jpg": "https://live.staticflickr.com/65535/52953284172_0e2d1f6a8c_b.jpg",
    "khajuraho.jpg": "https://live.staticflickr.com/65535/52908126532_5e3d4f0a2b_b.jpg",
}

print("Downloading temple images...")
for filename, url in temple_images.items():
    filepath = images_dir / filename
    if filepath.exists():
        print(f"✓ {filename} already exists")
        continue
    
    try:
        print(f"Downloading {filename}...")
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
            print(f"✓ Downloaded {filename}")
        else:
            print(f"✗ Failed to download {filename} (status: {response.status_code})")
    except Exception as e:
        print(f"✗ Error downloading {filename}: {str(e)}")

print("\nDownload complete!")
