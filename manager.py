#!/usr/bin/env python3

from socketserver import ThreadingTCPServer
from http.server import BaseHTTPRequestHandler
from os import getenv
import json
from threading import Thread, Lock
import requests
import subprocess
import shutil
import os, os.path, signal
import pwd

HOST = getenv("MANAGER_HOST", "")
PORT = int(getenv("MANAGER_PORT", "8089"))
STUD_GITLAB_WEBHOOK_TOKEN = getenv("STUD_GITLAB_WEBHOOK_TOKEN")
STUD_GITLAB_ACCESS_TOKEN = getenv("STUD_GITLAB_ACCESS_TOKEN")

if STUD_GITLAB_WEBHOOK_TOKEN == None or STUD_GITLAB_ACCESS_TOKEN == None:
    print("Missing some environment variables!")
    exit(1)

GAZELLESPRING_USER = "gazellespring"
GAZELLESPRING_HOME_DIR = "/home/gazellespring"
GAZELLESPRING_JAR = "gazelle-server.jar"
GAZELLE_WWW_DIR = "/var/www/html/gazelle"

GAZELLE_GITLAB_ARTIFACT_URL = "https://gitlab.stud.idi.ntnu.no/api/v4/projects/{project_id}/jobs/{job_id}/artifacts"
ARTIFACT_GAZELLE_JAR_NAME = "server/target/gazelle-server-0.1-SNAPSHOT.jar"
ARTIFACT_GAZELLE_WWW_DIR = "gazelle/dist"

gazelleSpringPID = None

def makeStatusPage():
    return "Status page!"

def runAsUser(command, user_name, cwd):
    pw_record = pwd.getpwnam(user_name)
    user_name      = pw_record.pw_name
    user_home_dir  = pw_record.pw_dir
    user_uid       = pw_record.pw_uid
    user_gid       = pw_record.pw_gid
    env = os.environ.copy()
    env[ 'HOME'     ]  = user_home_dir
    env[ 'LOGNAME'  ]  = user_name
    env[ 'PWD'      ]  = cwd
    env[ 'USER'     ]  = user_name

    def demote():
        os.setgid(user_gid)
        os.setuid(user_uid)

    process = subprocess.Popen(
        command, preexec_fn=demote, cwd=cwd, env=env
    )
    return process.pid

# Kills gracefully
def killAndWait(pid):
    os.kill(pid, signal.SIGTERM)
    os.waitpid(pid, 0)

def downloadGitlabArtifacts(project_id, job_id, target_file):
    url = GAZELLE_GITLAB_ARTIFACT_URL.format(project_id=project_id, job_id=job_id)
    headers={"PRIVATE-TOKEN": STUD_GITLAB_ACCESS_TOKEN}
    with requests.get(url, stream=True, allow_redirects=True, headers=headers) as r:
        r.raise_for_status()
        with open(target_file, "wb") as o:
            for chunk in r.iter_content(chunk_size=8192):
                o.write(chunk)

def unzip(filename, target_dir):
    os.rmtree(target_dir, ignore_errors=True)
    subprocess.run(["unzip", filename, "-d", target_dir])
    os.remove(filename)

def moveFile(fro, to):
    if os.path.isfile(to):
        os.remove(to)
    dirname = os.path.dirname(to)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    shutils.move(fro, to)

#fro is a directory, to is the new name/location of the directory
def moveDir(fro, to):
    if os.path.isdir(to):
        shutil.rmtree(to)
    os.rename(fro, to)

def downloadGazelle(project_id, job_id):
    print("Downloading gazelle server and site")

    ARTIFACT_ZIP = "artifacts.zip"
    ARTIFACT_DIR = "artifacts"
    downloadGitlabArtifacts(project_id, job_id, )
    print(f"Dowloaded {ARTIFACT_ZIP}")

    unzip(ARTIFACT_ZIP, ARTIFACT_DIR)

    artifact = lambda name: os.path.join(ARTIFACT_DIR, name)
    moveFile(artifact(ARTIFACT_GAZELLE_JAR_NAME), os.path.join(GAZELLESPRING_HOME_DIR, GAZELLESPRING_JAR))
    moveDir(artifact(ARTIFACT_GAZELLE_WWW_DIR), GAZELLE_WWW_DIR)

    print("Moved files to correct places")

def startGazelleServer():
    global gazelleSpringPID
    stopGazelleServer()

    print("Starting gazelle spring server")

    command = ["java", "-jar", GAZELLESPRING_JAR]
    gazelleSpringPID = runAsUser(command, GAZELLESPRING_USER, GAZELLESPRING_HOME_DIR)

def stopGazelleServer():
    global gazelleSpringPID
    if gazelleSpringPID == None:
        return
    print("Stopping gazelle spring server")
    killAndWait(gazelleSpringPID)
    gazelleSpringPID = None

def doGazelleUpdate(project_id, job_id):
    stopGazelleServer()
    print("Updating gazelle server")

    try:
        downloadGazelle(project_id, job_id)
    finally:
        startGazelleServer()

lock = Mutex()
def doLockedThread(func, args=()):
    def wrapper(func,args):
        try:
            mutex.acquire()
            func(*args)
        finally:
            mutex.release()
    Thread(target=wrapper, args=(func,args)).start()

class DropletManager(BaseHTTPRequestHandler):

    def output_binary(self, code, content, content_type):
        self.send_response(code)
        self.send_header("Content-length", len(content))
        if content_type != None:
            self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(content)

    def output(self, code, content, content_type="text/plain; charset=UTF-8"):
        self.output_binary(code, content.encode('utf-8'), content_type)

    def read_data(self):
        length = int(self.headers['Content-length'])
        data = self.rfile.read(length)
        return json.loads(data)

    def output_status_page(self):
        self.output(200, makeStatusPage(), "text/html; charset=UTF-8")

    def output_404(self):
        self.output(404, "404 page not found")

    def update_gazelle(self):
        if self.headers['X-Gitlab-Token'] != STUD_GITLAB_WEBHOOK_TOKEN:
            print("Ohoh, Got token: ", self.headers['X-Gitlab-Token'])
            return self.output(401, "Invalid token")
        if self.headers['X-Gitlab-Event'] != 'Pipeline Hook':
            return self.output(200, "Nothing to be done")

        data = self.read_data()
        if data["object_attributes"]["status"] != "success":
            return self.output(200, "Not a pipeline success")
        if data["object_attributes"]["ref"] != "master":
            return self.output(200, "Not on master branch")

        project_id = data["project"]["id"]
        job_id = next(build["id"] for build in data["builds"] if build["name"]=="deploy")

        doLockedThread(doGazelleUpdate, (project_id, job_id))
        self.output(200, "Success!")

    def do_GET(self):
        self.protocol_version = "HTTP/1.1"
        if self.path == "/" or self.path == "/index.html":
            self.output_status_page()
        else:
            self.output_404()

    def do_POST(self):
        self.protocol_version="HTTP/1.1"
        if self.path == "/new_gazelle":
            self.update_gazelle()
        else:
            self.output_404()

def main():

    print("Welcome to the droplet manager!")
    print("Doing startup actions: ")

    startGazelleServer()

    with ThreadingTCPServer((HOST, PORT), DropletManager) as httpd:
        print("Serving manager on port", PORT)
        httpd.serve_forever()

if __name__ == "__main__":
    main()
