#!/usr/bin/env python

from socketserver import ThreadingTCPServer
from http.server import BaseHTTPRequestHandler
from os import getenv
import json
from threading import Thread, Lock
import requests
from subprocess import run
import shutil
import os
import pwd

HOST = getenv("MANAGER_HOST", "")
PORT = int(getenv("MANAGER_PORT", "8089"))
STUD_GITLAB_WEBHOOK_TOKEN = getenv("STUD_GITLAB_WEBHOOK_TOKEN", None)
STUD_GITLAB_ACCESS_TOKEN = getenv("STUD_GITLAB_ACCESS_TOKEN", None)

gazelleSpringPID = None

def makeStatusPage():
    return "Status page!"

mutex = Lock()

def startGazelleServer():
    global gazelleSpringPID
    stopGazelleServer()

    print("Starting gazelle spring server")
    user_name = "gazellespring"
    cwd = "/home/gazellespring"
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
        ["java", "-jar", "gazelle-server.jar"], preexec_fn=demote, cwd=cwd, env=env
    )
    gazelleSpringPID = process.pid

def stopGazelleServer():
    global gazelleSpringPID
    if gazelleSpringPID == None:
        return
    print("Stopping gazelle spring server")
    os.kill(gazelleSpringPID)
    os.waitpid(gazelleSpringPID)
    gazelleSpringPID = None

def dowloadGazelle(project_id, job_id):
    print("Downloading gazelle server and site")

    url = f"https://gitlab.stud.idi.ntnu.no/api/v4/projects/{project_id}/jobs/{job_id}/artifacts"
    headers={"PRIVATE-TOKEN": STUD_GITLAB_ACCESS_TOKEN}
    with requests.get(url, stream=True, allow_redirects=True, headers=headers) as r:
        r.raise_for_status()
        with open("artifacts.zip", "wb") as o:
            for chunk in r.iter_content(chunk_size=8192):
                o.write(chunk)

    print("Dowloaded artifacts.zip")

    run(["unzip", "artifacts.zip"])

    os.remove("/home/gazellespring/gazelle-server.jar")
    shutil.move("server/target/gazelle-server-0.1-SNAPSHOT.jar", "/home/gazellespring/gazelle-server.jar")

    shutil.rmtree("/var/www/html/gazelle")
    os.rename("gazelle/public", "/var/www/html/gazelle")

    print("Moved files to correct places")


def doGazelleUpdate(project_id, job_id):
    stopGazelleServer()
    print("Updating gazelle server")

    try:
        downloadGazelle(project_id, job_id)
    finally:
        startGazelleServer()

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

        doLockedThread(doGazelleUpdate, (project_id, build_id))
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
