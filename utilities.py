import os
import pickle
import xml.etree.ElementTree as ET

def create_dir(path):
    exists = os.path.exists(path)
    if not exists:
        os.makedirs(path)

def store(data, path):
    with open(path, 'wb') as outp:
        if (type(data) == list):
            for item in data:
                pickle.dump(item, outp, pickle.HIGHEST_PROTOCOL)
        else:
            pickle.dump(data, outp, pickle.HIGHEST_PROTOCOL)


def retrieve(path):
    object_list = []
    with (open(path, "rb")) as openfile:
        while True:
            try:
                object_list.append(pickle.load(openfile))
            except EOFError:
                break
    if (len(object_list) == 1):
        return object_list[0]
    else:
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

def generate_config(net_file: str, route_file: str, start_time: int, end_time: int, output_file: str):
    config_root = ET.Element("configuration")

    input_config = ET.SubElement(config_root, 'input')
    ET.SubElement(input_config, 'net-file', {'value': net_file})
    ET.SubElement(input_config, 'route-files', {'value': route_file})
    time_config = ET.SubElement(config_root, 'time')
    ET.SubElement(time_config, 'begin', {'value': str(start_time)})
    ET.SubElement(time_config, 'step-length', {'value': '1'})
    ET.SubElement(time_config, 'end', {'value': str(start_time)})
    processing_config = ET.SubElement(config_root, 'processing')
    ET.SubElement(processing_config, 'ignore-route-errors', {'value': 'true'})
    routing_config = ET.SubElement(config_root, 'processing')
    ET.SubElement(routing_config, 'persontrip.transfer.taxi-walk', {'value': 'allJunctions'})
    ET.SubElement(routing_config, 'persontrip.transfer.walk-taxi', {'value': 'allJunctions'})
    taxi_config = ET.SubElement(config_root, 'taxi-device')
    ET.SubElement(taxi_config, 'device.taxi.dispatch-algorithm', {'value': 'traci'})
    ET.SubElement(taxi_config, 'device.taxi.idle-algorithm', {'value': 'randomCircling'})
    ET.SubElement(taxi_config, 'device.taxi.dispatch-algorithm.output', {'value': './out/taxi_dispatch.xml'})

    config_tree = ET.ElementTree(config_root)
    indent(config_root)
    config_tree.write(output_file, encoding="utf-8", xml_declaration=True)

    return output_file