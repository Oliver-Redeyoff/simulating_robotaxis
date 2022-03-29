# Import relevant libraries

from dataclasses import dataclass
from typing import List, Tuple
import pickle
import csv
import json
import requests
from enum import Enum
import os
import sys

import folium
import xml.etree.ElementTree as ET
import utm
from tqdm import tqdm
from matplotlib import pyplot as plt
from pyproj import Transformer
from shapely.geometry import shape, Point
import http.client as httplib
import urllib.parse as urlparse

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
    import osmGet
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

class p(Enum):
    count_point_id = 0
    direction_of_travel = 1
    year = 2
    count_date = 3
    hour = 4
    region_id = 5
    region_name = 6
    local_authority_id = 7
    local_authority_name = 8
    road_name = 9
    road_type = 10
    start_junction_road_name = 11
    end_junction_road_name = 12
    easting = 13
    northing = 14
    latitude = 15
    longitude = 16
    link_length_km = 17
    link_length_miles = 18
    pedal_cycles = 19
    two_wheeled_motor_vehicles = 20
    cars_and_taxis = 21
    buses_and_coaches = 22
    lgvs = 23
    hgvs_2_rigid_axle = 24
    hgvs_3_rigid_axle = 25
    hgvs_4_or_more_rigid_axle = 26
    hgvs_3_or_4_articulated_axle = 27
    hgvs_5_articulated_axle = 28
    hgvs_6_articulated_axle = 29
    all_hgvs = 30
    all_motor_vehicles = 31

Coord = Tuple[float, float]

@dataclass
class lane:
    id: str
    speed: float
    shape: List[Coord]
    allow: List[str]
    disallow: List[str]

@dataclass
class edge:
    id: str
    is_drivable: bool
    lanes: List[lane]

@dataclass
class count():
    hour: int
    value_sum: int
    value_count: int

@dataclass
class count_point():
    id: str
    road_name: str
    latitude: float
    longitude: float
    utm: any
    counts: List[count]
    closest_lane: Tuple[float, lane]

def aggregate_counts(count_point_: count_point, raw_count):

    for count_ in count_point_.counts:
        if (count_.hour == int(raw_count[p.hour.value])):
            # add count to average
            count_.value_sum += int(raw_count[p.cars_and_taxis.value])
            count_.value_count += 1
            return

    count_point_.counts.append(count(
        int(raw_count[p.hour.value]),
        int(raw_count[p.cars_and_taxis.value]),
        1
    ))

def run():


    ##########################################################################
    # Get name of target, and get it's position using google maps places api #
    ##########################################################################
    # target_name = input("Enter town name : ")
    target_name = "Bath"
    x = requests.get('https://maps.googleapis.com/maps/api/geocode/json?address=' + target_name + '&key=AIzaSyAhmPLZ2MEGQK1-7rTmyjbN_r6Pnqjr8YM')
    res = json.loads(x.text)

    target_geometry = res['results'][0]['geometry']
    target_bbox = target_geometry['viewport']
    m = folium.Map(location=[target_geometry['location']['lat'], target_geometry['location']['lng']])


    #################################################
    # Download osm data using bounding box of place #
    #################################################
    status = 504
    attempts = 1
    while (status == 504):
        if (attempts == 10):
            sys.exit('Took too many attempts to download osm data')
        print("Attempt {} to get osm data".format(attempts))
        bbox_str = ' '+str(target_bbox['southwest']['lng'])+','+str(target_bbox['southwest']['lat'])+','+str(target_bbox['northeast']['lng'])+','+str(target_bbox['northeast']['lat'])
        status = osmGet.get(['--bbox', bbox_str,
                    '--prefix', 'target',
                    '--output-dir', './temp'])
        attempts += 1


    ###################################################
    # Figure out which local authority the town is in #
    ###################################################
    with open('local_authorities.geojson', 'r') as myfile:
        local_authorities_raw = myfile.read()
    local_authorities = json.loads(local_authorities_raw)

    transformer = Transformer.from_crs("epsg:4326", "epsg:3857")
    target_position = Point(transformer.transform(target_geometry['location']['lat'], target_geometry['location']['lng']))
    local_authority_id = 0

    for local_authority in local_authorities['features']:
        multipolygon = shape(local_authority['geometry'])
        if multipolygon.contains(target_position):
            local_authority_id = local_authority['properties']['id']
            print("Found target area in " + local_authority['properties']['Name'])

    if (local_authority_id == 0):
        print("ERROR: could not find area in any british local authority")


    #####################################################
    # Get count point data for relevant local authority #
    #####################################################
    x = requests.get('https://storage.googleapis.com/dft-statistics/road-traffic/downloads/rawcount/local_authority_id/dft_rawcount_local_authority_id_' + str(local_authority_id) + '.csv');
    raw_counts = x.text.split('\n');
    raw_counts = list(csv.reader(raw_counts));
    list.pop(raw_counts);
    raw_counts.pop(0);


    #################################################################################
    # Reduce each count for a point at a certain time of day into one average value #
    #################################################################################
    # only include points from 2018
    raw_counts = [point for point in raw_counts if point[p.year.value]=='2018'];

    # now reduce all values to single averages for each time of day
    count_points: List[count_point] = []

    # reduce raw counts to average count at each count point
    for raw_count in raw_counts:

        count_point_id = raw_count[p.count_point_id.value];
        
        # need to define count_point if it hasn't been added yet
        if (count_point_id not in [point.id for point in count_points]):
            new_count_point = count_point(
                count_point_id,
                raw_count[p.road_name.value],
                float(raw_count[p.latitude.value]),
                float(raw_count[p.longitude.value]),
                utm.from_latlon(float(raw_count[p.latitude.value]), float(raw_count[p.longitude.value])),
                [],
                (-1, None)
            )
            aggregate_counts(new_count_point, raw_count)
            count_points.append(new_count_point)

        else:
            for count_point_ in count_points:
                if (count_point_.id == count_point_id):
                    aggregate_counts(count_point_, raw_count)


    ##################################
    # Write count_point data to file #
    ##################################
    with open('./temp/count_points.pkl', 'wb') as outp:
        for count_point_ in count_points:
            pickle.dump(count_point_, outp, pickle.HIGHEST_PROTOCOL)

if __name__ == '__main__':
    run()