#!/usr/bin/env python3

"""
Freight API - FastAPI wrapper for Freight NFS Migration Suite
Minimal web API that serves overview data as JSON
"""

import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

# Add the freight package to path
sys.path.insert(0, str(Path(__file__).parent))

from freight.orchestrator import FreightOrchestrator

app = FastAPI(title="Freight API", description="NFS Migration Suite API", version="1.0.0")

@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {"message": "Freight NFS Migration Suite API", "version": "1.0.0"}

@app.get("/overview/{migration_root:path}")
@app.get("/overview")
async def get_overview(migration_root: Optional[str] = None):
    """
    Get overview data for a migration root directory.
    
    Args:
        migration_root: Path to migration root directory (optional, uses global config if not provided)
    
    Returns:
        JSON with overview statistics and directory data
    """
    try:
        # Initialize orchestrator
        orchestrator = FreightOrchestrator(migration_root)
        
        # Ensure global config exists
        orchestrator.ensure_global_config(str(orchestrator.migration_root))
        
        # Scan directories and get overview data
        orchestrator.scan_directories()
        overview_data = orchestrator.get_overview_data()
        
        return JSONResponse(content=overview_data)
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        if "No migration root specified" in str(e):
            raise HTTPException(
                status_code=400, 
                detail="No migration root found in global config. Please run 'freight.py init' first or specify a migration root explicitly."
            )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)