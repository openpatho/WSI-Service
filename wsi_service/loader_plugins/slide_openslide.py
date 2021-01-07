import math

import openslide
import PIL
from fastapi import HTTPException

from wsi_service.models.slide import Extent, SlideInfo
from wsi_service.settings import Settings
from wsi_service.slide import Slide
from wsi_service.slide_utils import get_slide_info, rgba_to_rgb_with_background_color


class OpenSlideSlide(Slide):
    supported_file_types = ["mrxs", "tiff", "ndpi", "svs"]
    loader_name = "OpenSlide"

    def __init__(self, filepath, slide_id):
        self.openslide_slide = openslide.OpenSlide(filepath)
        self.slide_info = get_slide_info(self.openslide_slide, slide_id)

    def close(self):
        self.openslide_slide.close()

    def get_info(self):
        return self.slide_info

    def get_region(self, level, start_x, start_y, size_x, size_y):
        settings = Settings()
        try:
            downsample_factor = int(self.slide_info.levels[level].downsample_factor)
        except IndexError:
            raise HTTPException(
                422,
                detail="The requested pyramid level is not available. The coarsest available level is {}.".format(
                    len(self.slide_info.levels) - 1
                ),
            )
        base_level = self.openslide_slide.get_best_level_for_downsample(downsample_factor)
        remaining_downsample_factor = downsample_factor / self.openslide_slide.level_downsamples[base_level]
        base_size = (
            round(size_x * remaining_downsample_factor),
            round(size_y * remaining_downsample_factor),
        )
        level_0_location = (start_x * downsample_factor, start_y * downsample_factor)
        if base_size[0] * base_size[1] > settings.max_returned_region_size:
            raise HTTPException(
                403,
                "Requested image region is too large. Maximum number of pixels is set to {}, your request is for {} pixels.".format(
                    settings.max_returned_region_size, base_size[0] * base_size[1]
                ),
            )
        try:
            base_img = self.openslide_slide.read_region(level_0_location, base_level, base_size)
            rgba_img = base_img.resize((size_x, size_y), resample=PIL.Image.BILINEAR, reducing_gap=1.0)
            rgb_img = rgba_to_rgb_with_background_color(rgba_img)
        except openslide.OpenSlideError as e:
            raise HTTPException(
                422,
                "OpenSlideError: {}".format(e),
            )

        return rgb_img

    def get_thumbnail(self, max_x, max_y):
        return self.openslide_slide.get_thumbnail((max_x, max_y))

    def _get_associated_image(self, associated_image_name):
        if associated_image_name not in self.openslide_slide.associated_images:
            raise HTTPException(status_code=404)
        associated_image_rgba = self.openslide_slide.associated_images[associated_image_name]
        return associated_image_rgba.convert("RGB")

    def get_label(self):
        return self._get_associated_image("label")

    def get_macro(self):
        return self._get_associated_image("macro")

    def get_tile(self, level, tile_x, tile_y):
        return self.get_region(
            level,
            tile_x * self.slide_info.tile_extent.x,
            tile_y * self.slide_info.tile_extent.y,
            self.slide_info.tile_extent.x,
            self.slide_info.tile_extent.y,
        )