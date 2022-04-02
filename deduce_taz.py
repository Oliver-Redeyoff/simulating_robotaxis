# Import relevant libraries

import shutil
from typing import List
import csv
import os
import sys

import xml.etree.ElementTree as ET
from tqdm import tqdm

from utilities import store
from datatypes import lane, edge, taz

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools/contributed/saga'))
    import scenarioFromOSM
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")


def normalise_shape(shape_str, origin):
    shape = [list(map(float, point.split(","))) for point in shape_str.split(" ")]
    for point in shape:
        point[0] += origin[0]
        point[1] += origin[1]

    return shape

def run():

    #############################################################
    # Generate sumo network and deduce TAZs using the saga tool #
    #############################################################
    saga_options = ['--osm', './temp/target_bbox.osm.xml',
                '--out', './temp_saga',
                '--from-step', str(0),
                '--to-step', str(7),
                '--lefthand']
                
    scenarioFromOSM.main(saga_options)

    os.chdir('..')

    shutil.copyfile('./temp_saga/osm.net.xml', './temp/target.net.xml')

    
    ############################################
    # Extract all edges and their UTM position #
    ############################################
    net_tree = ET.parse('./temp/target.net.xml')
    net_root = net_tree.getroot()

    # get origin UTM position
    temp1 = net_root[0].attrib['projParameter'].split(' ')
    utm_zone = int(temp1[1].split('=')[1])

    origin = net_root[0].attrib['netOffset'].split(',')
    origin = [-1*float(coord) for coord in origin]

    edges: List[edge] = []

    for edge_element in tqdm(net_root.findall('edge'), desc='Extracting lanes from network'):

        # instantiate new edge
        new_edge = edge(
            edge_element.attrib['id'],
            False,
            []
        )

        # instantiate all new lanes
        for lane_element in edge_element.findall('lane'):
            new_lane = lane(
                lane_element.attrib['id'],
                float(lane_element.attrib['speed']),
                normalise_shape(lane_element.attrib['shape'], origin),
                lane_element.attrib['allow'].split(' ') if 'allow' in lane_element.attrib else [],
                lane_element.attrib['disallow'].split(' ') if 'disallow' in lane_element.attrib else []
            )
            if (new_lane.allow and 'passenger' in new_lane.allow):
                    new_edge.is_drivable = True
            elif (new_lane.disallow and 'passenger' not in new_lane.disallow):
                new_edge.is_drivable = True
            new_edge.lanes.append(new_lane)
        
        edges.append(new_edge)


    ###################################
    # Retrieve tazs and their weights #
    ###################################
    tazs: List[taz] = []

    taz_tree = ET.parse('./temp_saga/osm_taz.xml')
    taz_root = taz_tree.getroot()
    taz_total_weight = 0

    drivable_edges = set([edge_.id for edge_ in edges if edge_.is_drivable])

    # instantiate tazs
    for taz_ in tqdm(taz_root, desc='Generating tazs'):
        tazs.append(taz(
            taz_.attrib['id'],
            '',
            taz_.attrib['edges'].split(' '),
            list(drivable_edges.intersection(set(taz_.attrib['edges'].split(' ')))),
            0,
            0,
            0
        ))

    with open('./temp_saga/osm_taz_weight.csv', mode='r') as csv_taz_weights:
        csv_reader = csv.DictReader(csv_taz_weights)
        line_count = 0
        for row in csv_reader:
            taz_ = next(taz_ for taz_ in tazs if taz_.id == row['TAZ'])
            taz_.name = row['Name']
            taz_.node_count = int(row['#Nodes'])
            taz_.area = float(row['Area'])

    # filter out taz which don't have any drivable edges
    tazs = [taz_ for taz_ in tazs if len(taz_.drivable_edges)>0]

    taz_total_node_count = sum(taz_.node_count for taz_ in tazs)
    for taz_ in tazs:
        taz_.weight = taz_.node_count/taz_total_node_count

    ###############################
    # Write taz data data to file #
    ###############################
    store(tazs, './temp/tazs.pkl')

    ###############################################
    # Write edges and drivable edges data to file #
    ###############################################
    store(edges, './temp/edges.pkl')
    store(drivable_edges, './temp/drivable_edges.pkl')
            

if __name__ == '__main__':
    run()