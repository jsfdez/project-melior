import pygame
import queue
import cv2
import numpy as np
from src.core.contracts import VisionFrame

class DesktopApp:
    def __init__(self, input_queue: queue.Queue, width=800, height=600):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Melior - Desktop Vision Interface (Pygame)")

        self.input_queue = input_queue
        self.clock = pygame.time.Clock()
        self.running = True
        self.font = pygame.font.SysFont("Arial", 18)
        self.status_text = "Initializing..."
        self.log_messages = []

    def run(self):
        """Main Pygame loop."""
        while self.running:
            # 1. Handle Events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
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

        self._cleanup()

    def _update_state(self, vision_frame: VisionFrame):
        """Updates the internal state with data from the VisionFrame."""
        self.current_frame = vision_frame.frame
        self.status_text = f"Status: Active | Time: {vision_frame.timestamp:.2f}"

        if vision_frame.landmarks:
            self._log_message("Detected landmarks.")

    def _log_message(self, message: str):
        """Adds a message to the log."""
        timestamp = pygame.time.get_ticks() // 1000
        self.log_messages.append(f"[{timestamp}s] {message}")
        if len(self.log_messages) > 5:
            self.log_messages.pop(0)

    def _render(self):
        """Renders the screen."""
        self.screen.fill((26, 26, 26)) # Dark background

        # 1. Draw Video Frame
        if hasattr(self, 'current_frame') and self.current_frame is not None:
            frame = self.current_frame
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Create a surface from the frame
            # We need to handle resizing to fit our window
            h, w, _ = frame_rgb.shape
            target_aspect = w / h
            window_aspect = self.width / self.height

            if target_aspect > window_aspect:
                # Frame is wider than window
                new_w = self.width
                new_h = int(self.width / target_aspect)
            else:
                # Frame is taller than window
                new_h = self.height
                new_w = int(self.height * target_aspect)

            # Resize frame using pygame (or numpy/cv2 before converting)
            # Using cv2 for resize is often faster/better quality
            resized_frame = cv2.resize(frame_rgb, (new_w, new_h))

            # Convert to pygame surface
            # Pygame expects (width, height) and (R, G, B)
            # Note: numpy array is (H, W, C), pygame needs it as (W, H, C)
            surface = pygame.surfarray.make_surface(resized_frame.transpose(1, 0, 2))

            # Center the surface
            x_offset = (self.width - new_w) // 2
            y_offset = (self.height - new_h) // 2
            self.screen.blit(surface, (x_offset, y_offset))

        # 2. Draw Status
        status_surf = self.font.render(self.status_text, True, (255, 255, 255))
        self.screen.blit(status_surf, (10, self.height - 60))

        # 3. Draw Logs
        for i, msg in enumerate(self.log_messages):
            log_surf = self.font.render(msg, True, (170, 170, 170))
            self.screen.blit(log_surf, (10, self.height - 35 + (i * 15)))

        pygame.display.flip()

    def _cleanup(self):
        """Cleans up pygame resources."""
        pygame.quit()
