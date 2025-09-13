import requests

from wsi_service.models.v3.slide import SlideInfo
from wsi_service.tests.integration.plugin_example_tests.helpers import (
    get_image,
    get_tiff_image,
)


def check_get_slide_info_valid(
    slide_id,
    channels,
    channel_depth,
    num_levels,
    pixel_size_nm,
    tile_size,
    x,
    y,
    plugin="",
):
    response = requests.get(
        f"http://localhost:8080/v3/slides/{slide_id}/info?plugin={plugin}"
    )
    assert response.status_code == 200
    slide_info = SlideInfo.model_validate(response.json())
    assert slide_info.id == slide_id
    assert slide_info.num_levels == num_levels
    assert round(slide_info.pixel_size_nm.x) == pixel_size_nm
    assert round(slide_info.pixel_size_nm.y) == pixel_size_nm
    assert slide_info.extent.x == x
    assert slide_info.extent.y == y
    assert slide_info.tile_extent.x == tile_size[0]
    assert slide_info.tile_extent.y == tile_size[1]
    assert len(slide_info.channels) == channels
    assert slide_info.channel_depth == channel_depth


def check_get_slide_thumbnail_valid(
    image_format,
    image_quality,
    slide_id,
    return_value,
    pixel_location,
    testpixel_rgb,
    testpixel_multichannel,
    plugin="",
):
    max_size_x = 21
    max_size_y = 22
    response = requests.get(
        (
            f"http://localhost:8080/v3/slides/{slide_id}/thumbnail/max_size/{max_size_x}/{max_size_y}"
            f"?image_format={image_format}&image_quality={image_quality}&plugin={plugin}"
        ),
        stream=True,
    )
    assert response.status_code == return_value
    assert response.headers["content-type"] == f"image/{image_format}"
    if response.headers["content-type"] == "image/tiff":
        image = get_tiff_image(response)
        x, y = image.pages.keyframe.imagewidth, image.pages.keyframe.imagelength
        assert (x == max_size_x) or (y == max_size_y)
        narray = image.asarray()
        for i, pixel in enumerate(testpixel_multichannel):
            c = narray[i][pixel_location[0]][pixel_location[1]]
            assert c == pixel
    else:
        image = get_image(response)
        x, y = image.size
        assert (x == max_size_x) or (y == max_size_y)
        if image_format == "png":
            assert (
                image.getpixel((pixel_location[0], pixel_location[1])) == testpixel_rgb
            )


def check_get_slide_label_valid(
    image_format,
    image_quality,
    slide_id,
    has_label,
    pixel_location,
    testpixel,
    plugin="",
):
    max_x, max_y = 200, 200
    response = requests.get(
        (
            f"http://localhost:8080/v3/slides/{slide_id}/label/max_size/{max_x}/{max_y}"
            f"?image_format={image_format}&image_quality={image_quality}&plugin={plugin}"
        ),
        stream=True,
    )
    if has_label:
        assert response.status_code == 200
        assert response.headers["content-type"] == f"image/{image_format}"
        if response.headers["content-type"] == "image/tiff":
            image = get_tiff_image(response)
            narray = image.asarray()
            for i, value in enumerate(testpixel):
                c = narray[i][pixel_location[1]][pixel_location[0]]
                assert c == value
        else:
            image = get_image(response)
            if image_format == "png":
                assert (
                    image.getpixel((pixel_location[0], pixel_location[1])) == testpixel
                )
    else:
        assert response.status_code == 404


def check_get_slide_macro_valid(
    image_format,
    image_quality,
    slide_id,
    return_value,
    pixel_location,
    testpixel,
    plugin="",
):
    max_x, max_y = 200, 200
    response = requests.get(
        (
            f"http://localhost:8080/v3/slides/{slide_id}/macro/max_size/{max_x}/{max_y}"
            f"?image_format={image_format}&image_quality={image_quality}&plugin={plugin}"
        ),
        stream=True,
    )
    assert response.status_code == return_value
    if return_value == 200:
        if response.headers["content-type"] == "image/tiff":
            image = get_tiff_image(response)
            narray = image.asarray()
            for i, value in enumerate(testpixel):
                c = narray[i][pixel_location[1]][pixel_location[0]]
                print(f"Testpixel val: {c} | actual val {value}")
                assert c == value
        else:
            image = get_image(response)
            if image_format == "png":
                assert (
                    image.getpixel((pixel_location[0], pixel_location[1])) == testpixel
                )


def check_get_slide_region_valid_brightfield(
    image_format,
    image_quality,
    slide_id,
    pixel_location,
    testpixel,
    start_x,
    start_y,
    size,
    plugin="",
):
    level = 0
    size_x = size
    size_y = size + 198
    response = requests.get(
        (
            f"http://localhost:8080/v3/slides/{slide_id}/region/level/{level}/"
            f"start/{start_x}/{start_y}/size/{size_x}/{size_y}"
            f"?image_format={image_format}&image_quality={image_quality}&plugin={plugin}"
        ),
        stream=True,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == f"image/{image_format}"
    if response.headers["content-type"] == "image/tiff":
        image = get_tiff_image(response)
        x, y = image.pages.keyframe.imagewidth, image.pages.keyframe.imagelength
        assert (x == size_x) or (y == size_y)
        narray = image.asarray()
        r = narray[0][pixel_location[0]][pixel_location[1]]
        g = narray[1][pixel_location[0]][pixel_location[1]]
        b = narray[2][pixel_location[0]][pixel_location[1]]
        assert (r, g, b) == testpixel
    else:
        image = get_image(response)
        x, y = image.size
        assert (x == size_x) or (y == size_y)
        if image_format == "png":
            assert image.getpixel((pixel_location[0], pixel_location[1])) == testpixel


def check_get_slide_region_valid_fluorescence(
    slide_id,
    channels,
    start_point,
    size,
    pixel_location,
    testpixel_multichannel,
    testpixel_rgb,
    image_format,
    image_quality,
    plugin="",
):
    level = 2
    response = requests.get(
        (
            f"http://localhost:8080/v3/slides/{slide_id}/region/level/{level}/"
            f"start/{start_point[0]}/{start_point[1]}/size/{size[0]}/{size[1]}"
            f"?image_format={image_format}&image_quality={image_quality}&plugin={plugin}"
        ),
        stream=True,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == f"image/{image_format}"
    if response.headers["content-type"] == "image/tiff":
        image = get_tiff_image(response)
        assert image.pages.keyframe.shape[0] == channels
        x, y = image.pages.keyframe.imagewidth, image.pages.keyframe.imagelength
        assert (x == size[0]) or (y == size[1])
        narray = image.asarray()
        for i, value in enumerate(testpixel_multichannel):
            c = narray[i][pixel_location[0]][pixel_location[1]]
            assert c == value
    else:
        image = get_image(response)
        x, y = image.size
        assert (x == size[0]) or (y == size[1])
        if image_format in ["png", "bmp"]:
            assert (
                image.getpixel((pixel_location[0], pixel_location[1])) == testpixel_rgb
            )


def check_get_slide_region_dedicated_channel(
    slide_id,
    level,
    channels,
    start_point,
    size,
    pixel_location,
    testpixel_multichannel,
    testpixel_rgb,
    image_format,
    image_quality,
    plugin="",
):
    str_channels = "&".join([f"image_channels={str(ch)}" for ch in channels])
    response = requests.get(
        (
            f"http://localhost:8080/v3/slides/{slide_id}/region/level/{level}/"
            f"start/{start_point[0]}/{start_point[1]}/size/{size[0]}/{size[1]}"
            f"?image_format={image_format}&image_quality={image_quality}&{str_channels}&plugin={plugin}"
        ),
        stream=True,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == f"image/{image_format}"
    if response.headers["content-type"] == "image/tiff":
        image = get_tiff_image(response)
        x, y = image.pages.keyframe.imagewidth, image.pages.keyframe.imagelength
        assert (x == size[0]) or (y == size[1])
        narray = image.asarray()
        for i, value in enumerate(testpixel_multichannel):
            c = narray[i][pixel_location[0]][pixel_location[1]]
            assert c == value
    else:
        image = get_image(response)
        x, y = image.size
        assert (x == size[0]) or (y == size[1])
        if image_format == "png":
            assert (
                image.getpixel((pixel_location[0], pixel_location[1])) == testpixel_rgb
            )


def check_get_slide_region_invalid_channel(
    slide_id, channels, expected_response, plugin=""
):
    str_channels = "&".join([f"image_channels={str(ch)}" for ch in channels])
    response = requests.get(
        f"http://localhost:8080/v3/slides/{slide_id}/region/level/2/start/0/0/size/64/64?{str_channels}&plugin={plugin}",
        stream=True,
    )
    assert response.status_code == expected_response


def check_get_slide_region_invalid(
    slide_id, testpixel, start_x, start_y, size, status_code, plugin=""
):
    level = 0
    size_x = size
    size_y = size + 198
    response = requests.get(
        (
            f"http://localhost:8080/v3/slides/{slide_id}/region/level/{level}/"
            f"start/{start_x}/{start_y}/size/{size_x}/{size_y}?plugin={plugin}"
        ),
        stream=True,
    )
    assert response.status_code == status_code


def check_get_slide_tile_valid(
    image_format,
    image_quality,
    slide_id,
    testpixel,
    tile_x,
    tile_y,
    tile_size,
    plugin="",
):
    level = 0
    response = requests.get(
        (
            f"http://localhost:8080/v3/slides/{slide_id}/tile/level/{level}/tile/{tile_x}/{tile_y}"
            f"?image_format={image_format}&image_quality={image_quality}&plugin={plugin}"
        ),
        stream=True,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == f"image/{image_format}"
    if response.headers["content-type"] == "image/tiff":
        image = get_tiff_image(response)
        x, y = image.pages.keyframe.imagewidth, image.pages.keyframe.imagelength
        assert (x == tile_size[0]) or (y == tile_size[1])
        narray = image.asarray()
        for i, value in enumerate(testpixel):
            c = narray[i][0][0]
            assert c == value
    else:
        image = get_image(response)
        x, y = image.size
        assert (x == tile_size[0]) or (y == tile_size[1])
        if image_format == "png":
            assert image.getpixel((0, 0)) == testpixel
