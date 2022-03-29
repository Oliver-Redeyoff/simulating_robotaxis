# Import relevant libraries

from dataclasses import dataclass
from typing import List, Tuple
import math
import subprocess
import random
import pickle

import xml.etree.ElementTree as ET
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

@dataclass
class taz:
    id: str
    name: str
    edges: List[str]
    drivable_edges: List[str]
    node_count: int
    weight: float
    area: float

@dataclass
class simulation:
    start_time: int
    end_time: int
    duration: int

@dataclass
class trip:
    id: int
    depart: float
    from_: str
    to: str
    def __lt__(self, other):
         return self.depart < other.depart

@dataclass
class commuter:
    home_edge: edge
    destination_edge: edge
    trip1: trip
    trip2: trip

@dataclass
class tripinfo:
    trip_id: int
    duration: float
    waiting_time: float


def get_pickle(name):
    object_list = []
    with (open(name, "rb")) as openfile:
        while True:
            try:
                object_list.append(pickle.load(openfile))
            except EOFError:
                break
    return object_list

def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def get_random_drivable_edge(tazs, edges, drivable_edges) -> edge:
    if (random.random() <= 0.5):
        rand = random.random()
        ac_weight = 0
        for taz_ in tazs:
            ac_weight += taz_.weight
            if (rand <= ac_weight):
                edge_id = random.choice(taz_.drivable_edges)
                return next(edge_ for edge_ in edges if edge_.id == edge_id)
    else:
        edge_id = random.choice(list(drivable_edges))
        return next(edge_ for edge_ in edges if edge_.id == edge_id)

def run():

    #################
    # Retrieve data #
    #################

    count_points = get_pickle('./temp/count_points.pkl')
    tazs = get_pickle('./temp/tazs.pkl')
    edges = get_pickle('./temp/edges.pkl')
    drivable_edges = get_pickle('./temp/drivable_edges.pkl')


    ############################################################
    # Calculate traffic distribution based on count point data #
    ############################################################

    simulation_ = simulation(23, 0, 0)

    aggregated_counts = [{'sum': 0, 'count': 0, 'average': 0, 'distribution_value': 0} for i in range(1, 23)];

    # aggregate count point data by time
    for count_point_ in count_points:
        for count_ in count_point_.counts:
            hour = count_.hour

            if (hour < simulation_.start_time):
                simulation_.start_time = hour
            if (hour > simulation_.end_time):
                simulation_.end_time = hour

            aggregated_counts[count_.hour]['sum'] += count_.value_sum
            aggregated_counts[count_.hour]['count'] += count_.value_count

    simulation_.duration = (simulation_.end_time-simulation_.start_time)*3600

    # calculate distribution from aggregated data
    total = 0;
    for hour_count in aggregated_counts:
        if hour_count['count'] != 0:
            hour_count['average'] = hour_count['sum']/hour_count['count']
            total += hour_count['average']

    for idx, hour_count in enumerate(aggregated_counts):
        if hour_count['count'] != 0:
            hour_count['distribution_value'] = hour_count['average']/total

    # plt.plot([count['distribution_value'] for count in aggregated_counts])
    # plt.show()


    ######################
    # Generate commuters #
    ######################
            
    population = 100000
    commuter_percentage = 0.25
    total_commuters = round(population*commuter_percentage)
    total_trips = total_commuters*2

    commuters: List[commuter] = [commuter('', '', None, None) for i in range(total_commuters)]
    for commuter_ in tqdm(commuters):
        commuter_.home_edge = get_random_drivable_edge(tazs, edges, drivable_edges)
        commuter_.destination_edge = get_random_drivable_edge(tazs, edges, drivable_edges)

    
    ##################
    # Generate trips #
    ##################

    # For each hour, generate trips
    trip_id = 0
    for hour in tqdm(range(simulation_.start_time, simulation_.end_time+1)):
        trip_count = math.floor(total_trips * aggregated_counts[hour]['distribution_value'])
        generated_trip_count = 0
        processed_commuters = []

        while generated_trip_count != trip_count:
            commuter_ = random.choice(commuters)
            if (commuter_ in processed_commuters):
                continue
            
            if (commuter_.trip1 == None):
                commuter_.trip1 = trip(
                    trip_id,
                    float(hour*3600 + round(random.random()*3600)),
                    commuter_.home_edge.id,
                    commuter_.destination_edge.id
                )
            elif (commuter_.trip2 == None):
                commuter_.trip2 = trip(
                    trip_id,
                    float(hour*3600 + round(random.random()*3600)),
                    commuter_.destination_edge.id,
                    commuter_.home_edge.id
                )
            else:
                continue

            generated_trip_count += 1
            trip_id += 1


    #######################
    # Store trips in file #
    #######################

    base_routes_root = ET.Element("routes")

    for commuter_ in tqdm(commuters):
        if(commuter_.trip1):
            ET.SubElement(base_routes_root, 'trip', {
                'id': str(commuter_.trip1.id), 
                'depart': str(commuter_.trip1.depart),
                'from': commuter_.trip1.from_,
                'to': commuter_.trip1.to
            })
        if(commuter_.trip2):
            ET.SubElement(base_routes_root, 'trip', {
                'id': str(commuter_.trip2.id), 
                'depart': str(commuter_.trip2.depart),
                'from': commuter_.trip2.from_,
                'to': commuter_.trip2.to
            })

    base_routes_tree = ET.ElementTree(base_routes_root)
    indent(base_routes_root)
    base_routes_tree.write("./temp/base.trips.xml", encoding="utf-8", xml_declaration=True)


    #################################################
    # Generate base routes using the duarouter tool #
    #################################################

    duarouter_options = ['duarouter',
                        '--net-file', './temp/target.net.xml',
                        '--route-files', './temp/base.trips.xml',
                        '--output-file', './temp/base.routes.xml',
                        '--ignore-errors', 'true',
                        '--repair', 'true',
                        '--unsorted-input', 'true',
                        '--no-warnings', 'true']
                        
    subprocess.check_call(duarouter_options)


    #####################################
    # Generate taxi mobility definition #
    #####################################

    taxi_count = 0

    taxi_routes_root = ET.Element("routes")

    taxi_def = ET.SubElement(taxi_routes_root, 'vType', {
        'id': 'route_0',
        'edges': random.choice(list(drivable_edges))
    })
    ET.SubElement(taxi_routes_root, 'route', {
        'id': 'taxi',
        'vClass': 'taxi'
    })
    ET.SubElement(taxi_def, 'param', {
        'key': 'has.taxi.device',
        'value': 'true'
    })

    all_trips: List[trip] = []
    all_trips.extend([commuter_.trip1 for commuter_ in commuters if commuter_.trip1 != None])
    all_trips.extend([commuter_.trip2 for commuter_ in commuters if commuter_.trip2 != None])
    all_trips.sort()

    for taxi_id in range(taxi_count):
        taxi_vehicle = ET.SubElement(taxi_routes_root, 'vehicle', {
            'id': 'v'+str(taxi_id), 
            'depart': str(simulation_.start_time*3600) + '.00',
            'type': 'taxi',
            'line': 'taxi'
        })
        ET.SubElement(taxi_vehicle, 'route', {
            'edges': random.choice(list(drivable_edges))
        })

    person_id = 0
    # for trip_ in tqdm(all_trips):
    #     taxi_vehicle = ET.SubElement(taxi_routes_root, 'person', {
    #         'id': 'p'+str(person_id), 
    #         'depart': str(trip_.depart),
    #         'color': 'green'
    #     })
    #     ET.SubElement(taxi_vehicle, 'ride', {
    #         'from': trip_.from_,
    #         'to': trip_.to,
    #         'lines': 'taxi'
    #     })
    #     person_id += 1

    taxi_vehicle = ET.SubElement(taxi_routes_root, 'person', {
        'id': 'p'+str(person_id), 
        'depart': str(all_trips[0].depart),
        'color': 'green'
    })
    ET.SubElement(taxi_vehicle, 'ride', {
        'from': all_trips[0].from_,
        'to': all_trips[0].to,
        'lines': 'taxi'
    })

    taxi_routes_tree = ET.ElementTree(taxi_routes_root)
    indent(taxi_routes_root)
    taxi_routes_tree.write("./temp/taxi.trips.xml", encoding="utf-8", xml_declaration=True)
        

if __name__ == '__main__':
    run()