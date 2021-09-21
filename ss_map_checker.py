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

def check_ss_map(ss_map, edgerc_path, section, switchkey):
    # setting up authentication as in https://github.com/akamai/AkamaiOPEN-edgegrid-python
    answer = False
    edgerc = EdgeRc(edgerc_path)
    baseurl = 'https://%s' % edgerc.get(section, "host")
    http_request = requests.Session()
    http_request.auth = EdgeGridAuth.from_edgerc(edgerc, section)
    # setting up request headers
    #headers ={}
    #headers['PAPI-Use-Prefixes']="true"
    #http_request.headers = headers
    # api call
    http_response = http_request.get(urljoin(baseurl, '/siteshield/v1/maps?accountSwitchKey='+switchkey))
    http_status_code= http_response.status_code
    http_content = json.loads(http_response.text)
    if ss_map in http_content:
        answer = True
    return (answer)

def get_properties(contractId, groupId, groupName, edgerc_path, section, switchkey):
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
        dict_list = dict_list + [{"latestVersion": item['latestVersion'], "propertyId": item['propertyId'], "contractId":contractId, "groupId": groupId, "groupName":groupName, "propertyName":item['propertyName']}]
    return (dict_list)

def sort_properties_ss_map(ss_map, latestVersion, propertyId, contractId, groupId, groupName, edgerc_path, section, switchkey, propertyName):
    # setting up authentication as in https://github.com/akamai/AkamaiOPEN-edgegrid-python
    answer_list = [[],[],[]]
    ss_map_apex = re.search('(.*).akamai(.*)',ss_map).group(1)
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

    if ("customBehavior" in http_response.text) or ("customOverride" in http_response.text):
        if (ss_map_apex in http_response.text):
            answer_list[0] = answer_list[0] + [contractId +' > '+ groupName + ' > ' + propertyName]
        else:
            answer_list[2] = answer_list[2] + [contractId +' > '+ groupName + ' > ' + propertyName]
    else:
        if ("advanced" in http_response.text) or ("advancedOverride" in http_response.text):
            if (ss_map_apex in http_response.text):
                answer_list[0] = answer_list[0] + [contractId +' > '+ groupName + ' > ' + propertyName]
            else:
                answer_list[1] = answer_list[1] + [contractId +' > '+ groupName + ' > ' + propertyName]
        else:
            if (ss_map in http_response.text):
                answer_list[0] = answer_list[0] + [contractId +' > '+ groupName + ' > ' + propertyName]
            else:
                answer_list[1] = answer_list[1] + [contractId +' > '+ groupName + ' > ' + propertyName]
    return(answer_list)


def main():

    # defining variables
    dict_list = []
    
    # list of all property hostnames within the account that are cnamed to the input edge hostname
    answer_list = [[],[],[]]
    
    nb_groups = 0
    nb_contracts = 0
    nb_properties = 0
    continue_after_check = False

    # defining inputs & argparse
    parser = argparse.ArgumentParser(prog="ss_map_checker.py v2.0", description="The ss_map_checker.py script finds all properties containing a given Site Shield Map, within a Customer Account. The script uses edgegrid for python, dnspython and argparse libraries. Contributors: Miko (mswider) as Chief Programmer")
    parser.add_argument("ss_map", default=None, type=str, help="Site Shield Map to be tested")
    env_edgerc = os.getenv("AKAMAI_EDGERC")
    default_edgerc = env_edgerc if env_edgerc else os.path.join(os.path.expanduser("~"), ".edgerc")
    parser.add_argument("--edgerc_path", help="Full Path to .edgerc File including the filename", default=default_edgerc)
    env_edgerc_section = os.getenv("AKAMAI_EDGERC_SECTION")
    default_edgerc_section = env_edgerc_section if env_edgerc_section else "default"
    parser.add_argument("--section", help="Section Name in .edgerc File", required=False, default=default_edgerc_section)
    parser.add_argument("--switchkey", default="", required=False, help="Account SwitchKey")
    parser.add_argument("--enable_logs", default='False', required=False, help="Enable Logs", choices=['True', 'False'],)
    parser.add_argument("--enable_map_check", default='False', required=False, help="Enable Map Check", choices=['True', 'False'],)
    args = parser.parse_args()
    
    # Adjusting argpare variables with variables already used in previous version of script
    ss_map =args.ss_map
    edgerc_path = args.edgerc_path
    section = args.section
    switchkey = args.switchkey
    enable_logs = args.enable_logs
    enable_map_check = args.enable_map_check

    # SS Map Syntax Check

    try:
        ss_map_apex = re.search('(.*).akamai(.*)',ss_map).group(1)
    except AttributeError:
        print('The provided Site Shield Map has incorrect syntax.')
        return()

    # SS Map Check Logic
    if enable_map_check == 'False':
        continue_after_check = True
    else:
        if check_ss_map(ss_map, edgerc_path, section, switchkey)==True:
            print('\n' + ss_map + ' - SS Map Check Success')
            continue_after_check = True

    if continue_after_check == True:
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
                        dict_list = dict_list + get_properties(contractId, item['groupId'], item['groupName'], edgerc_path, section, switchkey)
                nb_properties = len(dict_list)
                print('There are '+str(nb_groups)+' groups, '+str(nb_contracts)+ ' contracts and '+str(nb_properties)+' properties in the '+str(switchkey)+' account.')
                print('\nProcessing all properties. This operation may take several minutes...')
                for bloc in dict_list:
                    sorted = sort_properties_ss_map(ss_map, bloc['latestVersion'], bloc['propertyId'], bloc['contractId'], bloc['groupId'], bloc['groupName'], edgerc_path, section, switchkey, bloc['propertyName'])
                    answer_list[0] = answer_list[0] + sorted[0]
                    answer_list[1] = answer_list[1] + sorted[1]
                    answer_list[2] = answer_list[2] + sorted[2]
                    if enable_logs == 'True':
                        print('Processing property '+ bloc['propertyName'] + ' within contract ' + bloc['contractId'] + ' and group ' + bloc['groupName'] + '...')
                
                # Creating the length list
                len_answer_list = [len(answer_list[0]),len(answer_list[1]),len(answer_list[2])]

                # Internal Script Check
                if len_answer_list[0] + len_answer_list[1] + len_answer_list[2] == nb_properties:
                    print("\nInternal Script Check Success \n")

                    print('There is/are '+str(len_answer_list[0])+' propertie(s) containing the '+ss_map+' Site Shield Map.')
                    print('There is/are '+str(len_answer_list[1])+' propertie(s) that do not contain '+ss_map+' Site Shield Map.')
                    print('There is/are '+str(len_answer_list[2])+' propertie(s) that need to be checked manually.')

                    if len_answer_list[0] !=0:
                        print('\nThe following properties contain the '+ss_map+' Site Shield Map:')
                        print(*answer_list[0], sep = "\n")
                    if len_answer_list[1] !=0:
                        print('\nThe following properties do not contain the '+ss_map+' Site Shield Map:')
                        print(*answer_list[1], sep = "\n")
                    if len_answer_list[2] !=0:
                        print('\nThe following properties need to be checked manually since these do not contain the '+ss_map+' Site Shield Map in their json Rule Tree but do contain a Custom Behavior or a Custom Override.')
                        print(*answer_list[2], sep = "\n")
                else:
                    print("\nInternal Script Check Failure \n ")
            else:
                print("\nAPI Call Failure")
                print(http_response.text)
    else: 
        print('\n' + ss_map + ' - SS Map Check Failure - The provided SS Map could not be found within the Account ' + switchkey + '.' )

if __name__ == '__main__':
    main()
