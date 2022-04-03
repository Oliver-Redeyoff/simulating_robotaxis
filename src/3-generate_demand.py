# Import relevant libraries

from typing import List
import math
import random
import os
import sys

import xml.etree.ElementTree as ET
from tqdm import tqdm

from datatypes import edge, simulation, trip, commuter
from utilities import retrieve, store

# we need to import python modules from the $SUMO_HOME/tools directory
if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
    from sumolib.net import readNet
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")


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

    count_points = retrieve('../temp/filtered_count_points.pkl')
    tazs = retrieve('../temp/tazs.pkl')
    edges = retrieve('../temp/edges.pkl')
    drivable_edges = retrieve('../temp/drivable_edges.pkl')

    net = readNet('../temp/target.net.xml', withInternal=True)


    ############################################################
    # Calculate traffic distribution based on count point data #
    ############################################################

    simulation_ = simulation(
        23, 
        0,
        0, 
        0,
        'target.net.xml',
        'base.routes.xml',
        'taxi.routes.xml')

    aggregated_counts = [{'sum': 0, 'count': 0, 'average': 0, 'distribution_value': 0} for i in range(1, 23)];

    # aggregate count point data by time
    for count_point_ in count_points:
        for count_ in count_point_.counts:
            hour = count_.hour

            if (hour < simulation_.start_hour):
                simulation_.start_hour = hour
            if (hour > simulation_.end_hour):
                simulation_.end_hour = hour

            aggregated_counts[count_.hour]['sum'] += count_.value_sum
            aggregated_counts[count_.hour]['count'] += count_.value_count
    
    simulation_.start_time = simulation_.start_hour*3600-200
    simulation_.end_time = simulation_.end_hour*3600

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
    for commuter_ in tqdm(commuters, desc='Generating commuters'):
        route_is_possible = False
        while not route_is_possible:
            start_edge = get_random_drivable_edge(tazs, edges, drivable_edges)
            end_edge = get_random_drivable_edge(tazs, edges, drivable_edges)

            start_sumo_edge = net.getEdge(start_edge.id)
            end_sumo_edge = net.getEdge(end_edge.id)

            shortestPath = net.getShortestPath(start_sumo_edge, end_sumo_edge, vClass="taxi")
            
            if (shortestPath[0] != None):
                route_is_possible = True
                commuter_.home_edge = start_edge
                commuter_.destination_edge = end_edge

    
    ##################
    # Generate trips #
    ##################

    # For each hour, generate trips
    trip_id = 0
    for hour in tqdm(range(simulation_.start_hour, simulation_.end_hour+1), desc='Generating trips'):
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

    trips: List[trip] = []
    trips.extend([commuter_.trip1 for commuter_ in commuters if commuter_.trip1 != None])
    trips.extend([commuter_.trip2 for commuter_ in commuters if commuter_.trip2 != None])
    trips.sort()

    ######################################
    # Store trips and simulation in file #
    ######################################
    store(trips, '../temp/trips.pkl')
    store(simulation_, '../temp/simulation.pkl')
        

if __name__ == '__main__':
    run()