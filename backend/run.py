import os
import uvicorn

if __name__ == "__main__":
    is_dev = os.getenv("ENV", "production") == "development"

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=is_dev,
        workers=1,
        access_log=not is_dev,
    )
