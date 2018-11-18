
import re

from django.core.exceptions import ValidationError

NUMBER = re.compile(r'[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?')
COORDINATE = re.compile(r"\s*({NUMBER})\s+({NUMBER})\s*".format(NUMBER=NUMBER.pattern))
COORDINATES = re.compile(r"\(({COORDINATE})(,{COORDINATE})*\)".format(COORDINATE=COORDINATE.pattern))

MULTIPOINT_COORDINATES = re.compile(r"\(({COORDINATE})(,{COORDINATE})*\)".format(
    COORDINATE=r'\s*\(' + COORDINATE.pattern + r'\s*\)'
))
POLYGON_COORDINATES = re.compile(r'\(\s*{COORDINATES}\s*(,\s*{COORDINATES}\s*)*\)'.format(
    COORDINATES=COORDINATES.pattern
))

POINT = re.compile(r'POINT\s+\({COORDINATE}\)'.format(COORDINATE=COORDINATE.pattern))
LINESTRING = re.compile(r'LINESTRING\s+({COORDINATES})'.format(COORDINATES=COORDINATES.pattern))
POLYGON = re.compile(r'POLYGON\s+{POLYGON_COORDINATES}'.format(
    POLYGON_COORDINATES=POLYGON_COORDINATES.pattern
))

MULTIPOINT = re.compile(r'MULTIPOINT\s+(({POINT_COORDINATES})|({COORDINATES}))'.format(
    COORDINATES=COORDINATES.pattern,
    POINT_COORDINATES=MULTIPOINT_COORDINATES.pattern
))

MULTILINESTRING = re.compile(r'MULTILINESTRING\s+{POLYGON_COORDINATES}'.format(
    POLYGON_COORDINATES=POLYGON_COORDINATES.pattern
))

MULTIPOLYGON = re.compile(r'MULTIPOLYGON\s+\(\s*{POLYGON_COORDINATES}\s*(,\s*{POLYGON_COORDINATES}\s*)*\)'.format(
    POLYGON_COORDINATES=POLYGON_COORDINATES.pattern
))


def validate_wkt(value):
    """Validates well-known text"""
    if not identify_geometry(value):
        raise ValidationError('The value is not valid well-known text')


def identify_geometry(value):
    """Finds the geometry type of WKT"""
    if not value:
        return 'EMPTY'

    if POINT.fullmatch(value):
        return 'POINT'
    elif LINESTRING.fullmatch(value):
        return 'LINESTRING'
    elif POLYGON.fullmatch(value):
        return 'POLYGON'
    elif MULTIPOINT.fullmatch(value):
        return 'MULTIPOINT'
    elif MULTILINESTRING.fullmatch(value):
        return 'MULTILINESTRING'
    elif MULTIPOLYGON.fullmatch(value):
        return 'MULTIPOLYGON'
    else:
        return None


def wkt_bounds(value):
    if value:
        # coordinates in WKT always look like this: 'X Y'
        # because there are some groups in the number regex, the indicies of the coords are
        # 0 and 2
        coords = [(float(match[0]), float(match[2])) for match in COORDINATE.findall(value)]
        if len(coords) > 1:
            x_coords, y_coords = zip(*coords)
            return {
                "xmin": min(x_coords),
                "xmax": max(x_coords),
                "ymin": min(y_coords),
                "ymax": max(y_coords)
            }
        elif len(coords) == 1:
            return {
                "xmin": coords[0][0],
                "xmax": coords[0][0],
                "ymin": coords[0][1],
                "ymax": coords[0][1]
            }

    return {
        "xmin": None,
        "xmax": None,
        "ymin": None,
        "ymax": None
    }