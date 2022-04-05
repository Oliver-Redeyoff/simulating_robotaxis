from typing import List
import subprocess

import xml.etree.ElementTree as ET
from tqdm import tqdm

from datatypes import trip, simulation
from utilities import create_dir, retrieve, indent, generate_config

def generate_trips_file(trips: List[trip]):
    base_trips_root = ET.Element('routes')

    for trip_ in tqdm(trips, desc='Generating base.trips.xml'):
        ET.SubElement(base_trips_root, 'trip', {
                'id': str(trip_.id), 
                'depart': str(trip_.depart),
                'from': trip_.from_,
                'to': trip_.to
            })

    base_trips_tree = ET.ElementTree(base_trips_root)
    indent(base_trips_root)
    base_trips_tree.write('../temp/base.trips.xml', encoding='utf-8', xml_declaration=True)

    return '../temp/base.trips.xml'

def run():

    # Retrieve list of trips
    trips: List[trip] = retrieve('../temp/trips.pkl')
    simulation_: simulation = retrieve('../temp/simulation.pkl')

    # Generate routes from trips using duarouter
    duarouter_options = ['duarouter',
                        '--net-file', '../temp/target.net.xml',
                        '--route-files', generate_trips_file(trips),
                        '--output-file', '../temp/' + simulation_.base_routes_file,
                        '--ignore-errors', 'true',
                        '--repair', 'true',
                        '--unsorted-input', 'true',
                        '--no-warnings', 'true']
    subprocess.check_call(duarouter_options)

    # Run the simulation using the sumo program
    create_dir('../out')
    generate_config(simulation_.net_file, simulation_.base_routes_file, simulation_.start_time, simulation_.end_time, '../temp/base.sumocfg')
    sumo_options = ['sumo',
                    '--configuration-file', '../temp/base.sumocfg',
                    # '--emission-output', './out/target.emissions.xml',
                    # '--statistic-output', './out/target.stats.xml',
                    '--tripinfo-output', '../out/base.tripinfo.xml']
    subprocess.check_call(sumo_options)

if __name__ == '__main__':
    run()