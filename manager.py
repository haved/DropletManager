#!/usr/bin/env python

from socketserver import ThreadingTCPServer
from http.server import BaseHTTPRequestHandler
from os import getenv
import json
from threading import Thread, Lock
import requests

HOST = getenv("MANAGER_HOST", "")
PORT = int(getenv("MANAGER_PORT", "8089"))
STUD_GITLAB_WEBHOOK_TOKEN = getenv("STUD_GITLAB_WEBHOOK_TOKEN", None)
STUD_GITLAB_ACCESS_TOKEN = getenv("STUD_GITLAB_ACCESS_TOKEN", None)

gazelleSpringPID = None

def makeStatusPage():
    return "Status page!"

mutex = Lock()

def startGazelleServer():
    print("Starting gazelle spring server")

def stopGazelleServer():
    if gazelleSpringPID == None:
        return
    print("Stopping gazelle spring server")

def dowloadGazelle():
    print("Downloading gazelle server and site")

def doGazelleUpdate():
    stopGazelleServer()
    print("Updating gazelle server")

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
        print("Debug:", data)
        print("Also debug:", json.dumps(data))
        if data["object_attributes"]["status"] != "success":
            return self.output(200, "Not a pipeline success")

        doLockedThread(doGazelleUpdate)
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

    with ThreadingTCPServer((HOST, PORT), DropletManager) as httpd:
        print("Serving manager on port", PORT)
        httpd.serve_forever()

if __name__ == "__main__":
    main()
