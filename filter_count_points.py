# Import relevant libraries

from dataclasses import dataclass
from typing import List, Tuple
import math
import pickle

import folium
import xml.etree.ElementTree as ET
import utm
from tqdm import tqdm

# Declare dataclasses

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
    

# Get distance from count_point to to lane
def min_dist_to_lane(lane_: lane, count_point_: count_point) -> float:

    min_dist = -1;

    for i in range(1, len(lane_.shape)):
        x = count_point_.utm[0];
        y = count_point_.utm[1];
        x1 = lane_.shape[i-1][0];
        y1 = lane_.shape[i-1][1];
        x2 = lane_.shape[i][0];
        y2 = lane_.shape[i][1];

        A = x - x1;
        B = y - y1;
        C = x2 - x1;
        D = y2 - y1;

        dot = A * C + B * D;
        len_sq = C * C + D * D;
        param = -1;
        if (len_sq != 0):
            param = dot / len_sq;

        xx = 0.0;
        yy = 0.0;

        if (param < 0):
            xx = x1;
            yy = y1;
        elif (param > 1):
            xx = x2;
            yy = y2;
        else:
            xx = x1 + param * C;
            yy = y1 + param * D;

        dx = x - xx;
        dy = y - yy;
        dist = math.sqrt(dx * dx + dy * dy);

        if (min_dist == -1 or dist<min_dist):
            min_dist = dist;
    
    return min_dist;

def get_pickle(name):
    object_list = []
    with (open(name, "rb")) as openfile:
        while True:
            try:
                object_list.append(pickle.load(openfile))
            except EOFError:
                break
    return object_list

def run():

    # Load count_points and edges
    edges: List[edge] = get_pickle('./temp/edges.pkl')
    count_points: List[count_point] = get_pickle('./temp/count_points.pkl')

    # find closest lane for each count_point
    for count_point_ in tqdm(count_points):
        closest_lane: Tuple[float, lane] = (-1, None)
        
        for edge_ in edges:
            for lane_ in edge_.lanes:
                dist = min_dist_to_lane(lane_, count_point_)
                if (closest_lane[0] == -1 or dist<closest_lane[0]):
                    closest_lane = (dist, lane_)
        
        count_point_.closest_lane = closest_lane

    # filter out count points which are more that 10 metres away from the closest lane
    count_points = [count_point_ for count_point_ in count_points if count_point_.closest_lane[0]<10]

    # place markers for each counting point on map
    # for count_point_ in count_points:
    #     folium.Marker([float(count_point_.latitude), float(count_point_.longitude)], popup=count_point_.id, icon=folium.Icon(color="red")).add_to(m)

    # m

    with open('./temp/filtered_count_points.pkl', 'wb') as outp:
        for count_point_ in count_points:
            pickle.dump(count_point_, outp, pickle.HIGHEST_PROTOCOL)

if __name__ == '__main__':
    run()