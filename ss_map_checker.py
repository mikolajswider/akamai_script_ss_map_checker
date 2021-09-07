#!/usr/bin/python3
import json
import dns.resolver
import time
import requests
from akamai.edgegrid import EdgeGridAuth, EdgeRc
from urllib.parse import urljoin
import re
import os
import argparse
import configparser

def get_properties(contractId, groupId, edgerc_path, section, switchkey):
    # setting up authentication as in https://github.com/akamai/AkamaiOPEN-edgegrid-python
    dict_list=[]
    edgerc = EdgeRc(edgerc_path)
    baseurl = 'https://%s' % edgerc.get(section, "host")
    http_request = requests.Session()
    http_request.auth = EdgeGridAuth.from_edgerc(edgerc, section)
    # setting up request headers
    headers ={}
    headers['PAPI-Use-Prefixes']="true"
    http_request.headers = headers
    # getting the latest property version: https://developer.akamai.com/api/core_features/property_manager/v1.html#getproperties
    http_response = http_request.get(urljoin(baseurl, '/papi/v1/properties?contractId='+contractId+'&groupId='+groupId+'&accountSwitchKey='+switchkey))
    http_status_code= http_response.status_code
    http_content = json.loads(http_response.text)
    for item in http_content['properties']['items']:
        dict_list = dict_list + [{"latestVersion": item['latestVersion'], "propertyId": item['propertyId'], "contractId":contractId, "groupId": groupId, "propertyName":item['propertyName']}]
    return (dict_list)

def sort_properties_ss_map(ss_map, latestVersion, propertyId, contractId, groupId, edgerc_path, section, switchkey, propertyName):
    # setting up authentication as in https://github.com/akamai/AkamaiOPEN-edgegrid-python
    answer_list = [[],[]]
    edgerc = EdgeRc(edgerc_path)
    baseurl = 'https://%s' % edgerc.get(section, "host")
    http_request = requests.Session()
    http_request.auth = EdgeGridAuth.from_edgerc(edgerc, section)
    # setting up request headers
    headers ={}
    headers['PAPI-Use-Prefixes']="true"
    http_request.headers = headers
    # getting the list of groups and contracts associated to groups: https://developer.akamai.com/api/core_features/property_manager/v1.html#getgroups
    http_response = http_request.get(urljoin(baseurl, '/papi/v1/properties/'+propertyId+'/versions/'+str(latestVersion)+'/rules?contractId='+contractId+'&groupId='+groupId+'&accountSwitchKey='+switchkey))
    http_status_code = http_response.status_code
    http_content = json.loads(http_response.text)    
    if ss_map in http_response.text:
        answer_list[0] = answer_list[0] + [propertyName] 
    else:
        answer_list[1] = answer_list[1] + [propertyName]     
    return(answer_list)

def main():

    # defining variables
    dict_list = []
    
    # list of all property hostnames within the account that are cnamed to the input edge hostname
    answer_list = [[],[]]
    
    nb_groups = 0
    nb_contracts = 0
    nb_properties = 0
    
    # defining inputs &  argparse
    parser = argparse.ArgumentParser(prog="ss_map_checker.py v1.0", description="The ss_map_checker.py script finds all properties containing a given Site Shield Map, within a Customer Account. The script uses edgegrid for python, dnspython and argparse libraries. Contributors: Miko (mswider) as Chief Programmer")
    parser.add_argument("ss_map", default=None, type=str, help="Site Shield Map to be tested")
    env_edgerc = os.getenv("AKAMAI_EDGERC")
    default_edgerc = env_edgerc if env_edgerc else os.path.join(os.path.expanduser("~"), ".edgerc")
    parser.add_argument("--edgerc_path", help="Full Path to .edgerc File including the filename", default=default_edgerc)
    env_edgerc_section = os.getenv("AKAMAI_EDGERC_SECTION")
    default_edgerc_section = env_edgerc_section if env_edgerc_section else "default"
    parser.add_argument("--section", help="Section Name in .edgerc File", required=False, default=default_edgerc_section)
    parser.add_argument("--switchkey", default="", required=False, help="Account SwitchKey")
    parser.add_argument("--enable_logs", default='False', required=False, help="Enable Logs", choices=['True', 'False'],)
    args = parser.parse_args()
    
    # Adjusting argpare variables with variables already used in previous version of script
    ss_map =args.ss_map
    edgerc_path = args.edgerc_path
    section = args.section
    switchkey = args.switchkey
    enable_logs = args.enable_logs


    # setting up authentication as in https://github.com/akamai/AkamaiOPEN-edgegrid-python
    try:
        edgerc = EdgeRc(edgerc_path)
        baseurl = 'https://%s' % edgerc.get(section, "host")
    except configparser.NoSectionError:
        print("\nThe path to the .edgerc File or the Section Name provided is not correct. Please review your inuputs.\n")
    else:
        http_request = requests.Session()
        http_request.auth = EdgeGridAuth.from_edgerc(edgerc, section)
        # setting up request headers
        headers ={}
        headers['PAPI-Use-Prefixes']="true"
        http_request.headers = headers
        print('\nGetting the list of all groups and all associated contracts...')
        #https://developer.akamai.com/api/core_features/property_manager/v1.html#getgroups
        http_response = http_request.get(urljoin(baseurl, '/papi/v1/groups?accountSwitchKey='+switchkey))
        http_status_code= http_response.status_code
        http_content= json.loads(http_response.text)
        # Checking the first API call response code to avoid any exceptions further on ...
        if http_status_code == 200:
            print('Getting the list of all properties...')
            for item in http_content['groups']['items']:
                nb_groups = nb_groups + 1
                for contractId in item['contractIds']:
                    nb_contracts = nb_contracts + 1
                    dict_list = dict_list + get_properties(contractId, item['groupId'], edgerc_path, section, switchkey)
            nb_properties = len(dict_list)
            print('There are '+str(nb_groups)+' groups, '+str(nb_contracts)+ ' contracts and '+str(nb_properties)+' properties in the '+str(switchkey)+' account.')
            print('\nProcessing all properties. This operation may take several minutes...')
            for bloc in dict_list:
                sorted = sort_properties_ss_map(ss_map, bloc['latestVersion'], bloc['propertyId'], bloc['contractId'], bloc['groupId'], edgerc_path, section, switchkey, bloc['propertyName'])
                answer_list[0] = answer_list[0] + sorted[0]
                answer_list[1] = answer_list[1] + sorted[1]
                if enable_logs == 'True':
                    print('Processing property '+ bloc['propertyName'] +'...')
            len_answer_list = [len(answer_list[0]),len(answer_list[1])]

            # Internal Script Check
            if len_answer_list[0] + len_answer_list[1] == nb_properties:
                print("\nInternal Script Check Success \n")

                print('There are '+str(len_answer_list[0])+' properties containing the '+ss_map+' Site Shield Map.')
                print('There are '+str(len_answer_list[1])+' properties that do not contain '+ss_map+' Site Shield Map.')
                if len_answer_list[0] !=0:
                    print('\nThe following properties contain the '+ss_map+' Site Shield Map:')
                    print(*answer_list[0], sep = "\n")
                if len_answer_list[1] !=0:
                    print('\nThe following properties do not contain the '+ss_map+' Site Shield Map:')
                    print(*answer_list[1], sep = "\n")
            else:
                print("\nInternal Script Check Failure \n ")
        else:
            print("\nAPI call not successful!")
            print(http_response.text)
            
if __name__ == '__main__':
    main()
