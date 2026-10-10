import cv2

def test_camera_indices(max_to_test=5):
    print(f"🔍 Scanning for camera devices (testing indices 0 to {max_to_test})...")
    found_indices = []

    for i in range(max_to_test):
        print(f"  Testing index {i}...", end=" ", flush=True)
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            # Try to read a frame to confirm it's actually working
            ret, frame = cap.read()
            if ret:
                print("✅ SUCCESS")
                found_indices.append(i)
            else:
                print("⚠️  OPENED BUT FAILED TO READ FRAME")
            cap.release()
        else:
            print("❌ FAILED")

    print("\n" + "="*30)
    if found_indices:
        print(f"✨ Found working camera(s) at index(es): {found_indices}")
        print(f"👉 Try changing `cv2.VideoCapture(0)` to `cv2.VideoCapture({found_indices[0]})` in your code.")
    else:
        print("💀 No working cameras found.")
        print("Possible causes:")
        print("1. The camera is being used by another application (Zoom, Teams, etc.).")
        print("2. You are in a remote environment (SSH/WSL) without hardware access.")
        print("3. Driver issues or hardware permissions.")
    print("="*30)

if __name__ == "__main__":
    test_camera_indices()
