import threading
import queue
import time
from src.core.contracts import VisionFrame
from src.vision.head_tracker import HeadTracker

class VisionWorker(threading.Thread):
    """
    A background worker that uses HeadTracker to capture vision data
    and pushes VisionFrame objects into a queue.
    """
    def __init__(self, output_queue: queue.Queue):
        super().__init__()
        self.output_queue = output_queue
        self._stop_event = threading.Event()
        self.daemon = True
        self.tracker = None

    def stop(self):
        """Signal the thread to stop."""
        self._stop_event.set()

    def run(self):
        """The main loop of the vision worker."""
        try:
            print("⚙️  [VisionWorker] Starting HeadTracker...")
            self.tracker = HeadTracker()
            print("✅ [VisionWorker] HeadTracker ready.")
            self._vision_loop()
        except Exception as e:
            print(f"❌ [VisionWorker] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._shutdown()

    def _vision_loop(self):
        print("👁️  [VisionWorker] Vision Loop Started")

        while not self._stop_event.is_set():
            frame, vision_frame = self.tracker.read()

            if vision_frame is None:
                if frame is not None:
                    # Send frame with empty data to keep UI alive
                    from src.core.contracts import HeadPose
                    vision_frame = VisionFrame(
                        timestamp=time.time(),
                        head_pose=HeadPose(pitch=0.0, yaw=0.0, roll=0.0),
                        blink=0.0,
                        frame=frame
                    )
                else:
                    time.sleep(0.01)
                    continue

            try:
                self.output_queue.put_nowait(vision_frame)
            except queue.Full:
                pass

            time.sleep(0.01)

    def _shutdown(self):
        print("🛑 [VisionWorker] Shutting down...")
        if self.tracker:
            self.tracker.close()
        print("✅ [VisionWorker] Shutdown complete.")
