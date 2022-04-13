from typing import List
import csv
import os
import sys
import subprocess
import xml.etree.ElementTree as ET

from tqdm import tqdm

from datatypes import Lane, Edge, Simulation, Taz
from utilities import retrieve, store

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools/contributed/saga'))
    import generateTAZBuildingsFromOSM
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")


def normalise_shape(shape_str, origin):
    shape = [list(map(float, point.split(","))) for point in shape_str.split(" ")]
    for point in shape:
        point[0] += origin[0]
        point[1] += origin[1]

    return shape

def run():

    simulation: Simulation = retrieve('../temp/simulation.pkl')

    # Generate sumo network
    netconvert_options = ['netconvert',
                        '--osm', '../temp/osm_bbox.osm.xml',
                        '--o', '../temp/' + simulation.net_file,
                        '--geometry.remove', 'true',
                        '--ramps.guess', 'true',
                        '--junctions.join', 'true',
                        '--tls.guess-signals', 'true',
                        '--tls.discard-simple', 'true',
                        '--tls.join', 'true',
                        '--tls.default-type', 'actuated',
                        '--lefthand', 'true',
                        '--edges.join', 'true',
                        '--remove-edges.isolated', 'true']
    subprocess.check_call(netconvert_options)

    # Deduce TAZs using the saga tool
    saga_options = ['--osm', '../temp/osm_bbox.osm.xml',
                '--net', '../temp/' + simulation.net_file,
                '--taz-output', '../temp/osm_taz.xml',
                '--weight-output', '../temp/osm_taz_weight.csv',
                '--poly-output', '../temp/poly.xml']
    generateTAZBuildingsFromOSM.main(saga_options)
    
    # Extract all edges and their UTM position
    net_tree = ET.parse('../temp/' + simulation.net_file)
    net_root = net_tree.getroot()

    # Get origin UTM position
    temp1 = net_root[0].attrib['projParameter'].split(' ')
    utm_zone = int(temp1[1].split('=')[1])

    origin = net_root[0].attrib['netOffset'].split(',')
    origin = [-1*float(coord) for coord in origin]

    edges: List[Edge] = []

    for edge_element in tqdm(net_root.findall('edge'), desc='Extracting lanes from network'):

        # Instantiate new edge
        new_edge = Edge(
            edge_element.attrib['id'],
            False,
            []
        )

        # Instantiate all new lanes
        for lane_element in edge_element.findall('lane'):
            new_lane = Lane(
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


    # Retrieve tazs and their weights
    tazs: List[Taz] = []

    taz_tree = ET.parse('../temp/osm_taz.xml')
    taz_root = taz_tree.getroot()

    drivable_edges = set([edge_.id for edge_ in edges if edge_.is_drivable])

    # Instantiate tazs
    for taz in tqdm(taz_root, desc='Generating tazs'):
        tazs.append(Taz(
            taz.attrib['id'],
            '',
            taz.attrib['edges'].split(' '),
            list(drivable_edges.intersection(set(taz.attrib['edges'].split(' ')))),
            0,
            0,
            0
        ))

    with open('../temp/osm_taz_weight.csv', mode='r') as csv_taz_weights:
        csv_reader = csv.DictReader(csv_taz_weights)
        for row in csv_reader:
            taz = next(taz for taz in tazs if taz.id == row['TAZ'])
            taz.name = row['Name']
            taz.node_count = int(row['#Nodes'])
            taz.area = float(row['Area'])

    # Filter out taz which don't have any drivable edges
    tazs = [taz for taz in tazs if len(taz.drivable_edges)>0]

    taz_total_node_count = sum(taz.node_count for taz in tazs)
    for taz in tazs:
        taz.weight = taz.node_count/taz_total_node_count

    # Write taz data data to file
    store(tazs, '../temp/tazs.pkl')

    # Write edges and drivable edges data to file
    store(edges, '../temp/edges.pkl')
    store(drivable_edges, '../temp/drivable_edges.pkl')
            

if __name__ == '__main__':
    run()