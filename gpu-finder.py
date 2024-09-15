#!/usr/bin/env python

# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Example of using the Compute Engine API to create and delete instances.
Creates a new compute engine instance and uses it to apply a caption to
an image.
    https://cloud.google.com/compute/docs/tutorials/python-guide
For more information, see the README.md under /compute.
"""

import time
import json
import googleapiclient.discovery

def check_gpu_config(config):
    compute_config = config
    if compute_config['instance_config']['machine_type'].startswith('a2'):
        number_of_gpus_requested = compute_config['instance_config']['number_of_gpus']
        gpus_in_machine_type = compute_config['instance_config']['machine_type'][(compute_config['instance_config']['machine_type'].find('highgpu')+8):(len(compute_config['instance_config']['machine_type'])-1)]
        if number_of_gpus_requested != int(gpus_in_machine_type):
            raise Exception("Please match the number of GPUs parameter with the correct machine type in the config file")

def get_zone_info(compute, project):
    zone_list = []
    request = compute.zones().list(project=project)
    while request is not None:
        response = request.execute()
        for zone in response['items']:
            if zone['status'] == 'UP':
                zone_regions = {
                    'region': zone['name'][0:len(zone['name'])-2],
                    'zone': zone['name']
                }
                zone_list.append(zone_regions)
        request = compute.zones().list_next(previous_request=request, previous_response=response)
    return zone_list

def check_machine_type_and_accelerator(compute, project, machine_type, gpu_type, zones):
    zone_list = zones
    available_zones = []
    for zone in zone_list:
        request = compute.machineTypes().list(project=project, zone=zone['zone'])
        while request is not None:
            response = request.execute()
            for machine in response['items']:
                if 'accelerators' in machine and machine['name'] == machine_type and machine['accelerators'][0]['guestAcceleratorType'] == gpu_type:
                    zones_with_instances = {
                        'machine_type': machine['name'],
                        'region': zone['region'],
                        'zone': zone['zone'],
                        'guest_cpus': machine['guestCpus'],
                        'description': machine['description'],
                        'accelerators': machine['accelerators']
                    }
                    available_zones.append(zones_with_instances)
                elif machine['name'] == machine_type:
                    zones_with_instances = {
                        'machine_type': machine['name'],
                        'region': zone['region'],
                        'zone': zone['zone'],
                        'guest_cpus': machine['guestCpus'],
                        'description': machine['description']
                    }
                    available_zones.append(zones_with_instances)
            request = compute.machineTypes().list_next(previous_request=request, previous_response=response)
    if not available_zones:
        raise Exception(f"No machine types of {machine_type} are available")
    return available_zones

def get_accelerator_quota(compute, project, config, zone, requested_gpus):
    zone_list = zone
    accelerator_list = []
    for i in zone_list:
        request = compute.acceleratorTypes().list(project=project, zone=i['zone'])
        while request is not None:
            response = request.execute()
            if 'items' in response:
                for accelerator in response['items']:
                    if accelerator['name'] == config['instance_config']['gpu_type']:
                        if requested_gpus <= accelerator['maximumCardsPerInstance']:
                            accelerator_dict = {
                                "region": i['region'],
                                "zone": i['zone'],
                                "machine_type": i['machine_type'],
                                "guest_cpus": i['guest_cpus'],
                                "name": accelerator['name'],
                                "description": accelerator['description'],
                                "maximum number of GPUs per instance": accelerator['maximumCardsPerInstance']
                            }
                            accelerator_list.append(accelerator_dict)
                            print(f"{requested_gpus} GPUs requested per instance, {i['zone']} has {accelerator['name']} GPUs with a maximum of {accelerator['maximumCardsPerInstance']} per instance")
                        else:
                            print(
                                f"{requested_gpus} GPUs requested per instance, {i['zone']} doesn't have enough GPUs, with a maximum of {accelerator['maximumCardsPerInstance']} per instance")
            request = compute.acceleratorTypes().list_next(previous_request=request, previous_response=response)
    if not accelerator_list:
        raise Exception(f"No accelerator types of {config['instance_config']['gpu_type']} are available with {config['instance_config']['machine_type']} in any zone, or wrong number of GPUs requested")
    return accelerator_list


def create_instance(compute, project, config, zone_list):
    compute_config = config
    regions_to_try = list({v['region'] for v in zone_list})
    created_instances = []
    instances = 0
    regions_attempted = 0
    print(f"There are {len(regions_to_try)} regions to try that match the GPU type and machine type configuration.")

    for region in regions_to_try:
        print(f"Attempting to create instances in {region}")
        zones = [z for z in zone_list if z['region'] == region]
        print(f"There are {len(zones)} zones to try in {region}")
        zones_attempted = 0
        move_regions = 0

        for i in range(len(zones)): 
            zone_config = zones[i]

        # Get the single gpu_type from config (assuming you've fixed this in gpu_config.json)
        gpu_type = config['instance_config']['gpu_type']

        # Check if there's a specific machine type for this GPU
        machine_type = config['instance_config'].get('gpu_machine_type_mapping', {}).get(gpu_type)
        if machine_type:
            compute_config['instance_config']['machine_type'] = machine_type
        else:
            # If no specific mapping, use the default machine type
            compute_config['instance_config']['machine_type'] = config['instance_config']['machine_type']

        for j in range(compute_config['number_of_instances']):
            # ... (rest of your instance creation logic)

            # Handle potential empty or invalid instance_name
            instance_name = compute_config['instance_config']['name'] + '-' + str(instances + 1) + '-' + zone_config['zone']
            if not instance_name or not instance_name.strip(): 
                print("Error: Invalid instance name. Skipping this iteration.")
                continue  # Skip to the next iteration

                print(f"Creating instance {instance_name}.")
                try:
                    operation = compute.instances().insert(
                        project=project,
                        zone=zone_config['zone'],
                        body=config).execute()

                    print('Waiting for operation to finish...') 

                    while True:
                        result = compute.zoneOperations().get(
                            project=project,
                            zone=zone_config['zone'],
                            operation=operation['name']).execute()

                        if result['status'] == 'DONE':
                            print("done.")
                            if 'error' in result: 

                                raise Exception(result['error'])
                            else:
                                instances += 1
                                move_regions = 0
                                print(f"Success: {instance_name} created")
                                print(f"{instances} created, {compute_config['number_of_instances'] - instances} more to create")
                                instance_details = {
                                    "name": instance_name,
                                    "zone": zone_config['zone']
                                }
                                created_instances.append(instance_details)
                                break 
  # Exit the inner loop if instance creation is successful

                except googleapiclient.errors.HttpError as e:
                    if e.resp.status == 403:
                        print(f"Error creating instance: {e}")
                        if "Quota exceeded" in str(e):
                            move_regions = 1
                            print(f"Quota exceeded in region {region}, moving to next region")
                            break  # Exit the inner loop and move to the next region
                    else:
                        raise e  # Re-raise other HttpErrors

                if instances >= compute_config['number_of_instances']:
                    print(f"Reached the desired number of instances")
                    break
                elif move_regions == 1:
                    print(f"Quota exceeded in region {region}, moving to next region")
                    break
                zones_attempted += 1

        regions_attempted += 1
        if instances >= compute_config['number_of_instances']:
            break
        elif regions_attempted >= len(regions_to_try):
            print(f"All regions attempted, there are not enough resources to create the desired {compute_config['number_of_instances']} instances, {instances} created")
            break

    return created_instances

    time.sleep(1)

def delete_instance(compute, project, instance_details):
    instances = instance_details
    print(f"Deleting {len(instances)} instances.")
    for i in range(len(instances)):
        instance = instances[i]
        zone = instance["zone"]
        name = instance["name"]

        print(f"Deleting instance {name}.")
        operation = compute.instances().delete(
            project=project,
            zone=zone,
            instance=name).execute()

        print('Waiting for operation to finish...')
        while True:
            result = compute.zoneOperations().get(
                project=project,
                zone=zone,
                operation=operation['name']).execute()

            if result['status'] == 'DONE':
                print("done.")
                if 'error' in result:
                    raise Exception(result['error'])
                break

def create_instance_test(compute, project, config, zone, requested_gpus):
    zone_list = zone
    accelerator_list = []
    for i in zone_list:
        request = compute.acceleratorTypes().list(project=project, zone=i['zone'])
        while request is not None:
            response = request.execute()
            if 'items' in response:
                for accelerator in response['items']:
                    print(accelerator)

 
def main(gpu_config, wait=True):
    compute = googleapiclient.discovery.build('compute', 'v1')
    if gpu_config["instance_config"]["zone"]:
        print(f"Processing selected zones from {gpu_config['instance_config']['zone']}")
        zone_info = get_zone_info(compute, gpu_config["project_id"])
        compute_zones = [z for z in zone_info if z['zone'] in gpu_config['instance_config']['zone']]
    else:
        print("Processing all zones")
        compute_zones = get_zone_info(compute, gpu_config["project_id"])
    check_gpu_config(gpu_config)
    # distinct_zones = list({v['zone'] for v in compute_zones})
    available_zones = check_machine_type_and_accelerator(compute, gpu_config["project_id"], gpu_config["instance_config"]["machine_type"], gpu_config["instance_config"]["gpu_type"], compute_zones)
    accelerators = get_accelerator_quota(compute, gpu_config["project_id"], gpu_config, available_zones, gpu_config["instance_config"]["number_of_gpus"])
    available_regions = list({v['region'] for v in available_zones})
    if available_regions:
        print(f"Machine type {gpu_config['instance_config']['machine_type']} is available in the following regions: {available_regions}")
        instance_details = create_instance(compute, gpu_config["project_id"], gpu_config, accelerators)
        if wait:
            print("hit enter to delete instances")
            input()
        delete_instance(compute, gpu_config["project_id"], instance_details)
    else:
        print(f"No regions available with the instance configuration {gpu_config['instance_config']['machine_type']} machine type and {gpu_config['instance_config']['gpu_type']} GPU type")

if __name__ == '__main__':
    with open('gpu-config.json', 'r') as f:
        gpu_config = json.load(f)
    main(gpu_config)
