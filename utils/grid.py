

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

def is_valid_cell(cell_x, cell_y, floor):
    """
    Validate if grid cell is inside bounds and not blocked
    """

    # Check bounds
    if cell_x < 0 or cell_x >= floor.cols:
        return False

    if cell_y < 0 or cell_y >= floor.rows:
        return False

    # Convert to cell_id
    cell_id = cell_y * floor.cols + cell_x

    # Check blocked cells
    if cell_id in floor.blocked_cells:
        return False

    return True