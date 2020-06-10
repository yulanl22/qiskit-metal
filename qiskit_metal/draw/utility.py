# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

# WILL NEED UPDATING TO NEW ELEMENT SCHEME

"""
Main module for basic geometric manipulation of non-shapely objects,
but objects such as points and arrays used in drawing.


@date: 2019
@author: Zlatko Minev (IBM)
"""

import math
from collections.abc import Iterable, Mapping
from typing import List, Tuple, Union

import numpy as np
import shapely
import shapely.wkt
from numpy import array
from numpy.linalg import norm
from shapely.geometry import MultiPolygon, Polygon

from .. import logger
from ..components.base import is_component
from . import BaseGeometry

__all__ = ['get_poly_pts', 'get_all_component_bounds', 'get_all_geoms', 'flatten_all_filter',
           'remove_colinear_pts', 'array_chop', 'vec_unit_planar',  'Vector']

#########################################################################
# Shapely Geometry Basic Coordinates


def get_poly_pts(poly: Polygon):
    """
    Return the coordinates of a Shapely polygon with the last repeating point removed

    Arguments:
        poly {[shapely.Polygon]} -- Shapely polygin

    Returns:
        [np.array] -- Sequence of coorindates.
    """
    return np.array(poly.exterior.coords)[:-1]


def get_all_geoms(obj, func=lambda x: x, root_name='components'):
    """Get a dict of dict of all shapely objects, from components, dict, etc.

    Used to compute the bounding box.

    Arguments:
        components {[dict,list,element,component]} --

    Keyword Arguments:
        func {[function]} -- [description] (default: {lambdax:x})
        root_name {str} -- Name to prepend in the flattening (default: {'components'})

    Returns:
        [dict] -- [description]
    """

    # Prelim
    # Calculate the new name
    def new_name(name): return root_name + '.' + \
        name if not (root_name == '') else name

    # Check what we have

    if is_component(obj):
        # Is it a metal component? Then traverse its components
        return obj.get_all_geom()  # dict of shapely geoms

    # elif is_element(obj):
    #    # is it a metal element?
    #    return {obj.name: obj.geom}  # shapely geom

    elif isinstance(obj, BaseGeometry):
        # Is it the shapely object? This is the bottom of the search tree, then return
        return obj

    elif isinstance(obj, Mapping):
        return {get_all_geoms(sub_obj, root_name=new_name(name)) for name, sub_obj in obj.items()}
        '''
        RES = {}
        for name, sub_obj in obj.items():
            if is_component(obj):
                RES[name] = get_all_geoms(
                    sub_obj.components, root_name=new_name(name))
            elif isinstance(sub_obj, dict):
                # if name.startswith('components'): # old school to remove eventually TODO
                #    RES[name] = func(obj) # allow transofmraiton of components
                # else:
                RES[name] = get_all_geoms(sub_obj, root_name=new_name(name))
            elif isinstance(sub_obj, BaseGeometry):
                RES[name] = func(obj)
        return RES
        '''

    else:
        logger.debug(
            f'warning: {root_name} was not an object or dict or the right handle')
        return None


def flatten_all_filter(components: dict, filter_obj=None):
    """Internal function to flatten a dict of shapely objects.

    Arguments:
        components {dict} -- [description]

    Keyword Arguments:
        filter_obj {[class]} -- Filter based on this calss (default: {None})
    """
    assert isinstance(components, dict)

    RES = []
    for name, obj in components.items():
        if isinstance(obj, dict):
            RES += flatten_all_filter(obj, filter_obj)
        else:
            if filter_obj is None:
                RES += [obj]  # add whatever we have in here
            else:
                if isinstance(obj, filter_obj):
                    RES += [obj]
                else:
                    print('flatten_all_filter: ', name)

    return RES


def get_all_component_bounds(components: dict, filter_obj=Polygon):
    """
    Pass in a dict of components to calcualte the total bounding box.

    Arguments:
        components {dict} -- [description]
        filter_obj {Polygon} -- only use instances of this object to
                             calcualte the bounds

    Returns:
        (x_min, y_min, x_max, y_max)
    """
    assert isinstance(components, dict)

    components = get_all_geoms(components)
    components = flatten_all_filter(components, filter_obj=filter_obj)

    (x_min, y_min, x_max, y_max) = MultiPolygon(components).bounds

    return (x_min, y_min, x_max, y_max)


#########################################################################
# POINT LIST FUNCTIONS

def check_duplicate_list(your_list):
    return len(your_list) != len(set(your_list))


def array_chop(vec, zero=0, rtol=0, machine_tol=100):
    '''
    Chop array entries close to zero.
    Zlatko quick solution.
    '''
    vec = np.array(vec)
    mask = np.isclose(vec, zero, rtol=rtol,
                      atol=machine_tol*np.finfo(float).eps)
    vec[mask] = 0
    return vec


def remove_colinear_pts(points):
    '''
    remove colinear points and identical consequtive points
    '''
    remove_idx = []
    for i in range(2, len(points)):
        v1 = array(points[i-2])-array(points[i-1])
        v2 = array(points[i-1])-array(points[i-0])
        if Vector.are_same(v1, v2):
            remove_idx += [i-1]
        elif Vector.angle_between(v1, v2) == 0:
            remove_idx += [i-1]
    points = np.delete(points, remove_idx, axis=0)

    # remove  consequtive duplicates
    remove_idx = []
    for i in range(1, len(points)):
        if norm(points[i]-points[i-1]) == 0:
            remove_idx += [i]
    points = np.delete(points, remove_idx, axis=0)

    return points


#########################################################################
# Vector functions


def vec_unit_planar(vector: np.array):
    """
    Make the planar 2D (x,y) part of a vector to be unit mag.
    Return a vector where is XY components now a unit vector.
    I.e., Normalizes only in the XY plane, leaves the Z plane alone.

    Arguments:
        vector {np.array} -- input 2D or 3D

    Raises:
        Exception: [description]

    Returns:
        np.array -- Same dimension 2D or 3D
    """
    vector = array_chop(vector)  # get rid of near zero crap

    if len(vector) == 2:
        _norm = norm(vector)

        if not bool(_norm):  # zero length vector
            logger.debug(f'Warning: zero vector length')
            return vector

        return vector / _norm

    elif len(vector) == 3:
        v2 = vec_unit_planar(vector[:2])
        return np.append(v2, vector[2])

    else:
        raise Exception('You did not give a 2 or 3 vec')


Vec2D = Union[list, np.ndarray]


class Vector:
    """
    Utility functions to call on 2D vectors, which can be np.ndarrays or lists.
    """

    normal_z = np.array([0, 0, 1])              # hardcoded

    @staticmethod
    def rotate_around_point(xy: Vec2D, radians: float, origin=(0, 0)) -> np.ndarray:
        r"""Rotate a point around a given point.
        Positive angles are counter-clockwise and negative are clockwise rotations.

        .. math::

            \begin{split}
            x_\mathrm{off} &= x_0 - x_0 \cos{\theta} + y_0 \sin{\theta} \\
            y_\mathrm{off} &= y_0 - x_0 \sin{\theta} - y_0 \cos{\theta}
            \end{split}

        Arguments:
            xy {Vec2D} -- A 2D vector.
            radians {float} -- Counter clockwise angle

        Keyword Arguments:
            origin {tuple} -- point to rotate about (default: {(0, 0)})

        Returns:
            np.ndarray -- rotated point
        """
        # see: https://gist.github.com/LyleScott/d17e9d314fbe6fc29767d8c5c029c362
        x, y = xy
        offset_x, offset_y = origin
        adjusted_x = (x - offset_x)
        adjusted_y = (y - offset_y)
        cos_rad = math.cos(radians)
        sin_rad = math.sin(radians)
        qx = offset_x + cos_rad * adjusted_x - sin_rad * adjusted_y
        qy = offset_y + sin_rad * adjusted_x + cos_rad * adjusted_y
        return qx, qy

    @staticmethod
    def rotate(xy: Vec2D, radians: float) -> np.ndarray:
        """Counter-clockwise rotation of the vector in radians.
        Positive angles are counter-clockwise and negative are clockwise rotations.

        Arguments:
            xy {Vec2D} -- A 2D vector.
            radians {float} -- Counter clockwise angle

        Returns:
            np.ndarray -- rotated point
        """
        x, y = xy
        cos_rad = math.cos(radians)
        sin_rad = math.sin(radians)
        qx = cos_rad * x - sin_rad * y
        qy = sin_rad * x + cos_rad * y
        return np.array([qx, qy]) #ADD ARRAY CHOP - draw_utility

    @staticmethod
    def angle(vector: Vec2D) -> float:
        """
        Return the angle in radians of a vector.

        Arguments:
            vector {Union[list, np.ndarray]} -- a 2D vector

        Returns:
            [type] -- [description]

        Caution:
            The angle is defined from the Y axis!

            See https://docs.scipy.org/doc/numpy/reference/generated/numpy.arctan2.html
            ```
                |-> Positive direction, defined from Y axis
                |
            --------
                |
                |

                x1	x2	arctan2(x1,x2)
                +/- 0	+0	+/- 0
                +/- 0	-0	+/- pi
                > 0	+/-inf	+0 / +pi
                < 0	+/-inf	-0 / -pi
                +/-inf	+inf	+/- (pi/4)
                +/-inf	-inf	+/- (3*pi/4)
            ```
            Note that +0 and -0 are distinct floating point numbers, as are +inf and -inf.
        """
        return np.arctan2(vector)

    @staticmethod
    def angle_between(v1: Vec2D, v2: Vec2D) -> float:
        """Returns the angle in radians between vectors 'v1' and 'v2'

        Arguments:
            v1 {Vec2D} -- First vector
            v2 {Vec2D} -- Second vector

        Returns:
            float -- angle in radians. The angle of the ray intersecting the unit
            circle at the given x-coordinate in radians [0, pi]. This is a scalar.
        """
        v1_u = vec_unit_planar(v1)
        v2_u = vec_unit_planar(v2)
        return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))

    @staticmethod
    def add_z(vec2D: np.array, z: float = 0.):
        """
        Turn a 2D vector into a 3D vector by adding the z coorindate.

        Arguments:
            vec2D {np.array} -- Input 2D vector.

        Keyword Arguments:
            z {float} -- Add this value to the 3rd dimension (default: {0})

        Returns:
            np.array -- 3D vector.
        """
        if isinstance(vec2D[0], Iterable):
            return array([Vector.add_z(vec, z=z) for vec in vec2D])
        else:
            return array(list(vec2D)+[z])

    @staticmethod
    def normed(vec: Vec2D) -> Vec2D:
        """Return normed vector

        Arguments:
            vec {Vec2D} -- Vector

        Returns:
            Vec2D -- Unit normed version of vector
        """
        return Vec2D / norm(Vec2D)

    @staticmethod
    def norm(vec: Vec2D) -> float:
        """Return the norm of a 2D vector

        Arguments:
            vec {Vec2D} -- 2D vector

        Returns:
            float -- length of vector
        """
        return norm(vec)

    def are_same(v1: Vec2D, v2: Vec2D, tol: int = 100) -> bool:
        """
        Check if two vectors are within an infentesmimal distance set
        by `tol` and machine epsilon

        Arguments:
            v1 {[type]} -- [description]
            v2 {[type]} -- [description]

        Keyword Arguments:
            tol {int} -- How much to multiply the machine precision, np.finfo(float).eps,
                        by as the tolerance (default: {100})

        Returns:
            bool -- same or not
        """
        v1, v2 = np.array(v1), np.array(v2)
        return Vector.is_zero(v1-v2, tol=tol)

    @staticmethod
    def is_zero(vec: Vec2D, tol: int = 100) -> bool:
        """Check if a vector is essentially zero within machine precision,
        set by `tol` and machine epsilon

        Arguments:
            vec {Vec2D} -- [description]

        Keyword Arguments:
            tol {int} -- How much to multiply the machine precision, np.finfo(float).eps,
                        by as the tolerance (default: {100})

        Returns:
            bool -- close to zero or not
        """
        return float(norm(vec)) < tol*np.finfo(float).eps

    @staticmethod
    def two_points_described(points2D: List[Vec2D]) -> Tuple[np.ndarray]:
        """
        For a list of exactly two given 2D points, get:
            d: the distance vector between them
            n: normal vector defined by d
            t: the vector tangent to n

        .. codeblock python
            vec_D, vec_d, vec_n = Vector.difference_dnt(points)

        Arguments:
            points {np.array or list} -- 2D list of points

        Returns:
            distance_vec, dist_unit_vec, tangent_vec -- Each is a vector np.array
        """
        assert len(points2D) == 2
        start = np.array(points2D[0])
        end = np.array(points2D[1])

        distance_vec = end - start                   # distance vector
        # unit vector along the direction of the two point
        unit_vec = distance_vec / norm(distance_vec)
        # tangent vector counter-clockwise 90 deg rotation
        tangent_vec = np.round(Vector.rotate(unit_vec, np.pi/2),decimals=11)

        if Vector.is_zero(distance_vec):
            logger.debug(f'Function `two_points_described` encountered a zero vector'
                         ' length. The two points should not be the same.')

        return distance_vec, unit_vec, tangent_vec

    @staticmethod
    def snap_unit_vector(vec_n:Vec2D, flip:bool=False) -> Vec2D:
        """snaps to either the x or y unit vecotrs

        Arguments:
            vec_n {Vec2D} -- [description]

        Keyword Arguments:
            flip {bool} -- [description] (default: {False})

        Returns:
            Vec2D -- [description]
        """
        #TODO: done silly, fix up
        m = np.argmax(abs(vec_n))
        m = m if flip == False else int(not(m))
        v = np.array([0,0])
        v[m] = np.sign(vec_n[m])
        vec_n = v
        return vec_n