from typing import List
import subprocess
import xml.etree.ElementTree as ET

from tqdm import tqdm

from datatypes import Trip, Simulation
from utilities import create_dir, retrieve, indent, generate_config

def generate_trips_file(trips: List[Trip]):
    base_trips_root = ET.Element('routes')

    for trip in tqdm(trips, desc='Generating base.trips.xml'):
        ET.SubElement(base_trips_root, 'trip', {
                'id': str(trip.id), 
                'depart': str(trip.depart),
                'from': trip.from_,
                'to': trip.to
            })

    base_trips_tree = ET.ElementTree(base_trips_root)
    indent(base_trips_root)
    base_trips_tree.write('../temp/base.trips.xml', encoding='utf-8', xml_declaration=True)

    return '../temp/base.trips.xml'

def run():

    # Retrieve list of trips
    trips: List[Trip] = retrieve('../temp/trips.pkl')
    simulation: Simulation = retrieve('../temp/simulation.pkl')

    # Generate routes from trips using duarouter
    duarouter_options = ['duarouter',
                        '--net-file', '../temp/target.net.xml',
                        '--route-files', generate_trips_file(trips),
                        '--output-file', '../temp/' + simulation.base_routes_file,
                        '--ignore-errors', 'true',
                        '--repair', 'true',
                        '--unsorted-input', 'true',
                        '--no-warnings', 'true']
    subprocess.check_call(duarouter_options)

    # Run the simulation using the sumo program
    create_dir('../out')
    generate_config(simulation.net_file, simulation.base_routes_file, simulation.start_time, simulation.end_time, '../temp/base.sumocfg', True)
    sumo_options = ['sumo',
                    '--configuration-file', '../temp/base.sumocfg',
                    '--tripinfo-output', '../out/base.tripinfo.xml']
    subprocess.check_call(sumo_options)

if __name__ == '__main__':
    run()