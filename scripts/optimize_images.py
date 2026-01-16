
import os
from PIL import Image

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAMS_DIR = os.path.join(ROOT_DIR, 'assets', 'teams')

MAX_SIZE = (200, 200)

def optimize_images():
    total_saved = 0
    files = [f for f in os.listdir(TEAMS_DIR) if f.lower().endswith('.png')]
    print(f"Optimizing {len(files)} images in {TEAMS_DIR}...")
    
    for filename in files:
        path = os.path.join(TEAMS_DIR, filename)
        try:
            original_size = os.path.getsize(path)
            
            with Image.open(path) as img:
                # Resize if needed
                if img.width > MAX_SIZE[0] or img.height > MAX_SIZE[1]:
                    img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)
                
                # Save optimized
                img.save(path, "PNG", optimize=True, compress_level=9)
            
            new_size = os.path.getsize(path)
            saved = original_size - new_size
            total_saved += saved
            
            # print(f"Optimized {filename}: {original_size/1024:.1f}KB -> {new_size/1024:.1f}KB (-{saved/1024:.1f}KB)")
            
        except Exception as e:
            print(f"Error optimizing {filename}: {e}")

    print(f"Optimization complete.")
    print(f"Total space saved: {total_saved / (1024*1024):.2f} MB")

if __name__ == "__main__":
    optimize_images()
