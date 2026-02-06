

import math

def get_cell_coordinates(x, y, image_width, image_height, rows, cols):
    """
    Convert (x,y) image coordinates into grid cell indexes
    """

    cell_width = image_width / cols
    cell_height = image_height / rows

    cell_x = math.floor(x / cell_width)
    cell_y = math.floor(y / cell_height)

    return cell_x, cell_y


def get_cell_id(cell_x, cell_y, cols):
    """
    Convert grid coordinates into linear cell id
    """

    return cell_y * cols + cell_x