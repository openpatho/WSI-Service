from fastapi import Path, Depends, Header
from fastapi.responses import JSONResponse

from .singletons import api_integration

def add_routes_annotations(app, settings, slide_manager):
    @app.get(
        "/annotations/native", 
        response_class=FileResponse, 
        responses={
            200: {
                "description": "A JSON file containing the annotations.",
                "content": {"application/json": {}}
            }
        },
        tags=["Main Routes"]
    )
    async def _(slide_id: str = SlideQuery, payload: Optional[str] = Depends(get_authorization_header)):
        """
        Get the path to the file on the server for a slide, given its ID
        """
        path = await slide_manager.get_slide_file_paths(slide_id)