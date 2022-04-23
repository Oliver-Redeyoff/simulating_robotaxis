from typing import List
import math
import random
import os
import sys
from matplotlib import pyplot as plt
import xml.etree.ElementTree as ET

from tqdm import tqdm

from datatypes import CountPoint, Edge, Taz, Simulation, Trip, Driver
from utilities import retrieve, store, generate_config, indent

# We need to import python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    from sumolib import checkBinary
    import traci
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")


def generate_temp_route_file():
    temp_routes_root = ET.Element('routes')

    taxi_def = ET.SubElement(temp_routes_root, 'vType', {
        'id': 'taxi',
        'vClass': 'taxi',
        'personCapacity': '8'
    })
    ET.SubElement(taxi_def, 'param', {
        'key': 'has.taxi.device',
        'value': 'true'
    })

    temp_trips_tree = ET.ElementTree(temp_routes_root)
    indent(temp_routes_root)
    temp_trips_tree.write('../temp/temp.routes.xml', encoding='utf-8', xml_declaration=True)
    return '../temp/temp.routes.xml'

def get_random_drivable_edge(tazs, edges, drivable_edges) -> Edge:
    if (random.random() <= 0.5):
        rand = random.random()
        ac_weight = 0
        for taz in tazs:
            ac_weight += taz.weight
            if (rand <= ac_weight):
                edge_id = random.choice(taz.drivable_edges)
                return next(edge for edge in edges if edge.id == edge_id)
    else:
        edge_id = random.choice(list(drivable_edges))
        return next(edge for edge in edges if edge.id == edge_id)

def run():

    # Retrieve data
    count_points: List[CountPoint] = retrieve('../temp/filtered_count_points.pkl')
    tazs: List[Taz] = retrieve('../temp/tazs.pkl')
    edges: List[Edge] = retrieve('../temp/edges.pkl')
    drivable_edges: List[str] = retrieve('../temp/drivable_edges.pkl')
    simulation: Simulation = retrieve('../temp/simulation.pkl')

    
    # Start sumo
    generate_config(simulation.net_file, generate_temp_route_file(), simulation.start_time, simulation.end_time, '../temp/temp.sumocfg', True)
    sumoBinary = checkBinary('sumo')
    traci.start([sumoBinary, "-c", '../temp/temp.sumocfg'])
    traci.simulationStep()


    # Calculate traffic distribution based on count point data
    aggregated_counts = [{'sum': 0, 'count': 0, 'average': 0, 'distribution_value': 0} for i in range(1, 23)];

    # Aggregate count point data by time
    for count_point in count_points:
        for count in count_point.counts:
            hour = count.hour

            if (hour < simulation.start_hour):
                simulation.start_hour = hour
            if (hour > simulation.end_hour):
                simulation.end_hour = hour

            aggregated_counts[count.hour]['sum'] += count.value_sum
            aggregated_counts[count.hour]['count'] += count.value_count
    
    simulation.start_time = simulation.start_hour*3600-200
    simulation.end_time = simulation.end_hour*3600

    # Calculate distribution from aggregated data
    total = 0;
    for hour_count in aggregated_counts:
        if hour_count['count'] != 0:
            hour_count['average'] = hour_count['sum']/hour_count['count']
            total += hour_count['average']

    for _, hour_count in enumerate(aggregated_counts):
        if hour_count['count'] != 0:
            hour_count['distribution_value'] = hour_count['average']/total

    # plt.plot([count['distribution_value'] for count in aggregated_counts])
    # plt.show()


    # Generate drivers
    driver_percentage = 0.33
    total_drivers = round(simulation.city.population*driver_percentage)
    total_trips = total_drivers*2

    drivers: List[Driver] = [Driver('', '', None, None) for i in range(total_drivers)]
    for driver in tqdm(drivers, desc='Generating drivers'):
        route_is_possible = False
        while not route_is_possible:

            # Retrieve two random distinct edges
            start_edge = get_random_drivable_edge(tazs, edges, drivable_edges)
            end_edge = get_random_drivable_edge(tazs, edges, drivable_edges)
            if (start_edge == end_edge):
                continue

            # Check that it is possible to travel to each point from the other
            route_1 = traci.simulation.findRoute(start_edge.id, end_edge.id, vType='taxi')
            route_2 = traci.simulation.findRoute(end_edge.id, start_edge.id, vType='taxi')

            if (route_1.length != 0 and route_2.length != 0):
                route_is_possible = True
                driver.home_edge = start_edge
                driver.destination_edge = end_edge

    
    # Generate trips
    # For each hour, generate trips
    trip_id = 0
    for hour in tqdm(range(simulation.start_hour, simulation.end_hour+1), desc='Generating trips'):
        trip_count = math.floor(total_trips * aggregated_counts[hour]['distribution_value'])
        generated_trip_count = 0
        processed_drivers = []

        while generated_trip_count != trip_count:
            driver = random.choice(drivers)
            if (driver in processed_drivers):
                continue
            
            if (driver.trip1 == None):
                driver.trip1 = Trip(
                    trip_id,
                    float(hour*3600 + round(random.random()*3600)),
                    driver.home_edge.id,
                    driver.destination_edge.id
                )
            elif (driver.trip2 == None):
                driver.trip2 = Trip(
                    trip_id,
                    float(hour*3600 + round(random.random()*3600)),
                    driver.destination_edge.id,
                    driver.home_edge.id
                )
            else:
                continue

            generated_trip_count += 1
            trip_id += 1

    trips: List[Trip] = []
    trips.extend([driver.trip1 for driver in drivers if driver.trip1 != None])
    trips.extend([driver.trip2 for driver in drivers if driver.trip2 != None])
    trips.sort()


    # Store trips and simulation in file
    store(trips, '../temp/trips.pkl')
    store(simulation, '../temp/simulation.pkl')

    traci.close()
        

if __name__ == '__main__':
    run()