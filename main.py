import asyncio
import queue
from src.core.vision_worker import VisionWorker
from src.interface.desktop_interface import DesktopApp
from src.interaction.gesture_engine import GestureEngine

async def main():
    # 1. Initialize communication queue
    vision_queue = queue.Queue(maxsize=10)

    # 2. Initialize and start the Vision Worker thread
    worker = VisionWorker(output_queue=vision_queue)
    worker.start()

    # 3. Initialize the Gesture Engine
    gesture_engine = GestureEngine()

    # 4. Initialize and run the Desktop Application
    app = DesktopApp(input_queue=vision_queue, gesture_engine=gesture_engine)

    try:
        print("🚀 Starting Melior Desktop Application (Pygame)...")
        # Run the Pygame main loop (blocks until app is closed)
        app.run()
    except Exception as e:
        print(f"❌ Error in main loop: {e}")
    finally:
        # 5. Graceful Shutdown
        print("🛑 Initiating shutdown sequence...")
        worker.stop()
        worker.join(timeout=5)
        print("✅ Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
