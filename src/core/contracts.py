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
    landmarks: Optional[List[Any]] = None
    frame: Any



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
