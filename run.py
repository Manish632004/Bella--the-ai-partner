"""
BELLA — Entry Point
Run with: python run.py
"""

import uvicorn
from bella.core.config import config

if __name__ == "__main__":
    uvicorn.run(
        "bella.app:app",
        host=config.HOST,
        port=config.PORT,
        reload=True,
        log_level="info",
    )
