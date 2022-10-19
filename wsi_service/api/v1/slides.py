from typing import List

from fastapi import HTTPException, Path
from fastapi.responses import StreamingResponse
from PIL import Image

from wsi_service.custom_models.queries import (
    ImageChannelQuery,
    ImageFormatsQuery,
    ImagePaddingColorQuery,
    ImageQualityQuery,
    ZStackQuery,
)
from wsi_service.custom_models.responses import ImageRegionResponse, ImageResponses
from wsi_service.models.v1.slide import SlideInfo
from wsi_service.utils.app_utils import (
    make_response,
    validate_hex_color_string,
    validate_image_channels,
    validate_image_request,
)


def add_routes_slides(app, settings, slide_manager):
    @app.get("/slides/{slide_id}/info", response_model=SlideInfo, tags=["Main Routes"])
    async def _(slide_id: str):
        """
        Get metadata information for a slide given its ID
        """
        return await slide_manager.get_slide_info(slide_id, slide_info_model=SlideInfo)

    @app.get(
        "/slides/{slide_id}/thumbnail/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id: str,
        max_x: int = Path(
            None, example=100, ge=1, le=settings.max_thumbnail_size, description="Maximum width of thumbnail"
        ),
        max_y: int = Path(
            None, example=100, ge=1, le=settings.max_thumbnail_size, description="Maximum height of thumbnail"
        ),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
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
        slide = await slide_manager.get_slide(slide_id)
        thumbnail = await slide.get_thumbnail(max_x, max_y)
        return make_response(slide, thumbnail, image_format, image_quality)

    @app.get(
        "/slides/{slide_id}/label/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id: str,
        max_x: int = Path(None, example=100, description="Maximum width of label image"),
        max_y: int = Path(None, example=100, description="Maximum height of label image"),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
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
        slide = await slide_manager.get_slide(slide_id)
        label = await slide.get_label()
        label.thumbnail((max_x, max_y), Image.ANTIALIAS)
        return make_response(slide, label, image_format, image_quality)

    @app.get(
        "/slides/{slide_id}/macro/max_size/{max_x}/{max_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id: str,
        max_x: int = Path(None, example=100, description="Maximum width of macro image"),
        max_y: int = Path(None, example=100, description="Maximum height of macro image"),
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
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
        slide = await slide_manager.get_slide(slide_id)
        macro = await slide.get_macro()
        macro.thumbnail((max_x, max_y), Image.ANTIALIAS)
        return make_response(slide, macro, image_format, image_quality)

    @app.get(
        "/slides/{slide_id}/region/level/{level}/start/{start_x}/{start_y}/size/{size_x}/{size_y}",
        responses=ImageRegionResponse,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id: str,
        level: int = Path(None, ge=0, example=0, description="Pyramid level of region"),
        start_x: int = Path(None, example=0, description="x component of start coordinate of requested region"),
        start_y: int = Path(None, example=0, description="y component of start coordinate of requested region"),
        size_x: int = Path(None, gt=0, example=1024, description="Width of requested region"),
        size_y: int = Path(None, gt=0, example=1024, description="Height of requested region"),
        image_channels: List[int] = ImageChannelQuery,
        z: int = ZStackQuery,
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
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

        * `image_format` - The image format can be selected. Formats include jpeg, png, tiff, bmp, gif.
        When tiff is specified as output format the raw data of the image is returned.
        Multi-channel images can also be represented as RGB-images (mostly for displaying reasons in the viewer).
        Note that the mapping of all color channels to RGB values is currently restricted to the first three channels.
        Default is jpeg.

        * `image_quality` - The image quality can be set for specific formats,
        e.g. for the jpeg format a value between 0 and 100 can be selected. Default is 90.
        """
        validate_image_request(image_format, image_quality)
        if size_x * size_y > settings.max_returned_region_size:
            raise HTTPException(
                status_code=422,
                detail=f"Requested region may not contain more than {settings.max_returned_region_size} pixels.",
            )

        slide = await slide_manager.get_slide(slide_id)
        if z != 0:
            try:
                image_region = await slide.get_region(level, start_x, start_y, size_x, size_y, padding_color=None, z=z)
            except TypeError as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"""Invalid ZStackQuery z={z}. The image does not support multiple z-layers.""",
                ) from e
        else:
            image_region = await slide.get_region(level, start_x, start_y, size_x, size_y, padding_color=None)
        validate_image_channels(slide, image_channels)
        return make_response(slide, image_region, image_format, image_quality, image_channels)

    @app.get(
        "/slides/{slide_id}/tile/level/{level}/tile/{tile_x}/{tile_y}",
        responses=ImageResponses,
        response_class=StreamingResponse,
        tags=["Main Routes"],
    )
    async def _(
        slide_id: str,
        level: int = Path(None, ge=0, example=0, description="Pyramid level of region"),
        tile_x: int = Path(None, example=0, description="Request the tile_x-th tile in x dimension"),
        tile_y: int = Path(None, example=0, description="Request the tile_y-th tile in y dimension"),
        image_channels: List[int] = ImageChannelQuery,
        z: int = ZStackQuery,
        padding_color: str = ImagePaddingColorQuery,
        image_format: str = ImageFormatsQuery,
        image_quality: int = ImageQualityQuery,
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
        slide = await slide_manager.get_slide(slide_id)
        if z != 0:
            try:
                image_tile = await slide.get_tile(level, tile_x, tile_y, padding_color=vp_color, z=z)
            except TypeError as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"""Invalid ZStackQuery z={z}. The image does not support multiple z-layers.""",
                ) from e
        else:
            image_tile = await slide.get_tile(level, tile_x, tile_y, padding_color=vp_color)
        validate_image_channels(slide, image_channels)
        return make_response(slide, image_tile, image_format, image_quality, image_channels)