import pytest

from wsi_service.tests.integration.plugin_example_tests.plugin_example_tests import (
    check_get_slide_info_valid,
    check_get_slide_region_valid_brightfield,
    check_get_slide_thumbnail_valid,
    check_get_slide_tile_valid,
)


@pytest.mark.parametrize(
    "slide_id, channels, channel_depth, num_levels, pixel_size_nm, tile_size, x, y",
    [
        # JPG
        ("7764a90026135d0f881c451d5bbf566a", 3, 8, 1, -1, (256, 256), 500, 358),
        # PNG
        ("035b26b0a0ab5b258cc0dafb91fb09cc", 3, 8, 1, -1, (256, 256), 500, 358),
    ],
)
def test_get_slide_info_valid(
    slide_id, channels, channel_depth, num_levels, pixel_size_nm, tile_size, x, y
):
    check_get_slide_info_valid(
        slide_id,
        channels,
        channel_depth,
        num_levels,
        pixel_size_nm,
        tile_size,
        x,
        y,
        plugin="pil",
    )


@pytest.mark.parametrize("image_format, image_quality", [("jpeg", 90)])
@pytest.mark.parametrize(
    "slide_id, return_value, pixel_location, testpixel_rgb",
    [
        (
            "7764a90026135d0f881c451d5bbf566a",
            200,
            (5, 5),
            (245, 246, 246),
        ),
        (
            "035b26b0a0ab5b258cc0dafb91fb09cc",
            200,
            (5, 5),
            (243, 245, 244),
        ),
    ],
)
def test_get_slide_thumbnail_valid(
    image_format,
    image_quality,
    slide_id,
    return_value,
    pixel_location,
    testpixel_rgb,
):
    check_get_slide_thumbnail_valid(
        image_format,
        image_quality,
        slide_id,
        return_value,
        pixel_location,
        testpixel_rgb,
        (None, None, None),
        plugin="pil",
    )


@pytest.mark.parametrize("image_format, image_quality", [("jpeg", 90)])
@pytest.mark.parametrize(
    "slide_id, testpixel, tile_x, tile_y, tile_size",
    [
        ("7764a90026135d0f881c451d5bbf566a", (243, 243, 243), 0, 0, (256, 256)),
        ("035b26b0a0ab5b258cc0dafb91fb09cc", (243, 243, 243), 0, 0, (256, 256)),
        (
            "7764a90026135d0f881c451d5bbf566a",
            (255, 255, 255),
            -1_000_000,
            -1_000_000,
            (256, 256),
        ),
        (
            "7764a90026135d0f881c451d5bbf566a",
            (255, 255, 255),
            1_000_000,
            1_000_000,
            (256, 256),
        ),
    ],
)
def test_get_slide_tile_valid(
    image_format, image_quality, slide_id, testpixel, tile_x, tile_y, tile_size
):
    check_get_slide_tile_valid(
        image_format,
        image_quality,
        slide_id,
        testpixel,
        tile_x,
        tile_y,
        tile_size,
        plugin="pil",
    )


@pytest.mark.parametrize("image_format, image_quality", [("jpeg", 90)])
@pytest.mark.parametrize(
    "slide_id,  pixel_location, testpixel, start_x, start_y, size",
    [
        (
            "7764a90026135d0f881c451d5bbf566a",
            (0, 0),
            (243, 243, 243),
            0,
            0,
            128,
        ),
        (
            "7764a90026135d0f881c451d5bbf566a",
            (0, 0),
            (255, 255, 255),
            -1_000_000,
            -1_000_000,
            128,
        ),
        (
            "7764a90026135d0f881c451d5bbf566a",
            (0, 0),
            (255, 255, 255),
            1_000_000,
            1_000_000,
            128,
        ),
    ],
)
def test_get_slide_region_valid_brightfield(
    image_format,
    image_quality,
    slide_id,
    pixel_location,
    testpixel,
    start_x,
    start_y,
    size,
):
    check_get_slide_region_valid_brightfield(
        image_format,
        image_quality,
        slide_id,
        pixel_location,
        testpixel,
        start_x,
        start_y,
        size,
        plugin="pil",
    )
