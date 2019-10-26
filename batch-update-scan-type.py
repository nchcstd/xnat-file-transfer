import sys
import configparser
import os
"""
    print project file export 
"""

import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.ERROR)

VER=0.1

try:
    import requests
except:
    print('please type "pip install requests" for installing request package')

requests.packages.urllib3.disable_warnings()


class XnatExport:
    XNAT_CONF_NAME = 'config.ini'
    XNAT_BASE_URL = 'https://dmxnat.nchc.org.tw'

    def __init__(self):
        data_dirs = self.scan_root_dir() 
        data_dir = data_dirs[0]
        self.auth_info = self.load_config(data_dir)
        self.session_id = None
        self.authErr = 0
        #self.listProjects(auth_info)

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
        api_url = "{0}/data/archive/{1}".format(self.XNAT_BASE_URL, api)
        print(api_url)

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

    def filesFromExperimentScanRes(self, experiment, scan, resource):
        data = self.xnatapi('experiments/{0}/scans/{1}/resources/{2}/files'.format(experiment, scan, resource))
        return data

    def resourcesFromExperimentScan(self, experiment, scan):
        data = self.xnatapi('experiments/{0}/scans/{1}/resources'.format(experiment, scan))
        return data

    def filesFromExperimentScan(self, experiment, scan):
        data = self.xnatapi('experiments/{0}/scans/{1}/files'.format(experiment, scan))
        return data

    def scansFromExperiment(self, experiment):
        data = self.xnatapi('experiments/{0}/scans'.format(experiment))
        return data

    def resourcesFromExperiment(self, experiment):
        data = self.xnatapi('experiments/{0}/resources'.format(experiment))
        return data

    def filesFromExperimentRes(self, experiment, resource):
        data = self.xnatapi('experiments/{0}/resources/{1}/files'.format(experiment, resource)) 
        return data 

    def filesFromExperiment(self, experiment):
        data = self.xnatapi('experiments/{0}/files'.format(experiment))
        return data

    def listExperiments(self, project, subject):

        data = self.xnatapi('projects/{0}/subjects/{1}/experiments'.format(project, subject))
        return data

    def getExperiment(self, project, subject, experiment):
        data = self.xnatapi('projects/{0}/subjects/{1}/experiments/{2}'.format(project, subject, experiment))
        return data

    def listSubjects(self, project):

        data = self.xnatapi('projects/{0}/subjects'.format(project))
        return data

    def listProjects(self):
        
        data = self.xnatapi('projects/')
        return data

    def getSubject(self, project, subject):
        data = self.xnatapi('projects/{0}/subjects/{1}'.format(project, subject))
        return data

    def getProject(self, project):
        data = self.xnatapi('projects/{0}'.format(project))
        return data

    def getFile(self, file):
        print("Name: ", file['Name'])
        print("Disest: ", file['digest'])
        print("Size: ", file['Size'])
        print("Collection: ", file['collection'])

    def downloadFile(self, fileName, link):
        auth_info = self.auth_info
        r = requests.get(link, auth=(auth_info[0], auth_info[1]), verify=False, allow_redirects=True)
        open(fileName, 'wb').write(r.content)

    def exportProject(self, project):
        print(project)
        projectData = self.getProject(project)
        if projectData == '':
            raise
        subjects = self.listSubjects(project)
        subjectsData = subjects['ResultSet']['Result']
        for subject in subjectsData:
            subjectID = subject['ID']
            subjectLabel = subject['label']
            basepath = "{0}/data/export".format(os.getcwd())
            basepath = "{0}/{1}".format(basepath, project)
            #self.createDir(basepath)
            sbpath = "{0}/{1}".format(basepath, subjectLabel)
            #self.createDir(sbpath)
            experiments = self.listExperiments(project, subjectID)
            experimentData = experiments['ResultSet']['Result']
            for experiment in experimentData:
                experimentID = experiment['ID']
                experimentLabel = experiment['label']
                expath = "{0}/{1}".format(sbpath, experimentLabel)
                #self.createDir(expath)
                #eFiles = self.filesFromExperiment(experimentID)
                #print(eFiles)
                scans = self.scansFromExperiment(experimentID)
                scansData = scans['ResultSet']['Result']
                for scan in scansData:
                    scanID = scan['ID']
                    scanFormat = scan['xsiType']
                    scanQuality = scan['quality']
                    scantype = scan['type']
                    update = 0
                    print("{},{},{},{}".format(scanID, scanFormat, scanQuality, scantype))
                    if scanQuality == '':
                        scanQuality = 'usable'
                        update=1
                    if scantype == '':
                        scantype = 'unknow'
                        update=1
                    if update == 1:
                        print('update scan metadata')
                        api_url = "projects/{0}/subjects/{1}/experiments/{2}/scans/{3}?format=json&{4}/type={5}&{4}/quality={6}".format(project, subjectID, experimentID, scanID, scanFormat, scantype, scanQuality)
                        r = self.xnatapi(api_url, 'put', 1)
                        if r.status_code < 400:
                            logging.info('update scan successfully!')
                        else:
                            logging.info('please check the status of xnat_create_scan')

                    #scanpath = "{0}/{1}".format(expath, scanID)
                    #self.createDir(scanpath)
                    #sFiles = self.filesFromExperimentScan(experimentID, scanID)
                    #sFilesData = sFiles['ResultSet']['Result']
                    #for sfile in sFilesData:
                    #    collectionpath = "{0}/{1}".format(scanpath, sfile['collection'])
                    #    self.createDir(collectionpath)
                    #    self.getFile(sfile)
                    #    fileLink = '/'.join([self.XNAT_BASE_URL, 'data', 'experiments', experimentID, 'scans', scanID, 'resources', sfile['collection'], 'files', sfile['Name']])
                    #    fileName = '/'.join([collectionpath, sfile['Name']])
                    #    print("URL: ", fileLink)
                    #    print("filename: ", fileName)
                    #    
                    #    self.downloadFile(fileName, fileLink)
                        

if __name__ == '__main__':
    proName=None
    prog=sys.argv[0]
    print("{0} ({1}): ready to test project's files.".format(prog, VER))
    if len(sys.argv) == 2:
        proName = sys.argv[1]
    xnatExport = XnatExport()
    if proName != None:
        xnatExport.exportProject(proName)
    else:
        projects = xnatExport.listProjects()
        projectsData = projects['ResultSet']['Result']
        for project in projectsData:
            projectID = project['ID']
            projectLabel = project['name']
            print("project: ", projectLabel)
            xnatExport.exportProject(projectID)
