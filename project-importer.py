from lxml import etree
import csv
import traceback
import subprocess
import pprint
import datetime
import configparser
import os
import pdb
import sys
import logging
"""
Assume user put the data in this directory structure
/<whatever>/projects/<project_ID>/<subject_ID>/<session_ID>/<session_data_type>/<scan_id>/<xant_data_type>/<scan_data_type>.

session_data_type:
    RAW, (support DICOM and others)
    RECON -> reconstructions (support NFTI)
 
"""

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

VER=0.4

try:
    import requests
except:
    print('please type "pip install requests" for installing request package')

requests.packages.urllib3.disable_warnings()

# r = requests.get('https://dmxnat.nchc.org.tw/data/projects', auth=('admin', 'admin@steps'), verify=False)


class XnatImporter:
    XNAT_CONF_NAME = 'config.ini'
    XNAT_BASE_URL = 'https://dmxnat.nchc.org.tw'
    AIM_SCHEMA_XSD = 'data/AIM_v4_rv44_XML.xsd'

    def __init__(self):
        self.results = {
            'exist': [],
            'success': [],
            'fail': []
        }

        data_dirs = self.scan_root_dir()
        data_dir = data_dirs[0]
        self.auth_info = self.load_config(data_dir)
        self.session_id = None
        self.authErr = 0
        self.scanExist = 0
        self.push_data_to_xnat(data_dirs)

    def scan_root_dir(self):
        data_dirs = []
        for item in os.listdir('.'):
            if (os.path.isdir(item)):
                if (item[:1] != '.'):
                    data_dirs.append(os.path.abspath(
                        os.path.join(os.getcwd(), item)))

        return data_dirs

    def load_config(self, dir):
        config_path = os.path.join(dir, self.XNAT_CONF_NAME)
        try:
            config = configparser.ConfigParser()
            config.read(config_path)

            username = config.get('xnat', 'username')
            password = config.get('xnat', 'password')
            xnat_url = config.get('xnat', 'url')

            # side effect?
            self.XNAT_BASE_URL = xnat_url

            return (username, password)
        except configparser.NoSectionError:
            logging.error(
                'please check the config file is exsit and format is right!')
        except:
            raise

    def session_request(self):
        if self.authErr >= 2:
            raise

        auth_info = self.auth_info
        api_url = '/'.join([self.XNAT_BASE_URL, 'data', 'JSESSION'])
        r = requests.get(api_url, auth=(auth_info[0], auth_info[1]), verify=False)
        if r.status_code < 400:
            self.session_id = r.text
            self.authErr = 0
            return True
        elif r.status_code == 401:
            logging.error('please check the status of api {0}'.format(api_url))
            logging.error(r.status_code)
            logging.error(r.text)
            print(r.text)
            self.authErr = self.authErr + 1
            raise EOFError
        else:
            logging.error('please check the status of api {0}'.format(api_url))
            logging.error(r.status_code)
            logging.error(r.text)
            print(r.text)
            raise EOFError

    def xnatapi(self, api, action='get', raw=0):
        cookies = dict(JSESSIONID=self.session_id)
        api_url = api
        print(action, api_url)

        if action == 'get':
            api_url = '{0}?format=json'.format(api_url)
            r = requests.get(api_url, cookies=cookies, verify=False)
        elif action == 'put':
            r = requests.put(api_url, cookies=cookies, verify=False)
        else:
            logging.error('please check api action {0}'.format(action))
            raise EOFError

        if r.status_code < 400:
            logging.info('api:{0} successfully!'.format(api_url))
            if raw == 1:
                return r
        elif r.status_code == 401:
            if self.session_request() == True:
                return self.xnatapi(api, action, raw)
        else:
            if raw == 1:
                return r
            logging.error('please check the status of api {0}'.format(api_url))
            logging.error(r.status_code)
            logging.error(r.text)
            print(r.text)
            raise
        return r.json()

    def build_full_file_path(self, dir_info):
        return [os.path.join(dir_info[0], file_name) for file_name in dir_info[2]]

    def build_restapi_parameter(self, dir_info):
        dir_structure = dir_info[0].split(os.sep)
        start_pos = dir_structure.index('projects')
        file_full_names = self.build_full_file_path(dir_info)

        logging.info(dir_info)

        enabled_data_type = ['cr', 'ct', 'mr', 'hd', 'dx']

        params = {
            'project_id': dir_structure[start_pos + 1],
            'subject_id': dir_structure[start_pos + 2],
            'session_id': dir_structure[start_pos + 3],
            'session_data_type': dir_structure[start_pos + 4],
            'scan_id': dir_structure[start_pos + 5],
            'xnat_data_type': dir_structure[start_pos + 6] + 'ScanData',
            'data_type': dir_structure[start_pos + 6],
            'scan_data_type': dir_structure[start_pos + 7],
            'file_names': file_full_names
        }

        params['session_id'] = params['subject_id'] + '_' + params['session_id']
        if params['data_type'] not in enabled_data_type:
            params['data_type'] = 'otherDicom'
            params['scan_data_type'] = 'otherDicom'

        return params

    def xnat_create_project(self, params, auth_info):
        api_url = '/'.join([self.XNAT_BASE_URL, 'data',
                            'projects', params['project_id']])

        r = self.xnatapi(api_url, 'put', 1)
        if r.status_code < 400:
            logging.info('create project successfully!')
        else:
            logging.error('please check the status of xnat_create_project')
            logging.error(r.status_code)
            logging.error(r.text)

    def xnat_create_subject(self, params, auth_info):
        api_url = '/'.join([self.XNAT_BASE_URL, 'data', 'projects',
                            params['project_id'], 'subjects', params['subject_id']])
        r = self.xnatapi(api_url, 'get',  1)
        if r.status_code == 200:
            logging.info('{0} exist!'.format(api_url))
            return

        #r = requests.put(api_url, auth=(
        #    auth_info[0], auth_info[1]), verify=False)
        r = self.xnatapi(api_url, 'put',  1)
        if r.status_code < 400:
            logging.info('create subject successfully!')
        else:
            logging.error('please check the status of xnat_create_subject')
            logging.error(r.status_code)
            logging.error(r.text)

    def xnat_create_session(self, params, auth_info):
        dateobj = datetime.date.today()
        date_str = dateobj.isoformat()
        query_params = '?xnat:' + \
            params['data_type']+'SessionData/date=' + date_str
        api_url = '/'.join([self.XNAT_BASE_URL, 'data', 'projects', params['project_id'],
                            'subjects', params['subject_id'], 'experiments', params['session_id']])

        r = self.xnatapi(api_url, 'get', 1)
        if r.status_code == 200:
            logging.info('{0} exist!'.format(api_url))
            return

        api_url = api_url + query_params
        r = self.xnatapi(api_url, 'put', 1)
        if r.status_code < 400:
            logging.info('create session successfully!')
        else:
            logging.error('please check the status of xnat_create_session')
            logging.error(r.status_code)
            logging.error(r.text)

    def xnat_create_scan(self, params, auth_info):
        #query_params = '?xsiType=xnat:' + params['xnat_data_type'] + '&xnat:' + params['xnat_data_type'] + '/type=' + params['scan_data_type']
        # http://140.110.28.227/data/archive/projects/nchc_lca_dev_2019102514/\
        #        subjects/NCHC02_S00268/experiments/NCHC02_E00228/scans/scan001?\
        #format=json&xnat:ctScanData/type=unknow&xnat:ctScanData/quality=usable
        origType = params['xnat_data_type']
        sType = origType
        print(params['xnat_data_type'])
        if params['xnat_data_type'] == 'dxScanData':
            sType = 'ctScanData'
        print(sType)
        query_params = '?xsiType=xnat:' + sType + '&xnat:' + sType + '/type=Unknow&xnat:' + sType + '/quality=usable'
        #params['xnat_data_type'] = origType
        api_url = '/'.join([
            self.XNAT_BASE_URL, 'data',
            'projects', params['project_id'],
            'subjects', params['subject_id'],
            'experiments', params['session_id'],
            'scans', params['scan_id']
        ])
        r = self.xnatapi(api_url, 'get', 1)
        if r.status_code == 200:
            logging.info('{0} exist!'.format(api_url))
            self.scanExist = 1
            return

        api_url = api_url + query_params
        #r = requests.put(api_url, auth=(
        #    auth_info[0], auth_info[1]), verify=False)
        r = self.xnatapi(api_url, 'put', 1)
        if r.status_code < 400:
            logging.info('create scan successfully!')
        else:
            logging.info('please check the status of xnat_create_scan')

    def xnat_create_resource_for_scan(self, params, auth_info):
        if params['session_data_type'] == 'DICOM':
            api_url = '/'.join([
                self.XNAT_BASE_URL, 'data',
                'projects', params['project_id'],
                'subjects', params['subject_id'],
                'experiments', params['session_id'],
                'scans', params['scan_id'],
                'resources/DICOM?format=DICOM&content=' +
                params['scan_data_type'] + '_RAW',
            ])
            #r = requests.put(api_url, auth=(
            #    auth_info[0], auth_info[1]), verify=False)
            r = self.xnatapi(api_url, 'put', 1)

        elif params['session_data_type'] == 'RECON':
            api_url = '/'.join([
                self.XNAT_BASE_URL, 'data',
                'projects', params['project_id'],
                'subjects', params['subject_id'],
                'experiments', params['session_id'],
                'scans', params['scan_id'],
                'reconstructions/' +
                params['scan_id'] + '/resources/NIFTI?format=NIFTI',
            ])
            #r = requests.put(api_url, auth=(
            #    auth_info[0], auth_info[1]), verify=False)
            r = self.xnatapi(api_url, 'put', 1)

        elif params['session_data_type'] == 'RAW':
            if self.scanExist == 1:
                logging.info('scan exist, skip resource!')
                return

            api_url = '/'.join([
                self.XNAT_BASE_URL, 'data',
                'projects', params['project_id'],
                'subjects', params['subject_id'],
                'experiments', params['session_id'],
                'scans', params['scan_id'],
                'resources/DICOM',
            ])
            #r = requests.put(api_url, auth=(
            #    auth_info[0], auth_info[1]), verify=False)
            r = self.xnatapi(api_url, 'put', 1)

            api_url = '/'.join([
                self.XNAT_BASE_URL, 'data',
                'projects', params['project_id'],
                'subjects', params['subject_id'],
                'experiments', params['session_id'],
                'scans', params['scan_id'],
                'resources/METADATA',
            ])
            #r = requests.put(api_url, auth=(
            #    auth_info[0], auth_info[1]), verify=False)
            r = self.xnatapi(api_url, 'put', 1)

        if r.status_code < 400:
            logging.info('create resource successfully!')
        elif r.status_code == 409:
            logging.info('The resource already exist: ' + api_url)
        else:
            logging.info('please check the status of creation')
            logging.info(r.status_code)

    def check_with_lxml(self, file_name):
        xsd = etree.parse(self.AIM_SCHEMA_XSD)
        xmlschema = etree.XMLSchema(xsd)
        xml_content = etree.parse(file_name)

        if xmlschema.validate(xml_content):
            return True
        else:
            return False

    def check_with_xmllint(self, file_name):
        cmds = ' '.join(
            ['xmllint', '--schema', self.AIM_SCHEMA_XSD,  file_name, '--noout'])
        try:
            ret = subprocess.check_output(
                cmds, shell=True, stderr=subprocess.STDOUT)
            if ret.decode('utf-8').find('validates') > 0:
                return True
            else:
                logging.error(ret)
                return False
        except subprocess.CalledProcessError:
            return False

    def verify_xml(self, file_name):
        if self.check_with_xmllint(file_name) and self.check_with_lxml(file_name):
            return True
        else:
            return False

    def xnat_upload_files(self, params, auth_info):
        if params['session_data_type'] == 'RAW':
            for file_name in params['file_names']:
                base_filename = os.path.basename(file_name)

                logging.info('File Extension: ' + base_filename[-3:])
                abspardir = os.path.abspath(os.path.join(file_name, os.pardir))
                pardir = os.path.basename(abspardir)

                # if base_filename[-3:] == 'dcm':
                if pardir == 'DICOM':
                    api_url = '/'.join([
                        self.XNAT_BASE_URL, 'data',
                        'projects', params['project_id'],
                        'subjects', params['subject_id'],
                        'experiments', params['session_id'],
                        'scans', params['scan_id'],
                        'resources/DICOM/files/' + base_filename
                    ])
                elif pardir == 'METADATA':
                    api_url = '/'.join([
                        self.XNAT_BASE_URL, 'data',
                        'projects', params['project_id'],
                        'subjects', params['subject_id'],
                        'experiments', params['session_id'],
                        'scans', params['scan_id'],
                        'resources/METADATA/files/' + base_filename
                    ])
                else:
                    api_url = '/'.join([
                        self.XNAT_BASE_URL, 'data',
                        'projects', params['project_id'],
                        'subjects', params['subject_id'],
                        'experiments', params['session_id'],
                        'scans', params['scan_id'],
                        'resources/OTHERS/files/' + base_filename
                    ])

                r = self.xnatapi(api_url, 'get', 1)
                if r.status_code == 200:
                    logging.info('{0} exist!'.format(api_url))
                    self.results['exist'].append(file_name)
                    return
                else:
                    r = 0
                    print("upload file...")

                if base_filename[-7:] == 'aim.xml' and pardir == 'METADATA':
                    # verify xml
                    if not self.verify_xml(file_name):
                        self.results['fail'].append(
                            [file_name, 'xml validate failed'])
                        continue

                with open(file_name, 'rb') as fh:
                    print("put", api_url)
                    file_data = fh.read()
                    r = requests.put(
                        api_url,
                        data=file_data,
                        headers={'content-type': 'text/plain'},
                        params={'file': base_filename},
                        auth=(auth_info[0], auth_info[1]),
                        verify=False
                    )

                    print("rt code", r.status_code)
                    if r.status_code < 400:
                        self.results['success'].append(file_name)

                        logging.info('upload ' + base_filename +
                                     ' successuflly!')
                        logging.info(r.text)
                    else:
                        self.results['fail'].append(file_name)

                        logging.error('upload failed: ' + file_name)
                        logging.error(r.text)

        elif params['session_data_type'] == 'RECON':
            for file_name in params['file_names']:
                base_filename = os.path.basename(file_name)
                api_url = '/'.join([
                    self.XNAT_BASE_URL, 'data',
                    'projects', params['project_id'],
                    'subjects', params['subject_id'],
                    'experiments', params['session_id'],
                    'scans', params['scan_id'],
                    'reconstructions/' +
                    params['scan_id'] +
                    '/resources/NIFTI/files/' + base_filename
                ])

                with open(file_name, 'rb') as fh:
                    file_data = fh.read()
                    r = requests.put(
                        api_url,
                        data=file_data,
                        headers={'content-type': 'text/plain'},
                        params={'file': base_filename},
                        auth=(auth_info[0], auth_info[1]),
                        verify=False)

                    if r.status_code < 400:
                        # logging.info('upload ' + base_filename + ' successuflly!')
                        # logging.info(r.text)
                        pass
                    else:
                        logging.error('upload failed' + file_name)
                        logging.error(r.text)

    def do_api_request(self, auth_info, data_dir):

        for index, dir_info in enumerate(os.walk(data_dir)):
            logging.info('dir_info >> ')
            logging.info(list(dir_info))
            dir_info = list(dir_info)
            dir_info[2] = list(filter(lambda x: x != '.DS_Store', dir_info[2]))

            if index > 1 and len(dir_info[2]) > 0:
                params = self.build_restapi_parameter(dir_info)
                try:
                    self.scanExist = 0
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

    def output_result_csv(self):
        with open('fail.csv', 'w') as csvfh:
            csv_writer = csv.writer(csvfh, delimiter=',')
            for row in self.results['fail']:
                csv_writer.writerow(row)


if __name__ == '__main__':
    progName=sys.argv[0]
    print("{0} ({1}): ready to import files.".format(progName, VER))
    xnat_importer = XnatImporter()

    pprint.pprint(xnat_importer.results)

    print("{0} ({1}): import files finish".format(progName, VER))
    xnat_importer.output_result_csv()
