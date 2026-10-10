import pygame
import queue
import cv2
import time
import numpy as np
from src.core.contracts import VisionFrame, GestureEvent

class DesktopApp:
    def __init__(self, input_queue: queue.Queue, gesture_engine=None):
        print("DEBUG: Initializing DesktopApp...")
        pygame.init()
        self.input_queue = input_queue
        self.gesture_engine = gesture_engine
        self.width = 800
        self.height = 600
        print(f"DEBUG: Attempting set_mode({self.width}, {self.height})...")
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Melior - Desktop Vision Interface (Pygame)")
        print("DEBUG: set_mode successful.")

        self.clock = pygame.time.Clock()
        self.running = True
        self.font = pygame.font.SysFont("Arial", 18)
        self.status_text = "Initializing..."
        self.log_messages = []
        self.current_frame = None

    def run(self):
        """Main Pygame loop."""
        print(f"DEBUG: Starting run() loop. self.running={self.running}")
        while self.running:
            # 1. Handle Events
            events = pygame.event.get()
            if events:
                print(f"DEBUG: Events received: {[e.type for e in events]}")
            for event in events:
                if event.type == pygame.QUIT:
                    print("DEBUG: QUIT event received")
                    self.running = False

            # 2. Process Queue
            try:
                # Get the latest frame, discarding older ones to avoid lag
                latest_frame = None
                while not self.input_queue.empty():
                    latest_frame = self.input_queue.get_nowait()

                if latest_frame:
                    self._update_state(latest_frame)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"❌ [DesktopApp] Error processing queue: {e}")

            # 3. Render
            self._render()

            # 4. Cap Frame Rate
            self.clock.tick(30)

        print(f"DEBUG: Loop exited. self.running={self.running}")
        self._cleanup()

    def _update_state(self, vision_frame: VisionFrame):
        """Updates the internal state with data from the VisionFrame."""
        self.current_frame = vision_frame.frame
        self.status_text = f"Status: Active | Time: {vision_frame.timestamp:.2f}"

        # Process gestures if engine is provided
        if self.gesture_engine:
            gestures = self.gesture_engine.update(vision_frame)
            for gesture in gestures:
                self._log_message(f"Gesture: {gesture.event_type} ({gesture.target_id or ''}) conf: {gesture.confidence:.2f}")

    def _log_message(self, message: str):
        """Adds a message to the log."""
        timestamp = time.strftime('%H:%M:%S')
        self.log_messages.append(f"[{timestamp}] {message}")
        if len(self.log_messages) > 5:
            self.log_messages.pop(0)

    def _render(self):
        """Renders the screen."""
        self.screen.fill((26, 26, 26)) # Dark background

        # 1. Draw Video Frame
        if self.current_frame is not None:
            frame = self.current_frame
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Resize frame to fit the window while maintaining aspect ratio
            h, w, _ = frame_rgb.shape
            target_aspect = w / h
            window_aspect = self.width / (self.height - 120) # Leave space for status/logs

            if target_aspect > window_aspect:
                new_w = self.width
                new_h = int(self.width / target_aspect)
            else:
                new_h = self.height - 120
                new_w = int((self.height - 120) * target_aspect)

            # Use cv2 for high quality resize
            resized_frame = cv2.resize(frame_rgb, (new_w, new_h))

            # Convert to pygame surface
            # Note: Pygame expects (width, height) and (R, G, B)
            # numpy array is (H, W, C), so we transpose to (W, H, C)
            surface = pygame.surfarray.make_surface(resized_frame.transpose(1, 0, 2))

            # Center the surface
            x_offset = (self.width - new_w) // 2
            y_offset = (self.height - 120 - new_h) // 2
            self.screen.blit(surface, (x_offset, y_offset))

        # 2. Draw Status
        status_surf = self.font.render(self.status_text, True, (255, 255, 255))
        self.screen.blit(status_surf, (10, self.height - 80))

        # 3. Draw Logs
        for i, msg in enumerate(self.log_messages):
            log_surf = self.font.render(msg, True, (170, 170, 170))
            self.screen.blit(log_surf, (10, self.height - 55 + (i * 18)))

        pygame.display.flip()

    def _cleanup(self):
        """Cleans up pygame resources."""
        pygame.quit()
