from pydantic import BaseModel
from typing import List, Optional, Any

# --- VISION -> INTERACTION ---

class HeadPose(BaseModel):
    pitch: float
    yaw: float
    roll: float

class VisionFrame(BaseModel):
    timestamp: float
    head_pose: HeadPose
    blink: float = 0.0  # mean eyeBlinkLeft/Right score, 0..1
    landmarks: Optional[List[Any]] = None


# --- INTERACTION -> INTERFACE ---

class GestureEvent(BaseModel):
    event_type: str  # "move", "dwell", "nod", "shake"
    target_id: Optional[str] = None
    confidence: float


# --- INTELLIGENCE -> INTERFACE ---

class Suggestion(BaseModel):
    text: str


class LLMSuggestions(BaseModel):
    suggestions: List[Suggestion]
    request_id: str
