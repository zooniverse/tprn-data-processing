import numpy as np
from scipy.interpolate import interp1d


class MissingCoordinateMetadata(Exception):
    # see tiling/convert_tiles_to_jpg.py
    """Raised when the subject doesn't have the metadata for pixel conversion to lat/lon"""
    pass


def get_lat_coords_from_pixels(marks, geo_metadata):
    try:
        the_y = np.array([0, geo_metadata['//tifsize_y_pix']], dtype=float)
        the_lat = np.array([geo_metadata['//lat_max'], geo_metadata['//lat_min']], dtype=float)
    except KeyError as e:
        # missing data for the converstion to lat / lon
        raise MissingCoordinateMetadata(str(e))
    # setup interpolation functions to get the lat / lon from pixel marks
    # don't throw an error if the coords are out of bounds, but also don't extrapolate
    f_y_lat = interp1d(the_y, the_lat, bounds_error=False, fill_value=(None, None))
    return f_y_lat(marks)


def get_lon_coords_from_pixels(marks, geo_metadata):
    try:
        the_x = np.array([0, geo_metadata['//tifsize_x_pix']], dtype=float)
        the_lon = np.array([geo_metadata['//lon_min'], geo_metadata['//lon_max']], dtype=float)
    except KeyError as e:
        # missing data for the converstion to lat / lon
        raise MissingCoordinateMetadata(str(e))
    # setup interpolation functions to get the lat / lon from pixel marks
    # don't throw an error if the coords are out of bounds, but also don't extrapolate
    f_x_lon = interp1d(the_x, the_lon, bounds_error=False, fill_value=(None, None))
    return f_x_lon(marks)
