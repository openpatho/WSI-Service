from typing import List, Optional
import asyncio

from fastapi import Path, Depends, Header
from fastapi.responses import FileResponse, JSONResponse

from fastapi import File, UploadFile
import traceback
import httpx
import json
import os

from pathlib import Path

from .singletons import api_integration

from wsi_service.models.v3.slide import SlideInfo

from wsi_service.custom_models.queries import (
    ImageChannelQuery,
    ImageFormatsQuery,
    ImagePaddingColorQuery,
    ImageQualityQuery,
    PluginQuery,
    ZStackQuery,
    SlideQuery,
)


async def get_authorization_header(authorization: Optional[str] = Header(None)):
    return authorization


def add_routes_annotations(app, settings, slide_manager):
    @app.get(
        "/annotations/native",
        response_class=JSONResponse,
        description="Accepts the main slide image's ID and returns all of the annotations in 'Native' JSON format",
        tags=["Main Routes"],
    )
    async def _(
        slide_id: str = SlideQuery,
        plugin: str = PluginQuery,
        skip_cache: bool = False,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Fetch the annotations in Native format for the specified slide
        """

        print("Checking Access")
        (valid, systemName) = await api_integration.allow_access_slide(
            calling_function="/annotations/native",
            auth_payload=payload,
            slide_id=slide_id,
            manager=slide_manager,
            plugin=plugin,
            slide=None,
        )

        # print("Getting Slide")
        # slide = await slide_manager.get_slide_info(slide_id, slide_info_model=SlideInfo, plugin=plugin)

        print("Getting Anotation filename to check if it exists")
        fileNames = await slide_manager.get_slide_file_paths(slide_id)
        anoPath = Path(fileNames[0]).with_suffix(".anotations.json")

        print("Temporarily over-riding the cache")
        skip_cache = True

        if anoPath.exists() and not skip_cache:
            print("Getting Anotations from cache")
            with open(str(anoPath), "r") as f:
                data = f.read()
            return data
        else:
            print(
                f"Getting Anotations from anotations api - (cache file present: {anoPath.exists()})"
            )
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    # print("Inside With - contacting:")
                    # print(settings.annotation_api)
                    response = await client.post(
                        f"{settings.annotation_api}",
                        json={
                            "slide_id": slide_id,
                            "auth_token": payload,
                            "system_name": systemName,
                        },
                    )
                    # print(f"Response status was: {response.status_code}")
                    # print(f"Response text was a {type(response.json())}")
                    if response.status_code == 200:
                        if response.json() is not None:
                            print(
                                f"Text was {len(response.text)} long, parsed response Json was a {type(response.json())}, {len(response.json())} in 'length'"
                            )
                        json_output = response.text  # Parse the JSON output
                    else:
                        json_output = {}
                        print(
                            f"Anotations API returned a {response.status_code} status and message: {response.text}"
                        )

                try:
                    with open(str(anoPath), "w") as file:
                        file.write(json_output)

                except Exception as e:
                    print(f"File Writing Error for Cache: {e}")
                    print(f"File write location already existed: {anoPath.exists()}")

                    parent = Path(anoPath.parents[0])
                    print(
                        f"Owner UID: {parent.stat().st_uid}, Current UID: {os.getuid()}"
                    )
                    print(
                        f"Group GID: {parent.stat().st_gid}, Current GID: {os.getgid()}"
                    )
                    print(f"Parent directory writable: {os.access(parent, os.W_OK)}")
                    pass
                return json_output
            except Exception as ex:
                print(f"What went wrong: {ex}")
                traceback.print_exc()
                raise ex

    @app.put(
        "/annotations/native",
        responses={
            200: {
                "description": "Successfully updated the annotations from the provided JSON file.",
                "content": {"application/json": {}},
            }
        },
        description="Accepts a JSON file with annotations and updates the annotations for the specified slide.",
        tags=["Main Routes"],
    )
    async def _(
        slide_id: str = SlideQuery,
        plugin: str = PluginQuery,
        file: UploadFile = File(...),
        payload: Optional[str] = Depends(get_authorization_header),
    ):

        # slide = await slide_manager.get_slide_info(slide_id, slide_info_model=SlideInfo, plugin=plugin)
        # await api_integration.allow_access_slide(calling_function="PUT /annotations/native",auth_payload=payload, slide_id=slide_id, manager=slide_manager,
        #                                         plugin=plugin, slide=slide)

        fileNames = await slide_manager.get_slide_file_paths(slide_id)
        anoPath = Path(fileNames[0]).with_suffix(".json")

        try:
            # Open the file directly and save it to disk
            with open(str(anoPath), "wb") as f:
                f.write(file.file.read())  # Write the uploaded file directly to disk

            # Optionally, you could log the size of the file for validation
            bytes_written = file.file.tell()  # Get the size of the file after writing

            # Assuming successful operation
            success = True

            return {
                "status": True,
                "slide_id": slide_id,
                "plugin": plugin,
                "bytes_written": bytes_written,
                "message": "Annotations updated successfully",
            }
        except:
            traceback.print_exc()
            return {
                "status": False,
                "slide_id": slide_id,
                "plugin": plugin,
                "bytes_written": 0,
                "message": "Failed to update annotations",
            }
