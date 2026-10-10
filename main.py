import asyncio
import queue
import threading
from src.core.vision_worker import VisionWorker
from src.interface.desktop_interface import DesktopApp

async def main():
    # 1. Initialize communication queue
    vision_queue = queue.Queue(maxsize=10)

    # 2. Initialize and start the Vision Worker thread
    worker = VisionWorker(output_queue=vision_queue)
    worker.start()

    # 3. Initialize and run the Desktop Application
    # We use the Pygame implementation which has its own main loop.
    app = DesktopApp(input_queue=vision_queue)

    try:
        print("🚀 Starting Melior Desktop Application (Pygame)...")
        # Run the Pygame main loop (blocks until app is closed)
        app.run()
    except Exception as e:
        print(f"❌ Error in main loop: {e}")
    finally:
        # 4. Graceful Shutdown
        print("🛑 Initiating shutdown sequence...")
        worker.stop()
        worker.join(timeout=5)
        print("✅ Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
