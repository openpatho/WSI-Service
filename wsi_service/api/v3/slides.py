from typing import List, Optional
import asyncio

from fastapi import Path, Depends, Header
from fastapi.responses import StreamingResponse
from PIL import Image
from zipfly import ZipFly

from wsi_service.custom_models.queries import (
    ImageChannelQuery,
    ImageFormatsQuery,
    ImagePaddingColorQuery,
    ImageQualityQuery,
    PluginQuery,
    ZStackQuery,
    IdQuery,
    SlideQuery,
)
from wsi_service.custom_models.responses import ImageRegionResponse, ImageResponses
from wsi_service.models.v3.slide import SlideInfo
from wsi_service.utils.app_utils import (
    make_response,
    validate_hex_color_string,
    validate_image_channels,
    validate_image_level,
    validate_image_request,
    validate_image_size,
    validate_image_z,
)
from wsi_service.custom_models.batch_queries import (
    IdListQuery,
    TileLevelListQuery,
    TileXListQuery,
    TileYListQuery,
    SlideListQuery,
)
from wsi_service.utils.app_batch_utils import (
    batch_safe_make_response,
    batch_safe_get_region,
    batch_safe_get_tile,
    safe_get_slide,
    safe_get_slide_for_query,
    safe_get_slide_info,
)
from wsi_service.utils.download_utils import (
    expand_folders,
    get_zipfly_paths,
    remove_folders,
)
from wsi_service.utils.image_utils import (
    check_complete_region_overlap,
    check_complete_tile_overlap,
    get_extended_region,
    get_extended_tile,
)
from .singletons import api_integration

try:
    from wsi_service.utils.cloudwrappers.redis_openpatho import RedisLogger
except:
    from utils.cloudwrappers.redis_openpatho import RedisLogger

redislogger = RedisLogger()


def log_slide_access(slide_id):
    log_data = {"slide_id": slide_id}
    redislogger.add_slide_access_log(log_data)


async def get_authorization_header(authorization: Optional[str] = Header(None)):
    return authorization


def add_routes_slides(app, settings, slide_manager):
    @app.get("/slides/info", response_model=SlideInfo, tags=["Main Routes"])
    async def _(
        slide_id=IdQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get metadata information for a slide given its ID
        """
        slide = await slide_manager.get_slide_info(
            slide_id, slide_info_model=SlideInfo, plugin=plugin
        )
        await api_integration.allow_access_slide(
            calling_function="/slides/info",
            auth_payload=payload,
            slide_id=slide_id,
            manager=slide_manager,
            plugin=plugin,
            slide=slide,
        )
        log_slide_access(slide_id)
        return slide

    @app.get("/slides/filepath", response_model=List[str], tags=["Main Routes"])
    async def _(
        slide_id: str = IdQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get the path to the file on the server for a slide, given its ID
        """
        path = await slide_manager.get_slide_file_paths(slide_id)
        log_slide_access(slide_id)
        return path

    @app.get(
        "/slides/thumbnail/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id=IdQuery,
        max_x: int = Path(
            examples=[100],
            ge=1,
            le=settings.max_thumbnail_size,
            description="Maximum width of thumbnail",
        ),
        max_y: int = Path(
            examples=[100],
            ge=1,
            le=settings.max_thumbnail_size,
            description="Maximum height of thumbnail",
        ),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get slide thumbnail image  given its ID.
        You additionally need to set a maximum width and height for the thumbnail.
        Images will be scaled to match these requirements while keeping the aspect ratio.

        Optionally, the image format and its quality (e.g. for jpeg) can be selected.
        Formats include jpeg, png, tiff, bmp, gif.
        When tiff is specified as output format the raw data of the image is returned.
        """
        validate_image_request(image_format, image_quality)
        await api_integration.allow_access_slide(
            calling_function=f"/slides/thumbnail/max_size/{max_x}/{max_y}",
            auth_payload=payload,
            slide_id=slide_id,
            manager=slide_manager,
            plugin=plugin,
        )
        slide = await slide_manager.get_slide(slide_id, plugin=plugin)
        thumbnail = await slide.get_thumbnail(max_x, max_y)
        log_slide_access(slide_id)
        return make_response(slide, thumbnail, image_format, image_quality)

    @app.get(
        "/slides/label/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id=IdQuery,
        max_x: int = Path(examples=[100], description="Maximum width of label image"),
        max_y: int = Path(examples=[100], description="Maximum height of label image"),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get the label image of a slide given its ID.
        You additionally need to set a maximum width and height for the label image.
        Images will be scaled to match these requirements while keeping the aspect ratio.

        Optionally, the image format and its quality (e.g. for jpeg) can be selected.
        Formats include jpeg, png, tiff, bmp, gif.
        When tiff is specified as output format the raw data of the image is returned.
        """
        validate_image_request(image_format, image_quality)
        await api_integration.allow_access_slide(
            calling_function=f"/slides/label/max_size/{max_x}/{max_y}",
            auth_payload=payload,
            slide_id=slide_id,
            manager=slide_manager,
            plugin=plugin,
        )
        slide = await slide_manager.get_slide(slide_id, plugin=plugin)
        label = await slide.get_label()
        label.thumbnail((max_x, max_y), Image.Resampling.LANCZOS)
        log_slide_access(slide_id)
        return make_response(slide, label, image_format, image_quality)

    @app.get(
        "/slides/macro/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id=IdQuery,
        max_x: int = Path(examples=[100], description="Maximum width of macro image"),
        max_y: int = Path(examples=[100], description="Maximum height of macro image"),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get the macro image of a slide given its ID.
        You additionally need to set a maximum width and height for the macro image.
        Images will be scaled to match these requirements while keeping the aspect ratio.

        Optionally, the image format and its quality (e.g. for jpeg) can be selected.
        Formats include jpeg, png, tiff, bmp, gif.
        When tiff is specified as output format the raw data of the image is returned.
        """
        validate_image_request(image_format, image_quality)
        await api_integration.allow_access_slide(
            calling_function=f"/slides/macro/max_size/{max_x}/{max_y}",
            auth_payload=payload,
            slide_id=slide_id,
            manager=slide_manager,
            plugin=plugin,
        )
        slide = await slide_manager.get_slide(slide_id, plugin=plugin)
        macro = await slide.get_macro()
        macro.thumbnail((max_x, max_y), Image.Resampling.LANCZOS)
        log_slide_access(slide_id)
        return make_response(slide, macro, image_format, image_quality)

    @app.get(
        "/slides/region/level/{level}/start/{start_x}/{start_y}/size/{size_x}/{size_y}",
        responses=ImageRegionResponse,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id=IdQuery,
        level: int = Path(ge=0, examples=[0], description="Pyramid level of region"),
        start_x: int = Path(
            examples=[0],
            description="x component of start coordinate of requested region",
        ),
        start_y: int = Path(
            examples=[0],
            description="y component of start coordinate of requested region",
        ),
        size_x: int = Path(
            gt=0, examples=[1024], description="Width of requested region"
        ),
        size_y: int = Path(
            gt=0, examples=[1024], description="Height of requested region"
        ),
        image_channels: List[int] = ImageChannelQuery,
        z: int = ZStackQuery,
        padding_color: str = ImagePaddingColorQuery,
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get a region of a slide given its ID and by providing the following parameters:

        * `level` - Pyramid level of the region. Level 0 is highest (original) resolution.
        The available levels depend on the image.

        * `start_x`, `start_y` - Start coordinates of the requested region.
        Coordinates are given with respect to the requested level.
        Coordinates define the upper left corner of the region with respect to the image origin
        (0, 0) at the upper left corner of the image.

        * `size_x`, `size_y` - Width and height of requested region.
        Size needs to be given with respect to the requested level.

        There are a number of addtional query parameters:

        * `image_channels` - Single channels (or multiple channels) can be retrieved through the optional parameter
        image_channels as an integer array referencing the channel IDs.
        This is paricularly important for images with abitrary image channels and channels with a higher
        color depth than 8bit (e.g. fluorescence images).
        The channel composition of the image can be obtained through the slide info endpoint,
        where the dedicated channels are listed along with its color, name and bitness.
        By default all channels are returned.

        * `z` - The region endpoint also offers the selection of a layer in a Z-Stack by setting the index z.
        Default is z=0.

        * `padding_color` - Background color as 24bit-hex-string with leading #,
        that is used when image region contains whitespace when out of image extent. Default is white.
        Only works for 8-bit RGB slides, otherwise the background color is black.

        * `image_format` - The image format can be selected. Formats include jpeg, png, tiff, bmp, gif.
        When tiff is specified as output format the raw data of the image is returned.
        Multi-channel images can also be represented as RGB-images (mostly for displaying reasons in the viewer).
        Note that the mapping of all color channels to RGB values is currently restricted to the first three channels.
        Default is jpeg.

        * `image_quality` - The image quality can be set for specific formats,
        e.g. for the jpeg format a value between 0 and 100 can be selected. Default is 90.
        """
        vp_color = validate_hex_color_string(padding_color)
        validate_image_request(image_format, image_quality)
        validate_image_size(size_x, size_y)
        log_slide_access(slide_id)
        await api_integration.allow_access_slide(
            calling_function=f"/slides/region/level/{level}/start/{start_x}/{start_y}/size/{size_x}/{size_y}",
            auth_payload=payload,
            slide_id=slide_id,
            manager=slide_manager,
            plugin=plugin,
        )
        slide = await slide_manager.get_slide(slide_id, plugin=plugin)
        slide_info = await slide.get_info()
        validate_image_level(slide_info, level)
        validate_image_z(slide_info, z)
        validate_image_channels(slide_info, image_channels)
        if check_complete_region_overlap(
            slide_info, level, start_x, start_y, size_x, size_y
        ):
            image_region = await slide.get_region(
                level, start_x, start_y, size_x, size_y, padding_color=vp_color, z=z
            )
        else:
            image_region = await get_extended_region(
                slide.get_region,
                slide_info,
                level,
                start_x,
                start_y,
                size_x,
                size_y,
                padding_color=vp_color,
                z=z,
            )

        log_slide_access(slide_id)
        return make_response(
            slide, image_region, image_format, image_quality, image_channels
        )

    @app.get(
        "/slides/tile/level/{level}/tile/{tile_x}/{tile_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id=IdQuery,
        level: int = Path(ge=0, examples=[0], description="Pyramid level of region"),
        tile_x: int = Path(
            examples=[0], description="Request the tile_x-th tile in x dimension"
        ),
        tile_y: int = Path(
            examples=[0], description="Request the tile_y-th tile in y dimension"
        ),
        image_channels: List[int] = ImageChannelQuery,
        z: int = ZStackQuery,
        padding_color: str = ImagePaddingColorQuery,
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get a tile of a slide given its ID and by providing the following parameters:

        * `level` - Pyramid level of the tile. Level 0 is highest (original) resolution.
        The available levels depend on the image.

        * `tile_x`, `tile_y` - Coordinates are given with respect to tiles,
        i.e. tile coordinate n is the n-th tile in the respective dimension.
        Coordinates are also given with respect to the requested level.
        Coordinates (0,0) select the tile at the upper left corner of the image.

        There are a number of addtional query parameters:

        * `image_channels` - Single channels (or multiple channels) can be retrieved through
        the optional parameter image_channels as an integer array referencing the channel IDs.
        This is paricularly important for images with abitrary image channels and channels
        with a higher color depth than 8bit (e.g. fluorescence images).
        The channel composition of the image can be obtained through the slide info endpoint,
        where the dedicated channels are listed along with its color, name and bitness.
        By default all channels are returned.

        * `z` - The region endpoint also offers the selection of a layer in a Z-Stack by setting the index z.
        Default is z=0.

        * `padding_color` - Background color as 24bit-hex-string with leading #,
        that is used when image tile contains whitespace when out of image extent. Default is white.
        Only works for 8-bit RGB slides, otherwise the background color is black.

        * `image_format` - The image format can be selected. Formats include jpeg, png, tiff, bmp, gif.
        When tiff is specified as output format the raw data of the image is returned.
        Multi-channel images can also be represented as RGB-images (mostly for displaying reasons in the viewer).
        Note that the mapping of all color channels to RGB values is currently restricted to the first three channels.
        Default is jpeg.

        * `image_quality` - The image quality can be set for specific formats,
        e.g. for the jpeg format a value between 0 and 100 can be selected. Default is 90.
        It is ignored if raw jpeg tiles are available through a WSI service plugin.
        """
        vp_color = validate_hex_color_string(padding_color)
        validate_image_request(image_format, image_quality)
        await api_integration.allow_access_slide(
            calling_function=f"/slides/tile/level/{level}/tile/{tile_x}/{tile_y}",
            auth_payload=payload,
            slide_id=slide_id,
            manager=slide_manager,
            plugin=plugin,
        )
        slide = await slide_manager.get_slide(slide_id, plugin=plugin)
        slide_info = await slide.get_info()
        validate_image_level(slide_info, level)
        validate_image_z(slide_info, z)
        validate_image_channels(slide_info, image_channels)
        if check_complete_tile_overlap(slide_info, level, tile_x, tile_y):
            image_tile = await slide.get_tile(
                level, tile_x, tile_y, padding_color=vp_color, z=z
            )
        else:
            image_tile = await get_extended_tile(
                slide.get_tile,
                slide_info,
                level,
                tile_x,
                tile_y,
                padding_color=vp_color,
                z=z,
            )
        log_slide_access(slide_id)
        return make_response(
            slide, image_tile, image_format, image_quality, image_channels
        )

    @app.get("/slides/download", tags=["Main Routes"])
    async def _(
        slide_id=IdQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Download raw slide data as zip
        """
        await api_integration.allow_access_slide(
            calling_function="/slides/download",
            auth_payload=payload,
            slide_id=slide_id,
            manager=slide_manager,
            plugin=plugin,
        )
        paths = await slide_manager.get_slide_file_paths(slide_id)
        # Paths contain file paths that are stored in the storage mapper.
        # This sometimes does not include all files that are associated
        # with a slide, but only a folder, e.g. DICOM. These folders are
        # expanded to include the files they contain, and then removed.
        paths = remove_folders(expand_folders(paths))
        zf = ZipFly(paths=get_zipfly_paths(paths), chunksize="1_000_000")
        log_slide_access(slide_id)
        return StreamingResponse(
            zf.generator(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment;filename={slide_id}.zip",
            },
        )

    ##
    # NEW API ALLOWING BATCH ACCESS
    ##
    @app.get("/files/info", response_model=List[SlideInfo], tags=["Main Routes"])
    async def info(
        paths: str = IdListQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get metadata information for a slide set (see description above sister function)
        """
        print("In the newer `info` code")
        slide_ids = paths.split(",")
        print(f"slide_ids are: {slide_ids}")
        requests = map(
            lambda sid: slide_manager.get_slide_info(
                sid, slide_info_model=SlideInfo, plugin=plugin
            ),
            slide_ids,
        )
        slide_list = await asyncio.gather(*requests)
        print("run map & gather")
        try:
            requests = [
                api_integration.allow_access_slide(
                    calling_function="/files/info",
                    auth_payload=payload,
                    slide_id=slide,
                    manager=slide_manager,
                    plugin=plugin,
                    slide=slide,
                )
                for slide in slide_ids
            ]
        except Exception as e:
            print(f"Auth Failed: {e}")
            raise e

        await asyncio.gather(*requests)
        print("finished the auth and gather")
        _ = [log_slide_access(slide) for slide in slide_ids]
        print("finished logging access")
        return slide_list

    @app.get(
        "/files/thumbnail/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def thumbnail(
        paths: str = IdListQuery,
        max_x: int = Path(
            example=100,
            ge=1,
            le=settings.max_thumbnail_size,
            description="Maximum width of thumbnail",
        ),
        max_y: int = Path(
            example=100,
            ge=1,
            le=settings.max_thumbnail_size,
            description="Maximum height of thumbnail",
        ),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get slide SET thumbnails image  given its ID. (see description above sister function)
        """
        slide_ids = paths.split(",")
        requests = [
            api_integration.allow_access_slide(
                calling_function=f"/batch/thumbnail/max_size/{max_x}/{max_y}",
                auth_payload=payload,
                slide_id=sid,
                manager=slide_manager,
                plugin=plugin,
            )
            for sid in slide_ids
        ]
        await asyncio.gather(*requests)

        validate_image_request(image_format, image_quality)
        requests = map(
            lambda sid: safe_get_slide(slide_manager, sid, plugin=plugin), slide_ids
        )
        slides = await asyncio.gather(*requests)

        requests = map(lambda slide: slide.get_thumbnail(max_x, max_y), slides)
        thumbnails = await asyncio.gather(*requests)
        _ = [log_slide_access(slide) for slide in slide_ids]
        return batch_safe_make_response(slides, thumbnails, image_format, image_quality)

    @app.get(
        "/files/label/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def label(
        paths: str = IdListQuery,
        max_x: int = Path(example=100, description="Maximum width of label image"),
        max_y: int = Path(example=100, description="Maximum height of label image"),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get the label image of a slide set given path(s). (see description above sister function)
        """
        slide_ids = paths.split(",")
        requests = [
            api_integration.allow_access_slide(
                calling_function=f"/batch/label/max_size/{max_x}/{max_y}",
                auth_payload=payload,
                slide_id=sid,
                manager=slide_manager,
                plugin=plugin,
            )
            for sid in slide_ids
        ]
        await asyncio.gather(*requests)

        validate_image_request(image_format, image_quality)
        requests = map(
            lambda sid: safe_get_slide(slide_manager, sid, plugin=plugin), slide_ids
        )
        slides = await asyncio.gather(*requests)

        requests = map(lambda slide: slide.get_label(), slides)
        labels = await asyncio.gather(*requests)
        map(lambda l: l.thumbnail((max_x, max_y), Image.ANTIALIAS), labels)
        _ = [log_slide_access(slide) for slide in slide_ids]
        return batch_safe_make_response(slides, labels, image_format, image_quality)

    @app.get(
        "/files/macro/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def macro(
        paths: str = IdListQuery,
        max_x: int = Path(example=100, description="Maximum width of macro image"),
        max_y: int = Path(example=100, description="Maximum height of macro image"),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get the macro image of a slide set given path(s). (see description above sister function)
        """
        slide_ids = paths.split(",")
        requests = [
            api_integration.allow_access_slide(
                calling_function=f"/batch/macro/max_size/{max_x}/{max_y}",
                auth_payload=payload,
                slide_id=sid,
                manager=slide_manager,
                plugin=plugin,
            )
            for sid in slide_ids
        ]
        await asyncio.gather(*requests)

        validate_image_request(image_format, image_quality)
        requests = map(
            lambda sid: safe_get_slide(slide_manager, sid, plugin=plugin), slide_ids
        )
        slides = await asyncio.gather(*requests)

        requests = map(lambda slide: slide.get_macro(), slides)
        macros = await asyncio.gather(*requests)
        map(lambda m: m.thumbnail((max_x, max_y), Image.ANTIALIAS), macros)
        _ = [log_slide_access(slide) for slide in slide_ids]
        return batch_safe_make_response(slides, macros, image_format, image_quality)

    @app.get(
        "/files/tile/level/{level}/tile/{tile_x}/{tile_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def tile(
        paths: str = IdListQuery,
        level: int = Path(ge=0, example=0, description="Pyramid level of region"),
        tile_x: int = Path(
            example=0, description="Request the tile_x-th tile in x dimension"
        ),
        tile_y: int = Path(
            example=0, description="Request the tile_y-th tile in y dimension"
        ),
        image_channels: List[int] = ImageChannelQuery,
        z: int = ZStackQuery,
        padding_color: str = ImagePaddingColorQuery,
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get a tile of a slide given its path (see description above sister function)
        """
        slide_ids = paths.split(",")
        requests = [
            api_integration.allow_access_slide(
                calling_function=f"/batch/tile/level/{level}/tile/{tile_x}/{tile_y}",
                auth_payload=payload,
                slide_id=sid,
                manager=slide_manager,
                plugin=plugin,
            )
            for sid in slide_ids
        ]
        await asyncio.gather(*requests)

        vp_color = validate_hex_color_string(padding_color)
        validate_image_request(image_format, image_quality)

        requests = map(
            lambda sid: safe_get_slide(slide_manager, sid, plugin=plugin), slide_ids
        )
        slides = await asyncio.gather(*requests)

        requests = map(safe_get_slide_info, slides)
        slide_infos = await asyncio.gather(*requests)
        requests = map(
            lambda i: batch_safe_get_tile(
                slides[i],
                slide_infos[i],
                level,
                tile_x,
                tile_y,
                image_channels,
                vp_color,
                z,
            ),
            range(slides.__len__()),
        )
        regions = await asyncio.gather(*requests)
        _ = [log_slide_access(slide) for slide in slide_ids]
        return batch_safe_make_response(
            slides, regions, image_format, image_quality, image_channels
        )

    # To allow for diverse regions etc..
    @app.get(
        "/files/batch/",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def batch(
        paths: str = IdListQuery,
        levels: str = TileLevelListQuery,
        xs: str = TileXListQuery,
        ys: str = TileYListQuery,
        image_channels: List[int] = ImageChannelQuery,
        z: int = ZStackQuery,  # TODO also?
        padding_color: str = ImagePaddingColorQuery,
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        """
        Get a tile of a slide given its path (see description above sister function)
        """
        slide_ids = paths.split(",")
        requests = [
            api_integration.allow_access_slide(
                calling_function="/batch/arbitrary/",
                auth_payload=payload,
                slide_id=sid,
                manager=slide_manager,
                plugin=plugin,
            )
            for sid in slide_ids
        ]
        await asyncio.gather(*requests)

        vp_color = validate_hex_color_string(padding_color)
        validate_image_request(image_format, image_quality)
        requests = map(
            lambda sid: safe_get_slide(slide_manager, sid, plugin=plugin), slide_ids
        )
        slides = await asyncio.gather(*requests)

        requests = map(safe_get_slide_info, slides)
        slide_infos = await asyncio.gather(*requests)

        xs = [int(x) for x in xs.split(",")]
        ys = [int(x) for x in ys.split(",")]
        levels = [int(x) for x in levels.split(",")]
        requests = map(
            lambda i: batch_safe_get_tile(
                slides[i],
                slide_infos[i],
                levels[i],
                xs[i],
                ys[i],
                image_channels,
                vp_color,
                z,
            ),
            range(slides.__len__()),
        )

        regions = await asyncio.gather(*requests)
        return batch_safe_make_response(
            slides, regions, image_format, image_quality, image_channels
        )

    #############################################
    # OLD ENDPOINTS FOR BACKWARDS COMPATIBILITY #
    #############################################
    @app.get("/batch/info", response_model=List[SlideInfo], tags=["Main Routes"])
    async def _(
        slides: str = SlideListQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        print("In the batch/info translation")
        slidesStr = str(slides)
        return await info(slidesStr, plugin, payload)

    @app.get(
        "/batch/thumbnail/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slides: str = SlideListQuery,
        max_x: int = Path(
            example=100,
            ge=1,
            le=settings.max_thumbnail_size,
            description="Maximum width of thumbnail",
        ),
        max_y: int = Path(
            example=100,
            ge=1,
            le=settings.max_thumbnail_size,
            description="Maximum height of thumbnail",
        ),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        return await thumbnail(
            slides, max_x, max_y, image_format, image_quality, plugin, payload
        )

    @app.get(
        "/batch/label/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slides: str = SlideListQuery,
        max_x: int = Path(example=100, description="Maximum width of label image"),
        max_y: int = Path(example=100, description="Maximum height of label image"),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        return await label(
            slides, max_x, max_y, image_format, image_quality, plugin, payload
        )

    @app.get(
        "/batch/macro/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slides: str = SlideListQuery,
        max_x: int = Path(example=100, description="Maximum width of macro image"),
        max_y: int = Path(example=100, description="Maximum height of macro image"),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        return await macro(
            slides, max_x, max_y, image_format, image_quality, plugin, payload
        )

    @app.get(
        "/batch/tile/level/{level}/tile/{tile_x}/{tile_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slides: str = SlideListQuery,
        level: int = Path(ge=0, example=0, description="Pyramid level of region"),
        tile_x: int = Path(
            example=0, description="Request the tile_x-th tile in x dimension"
        ),
        tile_y: int = Path(
            example=0, description="Request the tile_y-th tile in y dimension"
        ),
        image_channels: List[int] = ImageChannelQuery,
        z: int = ZStackQuery,
        padding_color: str = ImagePaddingColorQuery,
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        return await tile(
            slides,
            level,
            tile_x,
            tile_y,
            image_channels,
            z,
            padding_color,
            image_format,
            image_quality,
            plugin,
            payload,
        )

    @app.get(
        "/batch/batch/",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slides: str = SlideListQuery,
        levels: str = TileLevelListQuery,
        xs: str = TileXListQuery,
        ys: str = TileYListQuery,
        image_channels: List[int] = ImageChannelQuery,
        z: int = ZStackQuery,  # TODO also?
        padding_color: str = ImagePaddingColorQuery,
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
        plugin: str = PluginQuery,
        payload: Optional[str] = Depends(get_authorization_header),
    ):
        return await batch(
            slides,
            levels,
            xs,
            ys,
            image_channels,
            z,
            padding_color,
            image_format,
            image_quality,
            plugin,
            payload,
        )
