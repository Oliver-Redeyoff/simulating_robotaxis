from typing import List, Tuple
import math

import folium
import xml.etree.ElementTree as ET
import utm
from tqdm import tqdm

from utilities import retrieve, store
from datatypes import lane, edge, count_point
    

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

def run():

    # Load count_points and edges
    edges: List[edge] = retrieve('../temp/edges.pkl')
    count_points: List[count_point] = retrieve('../temp/count_points.pkl')

    # find closest lane for each count_point
    for count_point_ in tqdm(count_points, desc='Filtering count points'):
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

    store(count_points, '../temp/filtered_count_points.pkl')

if __name__ == '__main__':
    run()