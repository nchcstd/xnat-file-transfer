"""
Assume user put the data in this directory structure
/<whatever>/projects/<project_ID>/<subject_ID>/<session_ID>/<session_data_type>/<scan_id>/<xant_data_type>/<scan_data_type>.

session_data_type:
    RAW, (only support DICOM?)
    RECON -> reconstructions (support NFTI)
 
"""
import pdb
import os
import ConfigParser
import datetime
import traceback
import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

try:
    import requests
except:
    print('please type "pip install requests" for install request paketa')

requests.packages.urllib3.disable_warnings()

r = requests.get('https://dmxnat.nchc.org.tw/data/projects', auth=('admin', 'admin@steps'), verify=False)


class XnatImporter:  
    XNAT_CONF_NAME = 'config.ini'
    XNAT_BASE_URL = 'https://dmxnat.nchc.org.tw'

    def __init__(self):
        data_dirs = self.scan_root_dir()
        self.push_data_to_xnat(data_dirs)

    def scan_root_dir(self):
        data_dirs = []
        for item in os.listdir('.'):
            if ( os.path.isdir(item) ):
                if ( item[:1] != '.'):
                    data_dirs.append(os.path.abspath(os.path.join(os.getcwd(), item)))

        return data_dirs

    def load_config(self, dir):
        config_path = os.path.join(dir, self.XNAT_CONF_NAME)
        try:
            config = ConfigParser.RawConfigParser()
            config.read(config_path)

            username = config.get('xnat', 'username')
            password = config.get('xnat', 'password')

            return (username, password)
        except ConfigParser.NoSectionError:
            logging.error('please check the config file is exsit and format is right!')
        except:
            raise

    
    def build_full_file_path(self, dir_info):
        return [os.path.join(dir_info[0], file_name) for file_name in dir_info[2]]

    def build_restapi_parameter(self, dir_info):
        dir_structure = dir_info[0].split(os.sep)
        start_pos = dir_structure.index('projects')
        file_full_names = self.build_full_file_path(dir_info)
        
        params = {
            'project_id': dir_structure[start_pos + 1],
            'subject_id': dir_structure[start_pos + 2],
            'session_id': dir_structure[start_pos + 3],
            'session_data_type': dir_structure[start_pos + 4] ,
            'scan_id': dir_structure[start_pos + 5],
            'xnat_data_type': dir_structure[start_pos + 6],
            'scan_data_type': dir_structure[start_pos + 7],
            'file_names': file_full_names
        }

        return params

    def xnat_create_project(self, params, auth_info):
        api_url = '/'.join([self.XNAT_BASE_URL, 'data', 'projects', params['project_id']])
        r = requests.put(api_url, auth=(auth_info[0], auth_info[1]), verify=False)
        if r.status_code == 200:
            logging.info('create project successfully!')
        else:
            logging.info('please check the status of creation')

    def xnat_create_subject(self, params, auth_info):
        api_url = '/'.join([self.XNAT_BASE_URL, 'data', 'projects', params['project_id'], 'subjects', params['subject_id']])
        r = requests.put(api_url, auth=(auth_info[0], auth_info[1]), verify=False)
        if r.status_code == 200:
            logging.info('create subject successfully!')
        else:
            logging.info('please check the status of creation')

    def xnat_create_session(self, params, auth_info):
        dateobj = datetime.date.today()
        date_str = dateobj.isoformat()
        query_params = '?xnat:mrSessionData/date=' + date_str
        api_url = '/'.join([self.XNAT_BASE_URL, 'data', 'projects', params['project_id'], 'subjects', params['subject_id'], 'experiments', params['session_id'] + query_params])
        r = requests.put(api_url, auth=(auth_info[0], auth_info[1]), verify=False)
        if r.status_code == 200:
            logging.info('create session successfully!')
        else:
            logging.info('please check the status of creation')

    def xnat_create_scan(self, params, auth_info):
        query_params = '?xsiType=xnat:' + params['xnat_data_type'] + '&xnat:' + params['xnat_data_type'] + '/type=' + params['scan_data_type'] 
        api_url = '/'.join([
                            self.XNAT_BASE_URL, 'data', 
                            'projects', params['project_id'], 
                            'subjects', params['subject_id'], 
                            'experiments', params['session_id'], 
                            'scans', params['scan_id'] + query_params
        ])
        r = requests.put(api_url, auth=(auth_info[0], auth_info[1]), verify=False)
        if r.status_code == 200:
            logging.info('create scan successfully!')
        else:
            logging.info('please check the status of creation')
    
    def xnat_create_resource_for_scan(self, params, auth_info):
        if params['session_data_type'] == 'RAW':
            api_url = '/'.join([
                                self.XNAT_BASE_URL, 'data', 
                                'projects', params['project_id'], 
                                'subjects', params['subject_id'], 
                                'experiments', params['session_id'], 
                                'scans', params['scan_id'],
                                'resources/DICOM?format=DICOM&content=' + params['scan_data_type'] + '_RAW', 
            ])
            r = requests.put(api_url, auth=(auth_info[0], auth_info[1]), verify=False)
            
        elif params['session_data_type'] == 'RECON':
            api_url = '/'.join([
                                self.XNAT_BASE_URL, 'data', 
                                'projects', params['project_id'], 
                                'subjects', params['subject_id'], 
                                'experiments', params['session_id'], 
                                'scans', params['scan_id'],
                                'reconstructions/' + params['scan_id'] + '/resources/NIFTI?format=NIFTI',
            ])
            r = requests.put(api_url, auth=(auth_info[0], auth_info[1]), verify=False)

        if r.status_code == 200:
            logging.info('create resource successfully!')
        else:
            logging.info('please check the status of creation')

    def xnat_upload_files(self, params, auth_info):
        if params['session_data_type'] == 'RAW':
            for file_name in params['file_names']:
                base_filename = os.path.basename(file_name)
                api_url = '/'.join([
                                    self.XNAT_BASE_URL, 'data', 
                                    'projects', params['project_id'], 
                                    'subjects', params['subject_id'], 
                                    'experiments', params['session_id'], 
                                    'scans', params['scan_id'],
                                    'resources/DICOM/files/' + base_filename
                ])

                with open(file_name) as fh:
                    file_data = fh.read()
                    r = requests.put(
                        api_url, 
                        data = file_data,
                        headers={'content-type':'text/plain'},
                        params={'file': base_filename},
                        auth=(auth_info[0], auth_info[1]), 
                        verify=False)

                    if r.stat_code == 200:
                        logging.info('upload ' + base_filename + ' successuflly!')
                        logging.info(r.text)
                    else:
                        logging.error('upload failed')
                        logging.info(r.text)
            
        elif params['session_data_type'] == 'RECON':
            for file_name in params['file_names']:
                base_filename = os.path.basename(file_name)
                api_url = '/'.join([
                                    self.XNAT_BASE_URL, 'data', 
                                    'projects', params['project_id'], 
                                    'subjects', params['subject_id'], 
                                    'experiments', params['session_id'], 
                                    'scans', params['scan_id'],
                                    'reconstructions/' + params['scan_id'] + '/resources/NIFTI/files/' + base_filename
                ])

                with open(file_name) as fh:
                    file_data = fh.read()
                    r = requests.put(
                        api_url, 
                        data = file_data,
                        headers={'content-type':'text/plain'},
                        params={'file': base_filename},
                        auth=(auth_info[0], auth_info[1]), 
                        verify=False)

                    if r.stat_code == 200:
                        logging.info('upload ' + base_filename + ' successuflly!')
                        logging.info(r.text)
                    else:
                        logging.error('upload failed')
                        logging.info(r.text)

    def do_api_request(self, auth_info, data_dir):
        
        for index, dir_info in enumerate(os.walk(data_dir)):
            if index > 1 and len(dir_info[2]) > 0:
                
                params = self.build_restapi_parameter(dir_info)
                try:
                    self.xnat_create_project(params, auth_info)
                    self.xnat_create_subject(params, auth_info)
                    self.xnat_create_session(params, auth_info)
                    self.xnat_create_scan(params, auth_info)
                    self.xnat_create_resource_for_scan(params, auth_info)
                    self.xnat_upload_files(params, auth_info)
                except Exception:
                    traceback.print_exc()

    def push_data_to_xnat(self, data_dirs):
        for data_dir in data_dirs:
            auth_info = self.load_config(data_dir)
            
            self.do_api_request(auth_info, data_dir)


if __name__ == '__main__':
    xnat_importer = XnatImporter()


