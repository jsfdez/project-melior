import cv2
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
import asyncio

app = FastAPI()

# Initialize Webcam
camera = cv2.VideoCapture(0)

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            # Encode the frame in JPEG format
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            # Yield the frame in a format suitable for MJPEG streaming
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.get('/')
async def index():
    from fastapi.responses import HTMLResponse
    html_content = """
    <html>
        <head>
            <title>Melior Web Camera Viewer</title>
            <style>
                body { font-family: sans-serif; text-align: center; background: #1a1a1a; color: white; }
                img { border: 5px solid #333; border-radius: 8px; max-width: 90%; }
                h1 { margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1>Melior Camera Stream</h1>
            <img src="/video_feed">
            <p>Press Ctrl+C in the terminal to stop the server.</p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get('/video_feed')
async def video_feed():
    return StreamingResponse(generate_frames(), media_type='multipart/x-mixed-replace; boundary=frame')

@app.on_event("shutdown")
def shutdown_event():
    camera.release()

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Web Camera Viewer on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
